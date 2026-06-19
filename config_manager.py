import os
import re
import shutil
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List

logger = logging.getLogger("ValorantOptimizer")

def locate_game_user_settings() -> List[str]:
    """
    Locates potential Valorant GameUserSettings.ini file paths.
    Returns a list of absolute paths sorted by modification time (most recent first).
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        logger.warning("LOCALAPPDATA environment variable not found.")
        return []
    
    config_dir = os.path.join(local_appdata, "VALORANT", "Saved", "Config")
    if not os.path.exists(config_dir):
        logger.warning(f"Valorant configuration directory does not exist: {config_dir}")
        return []
    
    paths = []
    try:
        for item in os.listdir(config_dir):
            item_path = os.path.join(config_dir, item)
            if os.path.isdir(item_path):
                # Valorant directories can be GUID folders containing Windows or WindowsClient subfolders
                for sub in ["Windows", "WindowsClient"]:
                    ini_path = os.path.join(item_path, sub, "GameUserSettings.ini")
                    if os.path.exists(ini_path):
                        paths.append(ini_path)
    except Exception as e:
        logger.error(f"Error enumerating folders in config directory: {e}")
        
    # Sort files by modification date (newest first)
    paths.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
    
    logger.info(f"Located {len(paths)} settings file(s). Active choice: {paths[0] if paths else 'None'}")
    return paths

def get_valorant_accounts() -> List[Dict[str, Any]]:
    """
    Scans the Valorant config directory and returns info about all detected account folders.
    Sorted by modification time (most recent first).
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        logger.warning("LOCALAPPDATA environment variable not found.")
        return []
    
    config_dir = os.path.join(local_appdata, "VALORANT", "Saved", "Config")
    if not os.path.exists(config_dir):
        logger.warning(f"Valorant configuration directory does not exist: {config_dir}")
        return []
        
    accounts = []
    try:
        for item in os.listdir(config_dir):
            item_path = os.path.join(config_dir, item)
            if os.path.isdir(item_path):
                # Ignore non-account folders like generic CrashReportClient
                if item.lower() == "crashreportclient":
                    continue
                for sub in ["Windows", "WindowsClient"]:
                    ini_path = os.path.join(item_path, sub, "GameUserSettings.ini")
                    if os.path.exists(ini_path):
                        mtime = os.path.getmtime(ini_path)
                        dt = datetime.fromtimestamp(mtime)
                        accounts.append({
                            "guid": item,
                            "ini_path": ini_path,
                            "modified_time": mtime,
                            "modified_str": dt.strftime("%Y-%m-%d %I:%M %p")
                        })
                        break
    except Exception as e:
        logger.error(f"Error enumerating folders for accounts list: {e}")
        
    # Sort accounts by modification time (newest first)
    accounts.sort(key=lambda x: x["modified_time"], reverse=True)
    logger.info(f"Found {len(accounts)} Valorant account config folder(s).")
    return accounts

def create_backup(ini_path: str) -> str:
    """
    Creates a timestamped backup of the configuration file in the same folder.
    Returns the path to the backup file.
    """
    if not os.path.exists(ini_path):
        raise FileNotFoundError(f"Configuration file not found: {ini_path}")
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = os.path.dirname(ini_path)
    backup_path = os.path.join(directory, f"GameUserSettings.ini.backup-{timestamp}")
    
    try:
        shutil.copy2(ini_path, backup_path)
        logger.info(f"Backup successfully created at: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        raise RuntimeError(f"Could not back up settings file: {e}")

def restore_latest_backup(ini_path: str) -> str:
    """
    Restores the latest backup file in the same directory.
    Returns the path to the restored backup.
    """
    if not os.path.exists(ini_path):
        raise FileNotFoundError(f"Settings file not found: {ini_path}")
    
    directory = os.path.dirname(ini_path)
    backups = []
    prefix = "GameUserSettings.ini.backup-"
    
    try:
        for item in os.listdir(directory):
            if item.startswith(prefix):
                backups.append(os.path.join(directory, item))
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        raise RuntimeError(f"Could not list backup folder contents: {e}")
        
    if not backups:
        logger.warning(f"No backups found in directory: {directory}")
        raise FileNotFoundError("No settings backups found to restore.")
        
    # Sort by timestamp (since the timestamp is in YYYYMMDD-HHMMSS format, string sorting is chronological)
    backups.sort(reverse=True)
    latest_backup = backups[0]
    
    try:
        shutil.copy2(latest_backup, ini_path)
        logger.info(f"Restored settings from backup: {latest_backup}")
        return latest_backup
    except Exception as e:
        logger.error(f"Failed to restore from backup {latest_backup}: {e}")
        raise RuntimeError(f"Could not restore settings backup: {e}")

def apply_profile(ini_path: str, profile_settings: Dict[str, Dict[str, str]]) -> List[Tuple[str, str, str, str]]:
    """
    Applies recommended settings to the ini file without parsing round-trip.
    Preserves other lines, comments, casing, and ordering.
    Returns list of changes made: [(section, key, old_value, new_value)]
    """
    if not os.path.exists(ini_path):
        raise FileNotFoundError(f"Configuration file not found: {ini_path}")

    # Create case-insensitive mapping lookup for target settings
    targets = {}  # { section_lower: { key_lower: (orig_key, new_value) } }
    for section, keys in profile_settings.items():
        sec_lower = section.lower()
        targets[sec_lower] = {}
        for key, value in keys.items():
            targets[sec_lower][key.lower()] = (key, value)

    # Read original file contents
    try:
        with open(ini_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Fallback to local encoding if utf-8 fails
        with open(ini_path, 'r') as f:
            lines = f.readlines()

    new_lines = []
    current_section = ""
    applied_keys = {sec_lower: set() for sec_lower in targets}
    changes = []

    def flush_unapplied_keys(section_lower: str, line_ending: str) -> None:
        """Appends any keys for the section that were not found in the original file."""
        if section_lower in targets:
            for key_lower, (orig_key, val) in targets[section_lower].items():
                if key_lower not in applied_keys[section_lower]:
                    new_lines.append(f"{orig_key}={val}{line_ending}")
                    applied_keys[section_lower].add(key_lower)
                    changes.append((section_lower, orig_key, "None (Created)", val))

    # Process line by line
    for line in lines:
        line_ending = "\r\n" if line.endswith("\r\n") else "\n"
        
        # Check for section header: e.g. [ScalabilityGroups]
        section_match = re.match(r'^\s*\[([^\]]+)\]\s*$', line)
        if section_match:
            # Flush keys of the previous section before changing context
            flush_unapplied_keys(current_section.lower(), line_ending)
            current_section = section_match.group(1).strip()
            new_lines.append(line)
            continue
            
        # Check for key=value pair
        kv_match = re.match(r'^([^=]+)=(.*)$', line)
        if kv_match:
            key_part = kv_match.group(1)
            val_part = kv_match.group(2).rstrip('\r\n')
            
            key_stripped = key_part.strip()
            sec_lower = current_section.lower()
            key_lower = key_stripped.lower()
            
            if sec_lower in targets and key_lower in targets[sec_lower]:
                orig_key, new_value = targets[sec_lower][key_lower]
                if val_part != new_value:
                    changes.append((current_section, orig_key, val_part, new_value))
                    # Reconstruct line using original key prefix spacing
                    space_suffix = key_part[len(key_part.rstrip()):]
                    new_lines.append(f"{key_part.rstrip()}={new_value}{line_ending}")
                else:
                    new_lines.append(line)
                applied_keys[sec_lower].add(key_lower)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Flush final section keys
    flush_unapplied_keys(current_section.lower(), "\n")

    # If any section in targets was never visited, append it at the end of the file
    for sec_lower, keys in targets.items():
        if not any(key_lower in applied_keys[sec_lower] for key_lower in keys):
            # Find the original section casing
            orig_section = next(sec for sec in profile_settings if sec.lower() == sec_lower)
            new_lines.append(f"\n[{orig_section}]\n")
            for key_lower, (orig_key, val) in keys.items():
                new_lines.append(f"{orig_key}={val}\n")
                changes.append((orig_section, orig_key, "None (Created Section)", val))

    # Write modified lines back to the file
    try:
        with open(ini_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.error(f"Failed to write settings: {e}")
        raise RuntimeError(f"Could not write configuration modifications: {e}")

    # Log changes
    for change in changes:
        logger.info(f"Config modification - Section [{change[0]}], Key '{change[1]}': '{change[2]}' -> '{change[3]}'")
        
    return changes

def launch_valorant() -> str:
    """
    Resolves the Riot Client installation path and launches VALORANT.
    Returns launcher method used.
    """
    programdata = os.environ.get("ProgramData", "C:\\ProgramData")
    json_path = os.path.join(programdata, "Riot Games", "RiotClientInstalls.json")
    
    rc_path = None
    if os.path.exists(json_path):
        try:
            import json
            with open(json_path, 'r') as f:
                data = json.load(f)
                rc_path = data.get("rc_live") or data.get("rc_default")
        except Exception as e:
            logger.warning(f"Error reading RiotClientInstalls.json: {e}")

    # Fallback to default install location
    if not rc_path or not os.path.exists(rc_path):
        default_rc = "C:\\Riot Games\\Riot Client\\RiotClientServices.exe"
        if os.path.exists(default_rc):
            rc_path = default_rc

    import subprocess
    if rc_path and os.path.exists(rc_path):
        try:
            subprocess.Popen([rc_path, "--launch-product=valorant", "--launch-patchline=live"])
            logger.info(f"VALORANT launched via Riot Client executable: {rc_path}")
            return f"Riot Client executable ({os.path.basename(rc_path)})"
        except Exception as e:
            logger.error(f"Failed to launch via Riot Client path: {e}")

    # Ultimate fallback: start via URI scheme registered in Windows
    try:
        os.startfile("riotclient://launch-game/valorant/live")
        logger.info("VALORANT launched via Riot Client URI scheme")
        return "Riot Client URI Protocol"
    except Exception as e:
        logger.error(f"Failed to launch via URI: {e}")
        raise RuntimeError(f"Unable to launch VALORANT. No installation path found: {e}")
