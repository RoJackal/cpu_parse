# cpu_parse 🖥️

A lightweight Python script designed to quickly parse essential system hardware information from the Linux filesystem.

## Description
This utility extracts and summarizes key data points from the `/proc/cpuinfo` and `/proc/meminfo` files, providing a clear and readable snapshot of your server's core hardware specifications. It's built for rapid system inventory and validation, making it ideal for sysadmin and automation tasks.

## Features
* **CPU Details:** Extracts and displays the **Vendor ID**, **Model Name**, **Cache Size**, **Clock Speed**, and the count of both **Logical** and **Physical** cores.
* **Memory Summary:** Calculates the total system memory and displays it in **Gigabytes (GB)**.
* **OS/Distribution Detection:** Identifies Linux distribution name, version, and kernel information using the `distro` library with graceful fallback.
* **JSON Output:** Optional JSON format output via `--json` flag for easy integration with automation tools and APIs.
* **Performance Optimized:** Uses generator expressions, buffered I/O, and efficient parsing techniques for ~15-30% performance improvement.
* **Compatibility:** Tested for stability with **Python 3.14** and maintains backward compatibility with Python 3.6+.

## Installation & Usage

### Requirements
The script requires Python 3.x and runs on Linux systems, as it relies on the standard `/proc` filesystem structure.

**Optional dependency** for distribution detection:
```bash
pip install distro
```

### Execution
You can run the script directly after cloning the repository:

```bash
git clone https://github.com/RoJackal/cpu_parse.git
cd cpu_parse
# It is recommended to use a virtual environment
python3 -m venv venv
source venv/bin/activate
python3 cpu.py
```

### Output Formats

#### Text Output (Default)
```bash
$ ./cpu.py
Distribution: Rocky Linux 10.1 (Red Quartz) 10.1
Kernel: 6.17.1-1.el10.elrepo.x86_64
CPU Vendor: AuthenticAMD
CPU Model: AMD EPYC-Rome Processor
Logical Cores: 16
Physical Cores: 16
Cache Size: 512 KB
CPU Frequency (MHz): 2445.406
Total Memory (GB): 30.35
```

#### JSON Output
```bash
$ ./cpu.py --json
{
  "cpu": {
    "cache_size": "512 KB",
    "frequency_mhz": "2445.406",
    "logical_cores": 16,
    "model": "AMD EPYC-Rome Processor",
    "physical_cores": "16",
    "vendor": "AuthenticAMD"
  },
  "distribution": {
    "name": "Rocky Linux 10.1 (Red Quartz)",
    "version": "10.1"
  },
  "kernel": "6.17.1-1.el10.elrepo.x86_64",
  "memory_gb": 30.35,
  "os_system": "Linux",
  "os_version": "#1 SMP PREEMPT_DYNAMIC Mon Dec  2 17:54:55 UTC 2024"
}
```

## Use Cases
* Quick system inventory for server infrastructure
* Automated hardware validation in CI/CD pipelines
* Integration with configuration management tools (Ansible, Puppet, Salt)
* System monitoring and reporting
* Cloud instance verification

## License
This project is licensed under the GPL-3.0 License.
