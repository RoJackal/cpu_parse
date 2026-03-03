#!/usr/bin/env python3
"""CPU and System hardware parser for Linux systems."""
import argparse
import json
import os
import platform
import sys
from glob import glob
try:
    import distro
except ImportError:
    distro = None
def _read_first_line(path: str) -> str | None:
    """Reads the first line of a file safely."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readline().strip()
    except OSError:
        return None
def _read_file(path: str) -> str | None:
    """Reads the entire content of a file safely."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return None
def _read_int(path: str) -> int | None:
    """Reads an integer from a file."""
    s = _read_first_line(path)
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None
def _khz_to_mhz(khz: int | None) -> float | None:
    """Converts kHz to MHz rounded to 1 decimal."""
    if khz is None:
        return None
    return round(khz / 1000.0, 1)
def _detect_distribution() -> dict:
    """Detects Linux distribution details."""
    out = {"name": "Unknown", "version": "Unknown", "pretty": "Unknown"}
    try:
        if distro:
            out["name"] = distro.name(pretty=False) or "Unknown"
            out["version"] = distro.version(pretty=False) or "Unknown"
            out["pretty"] = (distro.name(pretty=True) or f"{out['name']} {out['version']}".strip())
            return out
    except (AttributeError, ValueError):
        pass
    pretty = version = name = None
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
    except OSError:
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
def _update_cpu_data(key: str, value: str, data: dict):
    """Helper to update the CPU data dictionary from proc info."""
    if key == "processor":
        data["logical_cores"] += 1
    elif key == "vendor_id" and data["vendor"] == "Unknown":
        data["vendor"] = value
    elif key == "model name" and data["model"] == "Unknown":
        data["model"] = value
    elif key == "cache size" and data["cache_size"] == "Unknown":
        data["cache_size"] = value
    elif key == "cpu MHz" and data["cpu_mhz"] is None:
        try:
            data["cpu_mhz"] = float(value)
        except ValueError:
            pass
    elif key == "physical id":
        try:
            data["current_socket"] = int(value)
        except ValueError:
            data["current_socket"] = None
    elif key == "cpu cores" and data["current_socket"] is not None:
        if data["current_socket"] not in data["sockets"]:
            try:
                data["sockets"][data["current_socket"]] = int(value)
            except ValueError:
                pass
def _parse_proc_cpuinfo() -> dict:
    """Parses /proc/cpuinfo for core and model details."""
    data = {
        "logical_cores": 0, "vendor": "Unknown", "model": "Unknown",
        "cache_size": "Unknown", "cpu_mhz": None, "sockets": {}, "current_socket": None
    }
    try:
        with open("/proc/cpuinfo", "r", buffering=8192, encoding="utf-8", errors="replace") as f:
            for line in f:
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                _update_cpu_data(key.strip(), value.strip(), data)
    except FileNotFoundError:
        print("Error: /proc/cpuinfo not found.", file=sys.stderr)
        sys.exit(1)
    physical_cores = sum(data["sockets"].values()) if data["sockets"] else 0
    return {
        "vendor": data["vendor"], "model": data["model"], "logical_cores": data["logical_cores"],
        "physical_cores": physical_cores, "cache_size": data["cache_size"],
        "frequency_mhz_cur": round(data["cpu_mhz"], 1) if data["cpu_mhz"] is not None else None,
    }
def _cpu_topology_from_sysfs() -> dict:
    """Fallback physical core counting using sysfs topology."""
    pairs = set()
    cpu_dirs = sorted(glob("/sys/devices/system/cpu/cpu[0-9]*/topology"))
    for tdir in cpu_dirs:
        pkg = _read_int(os.path.join(tdir, "physical_package_id"))
        core = _read_int(os.path.join(tdir, "core_id"))
        if pkg is not None and core is not None:
            pairs.add((pkg, core))
    return {"physical_cores": len(pairs) if pairs else 0}
def _cpufreq_from_sysfs() -> dict:
    """Reads CPU frequencies from sysfs."""
    policy0 = "/sys/devices/system/cpu/cpufreq/policy0"
    policy = policy0 if os.path.isdir(policy0) else None
    if not policy:
        policies = sorted(glob("/sys/devices/system/cpu/cpufreq/policy*"))
        policy = policies[0] if policies else None
    if not policy:
        return {"frequency_mhz_cur": None, "frequency_mhz_max": None, "cpufreq_policy": None}
    cur_khz = _read_int(os.path.join(policy, "scaling_cur_freq"))
    max_khz = _read_int(os.path.join(policy, "cpuinfo_max_freq"))
    return {
        "frequency_mhz_cur": _khz_to_mhz(cur_khz),
        "frequency_mhz_max": _khz_to_mhz(max_khz),
        "cpufreq_policy": os.path.basename(policy),
    }
def _mem_gib() -> float | None:
    """Reads total memory in GiB from /proc/meminfo."""
    try:
        with open("/proc/meminfo", "r", buffering=4096, encoding="utf-8", errors="replace") as f:
            line = next(f, "")
        if not line:
            return None
        parts = line.split()
        if len(parts) < 2:
            return None
        return round(int(parts[1]) / 1048576.0, 2)
    except (OSError, ValueError, StopIteration):
        return None
def get_cpu_stat() -> dict:
    """Aggregates all CPU and system statistics."""
    stats = {
        "distribution": _detect_distribution(), "kernel": "Unknown",
        "cpu": {
            "vendor": "Unknown", "model": "Unknown", "logical_cores": 0,
            "physical_cores": 0, "cache_size": "Unknown",
            "frequency_mhz_cur": None, "frequency_mhz_max": None,
        },
        "memory_gib": None, "os_system": platform.system(), "os_version": platform.version(),
    }
    try:
        stats["kernel"] = platform.uname().release
    except (AttributeError, OSError):
        pass
    stats["cpu"].update(_parse_proc_cpuinfo())
    if not stats["cpu"]["physical_cores"]:
        topo = _cpu_topology_from_sysfs()
        if topo["physical_cores"]:
            stats["cpu"]["physical_cores"] = topo["physical_cores"]
    freq = _cpufreq_from_sysfs()
    if freq["frequency_mhz_cur"] is not None:
        stats["cpu"]["frequency_mhz_cur"] = freq["frequency_mhz_cur"]
    if freq["frequency_mhz_max"] is not None:
        stats["cpu"]["frequency_mhz_max"] = freq["frequency_mhz_max"]
    stats["cpu"]["cpufreq_policy"] = freq["cpufreq_policy"]
    stats["memory_gib"] = _mem_gib()
    return stats
def print_short(stats: dict) -> None:
    """Prints a one-liner summary of system stats."""
    cpu = stats["cpu"]
    distro_pretty = stats["distribution"]["pretty"]
    model = cpu["model"] if cpu["model"] != "Unknown" else "Unknown CPU"
    model_short = (model[:28] + "..") if len(model) > 29 else model
    cur, mx = cpu.get("frequency_mhz_cur"), cpu.get("frequency_mhz_max")
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
    out = f"{distro_pretty} | CPU:{model_short:<30} {cpu['logical_cores']}t/"
    out += f"{cpu['physical_cores'] or '?'}c | RAM:{mem_s:<8} | {freq}"
    print(out)
def print_text(stats: dict) -> None:
    """Prints detailed system stats in plain text."""
    cpu = stats["cpu"]
    print(f"Distribution: {stats['distribution']['pretty']}")
    print(f"Kernel: {stats['kernel']}")
    print(f"CPU Vendor: {cpu['vendor']}")
    print(f"CPU Model: {cpu['model']}")
    print(f"Logical Cores (threads): {cpu['logical_cores']}")
    print(f"Physical Cores: {cpu['physical_cores'] if cpu['physical_cores'] else 'Unknown'}")
    print(f"Cache Size: {cpu['cache_size']}")
    cur, mx = cpu.get("frequency_mhz_cur"), cpu.get("frequency_mhz_max")
    print(f"CPU Frequency Current (MHz): {f'{cur:.1f}' if cur is not None else 'Unknown'}")
    print(f"CPU Frequency Max (MHz): {f'{mx:.1f}' if mx is not None else 'Unknown'}")
    if cpu.get("cpufreq_policy"):
        print(f"CPUFreq Policy: {cpu['cpufreq_policy']}")
    mem = stats["memory_gib"]
    print(f"Total Memory (GiB): {f'{mem:.2f}' if mem is not None else 'Unknown'}")
def print_json(stats: dict) -> None:
    """Prints system stats in JSON format."""
    print(json.dumps(stats, indent=2, sort_keys=True))
def main() -> int:
    """Main entry point for the hardware parser."""
    parser = argparse.ArgumentParser(
        description="Fast Linux system hardware parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  %(prog)s\n  %(prog)s --short\n  %(prog)s --json",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--short", action="store_true", help="Compact monitoring output")
    args = parser.parse_args()
    stats = get_cpu_stat()
    if args.json:
        print_json(stats)
    elif args.short:
        print_short(stats)
    else:
        print_text(stats)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
