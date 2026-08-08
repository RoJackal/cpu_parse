#!/usr/bin/env python3
"""Report Linux CPU, memory, kernel, and distribution information."""
import os
import sys
PROC_CPUINFO = "/proc/cpuinfo"
PROC_MEMINFO = "/proc/meminfo"
CPU_SYSFS = "/sys/devices/system/cpu"
CPUFREQ_SYSFS = f"{CPU_SYSFS}/cpufreq"
OS_RELEASE_PATHS = ("/etc/os-release", "/usr/lib/os-release")
UNKNOWN = "Unknown"
USAGE = """usage: cpu.py [-h] [--json | --short | -v]
Fast Linux system hardware parser
options:
  -h, --help     show this help message and exit
  --json         output formatted JSON
  --short        output one compact monitoring line
  -v, --verbose  include additional operating-system details
"""
def _read_first_line(path: str) -> str | None:
    """Return a stripped first line, or None if the file is unavailable."""
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            return stream.readline().strip()
    except OSError:
        return None
def _read_int(path: str) -> int | None:
    """Return an integer from a one-line file, or None when invalid."""
    value = _read_first_line(path)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
def _decode(value: bytes) -> str:
    """Decode a procfs value without failing on damaged firmware strings."""
    return value.decode("utf-8", errors="replace").strip()
def _finish_topology(
    socket_id: bytes | None,
    core_id: bytes | None,
    cores_in_socket: int | None,
    core_pairs: set[tuple[bytes, bytes]],
    socket_core_counts: dict[bytes, int],
) -> None:
    """Commit one logical processor's topology data."""
    if socket_id is not None and core_id is not None:
        core_pairs.add((socket_id, core_id))
    if socket_id is not None and cores_in_socket is not None:
        socket_core_counts[socket_id] = cores_in_socket
def _parse_proc_cpuinfo() -> tuple[dict[str, object], list[int]]:
    """Parse procfs once for CPU identity, topology, and frequency ranges."""
    try:
        with open(PROC_CPUINFO, "rb", buffering=0) as stream:
            data = stream.read()
    except OSError:
        logical = os.cpu_count() or 0
        return {
            "vendor": UNKNOWN,
            "model": UNKNOWN,
            "logical_cores": logical,
            "physical_cores": 0,
            "packages": 0,
            "cache_size": UNKNOWN,
            "frequency_mhz_cur": None,
            "frequency_mhz_cur_min": None,
        }, list(range(logical))
    vendor = UNKNOWN
    model = UNKNOWN
    fallback_model = UNKNOWN
    cache_size = UNKNOWN
    processor_ids: list[int] = []
    core_pairs: set[tuple[bytes, bytes]] = set()
    socket_core_counts: dict[bytes, int] = {}
    socket_id: bytes | None = None
    core_id: bytes | None = None
    cores_in_socket: int | None = None
    frequency_min: float | None = None
    frequency_max: float | None = None
    for raw_line in data.splitlines():
        if not raw_line:
            _finish_topology(
                socket_id,
                core_id,
                cores_in_socket,
                core_pairs,
                socket_core_counts,
            )
            socket_id = None
            core_id = None
            cores_in_socket = None
            continue
        key, separator, raw_value = raw_line.partition(b":")
        if not separator:
            continue
        key = key.strip()
        value = raw_value.strip()
        if key == b"processor":
            try:
                processor_ids.append(int(value))
            except ValueError:
                pass
        elif key in {b"vendor_id", b"CPU implementer", b"vendor"}:
            if vendor == UNKNOWN:
                vendor = _decode(value)
        elif key == b"model name":
            if model == UNKNOWN:
                model = _decode(value)
        elif key in {b"Processor", b"Hardware", b"cpu model"}:
            if fallback_model == UNKNOWN:
                fallback_model = _decode(value)
        elif key == b"cache size":
            if cache_size == UNKNOWN:
                cache_size = _decode(value)
        elif key == b"cpu MHz":
            try:
                frequency = float(value)
            except ValueError:
                continue
            frequency_min = frequency if frequency_min is None else min(frequency_min, frequency)
            frequency_max = frequency if frequency_max is None else max(frequency_max, frequency)
        elif key == b"physical id":
            socket_id = value
        elif key == b"core id":
            core_id = value
        elif key == b"cpu cores":
            try:
                cores_in_socket = int(value)
            except ValueError:
                pass
    _finish_topology(
        socket_id,
        core_id,
        cores_in_socket,
        core_pairs,
        socket_core_counts,
    )
    logical = len(processor_ids) or os.cpu_count() or 0
    physical = len(core_pairs) or sum(socket_core_counts.values())
    packages = len({pair[0] for pair in core_pairs}) or len(socket_core_counts)
    return {
        "vendor": vendor,
        "model": model if model != UNKNOWN else fallback_model,
        "logical_cores": logical,
        "physical_cores": physical,
        "packages": packages,
        "cache_size": cache_size,
        "frequency_mhz_cur": round(frequency_max, 1) if frequency_max is not None else None,
        "frequency_mhz_cur_min": round(frequency_min, 1) if frequency_min is not None else None,
    }, processor_ids or list(range(logical))
def _topology_from_sysfs(processor_ids: list[int]) -> tuple[int, int]:
    """Count unique cores and packages using stable kernel topology masks."""
    cores: set[str] = set()
    packages: set[str] = set()
    for processor_id in processor_ids:
        topology = f"{CPU_SYSFS}/cpu{processor_id}/topology"
        core_mask = _read_first_line(f"{topology}/core_cpus_list")
        package_mask = _read_first_line(f"{topology}/package_cpus_list")
        if core_mask is not None:
            cores.add(core_mask)
        if package_mask is not None:
            packages.add(package_mask)
    return len(cores), len(packages)
def _cpufreq_from_sysfs() -> dict[str, object]:
    """Aggregate every CPUFreq policy, including heterogeneous core policies."""
    try:
        with os.scandir(CPUFREQ_SYSFS) as entries:
            policies = sorted(
                (
                    (int(entry.name[6:]), entry.path)
                    for entry in entries
                    if entry.name.startswith("policy")
                    and entry.name[6:].isdigit()
                    and entry.is_dir()
                ),
                key=lambda item: item[0],
            )
    except OSError:
        policies = []
    current_min: int | None = None
    current_max: int | None = None
    hardware_max: int | None = None
    for _, policy in policies:
        current = _read_int(f"{policy}/cpuinfo_cur_freq")
        if current is None:
            current = _read_int(f"{policy}/scaling_cur_freq")
        maximum = _read_int(f"{policy}/cpuinfo_max_freq")
        if maximum is None:
            maximum = _read_int(f"{policy}/scaling_max_freq")
        if current is not None:
            current_min = current if current_min is None else min(current_min, current)
            current_max = current if current_max is None else max(current_max, current)
        if maximum is not None:
            hardware_max = maximum if hardware_max is None else max(hardware_max, maximum)
    return {
        "frequency_mhz_cur": round(current_max / 1_000, 1) if current_max is not None else None,
        "frequency_mhz_cur_min": round(current_min / 1_000, 1) if current_min is not None else None,
        "frequency_mhz_max": round(hardware_max / 1_000, 1) if hardware_max is not None else None,
        "cpufreq_policy": os.path.basename(policies[0][1]) if policies else None,
        "cpufreq_policy_count": len(policies),
    }
def _available_cpu_count() -> int:
    """Return logical CPUs usable by this process, respecting CPU affinity."""
    process_cpu_count = getattr(os, "process_cpu_count", None)
    if process_cpu_count is not None:
        count = process_cpu_count()
        if count is not None:
            return count
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 0
def _unquote_os_release(value: str) -> str:
    """Decode quoting and escapes defined for common os-release values."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.replace(r"\$", "$").replace(r'\"', '"').replace(r"\\", "\\")
def _detect_distribution() -> dict[str, str]:
    """Read Linux distribution details without third-party dependencies."""
    release: dict[str, str] = {}
    wanted = {"NAME", "VERSION_ID", "PRETTY_NAME"}
    for path in OS_RELEASE_PATHS:
        try:
            with open(path, encoding="utf-8", errors="replace") as stream:
                for raw_line in stream:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key in wanted:
                        release[key] = _unquote_os_release(value)
                        if len(release) == len(wanted):
                            break
            break
        except OSError:
            continue
    name = release.get("NAME", UNKNOWN)
    version = release.get("VERSION_ID", UNKNOWN)
    pretty = release.get("PRETTY_NAME")
    if not pretty:
        pretty = " ".join(part for part in (name, version) if part != UNKNOWN)
    return {"name": name, "version": version, "pretty": pretty or UNKNOWN}
def _memory_gib() -> float | None:
    """Read total physical memory from procfs."""
    line = _read_first_line(PROC_MEMINFO)
    if line is None:
        return None
    key, separator, value = line.partition(":")
    if not separator or key != "MemTotal":
        return None
    try:
        return round(int(value.split()[0]) / 1_048_576, 2)
    except (IndexError, ValueError):
        return None
def get_cpu_stat() -> dict[str, object]:
    """Collect system statistics with one pass over each relevant interface."""
    uname = os.uname()
    cpu, processor_ids = _parse_proc_cpuinfo()
    if not cpu["physical_cores"] or not cpu["packages"]:
        physical, packages = _topology_from_sysfs(processor_ids)
        if not cpu["physical_cores"]:
            cpu["physical_cores"] = physical
        if not cpu["packages"]:
            cpu["packages"] = packages
    frequency = _cpufreq_from_sysfs()
    if frequency["frequency_mhz_cur"] is not None:
        cpu["frequency_mhz_cur"] = frequency["frequency_mhz_cur"]
        cpu["frequency_mhz_cur_min"] = frequency["frequency_mhz_cur_min"]
    cpu["frequency_mhz_max"] = frequency["frequency_mhz_max"]
    cpu["cpufreq_policy"] = frequency["cpufreq_policy"]
    cpu["cpufreq_policy_count"] = frequency["cpufreq_policy_count"]
    cpu["available_logical_cores"] = _available_cpu_count()
    return {
        "distribution": _detect_distribution(),
        "kernel": uname.release,
        "cpu": cpu,
        "memory_gib": _memory_gib(),
        "os_system": uname.sysname,
        "os_version": uname.version,
    }
def _format_frequency(
    current_min: float | None,
    current_max: float | None,
    maximum: float | None,
) -> str:
    """Format the live CPU frequency range and hardware maximum."""
    if current_min is not None and current_max is not None:
        current = (
            f"{current_min:.0f}-{current_max:.0f}"
            if round(current_min) != round(current_max)
            else f"{current_max:.0f}"
        )
        return f"{current}/{maximum:.0f}MHz" if maximum is not None else f"{current}MHz"
    if maximum is not None:
        return f"max{maximum:.0f}MHz"
    return "n/a"
def print_short(stats: dict[str, object]) -> None:
    """Print a compact monitoring summary."""
    cpu = stats["cpu"]
    distribution = stats["distribution"]
    model = cpu["model"] if cpu["model"] != UNKNOWN else "Unknown CPU"
    model_short = f"{model[:28]}.." if len(model) > 29 else model
    frequency = _format_frequency(
        cpu["frequency_mhz_cur_min"],
        cpu["frequency_mhz_cur"],
        cpu["frequency_mhz_max"],
    )
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
    current_min = cpu["frequency_mhz_cur_min"]
    current_max = cpu["frequency_mhz_cur"]
    maximum = cpu["frequency_mhz_max"]
    memory = stats["memory_gib"]
    lines = [
        f"Distribution: {distribution['pretty']}",
        f"Kernel: {stats['kernel']}",
        f"CPU Vendor: {cpu['vendor']}",
        f"CPU Model: {cpu['model']}",
        f"Logical Cores (threads): {cpu['logical_cores']}",
        f"Available Logical Cores: {cpu['available_logical_cores']}",
        f"Physical Cores: {cpu['physical_cores'] or UNKNOWN}",
        f"CPU Packages: {cpu['packages'] or UNKNOWN}",
        f"Cache Size: {cpu['cache_size']}",
        f"CPU Frequency Current Min (MHz): {current_min:.1f}"
        if current_min is not None
        else "CPU Frequency Current Min (MHz): Unknown",
        f"CPU Frequency Current Max (MHz): {current_max:.1f}"
        if current_max is not None
        else "CPU Frequency Current Max (MHz): Unknown",
        f"CPU Frequency Hardware Max (MHz): {maximum:.1f}"
        if maximum is not None
        else "CPU Frequency Hardware Max (MHz): Unknown",
        f"CPUFreq Policies: {cpu['cpufreq_policy_count']}",
        f"Total Memory (GiB): {memory:.2f}"
        if memory is not None
        else "Total Memory (GiB): Unknown",
    ]
    if verbose:
        lines.extend((f"OS System: {stats['os_system']}", f"OS Version: {stats['os_version']}"))
    sys.stdout.write("\n".join(lines) + "\n")
def print_json(stats: dict[str, object]) -> None:
    """Print deterministic, formatted JSON while keeping normal startup lean."""
    import json
    sys.stdout.write(json.dumps(stats, indent=2, sort_keys=True) + "\n")
def _parse_args(argv: list[str]) -> tuple[str | None, str | None]:
    """Parse the small, fixed CLI without argparse's startup overhead."""
    mode = "text"
    selected: set[str] = set()
    for argument in argv:
        if argument in {"-h", "--help"}:
            selected.add("help")
        elif argument == "--json":
            selected.add("json")
        elif argument == "--short":
            selected.add("short")
        elif argument in {"-v", "--verbose"}:
            selected.add("verbose")
        else:
            return None, f"unrecognized argument: {argument}"
    if len(selected) > 1:
        return None, "--json, --short, --verbose, and --help are mutually exclusive"
    if selected:
        mode = selected.pop()
    return mode, None
def main(argv: list[str] | None = None) -> int:
    """Run the hardware parser."""
    if not sys.platform.startswith("linux"):
        sys.stderr.write("Error: this program supports Linux only.\n")
        return 1
    mode, error = _parse_args(sys.argv[1:] if argv is None else argv)
    if error is not None:
        sys.stderr.write(f"cpu.py: error: {error}\nTry 'cpu.py --help' for more information.\n")
        return 2
    if mode == "help":
        sys.stdout.write(USAGE)
        return 0
    stats = get_cpu_stat()
    if mode == "json":
        print_json(stats)
    elif mode == "short":
        print_short(stats)
    else:
        print_text(stats, verbose=mode == "verbose")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
