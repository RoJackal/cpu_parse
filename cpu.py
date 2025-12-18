#!/usr/bin/env python3
import platform
import json
import sys
import argparse
import os

try:
    import distro
except ImportError:
    distro = None

def get_cpu_stat():
    """Parse /proc files with full error handling and multi-socket support"""
    stats = {
        "distribution": {"name": "Unknown", "version": "Unknown"},
        "kernel": "Unknown",
        "cpu": {"vendor": "Unknown", "model": "Unknown", "logical_cores": 0, 
                "physical_cores": 0, "cache_size": "Unknown", "frequency_mhz": 0.0},
        "memory_gb": 0.0,
        "os_system": platform.system(),
        "os_version": platform.version()
    }
    
    # Kernel from uname
    try:
        stats["kernel"] = platform.uname().release
    except:
        pass

    # Distro detection with multiple fallbacks
    try:
        if distro:
            stats["distribution"]["name"] = distro.name(pretty=True) or "Unknown"
            stats["distribution"]["version"] = distro.version() or "Unknown"
        elif os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        stats["distribution"]["name"] = line.split('=')[1].strip().strip('"')
                        break
    except:
        pass

    # CPU parsing - single optimized pass
    logical_cores = 0
    cpu_sockets = {}
    current_socket = -1
    vendor_id = model_name = cache_size = cpu_mhz = "Unknown"
    
    try:
        with open("/proc/cpuinfo", "r", buffering=8192) as f:
            for line in f:
                if ':' not in line:
                    continue
                key, value = (x.strip() for x in line.partition(':')[::2])
                
                if key == "processor":
                    logical_cores += 1
                elif key == "physical id":
                    current_socket = int(value)
                elif key == "cpu cores" and current_socket not in cpu_sockets:
                    cpu_sockets[current_socket] = int(value)
                elif key == "vendor_id" and vendor_id == "Unknown":
                    vendor_id = value
                elif key == "model name" and model_name == "Unknown":
                    model_name = value
                elif key == "cache size" and cache_size == "Unknown":
                    cache_size = value
                elif key == "cpu MHz" and cpu_mhz == "Unknown":
                    cpu_mhz = value or "0"
                    
        stats["cpu"]["logical_cores"] = logical_cores
        stats["cpu"]["physical_cores"] = sum(cpu_sockets.values()) if cpu_sockets else 0
        stats["cpu"]["vendor"] = vendor_id
        stats["cpu"]["model"] = model_name
        stats["cpu"]["cache_size"] = cache_size
        stats["cpu"]["frequency_mhz"] = float(cpu_mhz) if cpu_mhz != "Unknown" else 0.0
        
    except FileNotFoundError:
        print("Error: /proc/cpuinfo not found. Not running on Linux?", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing CPU info: {e}", file=sys.stderr)
        sys.exit(1)

    # Memory - direct first-line parse
    try:
        with open("/proc/meminfo", "r", buffering=4096) as f:
            mem_total_kb = int(next(f).split()[1])
        stats["memory_gb"] = round(mem_total_kb / 1048576.0, 2)
    except:
        pass

    return stats

def print_short(stats):
    """Compact one-liner for monitoring"""
    cpu = stats["cpu"]
    model_short = cpu['model'][:20] if cpu['model'] != "Unknown" else "Unknown CPU"
    print(f"{stats['distribution']['name']} | CPU:{model_short:<20} {cpu['logical_cores']}c | RAM:{stats['memory_gb']:.1f}GB | {cpu['frequency_mhz']:.0f}MHz")

def print_text(stats):
    """Full human-readable output"""
    distro = stats["distribution"]
    cpu = stats["cpu"]
    print(f"Distribution: {distro['name']} {distro['version']}")
    print(f"Kernel: {stats['kernel']}")
    print(f"CPU Vendor: {cpu['vendor']}")
    print(f"CPU Model: {cpu['model']}")
    print(f"Logical Cores: {cpu['logical_cores']}")
    if cpu['physical_cores']:
        print(f"Physical Cores: {cpu['physical_cores']}")
    print(f"Cache Size: {cpu['cache_size']}")
    print(f"CPU Frequency (MHz): {cpu['frequency_mhz']:.1f}")
    print(f"Total Memory (GB): {stats['memory_gb']:.2f}")

def print_json(stats):
    """Print JSON output"""
    print(json.dumps(stats, indent=2, sort_keys=True))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fast Linux system hardware parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  %(prog)s                    # Full output\n  %(prog)s --short           # Monitoring one-liner\n  %(prog)s --json            # Structured JSON\n  %(prog)s --help            # Proper help"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--short", action="store_true", help="Compact monitoring output")
    args = parser.parse_args()

    stats = get_cpu_stat()
    
    if args.short:
        print_short(stats)
    elif args.json:
        print_json(stats)
    else:
        print_text(stats)

