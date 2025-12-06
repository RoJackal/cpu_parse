#!/usr/bin/env python3
import platform
import json
import sys
try:
    import distro
except ImportError:
    distro = None

def get_cpu_stat():
    # Pre-allocate common fields
    cores = set()
    cpu_model = cache_size = cpu_mhz = vendor_id = physical_cores_count = None
    
    # Fast /proc/cpuinfo parsing - read once, minimal string ops
    with open("/proc/cpuinfo", "r", buffering=8192) as f:
        for line in f:
            if ':' not in line:
                continue
            key, value = (x.strip() for x in line.split(':', 1))
            
            if key == "processor":
                cores.add(value)
            elif key == "cpu cores" and physical_cores_count is None:
                physical_cores_count = value
            elif key == "model name" and cpu_model is None:
                cpu_model = value
            elif key == "cache size" and cache_size is None:
                cache_size = value
            elif key == "cpu MHz" and cpu_mhz is None:
                cpu_mhz = value
            elif key == "vendor_id" and vendor_id is None:
                vendor_id = value

    # Fast memory parsing - read first line only
    with open("/proc/meminfo", "r", buffering=4096) as f:
        mem_total_kb = int(next(f).split()[1])
    mem_total_gb = mem_total_kb / 1048576.0  # Direct KB->GB

    # OS info
    uname = platform.uname()
    
    # Distro info with fallback
    distro_name = "Unknown"
    distro_version = "Unknown"
    if distro:
        distro_name = distro.name(pretty=True) or "Unknown"
        distro_version = distro.version() or "Unknown"

    stats = {
        "distribution": {
            "name": distro_name,
            "version": distro_version
        },
        "kernel": uname.release,
        "cpu": {
            "vendor": vendor_id,
            "model": cpu_model,
            "logical_cores": len(cores),
            "physical_cores": physical_cores_count,
            "cache_size": cache_size,
            "frequency_mhz": cpu_mhz
        },
        "memory_gb": round(mem_total_gb, 2),
        "os_system": uname.system,
        "os_version": uname.version
    }
    
    return stats

def print_text(stats):
    """Print human-readable text output"""
    print("Distribution: {} {}".format(stats["distribution"]["name"], stats["distribution"]["version"]))
    print("Kernel: {}".format(stats["kernel"]))
    print("CPU Vendor: {}".format(stats["cpu"]["vendor"]))
    print("CPU Model: {}".format(stats["cpu"]["model"]))
    print("Logical Cores: {}".format(stats["cpu"]["logical_cores"]))
    if stats["cpu"]["physical_cores"]:
        print("Physical Cores: {}".format(stats["cpu"]["physical_cores"]))
    print("Cache Size: {}".format(stats["cpu"]["cache_size"]))
    print("CPU Frequency (MHz): {}".format(stats["cpu"]["frequency_mhz"]))
    print("Total Memory (GB): {:.2f}".format(stats["memory_gb"]))

def print_json(stats):
    """Print JSON output"""
    print(json.dumps(stats, indent=2, sort_keys=True))

if __name__ == "__main__":
    # Parse command line argument
    json_output = "--json" in sys.argv
    
    stats = get_cpu_stat()
    
    if json_output:
        print_json(stats)
    else:
        print_text(stats)

