# cpu_parse 🖥️

A lightweight Python script designed to quickly parse essential system hardware information from the Linux filesystem.

## Description
This utility extracts and summarizes key data points from `/proc/cpuinfo` and `/proc/meminfo`, providing a clear snapshot of server hardware specs. Production-ready for sysadmin tasks, Ansible automation, and monitoring.

## Features
- **CPU Details**: Vendor ID, Model Name, Cache Size, Clock Speed, Logical/Physical cores (**multi-socket aware**)
- **Memory Summary**: Total system memory in **Gigabytes (GB)**
- **OS/Distribution Detection**: `distro` library + `/etc/os-release` fallback
- **Multiple Output Formats**:
  - Default: Human-readable text
  - `--json`: Structured JSON for automation
  - `--short`: Compact one-liner for monitoring
- **Production Ready**: Error handling, proper exit codes, **argparse CLI**
- **Performance Optimized**: Buffered I/O, single-pass parsing
- **Compatibility**: Python 3.6+, Linux `/proc` filesystem

## Installation & Usage

### Requirements
Python 3.6+
pip install distro # Optional: better distro detection

### Quick Start
git clone https://github.com/RoJackal/cpu_parse.git
cd cpu_parse
chmod +x cpu.py
./cpu.py

## Output Examples

### Default Output
$ ./cpu.py
Distribution: Rocky Linux 10.1 (Red Quartz) 10.1
Kernel: 6.17.1-1.el10.elrepo.x86_64
CPU Vendor: AuthenticAMD
CPU Model: AMD EPYC-Rome Processor
Logical Cores: 16
Physical Cores: 16
Cache Size: 512 KB
CPU Frequency (MHz): 2445.4
Total Memory (GB): 30.35

### Monitoring (`--short`)
$ ./cpu.py --short
Rocky Linux 10.1 (Red Quartz) | CPU:AMD EPYC-Rome Proces 16c | RAM:30.4GB | 2445MHz

### JSON (`--json`)
$ ./cpu.py --json
{
"cpu": {
"cache_size": "512 KB",
"frequency_mhz": 2445.406,
"logical_cores": 16,
"model": "AMD EPYC-Rome Processor",
"physical_cores": 16,
"vendor": "AuthenticAMD"
},
"distribution": {
"name": "Rocky Linux 10.1 (Red Quartz)",
"version": "10.1"
},
"kernel": "6.17.1-1.el10.elrepo.x86_64",
"memory_gb": 30.35,
"os_system": "Linux",
"os_version": "#1 SMP PREEMPT_DYNAMIC Mon Oct 6 13:41:29 EDT 2025"
}

### Help
$ ./cpu.py --help
usage: cpu.py [-h] [--json] [--short]

Fast Linux system hardware parser

options:
-h, --help show this help message and exit
--json JSON output
--short Compact monitoring output

Examples:
cpu.py # Full output
cpu.py --short # Monitoring one-liner
cpu.py --json # Structured JSON
cpu.py --help # Proper help

text

## Use Cases
- Server inventory across fleet
- Ansible automation (JSON parsing)
- Monitoring ( `--short` for cron/dashboards)
- CI/CD cloud instance validation
- Multi-socket physical core counting

## License
GPL-3.0 License - see [LICENSE](LICENSE) file.
