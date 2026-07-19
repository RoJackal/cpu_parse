#!/usr/bin/env python3
"""Report Linux CPU, memory, kernel, and distribution information."""
from __future__ import annotations
import argparse
import json
import os
import sys
PROC_CPUINFO = "/proc/cpuinfo"
PROC_MEMINFO = "/proc/meminfo"
CPU_SYSFS = "/sys/devices/system/cpu"
CPUFREQ_SYSFS = f"{CPU_SYSFS}/cpufreq"
OS_RELEASE_PATHS = ("/etc/os-release", "/usr/lib/os-release")
CPU_IDENTITY_KEYS = frozenset(
    {
        "processor",
        "vendor_id",
        "CPU implementer",
        "vendor",
        "model name",
        "Processor",
        "Hardware",
        "cpu model",
        "cache size",
        "cpu MHz",
    }
)
CPU_TOPOLOGY_KEYS = frozenset({"physical id", "core id", "cpu cores"})
def _read_first_line(path: str) -> str | None:
    """Return the stripped first line of a text file, or None on failure."""
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            return stream.readline().strip()
    except OSError:
        return None
def _read_int(path: str) -> int | None:
    """Return the integer stored in a text file, or None when unavailable."""
    value = _read_first_line(path)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
def _khz_to_mhz(value: int | None) -> float | None:
    """Convert an optional frequency from kHz to MHz."""
    return None if value is None else round(value / 1_000, 1)
def _unquote_os_release(value: str) -> str:
    """Decode the quoting and escapes commonly used by os-release."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.replace(r"\$", "$").replace(r'\"', '"').replace(r"\\", "\\")
def _detect_distribution() -> dict[str, str]:
    """Read Linux distribution details without third-party dependencies."""
    release: dict[str, str] = {}
    for path in OS_RELEASE_PATHS:
        try:
            with open(path, encoding="utf-8", errors="replace") as stream:
                for raw_line in stream:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    release[key] = _unquote_os_release(value)
            break
        except OSError:
            continue
    name = release.get("NAME") or "Unknown"
    version = release.get("VERSION_ID") or "Unknown"
    pretty = release.get("PRETTY_NAME")
    if not pretty:
        pretty = " ".join(part for part in (name, version) if part != "Unknown")
    return {"name": name, "version": version, "pretty": pretty or "Unknown"}
def _new_cpu_identity() -> dict[str, object]:
    """Return initial values collected from /proc/cpuinfo."""
    return {
        "logical_cores": 0,
        "vendor": "Unknown",
        "model": "Unknown",
        "fallback_model": "Unknown",
        "cache_size": "Unknown",
        "frequency_mhz_cur": None,
    }
def _update_cpu_identity(key: str, value: str, identity: dict[str, object]) -> None:
    """Update CPU identity and frequency fields from one cpuinfo entry."""
    if key == "processor":
        identity["logical_cores"] += 1
    elif key in {"vendor_id", "CPU implementer", "vendor"}:
        if identity["vendor"] == "Unknown":
            identity["vendor"] = value
    elif key == "model name":
        if identity["model"] == "Unknown":
            identity["model"] = value
    elif key in {"Processor", "Hardware", "cpu model"}:
        if identity["fallback_model"] == "Unknown":
            identity["fallback_model"] = value
    elif key == "cache size":
        if identity["cache_size"] == "Unknown":
            identity["cache_size"] = value
    elif key == "cpu MHz" and identity["frequency_mhz_cur"] is None:
        try:
            identity["frequency_mhz_cur"] = round(float(value), 1)
        except ValueError:
            pass
def _update_cpu_topology(key: str, value: str, topology: dict[str, object]) -> None:
    """Update the current processor's topology fields."""
    if key == "physical id":
        topology["socket_id"] = value
    elif key == "core id":
        topology["core_id"] = value
    elif key == "cpu cores":
        try:
            topology["cores_in_socket"] = int(value)
        except ValueError:
            pass
def _finish_processor(
    topology: dict[str, object],
    core_pairs: set[tuple[str, str]],
    socket_core_counts: dict[str, int],
) -> None:
    """Store one processor's topology and reset its temporary fields."""
    socket_id = topology["socket_id"]
    core_id = topology["core_id"]
    cores_in_socket = topology["cores_in_socket"]
    if socket_id is not None and core_id is not None:
        core_pairs.add((socket_id, core_id))
    if socket_id is not None and cores_in_socket is not None:
        socket_core_counts[socket_id] = cores_in_socket
    topology.update(socket_id=None, core_id=None, cores_in_socket=None)
def _parse_proc_cpuinfo() -> dict[str, object]:
    """Parse /proc/cpuinfo once for identity, topology, and frequency data."""
    identity = _new_cpu_identity()
    core_pairs: set[tuple[str, str]] = set()
    socket_core_counts: dict[str, int] = {}
    topology: dict[str, object] = {
        "socket_id": None,
        "core_id": None,
        "cores_in_socket": None,
    }
    try:
        with open(
            PROC_CPUINFO,
            encoding="utf-8",
            errors="replace",
            buffering=16_384,
        ) as stream:
            for raw_line in stream:
                if raw_line[0] in "\r\n":
                    _finish_processor(topology, core_pairs, socket_core_counts)
                    continue
                key, separator, value = raw_line.partition(":")
                if not separator:
                    continue
                key = key.strip()
                value = value.strip()
                if key in CPU_IDENTITY_KEYS:
                    _update_cpu_identity(key, value, identity)
                elif key in CPU_TOPOLOGY_KEYS:
                    _update_cpu_topology(key, value, topology)
            _finish_processor(topology, core_pairs, socket_core_counts)
    except OSError:
        identity["logical_cores"] = os.cpu_count() or 0
    physical_cores = len(core_pairs) or sum(socket_core_counts.values())
    return {
        "vendor": identity["vendor"],
        "model": (
            identity["model"]
            if identity["model"] != "Unknown"
            else identity["fallback_model"]
        ),
        "logical_cores": identity["logical_cores"] or os.cpu_count() or 0,
        "physical_cores": physical_cores,
        "cache_size": identity["cache_size"],
        "frequency_mhz_cur": identity["frequency_mhz_cur"],
    }
def _physical_cores_from_sysfs() -> int:
    """Count unique physical package and core pairs exposed by sysfs."""
    pairs: set[tuple[int, int]] = set()
    try:
        entries = os.scandir(CPU_SYSFS)
    except OSError:
        return 0
    with entries:
        for entry in entries:
            if not entry.name.startswith("cpu") or not entry.name[3:].isdigit():
                continue
            topology = f"{entry.path}/topology"
            package_id = _read_int(f"{topology}/physical_package_id")
            core_id = _read_int(f"{topology}/core_id")
            if package_id is not None and core_id is not None:
                pairs.add((package_id, core_id))
    return len(pairs)
def _first_cpufreq_policy() -> str | None:
    """Return policy0 or the numerically first available CPUFreq policy."""
    policy0 = f"{CPUFREQ_SYSFS}/policy0"
    if os.path.isdir(policy0):
        return policy0
    try:
        with os.scandir(CPUFREQ_SYSFS) as entries:
            policies = [
                entry
                for entry in entries
                if entry.is_dir() and entry.name.startswith("policy") and entry.name[6:].isdigit()
            ]
    except OSError:
        return None
    return min(policies, key=lambda entry: int(entry.name[6:])).path if policies else None
def _cpufreq_from_sysfs() -> dict[str, float | str | None]:
    """Read current and maximum CPU frequencies from the first policy."""
    policy = _first_cpufreq_policy()
    if policy is None:
        return {"frequency_mhz_cur": None, "frequency_mhz_max": None, "cpufreq_policy": None}
    current = _read_int(f"{policy}/scaling_cur_freq")
    if current is None:
        current = _read_int(f"{policy}/cpuinfo_cur_freq")
    maximum = _read_int(f"{policy}/cpuinfo_max_freq")
    if maximum is None:
        maximum = _read_int(f"{policy}/scaling_max_freq")
    return {
        "frequency_mhz_cur": _khz_to_mhz(current),
        "frequency_mhz_max": _khz_to_mhz(maximum),
        "cpufreq_policy": os.path.basename(policy),
    }
def _memory_gib() -> float | None:
    """Read total system memory from /proc/meminfo."""
    line = _read_first_line(PROC_MEMINFO)
    if line is None:
        return None
    key, separator, value = line.partition(":")
    if not separator or key != "MemTotal":
        return None
    fields = value.split()
    try:
        return round(int(fields[0]) / 1_048_576, 2)
    except (IndexError, ValueError):
        return None
def get_cpu_stat() -> dict[str, object]:
    """Collect system statistics with one pass over each relevant interface."""
    uname = os.uname()
    cpu = _parse_proc_cpuinfo()
    if not cpu["physical_cores"]:
        cpu["physical_cores"] = _physical_cores_from_sysfs()
    frequency = _cpufreq_from_sysfs()
    if frequency["frequency_mhz_cur"] is not None:
        cpu["frequency_mhz_cur"] = frequency["frequency_mhz_cur"]
    cpu["frequency_mhz_max"] = frequency["frequency_mhz_max"]
    cpu["cpufreq_policy"] = frequency["cpufreq_policy"]
    return {
        "distribution": _detect_distribution(),
        "kernel": uname.release,
        "cpu": cpu,
        "memory_gib": _memory_gib(),
        "os_system": uname.sysname,
        "os_version": uname.version,
    }
def _format_frequency(current: float | None, maximum: float | None) -> str:
    """Format current and maximum frequency for compact output."""
    if current is not None and maximum is not None:
        return f"{current:.0f}/{maximum:.0f}MHz"
    if current is not None:
        return f"{current:.0f}MHz"
    if maximum is not None:
        return f"max{maximum:.0f}MHz"
    return "n/a"
def print_short(stats: dict[str, object]) -> None:
    """Print a compact monitoring summary."""
    cpu = stats["cpu"]
    distribution = stats["distribution"]
    model = cpu["model"] if cpu["model"] != "Unknown" else "Unknown CPU"
    model_short = f"{model[:28]}.." if len(model) > 29 else model
    frequency = _format_frequency(cpu["frequency_mhz_cur"], cpu["frequency_mhz_max"])
    memory = stats["memory_gib"]
    memory_text = f"{memory:.1f}GiB" if memory is not None else "n/a"
    sys.stdout.write(
        f"{distribution['pretty']} | CPU:{model_short:<30} "
        f"{cpu['logical_cores']}t/{cpu['physical_cores'] or '?'}c | "
        f"RAM:{memory_text:<8} | {frequency}\n"
    )
def print_text(stats: dict[str, object], *, verbose: bool = False) -> None:
    """Print detailed system statistics as plain text."""
    cpu = stats["cpu"]
    distribution = stats["distribution"]
    current = cpu["frequency_mhz_cur"]
    maximum = cpu["frequency_mhz_max"]
    memory = stats["memory_gib"]
    lines = [
        f"Distribution: {distribution['pretty']}",
        f"Kernel: {stats['kernel']}",
        f"CPU Vendor: {cpu['vendor']}",
        f"CPU Model: {cpu['model']}",
        f"Logical Cores (threads): {cpu['logical_cores']}",
        f"Physical Cores: {cpu['physical_cores'] or 'Unknown'}",
        f"Cache Size: {cpu['cache_size']}",
        f"CPU Frequency Current (MHz): {current:.1f}"
        if current is not None
        else "CPU Frequency Current (MHz): Unknown",
        f"CPU Frequency Max (MHz): {maximum:.1f}"
        if maximum is not None
        else "CPU Frequency Max (MHz): Unknown",
    ]
    if cpu["cpufreq_policy"]:
        lines.append(f"CPUFreq Policy: {cpu['cpufreq_policy']}")
    lines.append(
        f"Total Memory (GiB): {memory:.2f}"
        if memory is not None
        else "Total Memory (GiB): Unknown"
    )
    if verbose:
        lines.extend(
            (f"OS System: {stats['os_system']}", f"OS Version: {stats['os_version']}")
        )
    sys.stdout.write("\n".join(lines) + "\n")
def print_json(stats: dict[str, object]) -> None:
    """Print system statistics as deterministic, formatted JSON."""
    sys.stdout.write(json.dumps(stats, indent=2, sort_keys=True) + "\n")
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fast Linux system hardware parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n  %(prog)s\n  %(prog)s --short\n"
            "  %(prog)s --json\n  %(prog)s --verbose"
        ),
        allow_abbrev=False,
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--json", action="store_true", help="output formatted JSON")
    modes.add_argument("--short", action="store_true", help="output one compact monitoring line")
    modes.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="include additional operating-system details",
    )
    return parser.parse_args(argv)
def main(argv: list[str] | None = None) -> int:
    """Run the hardware parser."""
    if not sys.platform.startswith("linux"):
        sys.stderr.write("Error: this program supports Linux only.\n")
        return 1
    args = _parse_args(argv)
    stats = get_cpu_stat()
    if args.json:
        print_json(stats)
    elif args.short:
        print_short(stats)
    else:
        print_text(stats, verbose=args.verbose)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
