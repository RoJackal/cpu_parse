#!/usr/bin/env python3
import argparse
import json
import os
import platform
import sys
from glob import glob

try:
    import distro  # optional
except ImportError:
    distro = None


def _read_first_line(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readline().strip()
    except OSError:
        return None


def _read_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return None


def _read_int(path: str) -> int | None:
    s = _read_first_line(path)
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _khz_to_mhz(khz: int | None) -> float | None:
    if khz is None:
        return None
    return round(khz / 1000.0, 1)


def _detect_distribution() -> dict:
    out = {"name": "Unknown", "version": "Unknown", "pretty": "Unknown"}
    try:
        if distro:
            # distro.name(pretty=True) already includes version/codename when available. [web:486]
            out["name"] = distro.name(pretty=False) or "Unknown"
            out["version"] = distro.version(pretty=False) or "Unknown"
            out["pretty"] = (
                distro.name(pretty=True) or f"{out['name']} {out['version']}".strip()
            )
            return out
    except Exception:
        pass

    # Fallback: /etc/os-release
    pretty = None
    version = None
    name = None
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PRETTY_NAME="):
                        pretty = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("NAME="):
                        name = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("VERSION_ID="):
                        version = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass

    if pretty:
        out["pretty"] = pretty
    if name:
        out["name"] = name
    if version:
        out["version"] = version

    if out["pretty"] == "Unknown":
        out["pretty"] = f"{out['name']} {out['version']}".strip()

    return out


def _parse_proc_cpuinfo() -> dict:
    logical_cores = 0
    vendor_id = "Unknown"
    model_name = "Unknown"
    cache_size = "Unknown"
    cpu_mhz = None  # current-ish; can be low when idle
    sockets = {}
    current_socket = None

    try:
        with open(
            "/proc/cpuinfo", "r", buffering=8192, encoding="utf-8", errors="replace"
        ) as f:
            for line in f:
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                if key == "processor":
                    logical_cores += 1
                elif key == "vendor_id" and vendor_id == "Unknown":
                    vendor_id = value
                elif key == "model name" and model_name == "Unknown":
                    model_name = value
                elif key == "cache size" and cache_size == "Unknown":
                    cache_size = value
                elif key == "cpu MHz" and cpu_mhz is None:
                    try:
                        cpu_mhz = float(value)
                    except ValueError:
                        cpu_mhz = None
                elif key == "physical id":
                    try:
                        current_socket = int(value)
                    except ValueError:
                        current_socket = None
                elif key == "cpu cores" and current_socket is not None:
                    if current_socket not in sockets:
                        try:
                            sockets[current_socket] = int(value)
                        except ValueError:
                            pass
    except FileNotFoundError:
        print("Error: /proc/cpuinfo not found. Not running on Linux?", file=sys.stderr)
        sys.exit(1)

    physical_cores = sum(sockets.values()) if sockets else 0

    return {
        "vendor": vendor_id,
        "model": model_name,
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
        "cache_size": cache_size,
        "frequency_mhz_cur": round(cpu_mhz, 1) if cpu_mhz is not None else None,
    }


def _cpu_topology_from_sysfs() -> dict:
    """
    Fallback physical core counting using sysfs topology:
    /sys/devices/system/cpu/cpuX/topology/{physical_package_id,core_id}. [web:496]
    """
    pairs = set()
    cpu_dirs = sorted(glob("/sys/devices/system/cpu/cpu[0-9]*/topology"))
    for tdir in cpu_dirs:
        pkg = _read_int(os.path.join(tdir, "physical_package_id"))
        core = _read_int(os.path.join(tdir, "core_id"))
        if pkg is None or core is None:
            continue
        pairs.add((pkg, core))
    return {"physical_cores": len(pairs) if pairs else 0}


def _cpufreq_from_sysfs() -> dict:
    """
    CPUFreq policy attributes:
      - scaling_cur_freq: current frequency in kHz
      - cpuinfo_max_freq: maximum possible operating frequency in kHz [web:492]
    """
    # Prefer policy0 if present; otherwise first policy found.
    policy0 = "/sys/devices/system/cpu/cpufreq/policy0"
    policy = policy0 if os.path.isdir(policy0) else None
    if not policy:
        policies = sorted(glob("/sys/devices/system/cpu/cpufreq/policy*"))
        policy = policies[0] if policies else None
    if not policy:
        return {
            "frequency_mhz_cur": None,
            "frequency_mhz_max": None,
            "cpufreq_policy": None,
        }

    cur_khz = _read_int(os.path.join(policy, "scaling_cur_freq"))
    max_khz = _read_int(os.path.join(policy, "cpuinfo_max_freq"))

    return {
        "frequency_mhz_cur": _khz_to_mhz(cur_khz),
        "frequency_mhz_max": _khz_to_mhz(max_khz),
        "cpufreq_policy": os.path.basename(policy),
    }


def _mem_gib() -> float | None:
    # /proc/meminfo: MemTotal is in kB.
    try:
        with open(
            "/proc/meminfo", "r", buffering=4096, encoding="utf-8", errors="replace"
        ) as f:
            line = next(f, "")
        if not line:
            return None
        parts = line.split()
        if len(parts) < 2:
            return None
        kb = int(parts[1])
        # Convert to GiB (1024^2 kB). Keep metric request in mind, but RAM is usually displayed in GiB.
        return round(kb / 1048576.0, 2)
    except Exception:
        return None


def get_cpu_stat() -> dict:
    stats = {
        "distribution": _detect_distribution(),
        "kernel": "Unknown",
        "cpu": {
            "vendor": "Unknown",
            "model": "Unknown",
            "logical_cores": 0,
            "physical_cores": 0,
            "cache_size": "Unknown",
            "frequency_mhz_cur": None,
            "frequency_mhz_max": None,
        },
        "memory_gib": None,
        "os_system": platform.system(),
        "os_version": platform.version(),
    }

    try:
        stats["kernel"] = platform.uname().release
    except Exception:
        pass

    cpuinfo = _parse_proc_cpuinfo()
    stats["cpu"].update(cpuinfo)

    # If physical core count couldn't be derived from /proc/cpuinfo, use sysfs topology. [web:496]
    if not stats["cpu"]["physical_cores"]:
        topo = _cpu_topology_from_sysfs()
        if topo["physical_cores"]:
            stats["cpu"]["physical_cores"] = topo["physical_cores"]

    # Prefer cpufreq sysfs for current/max where available. [web:492]
    freq = _cpufreq_from_sysfs()
    if freq["frequency_mhz_cur"] is not None:
        stats["cpu"]["frequency_mhz_cur"] = freq["frequency_mhz_cur"]
    if freq["frequency_mhz_max"] is not None:
        stats["cpu"]["frequency_mhz_max"] = freq["frequency_mhz_max"]

    stats["cpu"]["cpufreq_policy"] = freq["cpufreq_policy"]

    stats["memory_gib"] = _mem_gib()

    return stats


def print_short(stats: dict) -> None:
    cpu = stats["cpu"]
    distro_pretty = stats["distribution"]["pretty"]
    model = cpu["model"] if cpu["model"] != "Unknown" else "Unknown CPU"
    model_short = (model[:28] + "…") if len(model) > 29 else model

    cur = cpu.get("frequency_mhz_cur")
    mx = cpu.get("frequency_mhz_max")
    if cur is not None and mx is not None:
        freq = f"{cur:.0f}/{mx:.0f}MHz"
    elif cur is not None:
        freq = f"{cur:.0f}MHz"
    elif mx is not None:
        freq = f"max{mx:.0f}MHz"
    else:
        freq = "n/a"

    mem = stats["memory_gib"]
    mem_s = f"{mem:.1f}GiB" if mem is not None else "n/a"

    print(
        f"{distro_pretty} | CPU:{model_short:<30} {cpu['logical_cores']}t/{cpu['physical_cores'] or '?'}c | RAM:{mem_s:<8} | {freq}"
    )


def print_text(stats: dict) -> None:
    distro_info = stats["distribution"]
    cpu = stats["cpu"]

    print(f"Distribution: {distro_info['pretty']}")
    print(f"Kernel: {stats['kernel']}")
    print(f"CPU Vendor: {cpu['vendor']}")
    print(f"CPU Model: {cpu['model']}")
    print(f"Logical Cores (threads): {cpu['logical_cores']}")
    print(
        f"Physical Cores: {cpu['physical_cores'] if cpu['physical_cores'] else 'Unknown'}"
    )
    print(f"Cache Size: {cpu['cache_size']}")

    cur = cpu.get("frequency_mhz_cur")
    mx = cpu.get("frequency_mhz_max")
    if cur is not None:
        print(f"CPU Frequency Current (MHz): {cur:.1f}")
    else:
        print("CPU Frequency Current (MHz): Unknown")

    if mx is not None:
        print(f"CPU Frequency Max (MHz): {mx:.1f}")
    else:
        print("CPU Frequency Max (MHz): Unknown")

    if cpu.get("cpufreq_policy"):
        print(f"CPUFreq Policy: {cpu['cpufreq_policy']}")

    mem = stats["memory_gib"]
    if mem is not None:
        print(f"Total Memory (GiB): {mem:.2f}")
    else:
        print("Total Memory (GiB): Unknown")


def print_json(stats: dict) -> None:
    print(json.dumps(stats, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fast Linux system hardware parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s               # Full output\n"
            "  %(prog)s --short       # Monitoring one-liner\n"
            "  %(prog)s --json        # Structured JSON\n"
        ),
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--short", action="store_true", help="Compact monitoring output"
    )
    args = parser.parse_args()

    stats = get_cpu_stat()

    if args.short:
        print_short(stats)
    elif args.json:
        print_json(stats)
    else:
        print_text(stats)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
