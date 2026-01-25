# cpu_parse

A lightweight Python script designed to quickly parse essential system hardware information from the Linux filesystem.

## Description

This utility extracts and summarizes key data points from `/proc/cpuinfo` and `/proc/meminfo`, plus optional CPU frequency/topology data from sysfs when available, providing a clear snapshot of server hardware specs.

It's suitable for sysadmin tasks, Ansible automation, and quick monitoring checks.

## Features

- **CPU Details**: Vendor, model, cache size, logical threads, physical cores (multi-socket aware; sysfs topology fallback for VMs/containers)
- **Memory Summary**: Total system memory in **GiB** (binary units)
- **OS/Distribution Detection**: `distro` library + `/etc/os-release` fallback
- **CPU Frequency** (best effort):
  - Current frequency via CPUFreq sysfs when available
  - Max frequency via CPUFreq sysfs when available
  - Falls back to `/proc/cpuinfo` "cpu MHz" when CPUFreq isn't available
- **Multiple Output Formats**:
  - Default: Human-readable text
  - `--json`: Structured JSON for automation
  - `--short`: Compact one-liner for monitoring
- **Production Ready**: Error handling, proper exit codes, argparse-based CLI
- **Performance Optimized**: Buffered I/O, single-pass parsing
- **Compatibility**: Python 3.6+, Linux `/proc` filesystem

## Installation & Usage

### Requirements

- Python 3.6+
- Linux with `/proc` mounted

### Optional Dependency

For better distribution detection:

```bash
pip install distro
```

### Quick Start

```bash
git clone https://github.com/RoJackal/cpu_parse.git
cd cpu_parse
chmod +x cpu.py
./cpu.py
```

## Output Examples

### Default Output

```
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

### Monitoring (`--short`)

```
$ ./cpu.py --short
Rocky Linux 10.1 (Red Quartz) | CPU:AMD EPYC-Rome Processor        16t/16c | RAM:30.4GiB  | 2445MHz
```

### JSON (`--json`)

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
  "os_version": "#1 SMP PREEMPT_DYNAMIC Mon Oct  6 13:41:29 EDT 2025"
}
```

### Help

```
$ ./cpu.py --help
usage: cpu.py [-h] [--json] [--short]

Fast Linux system hardware parser

options:
  -h, --help  show this help message and exit
  --json      JSON output
  --short     Compact monitoring output

Examples:
  cpu.py         # Full output
  cpu.py --short # Monitoring one-liner
  cpu.py --json  # Structured JSON
  cpu.py --help  # Proper help
```

## Use Cases

- Server inventory across fleet
- Ansible automation (JSON parsing)
- Monitoring (`--short` for cron/dashboards)
- CI/CD cloud instance validation
- Multi-socket physical core counting

## License

GPL-3.0 License - see [LICENSE](LICENSE) file.
