import os
import re
import logging
from dataclasses import dataclass

# Set up logging
logger = logging.getLogger("ValorantOptimizer")

@dataclass
class HardwareProfile:
    cpu_model: str
    cpu_cores_physical: int
    cpu_cores_logical: int
    cpu_clock_speed_ghz: float
    ram_gb: float
    gpu_model: str
    gpu_vram_gb: float
    storage_type: str  # SSD, HDD, or Unknown

def get_cpu_info() -> tuple[str, int, int, float]:
    """Detects CPU details. Returns (model_name, physical_cores, logical_cores, clock_speed_ghz)"""
    cpu_model = "Unknown CPU"
    physical_cores = 0
    logical_cores = 0
    clock_speed = 0.0

    # 1. Core count detection via psutil
    try:
        import psutil
        physical_cores = psutil.cpu_count(logical=False) or 0
        logical_cores = psutil.cpu_count(logical=True) or 0
        cpu_freq = psutil.cpu_freq()
        if cpu_freq and cpu_freq.max:
            clock_speed = round(cpu_freq.max / 1000.0, 2)
    except Exception as e:
        logger.warning(f"Failed to get CPU cores/freq via psutil: {e}")

    # 2. CPU Model Name detection via py-cpuinfo
    try:
        import cpuinfo
        info = cpuinfo.get_cpu_info()
        if info and "brand_raw" in info:
            cpu_model = info["brand_raw"]
        elif info and "hz_advertised" in info:
            # Fallback format
            cpu_model = info.get("hz_advertised_friendly", "Unknown CPU")
    except Exception as e:
        logger.warning(f"Failed to get CPU model via py-cpuinfo: {e}")

    # 3. Fallback to WMI if py-cpuinfo returns default or fails
    if cpu_model == "Unknown CPU" or not cpu_model:
        try:
            import wmi
            w = wmi.WMI()
            processors = w.Win32_Processor()
            if processors:
                cpu_model = processors[0].Name.strip()
                if clock_speed == 0.0 and processors[0].MaxClockSpeed:
                    clock_speed = round(processors[0].MaxClockSpeed / 1000.0, 2)
        except Exception as e:
            logger.warning(f"Failed to get CPU info via WMI: {e}")

    return cpu_model, physical_cores, logical_cores, clock_speed

def get_ram_info() -> float:
    """Detects total system RAM in GB."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return round(mem.total / (1024 ** 3), 2)
    except Exception as e:
        logger.warning(f"Failed to get RAM info: {e}")
        return 0.0

def get_gpu_info() -> tuple[str, float]:
    """Detects GPU model name and VRAM in GB. Returns (gpu_model, gpu_vram_gb)"""
    gpu_model = "Unknown GPU"
    vram_gb = 0.0

    try:
        import wmi
        w = wmi.WMI()
        gpus = w.Win32_VideoController()
        
        valid_gpus = []
        for gpu in gpus:
            name = gpu.Name
            # Ignore basic software/mirror drivers if possible
            if name and "Microsoft Basic Display Adapter" not in name and "Citrix" not in name:
                valid_gpus.append(gpu)

        primary_gpu = valid_gpus[0] if valid_gpus else (gpus[0] if gpus else None)
        
        if primary_gpu:
            gpu_model = primary_gpu.Name.strip()
            
            # Read AdapterRAM (VRAM)
            raw_ram = primary_gpu.AdapterRAM
            if raw_ram is not None:
                val = int(raw_ram)
                # Handle signed 32-bit int overflow in WMI
                if val < 0:
                    val += 2**32
                vram_gb = round(val / (1024 ** 3), 2)
    except Exception as e:
        logger.warning(f"Failed to get GPU info via WMI: {e}")

    return gpu_model, vram_gb

def get_storage_type() -> str:
    """Detects whether the system drive (usually C:) is SSD or HDD."""
    sys_drive = os.environ.get("SystemDrive", "C:")
    
    try:
        import wmi
        w = wmi.WMI()
        disk_index = None

        # 1. Match logical drive C: to physical disk partition
        for assoc in w.Win32_LogicalDiskToPartition():
            dep_str = str(assoc.Dependent)
            if sys_drive.lower() in dep_str.lower():
                # Find "Disk #X" in string like: Win32_DiskPartition.DeviceID="Disk #0, Partition #1"
                m = re.search(r'Disk #(\d+)', str(assoc.Antecedent))
                if m:
                    disk_index = int(m.group(1))
                    break

        if disk_index is not None:
            # 2. Query MSFT_PhysicalDisk in root\Microsoft\Windows\Storage using disk_index
            storage_wmi = wmi.WMI(namespace=r"Root\Microsoft\Windows\Storage")
            disks = storage_wmi.MSFT_PhysicalDisk(DeviceId=str(disk_index))
            if disks:
                media_type = disks[0].MediaType
                # MediaType values: 3 = HDD, 4 = SSD, 5 = SCM, 0 = Unspecified
                if media_type in (4, 5):
                    return "SSD"
                elif media_type == 3:
                    return "HDD"
    except Exception as e:
        logger.warning(f"WMI system disk linking failed: {e}")

    # Fallback: Query all physical disks. If any is SSD, we guess SSD as OS drive
    try:
        import wmi
        storage_wmi = wmi.WMI(namespace=r"Root\Microsoft\Windows\Storage")
        disks = storage_wmi.MSFT_PhysicalDisk()
        for disk in disks:
            if disk.MediaType in (4, 5):
                return "SSD"
        if disks:
            return "HDD"
    except Exception as e:
        logger.warning(f"WMI general disk query failed: {e}")

    return "Unknown"

def scan_hardware() -> HardwareProfile:
    """Performs a full hardware scan and returns a HardwareProfile."""
    logger.info("Starting hardware scan")
    
    cpu_model, physical_cores, logical_cores, clock_speed = get_cpu_info()
    ram_gb = get_ram_info()
    gpu_model, gpu_vram_gb = get_gpu_info()
    storage_type = get_storage_type()

    profile = HardwareProfile(
        cpu_model=cpu_model,
        cpu_cores_physical=physical_cores,
        cpu_cores_logical=logical_cores,
        cpu_clock_speed_ghz=clock_speed,
        ram_gb=ram_gb,
        gpu_model=gpu_model,
        gpu_vram_gb=gpu_vram_gb,
        storage_type=storage_type
    )

    logger.info(f"Hardware scan completed: CPU={profile.cpu_model} ({profile.cpu_cores_physical} cores), "
                f"RAM={profile.ram_gb} GB, GPU={profile.gpu_model} ({profile.gpu_vram_gb} GB VRAM), "
                f"Storage={profile.storage_type}")
    
    return profile
