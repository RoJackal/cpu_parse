cpu_parse 🖥️

A lightweight Python script designed to quickly parse essential system hardware information from the Linux filesystem.

## Description
This utility extracts and summarizes key data points from the `/proc/cpuinfo` and `/proc/meminfo` files, providing a clear and readable snapshot of your server's core hardware specifications. It's built for rapid system inventory and validation, making it ideal for sysadmin and automation tasks.

## Features
* **CPU Details:** Extracts and displays the **Vendor ID**, **Model Name**, **Cache Size**, **Clock Speed**, and the count of both **Logical** and **Physical** cores.
* **Memory Summary:** Calculates the total system memory and displays it in **Gigabytes (GB)**.
* **Compatibility:** Tested for stability with **Python 3.14**.

## Installation & Usage (Example)

### Requirements
The script requires Python 3.x and runs on Linux systems, as it relies on the standard `/proc` filesystem structure.

### Execution
You can run the script directly after cloning the repository:

```bash
git clone [https://github.com/RoJackal/cpu_parse.git](https://github.com/RoJackal/cpu_parse.git)
cd cpu_parse
# It is recommended to use a virtual environment
python3 -m venv venv
source venv/bin/activate
python3 cpu_parse.py
