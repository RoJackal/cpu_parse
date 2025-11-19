#!/usr/bin/env python3 
def get_cpu_stat():
    cores = set()
    physical_cores = set()
    cpu_model = None
    cache_size = None
    cpu_mhz = None
    vendor_id = None
    physical_id = None

    with open("/proc/cpuinfo") as f:
        for line in f:
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if key == "processor":
                cores.add(value)  # unique logical processors
            elif key == "cpu cores":
                # cpu cores is per physical package, only set on first occurrence
                if physical_id is None:
                    physical_cores_count = value
            elif key == "model name" and cpu_model is None:
                cpu_model = value
            elif key == "cache size" and cache_size is None:
                cache_size = value
            elif key == "cpu MHz" and cpu_mhz is None:
                cpu_mhz = value
            elif key == "vendor_id" and vendor_id is None:
                vendor_id = value
            elif key == "physical id" and physical_id is None:
                physical_id = value

    # Get memory size
    mem_total_kb = 0
    with open("/proc/meminfo") as memf:
        for line in memf:
            if line.startswith("MemTotal:"):
                parts = line.split()
                mem_total_kb = int(parts[1])  # in kilobytes
                break
    mem_total_gb = mem_total_kb / 1024 / 1024  # convert to GB approx

    return {
        "number_of_logical_cores": len(cores),
        "cpu_model": cpu_model,
        "cache_size": cache_size,
        "cpu_mhz": cpu_mhz,
        "vendor_id": vendor_id,
        "physical_cores_count": physical_cores_count if 'physical_cores_count' in locals() else None,
        "memory_gb": mem_total_gb
    }

if __name__ == "__main__":
    stats = get_cpu_stat()
    print(f"CPU Vendor: {stats['vendor_id']}")
    print(f"CPU Model: {stats['cpu_model']}")
    print(f"Logical Cores: {stats['number_of_logical_cores']}")
    if stats['physical_cores_count']:
        print(f"Physical Cores: {stats['physical_cores_count']}")
    print(f"Cache Size: {stats['cache_size']}")
    print(f"CPU Frequency (MHz): {stats['cpu_mhz']}")
    print(f"Total Memory (GB): {stats['memory_gb']:.2f}")

