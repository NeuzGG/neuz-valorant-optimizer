# Neuz Valorant Optimizer

Neuz Valorant Optimizer is a local configuration manager and performance utility designed to evaluate Windows hardware properties and apply optimal in-game graphics and display settings for VALORANT. 

The optimizer targets maximum FPS, reduced input latency, and consistent frame times, making it ideal for competitive setups ranging from low-end integrated graphics units to high-end enthusiast gaming systems.

---

## Key Features

1. **Hardware Scanning Module**
   - Scans and lists the exact CPU product name, physical core and logical thread counts, and peak clock frequency.
   - Measures total system physical RAM in gigabytes.
   - Queries primary GPU display adapter name and dedicated VRAM, automatically converting signed 32-bit values to prevent reporting errors.
   - Traverses Win32 partition associations to determine whether the Windows OS system drive (typically C:) is stored on an SSD or HDD, falling back to safe defaults if WMI namespaces are unavailable.

2. **Heuristic Performance Engine**
   - Assigns a performance tier (Low, Mid, High, or Enthusiast) using a weighted average where the GPU carries the most weight (2.0x) to accurately reflect bottleneck limitations.
   - Defines distinct graphics settings profiles targeting the ideal balance of visuals and framerate for each performance level.
   - Provides clear, plain-language explanations explaining the performance and visual purpose behind every setting choice.

3. **Multi-Account Profile Manager**
   - Automatically scans `%LOCALAPPDATA%\VALORANT\Saved\Config\` to discover all user account profile directories (GUID folders) stored on the PC.
   - Identifies the active/recent profile by sorting modification timestamps, highlighting the most recently played account with a "Most Recent" tag.
   - Integrates a dropdown selector allowing users with multiple accounts to explicitly choose which profile GUID they wish to customize.
   - Displays the exact date and time each account was last played to help you verify which folder matches your active account.

4. **Dynamic Override Selection**
   - Auto-detects the hardware recommendation tier on launch but allows users to override it by selecting a different tier via a dropdown list.
   - Instantly updates descriptions, recommended values, and visual tables to match the manually selected tier.
   - Highlights manual overrides in red text to clearly differentiate customized profiles from the system's recommendations.

5. **Safe Config Editor & Backup Engine**
   - Reads the local `GameUserSettings.ini` file line-by-line, updating only target keys while preserving comments, line spacing, ordering, and casing to prevent file corruption.
   - Creates an automatic, timestamped backup file (`GameUserSettings.ini.backup-YYYYMMDD-HHMMSS`) in the same directory before performing any write operations.
   - Provides a one-click restore button that copies the latest backup over the active configuration file to instantly undo optimizations.

6. **Integrated Game Launcher**
   - Resolves the official Riot Client installation directory by parsing `RiotClientInstalls.json` in ProgramData or default locations.
   - Executes the game client directly with official startup parameters (`--launch-product=valorant --launch-patchline=live`).
   - Falls back to the Windows URI registration protocol (`riotclient://`) to launch the client if executable pathways are modified.

7. **Modern Dark-Themed GUI**
   - Styled with a charcoal background, light gray text, and a striking crimson red accent.
   - Loads the branding logo image and sets a custom multi-size `.ico` window icon converted from the logo.
   - Runs hardware scans on a separate background thread to keep the user interface responsive.
   - Features a process-monitoring guard loop that automatically disables the "Apply Settings" button and displays a warning banner if `VALORANT-Win64-Shipping.exe` is detected running on the system.
   - Free of all emojis in logs, labels, and text displays.

---

## Safety and Anti-Cheat Compliance (Vanguard Safe)

This utility is fully compliant with Riot Vanguard. It operates under strict limitations:
- **Standard Settings Only**: The tool only modifies display resolution, display modes (Fullscreen, Borderless, Windowed), frame rate limits, V-Sync, and standard graphics scalability categories (Shadows, Textures, Effects, Detail, Anti-Aliasing, Shading, Foliage, Post-Processing) identical to changes made in-game.
- **Out of Scope (Forbidden Tweaks)**: The application does NOT tamper with gameplay-affecting components, including memory injection, aim acceleration curves, hitbox dimensions, weapon properties, or field-of-view (FOV) sliders.
- **Local Text File Modification**: The tool operates solely by editing the standard local text configuration file (`GameUserSettings.ini`) and its own backups. It does not hook system APIs or monitor active gameplay.

---

## Technical Architecture

The program is structured as a modular Python package:
- `app.py`: Coordinates the application window, threading, warning banners, footer layout, and event handlers.
- `hardware_scan.py`: Executes WMI queries and psutil checks to safely retrieve CPU, GPU, RAM, and Storage partition profiles.
- `recommend.py`: Holds weighted scoring rules and profile settings presets for each performance tier.
- `config_manager.py`: Controls file paths enumeration, backup copying, line-preservation edits, backup restoration, and client execution.

---

## Installation and Execution

For detailed developer instructions on installing dependencies, testing the program, or building the final standalone `.exe` using PyInstaller, please refer to the [BUILD.md](file:///c:/Users/Neuz/Documents/Neuz%20Valorant/BUILD.md) guide.

---

## Troubleshooting

### Config File Not Found Automatically
By default, the optimizer checks standard Windows AppData directories. If Valorant is installed on a non-system drive (e.g., D: or E:) or registry structures are customized, the path may not be located.
- **Solution**: Click the "Locate" button in the Target Account Profile box, navigate to your active configuration folder, and select `GameUserSettings.ini` manually.

### Game Running Warning
The application blocks writes if the game process is running to prevent settings from being overwritten when the game closes.
- **Solution**: Save your settings, exit the VALORANT client fully, and wait a few seconds. The warning banner will clear, and the "Apply Settings" button will enable.

### Multiple Account Verification
If your computer has multiple profiles and you are unsure which folder belongs to which active account:
1. Log into your desired Valorant profile via the Riot Client.
2. Launch VALORANT and then close the game.
3. Open the optimizer and click "Scan My PC". The top entry in the "Target Account Profile" list marked as `(Most Recent)` will be your active account, with the timestamp matching the current time.
4. If you wish to customize an older profile, select it from the dropdown list.
