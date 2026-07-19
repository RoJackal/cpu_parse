# cpu_parse

`cpu_parse` is a lightweight, dependency-free Python utility for reporting essential Linux CPU, memory, kernel, and distribution information.

It reads directly from `/proc`, sysfs, and `os-release`, making it suitable for server inventory, Ansible automation, monitoring checks, CI/CD validation, virtual machines, and containers.

## Features

- **CPU details:** Vendor, model, cache size, logical threads, and physical cores
- **Topology-aware core counting:** Counts unique socket/core pairs with a sysfs fallback
- **Architecture fallbacks:** Handles common x86 and ARM CPU information fields
- **Memory summary:** Reports total memory in GiB
- **Distribution detection:** Reads `/etc/os-release` or `/usr/lib/os-release`
- **Kernel details:** Uses a single `os.uname()` call
- **CPU frequency detection:**
  - Current frequency from CPUFreq sysfs when available
  - Maximum frequency from CPUFreq sysfs when available
  - Current-frequency fallback from `/proc/cpuinfo`
- **Output modes:**
  - Default human-readable output
  - `--short` compact monitoring output
  - `--json` deterministic JSON output
  - `--verbose` detailed output with additional operating-system fields
- **Automation-friendly:** Stable exit codes, mutually exclusive output modes, and no abbreviated options
- **Dependency-free:** Uses only the Python standard library

## Requirements

- Linux with `/proc` mounted
- Python 3.10 or newer
- Python 3.14 or newer recommended

No third-party packages are required.

## Installation

```bash
git clone https://github.com/RoJackal/cpu_parse.git
cd cpu_parse
chmod +x cpu.py
```

Run it directly:

```bash
./cpu.py
```

Alternatively:

```bash
python3 cpu.py
```

## Usage

```text
usage: cpu.py [-h] [--json | --short | -v]

Fast Linux system hardware parser

options:
  -h, --help     show this help message and exit
  --json         output formatted JSON
  --short        output one compact monitoring line
  -v, --verbose  include additional operating-system details

Examples:
  cpu.py
  cpu.py --short
  cpu.py --json
  cpu.py --verbose
```

Output modes are mutually exclusive. For example, using `--json` and `--short` together returns an argument error instead of silently choosing one format.

## Output Examples

### Default output

```text
$ ./cpu.py
Distribution: Rocky Linux 10.1 (Red Quartz)
Kernel: 6.17.1-1.el10.elrepo.x86_64
CPU Vendor: AuthenticAMD
CPU Model: AMD EPYC-Rome Processor
Logical Cores (threads): 16
Physical Cores: 16
Cache Size: 512 KB
CPU Frequency Current (MHz): 2445.4
CPU Frequency Max (MHz): Unknown
Total Memory (GiB): 30.35
```

### Compact monitoring output

```text
$ ./cpu.py --short
Rocky Linux 10.1 (Red Quartz) | CPU:AMD EPYC-Rome Processor        16t/16c | RAM:30.4GiB  | 2445MHz
```

### Verbose output

`--verbose` includes the normal detailed output plus `OS System` and `OS Version`:

```text
$ ./cpu.py --verbose
Distribution: Rocky Linux 10.1 (Red Quartz)
Kernel: 6.17.1-1.el10.elrepo.x86_64
CPU Vendor: AuthenticAMD
CPU Model: AMD EPYC-Rome Processor
Logical Cores (threads): 16
Physical Cores: 16
Cache Size: 512 KB
CPU Frequency Current (MHz): 2445.4
CPU Frequency Max (MHz): Unknown
Total Memory (GiB): 30.35
OS System: Linux
OS Version: #1 SMP PREEMPT_DYNAMIC Mon Oct 6 13:41:29 EDT 2025
```

### JSON output

```json
{
  "cpu": {
    "cache_size": "512 KB",
    "cpufreq_policy": null,
    "frequency_mhz_cur": 2445.4,
    "frequency_mhz_max": null,
    "logical_cores": 16,
    "model": "AMD EPYC-Rome Processor",
    "physical_cores": 16,
    "vendor": "AuthenticAMD"
  },
  "distribution": {
    "name": "Rocky Linux",
    "pretty": "Rocky Linux 10.1 (Red Quartz)",
    "version": "10.1"
  },
  "kernel": "6.17.1-1.el10.elrepo.x86_64",
  "memory_gib": 30.35,
  "os_system": "Linux",
  "os_version": "#1 SMP PREEMPT_DYNAMIC Mon Oct 6 13:41:29 EDT 2025"
}
```

JSON field values may be `null` when the kernel or virtualized environment does not expose the corresponding information.

## Data Sources

| Information | Primary source | Fallback |
| --- | --- | --- |
| CPU identity and logical threads | `/proc/cpuinfo` | `os.cpu_count()` for logical threads |
| Physical cores | Unique `physical id` and `core id` pairs | `/sys/devices/system/cpu/cpu*/topology` |
| Current CPU frequency | CPUFreq `scaling_cur_freq` | CPUFreq `cpuinfo_cur_freq`, then `/proc/cpuinfo` |
| Maximum CPU frequency | CPUFreq `cpuinfo_max_freq` | CPUFreq `scaling_max_freq` |
| Total memory | `/proc/meminfo` | Reported as unknown |
| Distribution | `/etc/os-release` | `/usr/lib/os-release` |
| Kernel and OS | `os.uname()` | None |

CPU frequency reporting is best effort. Some virtual machines, containers, hypervisors, and kernels do not expose CPUFreq information.

## Use Cases

- Server inventory across a fleet
- Ansible automation using JSON output
- Cron jobs and monitoring dashboards using `--short`
- CI/CD validation of cloud instances
- Virtual-machine and container inspection
- Multi-socket physical-core counting

## Performance

The parser minimizes startup and collection overhead by:

- Reading `/proc/cpuinfo` once
- Importing `json` only when JSON output is requested
- Avoiding third-party distribution-detection packages
- Using `os.scandir()` for sysfs fallback discovery
- Calling `os.uname()` once
- Building human-readable output before writing it to standard output

In a 100-run process-start benchmark on the development host, the optimized version was approximately 9% faster than the previous implementation. Actual results depend on the Python build, CPU, filesystem, kernel, and virtualization environment.

## Changelog

### Unreleased — 2026-07-19

#### Added

- Added functional `--verbose` output with `OS System` and `OS Version`
- Added ARM-oriented fallbacks for CPU vendor and model fields
- Added `/usr/lib/os-release` as a distribution-detection fallback
- Added CPUFreq fallbacks through `cpuinfo_cur_freq` and `scaling_max_freq`
- Added an explicit Linux-only runtime check
- Added modern type annotations and reusable filesystem path constants

#### Changed

- Replaced the optional `distro` package with direct `os-release` parsing
- Replaced repeated `platform` calls with one `os.uname()` call
- Reworked `/proc/cpuinfo` handling into a single-pass parser
- Replaced glob-based sysfs discovery with `os.scandir()`
- Changed CPUFreq policy selection to prefer `policy0`, then the numerically first available policy
- Changed text and compact output to buffered standard-output writes
- Changed JSON loading to a lazy import used only for `--json`
- Made `--json`, `--short`, and `--verbose` mutually exclusive
- Disabled abbreviated command-line options with `allow_abbrev=False`
- Updated the supported Python baseline from the incorrect `3.6+` claim to Python 3.10+
- Removed all third-party runtime dependencies

#### Fixed

- Fixed `--verbose` previously being accepted but having no effect
- Fixed conflicting output flags being silently resolved by argument order
- Fixed potential physical-core miscounts by counting unique socket/core pairs
- Fixed topology fallback behavior for systems without usable `/proc/cpuinfo` topology fields
- Fixed empty or malformed `/proc/meminfo` handling
- Fixed distribution parsing when `/etc/os-release` is unavailable
- Improved CPU model detection on non-x86 systems

#### Validation

- Verified successful Python bytecode compilation
- Verified default, short, verbose, and JSON output modes
- Verified that JSON output parses successfully
- Verified invalid conflicting output modes return exit status `2`
- Verified logical and physical core counts match `lscpu` on the development host
- Measured approximately 9% lower process-start runtime over 100 executions on the development host

## Compatibility Notes

- Existing default, `--short`, and `--json` output formats remain available.
- The script no longer supports the README's previous Python 3.6 claim.
- The `distro` package is no longer used or required.
- Combining output-mode options now produces an error instead of silently selecting one.
- Python 3.14-specific execution was not available in the validation environment; the script was compiled and tested with Python 3.12 using standard-library interfaces supported by Python 3.14.

## License

GPL-3.0 License. See [LICENSE](LICENSE).
