import os
import sys
import threading
import time
import logging
import webbrowser
from datetime import datetime

# Configure logging
logging.basicConfig(
    filename="optimizer.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ValorantOptimizer")

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    import tkinter as tk
    from tkinter import ttk
    HAS_CTK = False

from tkinter import filedialog, messagebox
import hardware_scan
import recommend
import config_manager

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Design Color Palette
COLOR_BG = "#0f1115"
COLOR_PANEL = "#161920"
COLOR_CARD = "#1a1d24"
COLOR_PRIMARY = "#ff4655"
COLOR_PRIMARY_HOVER = "#ff5c6a"
COLOR_SECONDARY = "#2e3440"
COLOR_SECONDARY_HOVER = "#3b4252"
COLOR_SUCCESS = "#238636"
COLOR_WARNING = "#da3633"
COLOR_TEXT_MAIN = "#f8f9fa"
COLOR_TEXT_MUTED = "#8b949e"
COLOR_BORDER = "#2b303b"

class ValorantOptimizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Neuz VALORANT Hardware-Aware Settings Optimizer")
        self.root.geometry("900x740")
        self.root.configure(fg_color=COLOR_BG) if HAS_CTK else self.root.configure(bg=COLOR_BG)
        
        # Load window icon and logo images
        self.load_assets()
        
        # State variables
        self.hardware_profile = None
        self.selected_ini_path = None
        self.recommended_tier = None
        self.recommended_settings = None
        self.tier_description = ""
        self.is_scan_running = False
        self.running_check_thread_active = True
        
        # Build layout
        self.create_widgets()
        
        # Check active settings automatically
        self.find_settings_file()
        
        # Start background check to see if Valorant is running
        self.proc_thread = threading.Thread(target=self.process_guard_loop, daemon=True)
        self.proc_thread.start()

    def load_assets(self):
        # 1. Set window icon
        icon_path = resource_path("icon.ico")
        try:
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Failed to set window icon: {e}")

        # 2. Load logo image for CustomTkinter
        self.logo_image = None
        logo_path = resource_path("logo.jpg")
        if HAS_CTK:
            try:
                from PIL import Image
                if os.path.exists(logo_path):
                    raw_img = Image.open(logo_path)
                    self.logo_image = ctk.CTkImage(light_image=raw_img, dark_image=raw_img, size=(60, 60))
            except Exception as e:
                logger.warning(f"Failed to load CTk logo image: {e}")

        # 3. Load logo image for Tkinter fallback
        self.tk_logo_image = None
        try:
            from PIL import Image, ImageTk
            if os.path.exists(logo_path):
                raw_img = Image.open(logo_path).resize((60, 60), Image.Resampling.LANCZOS)
                self.tk_logo_image = ImageTk.PhotoImage(raw_img)
        except Exception as e:
            logger.warning(f"Failed to load Tkinter logo image: {e}")

    def create_widgets(self):
        if HAS_CTK:
            self.build_ctk_ui()
        else:
            self.build_tk_ui()

    def find_settings_file(self):
        self.accounts_list = config_manager.get_valorant_accounts()
        if self.accounts_list:
            # Set default selection to the first account (most recently modified)
            self.selected_ini_path = self.accounts_list[0]["ini_path"]
            self.update_path_label(f"Active Config Path: {self.selected_ini_path}")
            
            # Format display names for dropdown list
            dropdown_values = []
            for idx, acc in enumerate(self.accounts_list):
                recent_tag = " (Most Recent)" if idx == 0 else ""
                short_guid = acc["guid"][:12] + "..." if len(acc["guid"]) > 15 else acc["guid"]
                display_name = f"{short_guid} ({acc['modified_str']}){recent_tag}"
                dropdown_values.append(display_name)
                
            if HAS_CTK:
                self.account_selector.configure(values=dropdown_values, state="normal")
                self.account_selector.set(dropdown_values[0])
            else:
                # Fallback tkinter OptionMenu update
                self.tk_account_menu['menu'].delete(0, 'end')
                for val in dropdown_values:
                    self.tk_account_menu['menu'].add_command(label=val, command=lambda v=val: self.tk_account_var.set(v))
                self.tk_account_var.set(dropdown_values[0])
                self.account_selector.configure(state="normal")
        else:
            self.selected_ini_path = None
            self.update_path_label("Config file not automatically found. Please locate it manually.")
            if HAS_CTK:
                self.account_selector.configure(values=["No Accounts Found"], state="disabled")
                self.account_selector.set("No Accounts Found")
            else:
                self.tk_account_var.set("No Accounts Found")
                self.account_selector.configure(state="disabled")

    def on_account_selected(self, selected_display_name):
        if not hasattr(self, "accounts_list") or not self.accounts_list:
            return
            
        matched_acc = None
        for acc in self.accounts_list:
            # Match using prefix GUID and modified timestamp string
            short_guid = acc["guid"][:12]
            if short_guid in selected_display_name and acc["modified_str"] in selected_display_name:
                matched_acc = acc
                break
                
        if matched_acc:
            self.selected_ini_path = matched_acc["ini_path"]
            self.update_path_label(f"Active Config Path: {self.selected_ini_path}")
            logger.info(f"Target account changed to: {matched_acc['guid']} (Path: {self.selected_ini_path})")
            
            self.lbl_status.configure(
                text=f"Selected Target Profile: {matched_acc['guid'][:8]}... (Active)", 
                text_color=COLOR_TEXT_MUTED
            )

    def select_file_manually(self):
        initial_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "VALORANT", "Saved", "Config")
        if not os.path.exists(initial_dir):
            initial_dir = os.path.expanduser("~")
            
        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Select GameUserSettings.ini",
            filetypes=[("Configuration Files", "*.ini"), ("All Files", "*.*")]
        )
        if file_path:
            if os.path.basename(file_path) == "GameUserSettings.ini":
                self.selected_ini_path = file_path
                self.update_path_label(f"Manual Config Path: {self.selected_ini_path}")
                logger.info(f"User manually selected config path: {self.selected_ini_path}")
            else:
                messagebox.showerror(
                    "Invalid File", 
                    "Please select the active GameUserSettings.ini file for Valorant."
                )

    def update_path_label(self, text):
        if hasattr(self, "path_label"):
            self.path_label.configure(text=text)

    def run_hardware_scan(self):
        if self.is_scan_running:
            return
        
        self.is_scan_running = True
        self.scan_button.configure(state="disabled", text="Scanning system...")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, columnspan=2, pady=10, sticky="ew")
        
        def scan_worker():
            try:
                # Mock step-by-step progress update
                for i in range(1, 10):
                    time.sleep(0.1)
                    self.progress_bar.set(i / 10.0)
                    
                profile = hardware_scan.scan_hardware()
                self.hardware_profile = profile
                
                # Fetch settings recommendations
                tier, settings, desc = recommend.get_recommendation(profile)
                self.recommended_tier = tier
                self.recommended_settings = settings
                self.tier_description = desc
                
                # Render results in UI
                self.root.after(0, self.on_scan_complete)
            except Exception as e:
                logger.error(f"Hardware scan failed: {e}")
                self.root.after(0, lambda: self.on_scan_failed(str(e)))

        threading.Thread(target=scan_worker, daemon=True).start()

    def on_scan_complete(self):
        self.is_scan_running = False
        self.progress_bar.grid_remove()
        self.scan_button.configure(state="normal", text="Re-Scan System")
        self.render_scan_results()

    def on_scan_failed(self, error_msg):
        self.is_scan_running = False
        self.progress_bar.grid_remove()
        self.scan_button.configure(state="normal", text="Scan My PC")
        messagebox.showerror("Scan Error", f"Hardware detection failed: {error_msg}")

    def on_tier_selected(self, selected_tier):
        if not self.hardware_profile:
            return
        if selected_tier not in ["LOW", "MID", "HIGH", "ENTHUSIAST"]:
            return

        # Update settings to match selected tier
        self.recommended_tier = selected_tier
        self.recommended_settings = recommend.TIERS[selected_tier]["settings"]
        self.tier_description = recommend.TIERS[selected_tier]["description"]
        
        # Re-render description and settings list
        self.lbl_tier_desc.configure(text=self.tier_description)
        self.populate_recommendation_table()
        
        # Update status message to show recommendation match status
        rec_tier = recommend.classify_hardware(self.hardware_profile)
        if selected_tier == rec_tier:
            self.lbl_status.configure(text=f"Selected Profile Tier: {selected_tier} (Recommended)", text_color=COLOR_TEXT_MUTED)
        else:
            self.lbl_status.configure(text=f"Selected Profile Tier: {selected_tier} (Manual Override - Recommended was {rec_tier})", text_color=COLOR_PRIMARY)

    def render_scan_results(self):
        if not self.hardware_profile:
            return

        # 1. Update Hardware specs display
        self.lbl_cpu_val.configure(text=self.hardware_profile.cpu_model)
        self.lbl_cores_val.configure(
            text=f"{self.hardware_profile.cpu_cores_physical} Physical / {self.hardware_profile.cpu_cores_logical} Logical"
        )
        self.lbl_gpu_val.configure(
            text=f"{self.hardware_profile.gpu_model} (VRAM: {self.hardware_profile.gpu_vram_gb} GB)"
        )
        self.lbl_ram_val.configure(text=f"{self.hardware_profile.ram_gb} GB")
        self.lbl_storage_val.configure(text=f"{self.hardware_profile.storage_type} Drive")

        # 2. Update Recommendation Selector dropdown
        if HAS_CTK:
            self.tier_selector.configure(state="normal")
            self.tier_selector.set(self.recommended_tier)
        else:
            self.tier_selector.configure(state="normal")
            self.tk_tier_var.set(self.recommended_tier)

        self.lbl_tier_desc.configure(text=self.tier_description)
        
        # 3. Populate recommendation table
        self.populate_recommendation_table()

        # Show control action buttons
        self.apply_button.configure(state="normal")
        self.restore_button.configure(state="normal")

    def populate_recommendation_table(self):
        for widget in self.table_container.winfo_children():
            widget.destroy()

        headers = ["Setting", "Recommended Value", "Description / Reason"]
        for col_idx, header in enumerate(headers):
            lbl = ctk.CTkLabel(
                self.table_container, 
                text=header, 
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_TEXT_MAIN
            ) if HAS_CTK else tk.Label(self.table_container, text=header, fg=COLOR_TEXT_MAIN, bg=COLOR_CARD, font=("Arial", 10, "bold"))
            lbl.grid(row=0, column=col_idx, padx=10, pady=5, sticky="w")

        # Flatten settings from categories
        row_idx = 1
        all_recs = []
        for section, keys in self.recommended_settings.items():
            for key, val in keys.items():
                all_recs.append((key, val))

        for key, val in all_recs:
            # Map values to readable strings if needed
            display_val = val
            if key == "FullscreenMode" or key == "LastConfirmedFullscreenMode":
                if val == "0":
                    display_val = "Fullscreen"
                elif val == "1":
                    display_val = "Borderless"
                else:
                    display_val = "Windowed"
            elif key == "bUseVSync":
                display_val = "Off" if val == "False" else "On"
            elif key == "FrameRateLimit":
                display_val = "Uncapped" if float(val) == 0.0 else f"{int(float(val))} FPS"
            elif key.startswith("sg."):
                levels = ["Low / Off", "Medium", "High", "Ultra / Max"]
                try:
                    display_val = levels[int(val)]
                except Exception:
                    display_val = val

            explanation = recommend.SETTING_EXPLANATIONS.get(key, "Optimized settings for performance.")

            # Create labels
            lbl_key = ctk.CTkLabel(self.table_container, text=key, text_color=COLOR_TEXT_MAIN) if HAS_CTK else tk.Label(self.table_container, text=key, fg=COLOR_TEXT_MAIN, bg=COLOR_CARD)
            lbl_val = ctk.CTkLabel(self.table_container, text=display_val, text_color=COLOR_PRIMARY) if HAS_CTK else tk.Label(self.table_container, text=display_val, fg=COLOR_PRIMARY, bg=COLOR_CARD)
            lbl_exp = ctk.CTkLabel(self.table_container, text=explanation, text_color=COLOR_TEXT_MUTED, wraplength=350, justify="left") if HAS_CTK else tk.Label(self.table_container, text=explanation, fg=COLOR_TEXT_MUTED, bg=COLOR_CARD, wraplength=350, justify="left")

            lbl_key.grid(row=row_idx, column=0, padx=10, pady=4, sticky="w")
            lbl_val.grid(row=row_idx, column=1, padx=10, pady=4, sticky="w")
            lbl_exp.grid(row=row_idx, column=2, padx=10, pady=4, sticky="w")
            row_idx += 1

    def apply_settings(self):
        if not self.selected_ini_path:
            messagebox.showerror("Error", "Please select or locate the GameUserSettings.ini file first.")
            return

        if self.is_valorant_running():
            messagebox.showwarning(
                "Valorant is Running", 
                "Valorant must be fully closed before applying settings to prevent overwrites."
            )
            return

        confirm = messagebox.askyesno(
            "Apply Recommended Settings",
            "This action will modify GameUserSettings.ini.\nA backup of your current settings will be created automatically. Proceed?"
        )
        if not confirm:
            return

        try:
            # 1. Create Backup
            backup_file = config_manager.create_backup(self.selected_ini_path)
            
            # 2. Apply config modifications
            changes = config_manager.apply_profile(self.selected_ini_path, self.recommended_settings)
            
            log_msg = f"Applied optimized settings to {self.selected_ini_path}. Made {len(changes)} changes."
            logger.info(log_msg)
            
            self.lbl_status.configure(
                text=f"Success: Settings applied successfully. Backup created: {os.path.basename(backup_file)}",
                text_color=COLOR_TEXT_MAIN
            )
            self.launch_btn.configure(state="normal")
            
            messagebox.showinfo(
                "Optimization Applied", 
                f"Settings applied successfully.\nBackup file created:\n{os.path.basename(backup_file)}"
            )
        except Exception as e:
            logger.error(f"Failed to apply settings: {e}")
            self.lbl_status.configure(text=f"Error: Failed to apply settings - {str(e)}", text_color=COLOR_WARNING)
            messagebox.showerror("Error", f"Failed to apply settings: {e}")

    def restore_settings(self):
        if not self.selected_ini_path:
            messagebox.showerror("Error", "Please select or locate the GameUserSettings.ini file first.")
            return

        confirm = messagebox.askyesno(
            "Restore Settings",
            "Are you sure you want to revert to your previous settings from the latest backup file?"
        )
        if not confirm:
            return

        try:
            restored_file = config_manager.restore_latest_backup(self.selected_ini_path)
            self.lbl_status.configure(
                text=f"Success: Settings reverted to backup {os.path.basename(restored_file)}",
                text_color=COLOR_TEXT_MAIN
            )
            messagebox.showinfo("Settings Restored", f"Settings successfully restored from:\n{os.path.basename(restored_file)}")
        except Exception as e:
            logger.error(f"Failed to restore settings: {e}")
            self.lbl_status.configure(text=f"Error: Restore failed - {str(e)}", text_color=COLOR_WARNING)
            messagebox.showerror("Restore Error", f"Failed to restore: {str(e)}")

    def run_game(self):
        try:
            method = config_manager.launch_valorant()
            self.lbl_status.configure(text=f"Game launched successfully via {method}", text_color=COLOR_TEXT_MAIN)
        except Exception as e:
            messagebox.showerror("Launch Error", str(e))

    def is_valorant_running(self) -> bool:
        import psutil
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == "VALORANT-Win64-Shipping.exe":
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def process_guard_loop(self):
        """Monitors system processes to verify if Valorant is running."""
        while self.running_check_thread_active:
            try:
                running = self.is_valorant_running()
                if running:
                    self.lbl_warning_banner.configure(
                        text="Warning: VALORANT is currently running. Please close the game before applying settings.",
                        text_color=COLOR_WARNING
                    )
                    self.apply_button.configure(state="disabled")
                else:
                    self.lbl_warning_banner.configure(
                        text="Status: VALORANT is closed. You can apply modifications safely.",
                        text_color=COLOR_TEXT_MUTED
                    )
                    # Restore apply button state if scan was already performed
                    if self.hardware_profile and not self.is_scan_running:
                        self.apply_button.configure(state="normal")
            except Exception as e:
                logger.warning(f"Error checking processes in thread: {e}")
            time.sleep(1.5)

    def open_github(self):
        try:
            webbrowser.open("https://github.com")
            logger.info("Opened GitHub repository link in web browser.")
        except Exception as e:
            logger.error(f"Failed to open GitHub link: {e}")

    def build_ctk_ui(self):
        # Master Frame
        main_container = ctk.CTkFrame(self.root, fg_color=COLOR_BG, corner_radius=0)
        main_container.pack(fill="both", expand=True)

        # 1. Header panel
        header = ctk.CTkFrame(main_container, fg_color=COLOR_PANEL, height=90, corner_radius=0)
        header.pack(fill="x")
        
        # Center-aligned wrapper
        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(pady=10)
        
        if hasattr(self, "logo_image") and self.logo_image:
            lbl_logo = ctk.CTkLabel(header_content, image=self.logo_image, text="")
            lbl_logo.pack(side="left", padx=(0, 15))
            
        text_frame = ctk.CTkFrame(header_content, fg_color="transparent")
        text_frame.pack(side="left")
        
        lbl_title = ctk.CTkLabel(
            text_frame, 
            text="NEUZ VALORANT OPTIMIZER", 
            font=ctk.CTkFont(family="Helvetica", size=22, weight="bold"),
            text_color=COLOR_PRIMARY
        )
        lbl_title.pack(anchor="w")
        
        lbl_subtitle = ctk.CTkLabel(
            text_frame,
            text="Safe Hardware Detection and Graphics Quality Configuration",
            font=ctk.CTkFont(family="Helvetica", size=12),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_subtitle.pack(anchor="w")

        # 2. Bottom panels: Footer & Warning Banner
        # Pack footer first so it goes to the absolute bottom
        footer_frame = ctk.CTkFrame(main_container, fg_color=COLOR_PANEL, height=35, corner_radius=0)
        footer_frame.pack(fill="x", side="bottom")
        
        lbl_footer_text = ctk.CTkLabel(
            footer_frame, 
            text="Neuz Valorant Optimizer - Created for Competitive Performance", 
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_footer_text.pack(side="left", padx=20, pady=5)
        
        btn_github = ctk.CTkButton(
            footer_frame,
            text="GitHub Repository",
            fg_color="transparent",
            text_color=COLOR_PRIMARY,
            hover_color=COLOR_CARD,
            font=ctk.CTkFont(size=11, underline=True),
            width=100,
            command=self.open_github
        )
        btn_github.pack(side="right", padx=20, pady=5)

        # Warning banner goes directly above footer
        self.lbl_warning_banner = ctk.CTkLabel(
            main_container,
            text="Status: Checking game running status...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_PANEL
        )
        self.lbl_warning_banner.pack(fill="x", side="bottom", ipady=8)

        # Middle Content Frame (Split: Left = Hardware Scan, Right = Recommendation)
        content_frame = ctk.CTkFrame(main_container, fg_color=COLOR_BG, corner_radius=0)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        content_frame.columnconfigure(0, weight=4)  # Left
        content_frame.columnconfigure(1, weight=5)  # Right
        content_frame.rowconfigure(0, weight=1)

        # LEFT PANEL: Scan & Hardware Specs Card
        left_panel = ctk.CTkFrame(content_frame, fg_color=COLOR_BG, corner_radius=0)
        left_panel.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        
        # Scan action frame
        scan_action_frame = ctk.CTkFrame(left_panel, fg_color=COLOR_PANEL, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        scan_action_frame.pack(fill="x", pady=(0, 15), ipady=10)
        
        lbl_action = ctk.CTkLabel(
            scan_action_frame, 
            text="System Evaluation", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl_action.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")

        self.scan_button = ctk.CTkButton(
            scan_action_frame,
            text="Scan My PC",
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(weight="bold"),
            command=self.run_hardware_scan
        )
        self.scan_button.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        
        self.progress_bar = ctk.CTkProgressBar(scan_action_frame, progress_color=COLOR_PRIMARY, height=8)
        
        scan_action_frame.columnconfigure(0, weight=1)

        # Hardware Spec Card
        hw_card = ctk.CTkFrame(left_panel, fg_color=COLOR_PANEL, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        hw_card.pack(fill="both", expand=True, ipady=10)
        
        lbl_hw_title = ctk.CTkLabel(
            hw_card, 
            text="Detected Hardware Specifications", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl_hw_title.pack(anchor="w", padx=15, pady=15)

        # Fields helper
        def add_spec_row(parent, label_text):
            lbl_name = ctk.CTkLabel(parent, text=label_text, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED)
            lbl_name.pack(anchor="w", padx=15, pady=(5, 0))
            lbl_val = ctk.CTkLabel(parent, text="Not Scanned Yet", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_MAIN)
            lbl_val.pack(anchor="w", padx=15, pady=(0, 10))
            return lbl_val

        self.lbl_cpu_val = add_spec_row(hw_card, "Processor (CPU)")
        self.lbl_cores_val = add_spec_row(hw_card, "Cores Structure")
        self.lbl_gpu_val = add_spec_row(hw_card, "Graphics Adapter (GPU)")
        self.lbl_ram_val = add_spec_row(hw_card, "System Memory (RAM)")
        self.lbl_storage_val = add_spec_row(hw_card, "Windows Storage Medium")

        # RIGHT PANEL: Recommendation and actions
        right_panel = ctk.CTkFrame(content_frame, fg_color=COLOR_BG, corner_radius=0)
        right_panel.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        # Config Locator Box
        config_box = ctk.CTkFrame(right_panel, fg_color=COLOR_PANEL, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        config_box.pack(fill="x", pady=(0, 15), ipady=10)
        
        # Account selection row
        selector_row = ctk.CTkFrame(config_box, fg_color="transparent")
        selector_row.pack(fill="x", padx=15, pady=(5, 5))
        
        lbl_acc_label = ctk.CTkLabel(
            selector_row, 
            text="Target Account Profile:", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl_acc_label.pack(side="left", padx=(0, 10))
        
        self.account_selector = ctk.CTkOptionMenu(
            selector_row,
            values=["Scanning for accounts..."],
            fg_color=COLOR_SECONDARY,
            button_color=COLOR_SECONDARY,
            button_hover_color=COLOR_SECONDARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color=COLOR_CARD,
            dropdown_hover_color=COLOR_SECONDARY,
            dropdown_text_color=COLOR_TEXT_MAIN,
            state="disabled",
            command=self.on_account_selected
        )
        self.account_selector.pack(side="left", fill="x", expand=True)

        # Path display and browse row
        path_row = ctk.CTkFrame(config_box, fg_color="transparent")
        path_row.pack(fill="x", padx=15, pady=(5, 5))

        self.path_label = ctk.CTkLabel(
            path_row, 
            text="Checking Valorant install directories...", 
            font=ctk.CTkFont(size=11), 
            text_color=COLOR_TEXT_MUTED,
            wraplength=350,
            justify="left"
        )
        self.path_label.pack(side="left", fill="x", expand=True)

        btn_browse = ctk.CTkButton(
            path_row,
            text="Locate",
            fg_color=COLOR_SECONDARY,
            hover_color=COLOR_SECONDARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
            width=60,
            command=self.select_file_manually
        )
        btn_browse.pack(side="right")

        # Recommendations details card
        rec_card = ctk.CTkFrame(right_panel, fg_color=COLOR_PANEL, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        rec_card.pack(fill="both", expand=True, ipady=10)

        # Title of card
        self.lbl_tier_card_title = ctk.CTkLabel(
            rec_card, 
            text="Optimized Graphics Profile", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        self.lbl_tier_card_title.pack(anchor="w", padx=15, pady=(15, 2))

        # Selector Row Frame
        selector_frame = ctk.CTkFrame(rec_card, fg_color="transparent")
        selector_frame.pack(fill="x", padx=15, pady=(5, 10))
        
        lbl_select_label = ctk.CTkLabel(
            selector_frame, 
            text="Active Profile Tier:", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl_select_label.pack(side="left", padx=(0, 10))
        
        self.tier_selector = ctk.CTkOptionMenu(
            selector_frame,
            values=["LOW", "MID", "HIGH", "ENTHUSIAST"],
            fg_color=COLOR_SECONDARY,
            button_color=COLOR_SECONDARY,
            button_hover_color=COLOR_SECONDARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
            dropdown_fg_color=COLOR_CARD,
            dropdown_hover_color=COLOR_SECONDARY,
            dropdown_text_color=COLOR_TEXT_MAIN,
            state="disabled",
            command=self.on_tier_selected
        )
        self.tier_selector.pack(side="left")

        self.lbl_tier_desc = ctk.CTkLabel(
            rec_card,
            text="Please perform a hardware scan to see recommendations.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED,
            wraplength=400,
            justify="left"
        )
        self.lbl_tier_desc.pack(anchor="w", padx=15, pady=(0, 15))

        # Recommendations list (Scrollable Frame)
        self.table_container = ctk.CTkScrollableFrame(
            rec_card, 
            fg_color=COLOR_CARD,
            scrollbar_button_color=COLOR_SECONDARY,
            scrollbar_button_hover_color=COLOR_SECONDARY_HOVER,
            corner_radius=4
        )
        self.table_container.pack(fill="both", expand=True, padx=15, pady=5)
        self.table_container.columnconfigure(0, weight=3)
        self.table_container.columnconfigure(1, weight=2)
        self.table_container.columnconfigure(2, weight=4)

        # Control Panel Box (Apply / Restore / Launch)
        control_box = ctk.CTkFrame(right_panel, fg_color=COLOR_PANEL, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        control_box.pack(fill="x", pady=(15, 0), ipady=10)

        self.lbl_status = ctk.CTkLabel(
            control_box,
            text="System status: Idle",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_status.pack(pady=(10, 5))

        actions_frame = ctk.CTkFrame(control_box, fg_color=COLOR_PANEL, corner_radius=0)
        actions_frame.pack(fill="x", padx=15, pady=5)
        actions_frame.columnconfigure(0, weight=1)
        actions_frame.columnconfigure(1, weight=1)
        actions_frame.columnconfigure(2, weight=1)

        self.apply_button = ctk.CTkButton(
            actions_frame,
            text="Apply Settings",
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
            state="disabled",
            font=ctk.CTkFont(weight="bold"),
            command=self.apply_settings
        )
        self.apply_button.grid(row=0, column=0, padx=5, sticky="ew")

        self.restore_button = ctk.CTkButton(
            actions_frame,
            text="Restore Settings",
            fg_color=COLOR_SECONDARY,
            hover_color=COLOR_SECONDARY_HOVER,
            text_color=COLOR_TEXT_MAIN,
            state="disabled",
            command=self.restore_settings
        )
        self.restore_button.grid(row=0, column=1, padx=5, sticky="ew")

        self.launch_btn = ctk.CTkButton(
            actions_frame,
            text="Launch VALORANT",
            fg_color=COLOR_SUCCESS,
            hover_color="#1f702e",
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(weight="bold"),
            state="normal", # Let it always launch if they want, fallback is URI
            command=self.run_game
        )
        self.launch_btn.grid(row=0, column=2, padx=5, sticky="ew")

    def build_tk_ui(self):
        # Muted backup UI for standard Tkinter
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", thickness=8, troughcolor=COLOR_BG, background=COLOR_PRIMARY)
        
        main_container = tk.Frame(self.root, bg=COLOR_BG)
        main_container.pack(fill="both", expand=True)

        header = tk.Frame(main_container, bg=COLOR_PANEL)
        header.pack(fill="x", ipady=10)
        
        # Center-aligned wrapper
        header_content = tk.Frame(header, bg=COLOR_PANEL)
        header_content.pack(pady=10)
        
        if hasattr(self, "tk_logo_image") and self.tk_logo_image:
            lbl_logo = tk.Label(header_content, image=self.tk_logo_image, bg=COLOR_PANEL)
            lbl_logo.pack(side="left", padx=(0, 15))
            
        text_frame = tk.Frame(header_content, bg=COLOR_PANEL)
        text_frame.pack(side="left")
        
        lbl_title = tk.Label(text_frame, text="NEUZ VALORANT OPTIMIZER", fg=COLOR_PRIMARY, bg=COLOR_PANEL, font=("Helvetica", 18, "bold"))
        lbl_title.pack(anchor="w")
        
        lbl_sub = tk.Label(text_frame, text="Safe Hardware Detection and Graphics Quality Configuration", fg=COLOR_TEXT_MUTED, bg=COLOR_PANEL, font=("Helvetica", 10))
        lbl_sub.pack(anchor="w")

        # Bottom panels: Footer & Warning Banner
        # Pack footer first so it goes to the absolute bottom
        footer_frame = tk.Frame(main_container, bg=COLOR_PANEL)
        footer_frame.pack(fill="x", side="bottom")
        
        lbl_footer_text = tk.Label(footer_frame, text="Neuz Valorant Optimizer - Created for Competitive Performance", fg=COLOR_TEXT_MUTED, bg=COLOR_PANEL, font=("Helvetica", 9))
        lbl_footer_text.pack(side="left", padx=20, pady=5)
        
        btn_github = tk.Button(
            footer_frame,
            text="GitHub Repository",
            fg=COLOR_PRIMARY,
            bg=COLOR_PANEL,
            activeforeground=COLOR_PRIMARY_HOVER,
            activebackground=COLOR_PANEL,
            font=("Helvetica", 9, "underline"),
            bd=0,
            command=self.open_github
        )
        btn_github.pack(side="right", padx=20, pady=5)

        # Warning Banner goes directly above footer
        self.lbl_warning_banner = tk.Label(
            main_container, 
            text="Status: Checking game running status...", 
            fg=COLOR_TEXT_MUTED, 
            bg=COLOR_PANEL,
            font=("Helvetica", 10, "bold")
        )
        self.lbl_warning_banner.pack(fill="x", side="bottom", ipady=8)

        # Content frame
        content_frame = tk.Frame(main_container, bg=COLOR_BG)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)

        # Left Column: Scan
        left_panel = tk.Frame(content_frame, bg=COLOR_BG)
        left_panel.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        scan_box = tk.Frame(left_panel, bg=COLOR_PANEL, bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        scan_box.pack(fill="x", pady=(0, 15), ipady=10)
        
        lbl_act = tk.Label(scan_box, text="System Evaluation", fg=COLOR_TEXT_MAIN, bg=COLOR_PANEL, font=("Helvetica", 11, "bold"))
        lbl_act.pack(anchor="w", padx=15, pady=5)
        
        self.scan_button = tk.Button(scan_box, text="Scan My PC", bg=COLOR_PRIMARY, fg=COLOR_TEXT_MAIN, activebackground=COLOR_PRIMARY_HOVER, activeforeground=COLOR_TEXT_MAIN, font=("Helvetica", 10, "bold"), command=self.run_hardware_scan, relief="flat", bd=0, ipady=5)
        self.scan_button.pack(fill="x", padx=15, pady=5)
        
        # Tkinter ProgressBar
        self.progress_bar = ttk.Progressbar(scan_box, orient="horizontal", mode="determinate", style="TProgressbar")

        # Specs Box
        hw_box = tk.Frame(left_panel, bg=COLOR_PANEL, bd=1, relief="solid")
        hw_box.pack(fill="both", expand=True, ipady=10)
        
        tk.Label(hw_box, text="Detected Hardware Specifications", fg=COLOR_TEXT_MAIN, bg=COLOR_PANEL, font=("Helvetica", 11, "bold")).pack(anchor="w", padx=15, pady=10)

        def add_spec_row_tk(parent, label_text):
            tk.Label(parent, text=label_text, fg=COLOR_TEXT_MUTED, bg=COLOR_PANEL, font=("Helvetica", 9)).pack(anchor="w", padx=15, pady=(5, 0))
            val = tk.Label(parent, text="Not Scanned Yet", fg=COLOR_TEXT_MAIN, bg=COLOR_PANEL, font=("Helvetica", 10, "bold"))
            val.pack(anchor="w", padx=15, pady=(0, 5))
            return val

        self.lbl_cpu_val = add_spec_row_tk(hw_box, "Processor (CPU)")
        self.lbl_cores_val = add_spec_row_tk(hw_box, "Cores Structure")
        self.lbl_gpu_val = add_spec_row_tk(hw_box, "Graphics Adapter (GPU)")
        self.lbl_ram_val = add_spec_row_tk(hw_box, "System Memory (RAM)")
        self.lbl_storage_val = add_spec_row_tk(hw_box, "Windows Storage Medium")

        # Right Column: Recs
        right_panel = tk.Frame(content_frame, bg=COLOR_BG)
        right_panel.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        # Path box
        path_box = tk.Frame(right_panel, bg=COLOR_PANEL, bd=1, relief="solid")
        path_box.pack(fill="x", pady=(0, 15), ipady=10)
        
        # Account selection row
        selector_row = tk.Frame(path_box, bg=COLOR_PANEL)
        selector_row.pack(fill="x", padx=10, pady=5)
        
        lbl_acc_label = tk.Label(selector_row, text="Target Account Profile:", fg=COLOR_TEXT_MAIN, bg=COLOR_PANEL, font=("Helvetica", 9, "bold"))
        lbl_acc_label.pack(side="left", padx=(0, 10))
        
        self.tk_account_var = tk.StringVar(value="Scanning...")
        self.tk_account_var.trace_add("write", lambda *args: self.on_account_selected(self.tk_account_var.get()))
        
        self.account_selector = tk.OptionMenu(
            selector_row,
            self.tk_account_var,
            "Scanning..."
        )
        self.account_selector.configure(bg=COLOR_SECONDARY, fg=COLOR_TEXT_MAIN, activebackground=COLOR_SECONDARY_HOVER, activeforeground=COLOR_TEXT_MAIN, bd=0, relief="flat")
        self.account_selector.pack(side="left", fill="x", expand=True)
        self.account_selector.configure(state="disabled")
        
        self.tk_account_menu = self.account_selector

        # Path display and browse row
        path_row = tk.Frame(path_box, bg=COLOR_PANEL)
        path_row.pack(fill="x", padx=10, pady=5)

        self.path_label = tk.Label(path_row, text="Checking Valorant install directories...", fg=COLOR_TEXT_MUTED, bg=COLOR_PANEL, font=("Helvetica", 9), wraplength=250, justify="left")
        self.path_label.pack(side="left")
        
        btn_loc = tk.Button(path_row, text="Locate", bg=COLOR_SECONDARY, fg=COLOR_TEXT_MAIN, activebackground=COLOR_SECONDARY_HOVER, font=("Helvetica", 9), command=self.select_file_manually, relief="flat", bd=0)
        btn_loc.pack(side="right")

        # Rec Box
        rec_box = tk.Frame(right_panel, bg=COLOR_PANEL, bd=1, relief="solid")
        rec_box.pack(fill="both", expand=True, ipady=10)
        
        # Title of card
        self.lbl_tier_card_title = tk.Label(rec_box, text="Optimized Graphics Profile", fg=COLOR_TEXT_MAIN, bg=COLOR_PANEL, font=("Helvetica", 11, "bold"))
        self.lbl_tier_card_title.pack(anchor="w", padx=15, pady=(10, 2))

        # Selector Row Frame
        selector_frame = tk.Frame(rec_box, bg=COLOR_PANEL)
        selector_frame.pack(fill="x", padx=15, pady=(5, 10))
        
        lbl_select_label = tk.Label(selector_frame, text="Active Profile Tier:", fg=COLOR_TEXT_MAIN, bg=COLOR_PANEL, font=("Helvetica", 9, "bold"))
        lbl_select_label.pack(side="left", padx=(0, 10))
        
        # Tkinter option menu needs a StringVar
        self.tk_tier_var = tk.StringVar(value="None")
        self.tk_tier_var.trace_add("write", lambda *args: self.on_tier_selected(self.tk_tier_var.get()))
        
        self.tier_selector = tk.OptionMenu(
            selector_frame,
            self.tk_tier_var,
            "LOW", "MID", "HIGH", "ENTHUSIAST"
        )
        self.tier_selector.configure(bg=COLOR_SECONDARY, fg=COLOR_TEXT_MAIN, activebackground=COLOR_SECONDARY_HOVER, activeforeground=COLOR_TEXT_MAIN, bd=0, relief="flat")
        self.tier_selector.pack(side="left")
        self.tier_selector.configure(state="disabled")

        self.lbl_tier_desc = tk.Label(rec_box, text="Please perform a hardware scan to see recommendations.", fg=COLOR_TEXT_MUTED, bg=COLOR_PANEL, font=("Helvetica", 9), wraplength=350, justify="left")
        self.lbl_tier_desc.pack(anchor="w", padx=15, pady=(0, 10))

        # Canvas for scrollable list in standard TK
        list_canvas_frame = tk.Frame(rec_box, bg=COLOR_CARD)
        list_canvas_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.table_container = tk.Frame(list_canvas_frame, bg=COLOR_CARD)
        self.table_container.pack(fill="both", expand=True)

        # Controls
        ctrl_box = tk.Frame(right_panel, bg=COLOR_PANEL, bd=1, relief="solid")
        ctrl_box.pack(fill="x", pady=(15, 0), ipady=10)
        
        self.lbl_status = tk.Label(ctrl_box, text="System status: Idle", fg=COLOR_TEXT_MUTED, bg=COLOR_PANEL, font=("Helvetica", 9))
        self.lbl_status.pack(pady=5)

        act_frame = tk.Frame(ctrl_box, bg=COLOR_PANEL)
        act_frame.pack(fill="x", padx=10)
        act_frame.columnconfigure(0, weight=1)
        act_frame.columnconfigure(1, weight=1)
        act_frame.columnconfigure(2, weight=1)

        self.apply_button = tk.Button(act_frame, text="Apply Settings", bg=COLOR_PRIMARY, fg=COLOR_TEXT_MAIN, font=("Helvetica", 9, "bold"), state="disabled", command=self.apply_settings, relief="flat", bd=0, ipady=5)
        self.apply_button.grid(row=0, column=0, padx=5, sticky="ew")

        self.restore_button = tk.Button(act_frame, text="Restore Settings", bg=COLOR_SECONDARY, fg=COLOR_TEXT_MAIN, state="disabled", command=self.restore_settings, relief="flat", bd=0, ipady=5)
        self.restore_button.grid(row=0, column=1, padx=5, sticky="ew")

        self.launch_btn = tk.Button(act_frame, text="Launch VALORANT", bg=COLOR_SUCCESS, fg=COLOR_TEXT_MAIN, font=("Helvetica", 9, "bold"), command=self.run_game, relief="flat", bd=0, ipady=5)
        self.launch_btn.grid(row=0, column=2, padx=5, sticky="ew")

    def on_closing(self):
        self.running_check_thread_active = False
        self.root.destroy()

if __name__ == "__main__":
    if HAS_CTK:
        app = ctk.CTk()
    else:
        app = tk.Tk()
        
    main_app = ValorantOptimizerApp(app)
    
    # Intercept close window event to stop background threads safely
    if HAS_CTK:
        app.protocol("WM_DELETE_WINDOW", main_app.on_closing)
    else:
        app.protocol("WM_DELETE_WINDOW", main_app.on_closing)
        
    app.mainloop()
