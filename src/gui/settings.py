"""
Settings Tab - Configuration management
"""
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
from src.config import TradingConfig
from src.updater import Updater

class SettingsTab:
    """Settings tab for configuration"""
    
    def __init__(self, parent, main_window, config: TradingConfig):
        self.main_window = main_window
        self.config = config
        self.frame = tk.Frame(parent, bg=main_window.bg_primary)
        self._create_ui()
    
    def _create_ui(self):
        """Create settings UI"""
        container = tk.Frame(self.frame, bg=self.main_window.bg_primary)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Two column layout
        left_col = tk.Frame(container, bg=self.main_window.bg_primary)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        
        right_col = tk.Frame(container, bg=self.main_window.bg_primary)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        
        # Store entry widgets
        self.entries = {}
        
        # LEFT COLUMN
        
        # MT5 Connection
        mt5_card = self._create_card(left_col, "MT5 Connection")
        
        self.entries['mt5_path'] = self._add_path_row(mt5_card, "MT5 Path", str(self.config.mt5_path or ""))
        
        # Info and Test Connection row (inline)
        action_row = tk.Frame(mt5_card, bg=self.main_window.bg_card)
        action_row.pack(fill=tk.X, padx=12, pady=(8, 10))
        
        tk.Label(action_row, 
                text="💡 Make sure you're logged into MetaTrader 5",
                bg=self.main_window.bg_card, fg=self.main_window.accent_blue,
                font=(self.main_window.font_family, 7)).pack(side=tk.LEFT)
        
        tk.Button(action_row, text="ⓘ", 
                 command=self._show_mt5_instructions,
                 bg=self.main_window.bg_card, fg=self.main_window.accent_blue,
                 font=(self.main_window.font_family, 10, "bold"),
                 relief=tk.FLAT, padx=4, pady=0, cursor="hand2",
                 borderwidth=0).pack(side=tk.LEFT, padx=(5, 0))
        
        tk.Button(action_row, text="Test Connection", command=self._test_mt5_connection,
                 bg=self.main_window.accent_green, fg="white",
                 font=(self.main_window.font_family, 8, "bold"),
                 relief=tk.FLAT, padx=12, pady=4, cursor="hand2",
                 borderwidth=0).pack(side=tk.RIGHT)
        
        # Risk Settings
        risk_card = self._create_card(left_col, "Risk Settings")
        
        self.entries['risk_percent'] = self._add_editable_row(risk_card, "Risk Percent", str(self.config.risk_percent))
        self.entries['min_lot'] = self._add_editable_row(risk_card, "Min Lot", str(self.config.min_lot))
        self.entries['max_lot'] = self._add_editable_row(risk_card, "Max Lot", str(self.config.max_lot))
        self.entries['max_open_trades'] = self._add_editable_row(risk_card, "Max Open Trades", str(self.config.max_open_trades))
        
        tk.Label(risk_card, text="", bg=self.main_window.bg_card).pack(pady=4)
        
        # Break-Even Settings
        be_card = self._create_card(left_col, "Break-Even Settings")
        
        self.entries['use_break_even'] = self._add_checkbox_row(be_card, "Enabled", self.config.use_break_even)
        self.entries['break_even_at'] = self._add_editable_row(be_card, "Activate At (pips)", str(self.config.break_even_at_pips))
        self.entries['break_even_offset'] = self._add_editable_row(be_card, "Offset (pips)", str(self.config.break_even_offset_pips))
        
        tk.Label(be_card, text="", bg=self.main_window.bg_card).pack(pady=4)
        
        # RIGHT COLUMN
        
        # Trailing Stop Settings
        ts_card = self._create_card(right_col, "Trailing Stop Settings")
        
        self.entries['use_trailing'] = self._add_checkbox_row(ts_card, "Enabled", self.config.use_trailing_stop)
        self.entries['trailing_start'] = self._add_editable_row(ts_card, "Start At (pips)", str(self.config.trailing_start_pips))
        self.entries['trailing_step'] = self._add_editable_row(ts_card, "Step (pips)", str(self.config.trailing_step_pips))
        
        tk.Label(ts_card, text="", bg=self.main_window.bg_card).pack(pady=4)
        
        # Discord Settings
        discord_card = self._create_card(right_col, "Discord Settings")
        
        self.entries['discord_token'] = self._add_editable_row(discord_card, "Bot Token", str(self.config.discord_token or ""))
        self.entries['discord_channel'] = self._add_editable_row(discord_card, "Channel ID", str(self.config.discord_channel_id or ""))
        self.entries['discord_notification'] = self._add_editable_row(discord_card, "Notification Channel", str(self.config.discord_notification_channel_id or ""))
        
        tk.Label(discord_card, text="", bg=self.main_window.bg_card).pack(pady=4)
        
        # Spread Limits
        spread_card = self._create_card(right_col, "Spread Limits (points)")
        
        self.entries['spread_forex'] = self._add_editable_row(spread_card, "Forex", str(self.config.max_spread_forex))
        self.entries['spread_gold'] = self._add_editable_row(spread_card, "Gold", str(self.config.max_spread_gold))
        self.entries['spread_indices'] = self._add_editable_row(spread_card, "Indices", str(self.config.max_spread_indices))
        self.entries['spread_crypto'] = self._add_editable_row(spread_card, "Crypto", str(self.config.max_spread_crypto))
        
        tk.Label(spread_card, text="", bg=self.main_window.bg_card).pack(pady=4)
        
        # Update Section
        update_card = self._create_card(right_col, "Application Updates")
        
        update_info_row = tk.Frame(update_card, bg=self.main_window.bg_card)
        update_info_row.pack(fill=tk.X, padx=12, pady=3)
        
        from src.__version__ import __version__
        tk.Label(update_info_row, text=f"Current Version: v{__version__}", 
                bg=self.main_window.bg_card, fg=self.main_window.text_secondary,
                font=(self.main_window.font_family, 8)).pack(side=tk.LEFT)
        
        update_btn_row = tk.Frame(update_card, bg=self.main_window.bg_card)
        update_btn_row.pack(fill=tk.X, padx=12, pady=(5, 10))
        
        tk.Button(update_btn_row, text="Check for Updates", 
                 command=self._check_for_updates,
                 bg=self.main_window.accent_blue, fg="white",
                 font=(self.main_window.font_family, 8, "bold"),
                 relief=tk.FLAT, padx=12, pady=4, cursor="hand2",
                 borderwidth=0).pack(side=tk.LEFT)
    
    def _create_card(self, parent, title):
        """Create a settings card"""
        card = tk.Frame(parent, bg=self.main_window.bg_card, relief=tk.FLAT, bd=1,
                       highlightbackground=self.main_window.border_color, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(card, text=title, 
                bg=self.main_window.bg_card, fg=self.main_window.text_primary,
                font=(self.main_window.font_family, 9, "bold")).pack(anchor=tk.W, padx=12, pady=(10, 8))
        
        return card
    
    def _add_editable_row(self, parent, label, value):
        """Add an editable setting row"""
        row = tk.Frame(parent, bg=self.main_window.bg_card)
        row.pack(fill=tk.X, padx=12, pady=3)
        
        tk.Label(row, text=label, 
                bg=self.main_window.bg_card, fg=self.main_window.text_secondary,
                font=(self.main_window.font_family, 8), width=18, anchor=tk.W).pack(side=tk.LEFT)
        
        entry = tk.Entry(row, 
                        bg=self.main_window.bg_secondary, fg=self.main_window.text_primary,
                        font=(self.main_window.font_family, 8),
                        relief=tk.FLAT, insertbackground=self.main_window.text_primary,
                        width=25)
        entry.insert(0, value)
        entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Auto-save on change
        entry.bind('<FocusOut>', lambda e: self._auto_save())
        entry.bind('<Return>', lambda e: self._auto_save())
        
        return entry
    
    def _add_path_row(self, parent, label, value):
        """Add a path entry row with browse button"""
        row = tk.Frame(parent, bg=self.main_window.bg_card)
        row.pack(fill=tk.X, padx=12, pady=3)
        
        tk.Label(row, text=label, 
                bg=self.main_window.bg_card, fg=self.main_window.text_secondary,
                font=(self.main_window.font_family, 8), width=18, anchor=tk.W).pack(side=tk.LEFT)
        
        entry_frame = tk.Frame(row, bg=self.main_window.bg_card)
        entry_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        entry = tk.Entry(entry_frame, 
                        bg=self.main_window.bg_secondary, fg=self.main_window.text_primary,
                        font=(self.main_window.font_family, 8),
                        relief=tk.FLAT, insertbackground=self.main_window.text_primary)
        entry.insert(0, value)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(entry_frame, text="...", 
                 command=lambda: self._browse_mt5_path(entry),
                 bg=self.main_window.bg_secondary, fg=self.main_window.text_primary,
                 font=(self.main_window.font_family, 8),
                 relief=tk.FLAT, padx=8, pady=0, cursor="hand2",
                 borderwidth=0).pack(side=tk.RIGHT, padx=(2, 0))
        
        # Auto-save on change
        entry.bind('<FocusOut>', lambda e: self._auto_save())
        entry.bind('<Return>', lambda e: self._auto_save())
        
        return entry
    
    def _browse_mt5_path(self, entry):
        """Open file browser for MT5 terminal64.exe"""
        filename = filedialog.askopenfilename(
            title="Select MetaTrader 5 terminal64.exe",
            filetypes=[("MT5 Terminal", "terminal64.exe"), ("All files", "*.*")],
            initialdir="C:/Program Files"
        )
        if filename:
            entry.delete(0, tk.END)
            entry.insert(0, filename)
            self._auto_save()
    
    def _add_checkbox_row(self, parent, label, value):
        """Add a checkbox row"""
        row = tk.Frame(parent, bg=self.main_window.bg_card)
        row.pack(fill=tk.X, padx=12, pady=3)
        
        tk.Label(row, text=label, 
                bg=self.main_window.bg_card, fg=self.main_window.text_secondary,
                font=(self.main_window.font_family, 8), width=18, anchor=tk.W).pack(side=tk.LEFT)
        
        var = tk.BooleanVar(value=value)
        
        # Auto-save on change
        def on_change():
            self._auto_save()
        
        tk.Checkbutton(row, variable=var,
                      bg=self.main_window.bg_card,
                      activebackground=self.main_window.bg_card,
                      selectcolor=self.main_window.bg_secondary,
                      command=on_change).pack(side=tk.RIGHT)
        
        return var
    
    def _auto_save(self):
        """Auto-save settings when changed"""
        try:
            from pathlib import Path
            
            # Read current .env file
            env_path = Path("copy-trade-from-jarvis/agent-j-master/.env")
            if not env_path.exists():
                env_path = Path(".env")
            
            # Update config values
            updates = {
                'MT5_PATH': self.entries['mt5_path'].get(),
                'RISK_PERCENT': self.entries['risk_percent'].get(),
                'MIN_LOT': self.entries['min_lot'].get(),
                'MAX_LOT': self.entries['max_lot'].get(),
                'MAX_OPEN_TRADES': self.entries['max_open_trades'].get(),
                'USE_BREAK_EVEN': 'true' if self.entries['use_break_even'].get() else 'false',
                'BREAK_EVEN_AT_PIPS': self.entries['break_even_at'].get(),
                'BREAK_EVEN_OFFSET_PIPS': self.entries['break_even_offset'].get(),
                'USE_TRAILING_STOP': 'true' if self.entries['use_trailing'].get() else 'false',
                'TRAILING_START_PIPS': self.entries['trailing_start'].get(),
                'TRAILING_STEP_PIPS': self.entries['trailing_step'].get(),
                'DISCORD_TOKEN': self.entries['discord_token'].get(),
                'DISCORD_CHANNEL_ID': self.entries['discord_channel'].get(),
                'DISCORD_NOTIFICATION_CHANNEL_ID': self.entries['discord_notification'].get(),
                'MAX_SPREAD_FOREX': self.entries['spread_forex'].get(),
                'MAX_SPREAD_GOLD': self.entries['spread_gold'].get(),
                'MAX_SPREAD_INDICES': self.entries['spread_indices'].get(),
                'MAX_SPREAD_CRYPTO': self.entries['spread_crypto'].get(),
            }
            
            # Read existing .env
            lines = []
            if env_path.exists():
                with open(env_path, 'r') as f:
                    lines = f.readlines()
            
            # Update or add values
            updated_keys = set()
            for i, line in enumerate(lines):
                for key, value in updates.items():
                    if line.startswith(f"{key}="):
                        lines[i] = f"{key}={value}\n"
                        updated_keys.add(key)
                        break
            
            # Add new keys that weren't in the file
            for key, value in updates.items():
                if key not in updated_keys:
                    lines.append(f"{key}={value}\n")
            
            # Write back to .env
            with open(env_path, 'w') as f:
                f.writelines(lines)
            
            # Update the live config object
            self.config.mt5_path = self.entries['mt5_path'].get()
            self.config.discord_token = self.entries['discord_token'].get()
            self.config.discord_channel_id = int(self.entries['discord_channel'].get()) if self.entries['discord_channel'].get() else 0
            self.config.discord_notification_channel_id = int(self.entries['discord_notification'].get()) if self.entries['discord_notification'].get() else 0
            self.config.risk_percent = float(self.entries['risk_percent'].get()) if self.entries['risk_percent'].get() else 1.0
            self.config.min_lot = float(self.entries['min_lot'].get()) if self.entries['min_lot'].get() else 0.01
            self.config.max_lot = float(self.entries['max_lot'].get()) if self.entries['max_lot'].get() else 10.0
            self.config.max_open_trades = int(self.entries['max_open_trades'].get()) if self.entries['max_open_trades'].get() else 3
            self.config.use_break_even = self.entries['use_break_even'].get()
            self.config.break_even_at_pips = float(self.entries['break_even_at'].get()) if self.entries['break_even_at'].get() else 10.0
            self.config.break_even_offset_pips = float(self.entries['break_even_offset'].get()) if self.entries['break_even_offset'].get() else 2.0
            self.config.use_trailing_stop = self.entries['use_trailing'].get()
            self.config.trailing_start_pips = float(self.entries['trailing_start'].get()) if self.entries['trailing_start'].get() else 15.0
            self.config.trailing_step_pips = float(self.entries['trailing_step'].get()) if self.entries['trailing_step'].get() else 5.0
            self.config.max_spread_forex = int(self.entries['spread_forex'].get()) if self.entries['spread_forex'].get() else 20
            self.config.max_spread_gold = int(self.entries['spread_gold'].get()) if self.entries['spread_gold'].get() else 500
            self.config.max_spread_indices = int(self.entries['spread_indices'].get()) if self.entries['spread_indices'].get() else 300
            self.config.max_spread_crypto = int(self.entries['spread_crypto'].get()) if self.entries['spread_crypto'].get() else 5000
            
        except Exception as e:
            print(f"Auto-save error: {e}")
    
    def _test_mt5_connection(self):
        """Test MT5 connection with current settings"""
        import MetaTrader5 as mt5
        
        try:
            # Check if bot is running
            bot = self.main_window.get_bot()
            if bot and self.main_window.running:
                # Bot is running - reconnect
                if messagebox.askyesno("Reconnect MT5", 
                    "Bot is currently running.\n\n"
                    "Do you want to reconnect MT5 with the new settings?\n"
                    "(This will restart the MT5 connection)"):
                    
                    # Disconnect and reconnect
                    if hasattr(bot, 'trader') and bot.trader:
                        bot.trader.disconnect()
                        
                        # Reconnect with new settings
                        if bot.trader.connect():
                            account_info = mt5.account_info()
                            if account_info:
                                balance = account_info.balance
                                equity = account_info.equity
                                name = account_info.name
                                company = account_info.company
                                account_login = account_info.login
                                account_server = account_info.server
                                
                                messagebox.showinfo(
                                    "Reconnection Successful ✓", 
                                    f"Reconnected to MT5!\n\n"
                                    f"Account: {account_login}\n"
                                    f"Name: {name}\n"
                                    f"Broker: {company}\n"
                                    f"Server: {account_server}\n"
                                    f"Balance: ${balance:,.2f}\n"
                                    f"Equity: ${equity:,.2f}"
                                )
                            else:
                                messagebox.showerror("Reconnection Failed", 
                                    "Could not retrieve account info after reconnection.")
                        else:
                            messagebox.showerror("Reconnection Failed", 
                                "Failed to reconnect to MT5.\n\n"
                                "Please check your settings and try again.")
                return
            
            # Bot is not running - just test connection
            # Initialize MT5
            mt5_path = self.config.mt5_path if self.config.mt5_path else None
            if not mt5.initialize(path=mt5_path):
                error = mt5.last_error()
                messagebox.showerror("Connection Failed", 
                    f"MT5 initialize failed:\n"
                    f"Error: {error}\n\n"
                    f"⚠️ Please make sure:\n"
                    f"1. MetaTrader 5 is installed\n"
                    f"2. You are logged into your MT5 account\n"
                    f"3. MT5 terminal is running")
                return
            
            # Get account info (uses current MT5 login)
            account_info = mt5.account_info()
            if account_info:
                balance = account_info.balance
                equity = account_info.equity
                name = account_info.name
                company = account_info.company
                account_login = account_info.login
                account_server = account_info.server
                mt5.shutdown()
                
                messagebox.showinfo(
                    "Connection Successful ✓", 
                    f"Connected to MT5!\n\n"
                    f"Account: {account_login}\n"
                    f"Name: {name}\n"
                    f"Broker: {company}\n"
                    f"Server: {account_server}\n"
                    f"Balance: ${balance:,.2f}\n"
                    f"Equity: ${equity:,.2f}"
                )
            else:
                mt5.shutdown()
                messagebox.showerror("Connection Failed", 
                    "Could not retrieve account info.\n\n"
                    "Please make sure you're logged into MT5.")
                
        except Exception as e:
            try:
                mt5.shutdown()
            except:
                pass
            messagebox.showerror("Error", f"Connection test failed:\n{str(e)}")
    
    def _show_mt5_instructions(self):
        """Show MT5 setup instructions"""
        instructions = """MT5 Path Setup Instructions:

1. Click the "..." button to browse for terminal64.exe

2. Common installation paths:
   • C:/Program Files/MetaTrader 5/terminal64.exe
   • C:/Program Files (x86)/MetaTrader 5/terminal64.exe
   • C:/Users/[YourName]/AppData/Roaming/MetaQuotes/Terminal/[BrokerFolder]/terminal64.exe

3. If you can't find it:
   • Open MetaTrader 5
   • Right-click on the MT5 icon in taskbar
   • Click "Open file location"
   • Look for terminal64.exe

4. After setting the path:
   • Make sure you're logged into MT5
   • Click "Test Connection" to verify

Note: Leave the path empty if MT5 is installed in the default location."""
        
        messagebox.showinfo("MT5 Path Instructions", instructions)
    
    def _check_for_updates(self):
        """Check for updates and install if available"""
        # Disable button during check
        for widget in self.frame.winfo_children():
            self._disable_widget(widget)
        
        # Show progress dialog
        progress = tk.Toplevel(self.main_window.root)
        progress.title("Checking for Updates")
        progress.geometry("400x150")
        progress.resizable(False, False)
        progress.configure(bg=self.main_window.bg_primary)
        progress.transient(self.main_window.root)
        progress.grab_set()
        
        # Center the window
        progress.update_idletasks()
        x = (progress.winfo_screenwidth() // 2) - (progress.winfo_width() // 2)
        y = (progress.winfo_screenheight() // 2) - (progress.winfo_height() // 2)
        progress.geometry(f"+{x}+{y}")
        
        status_label = tk.Label(progress, text="Checking for updates...", 
                               bg=self.main_window.bg_primary, fg=self.main_window.text_primary,
                               font=(self.main_window.font_family, 10))
        status_label.pack(pady=30)
        
        progress_bar = tk.Canvas(progress, width=300, height=4, 
                                bg=self.main_window.bg_secondary, 
                                highlightthickness=0)
        progress_bar.pack(pady=10)
        
        # Animated progress bar
        def animate_progress():
            for i in range(300):
                if not progress.winfo_exists():
                    return
                progress_bar.delete("all")
                progress_bar.create_rectangle(0, 0, (i % 300), 4, 
                                             fill=self.main_window.accent_blue, 
                                             outline="")
                progress.update()
                import time
                time.sleep(0.01)
        
        def check_update_thread():
            try:
                # TODO: Replace with your actual GitHub repo
                updater = Updater(github_repo="mark-aguirre/agent-j")
                
                status_label.config(text="Checking for updates...")
                has_update, latest_version, download_url = updater.check_for_updates()
                
                if not progress.winfo_exists():
                    return
                
                progress.destroy()
                
                # Re-enable widgets
                for widget in self.frame.winfo_children():
                    self._enable_widget(widget)
                
                if has_update:
                    # Ask user if they want to update
                    response = messagebox.askyesno(
                        "Update Available",
                        f"A new version is available!\n\n"
                        f"Current version: v{updater.current_version}\n"
                        f"Latest version: v{latest_version}\n\n"
                        f"Would you like to download and install it now?\n\n"
                        f"Note: The application will need to restart after the update."
                    )
                    
                    if response:
                        self._perform_update(updater, latest_version)
                else:
                    if latest_version:
                        messagebox.showinfo(
                            "No Updates",
                            f"You are running the latest version (v{latest_version})"
                        )
                    else:
                        messagebox.showwarning(
                            "Update Check Failed",
                            "Could not check for updates.\n\n"
                            "Please check your internet connection and try again."
                        )
                        
            except Exception as e:
                if progress.winfo_exists():
                    progress.destroy()
                
                # Re-enable widgets
                for widget in self.frame.winfo_children():
                    self._enable_widget(widget)
                
                messagebox.showerror("Error", f"Failed to check for updates:\n{str(e)}")
        
        # Start animation and check in separate threads
        threading.Thread(target=animate_progress, daemon=True).start()
        threading.Thread(target=check_update_thread, daemon=True).start()
    
    def _perform_update(self, updater, latest_version):
        """Perform the actual update"""
        # Show update progress dialog
        progress = tk.Toplevel(self.main_window.root)
        progress.title("Installing Update")
        progress.geometry("450x200")
        progress.resizable(False, False)
        progress.configure(bg=self.main_window.bg_primary)
        progress.transient(self.main_window.root)
        progress.grab_set()
        
        # Center the window
        progress.update_idletasks()
        x = (progress.winfo_screenwidth() // 2) - (progress.winfo_width() // 2)
        y = (progress.winfo_screenheight() // 2) - (progress.winfo_height() // 2)
        progress.geometry(f"+{x}+{y}")
        
        status_label = tk.Label(progress, text="Downloading update...", 
                               bg=self.main_window.bg_primary, fg=self.main_window.text_primary,
                               font=(self.main_window.font_family, 10))
        status_label.pack(pady=30)
        
        detail_label = tk.Label(progress, text="Please wait, this may take a few minutes...", 
                               bg=self.main_window.bg_primary, fg=self.main_window.text_secondary,
                               font=(self.main_window.font_family, 8))
        detail_label.pack(pady=5)
        
        progress_bar = tk.Canvas(progress, width=350, height=6, 
                                bg=self.main_window.bg_secondary, 
                                highlightthickness=0)
        progress_bar.pack(pady=15)
        
        # Animated progress bar
        def animate_progress():
            i = 0
            while progress.winfo_exists():
                progress_bar.delete("all")
                progress_bar.create_rectangle(0, 0, (i % 350), 6, 
                                             fill=self.main_window.accent_green, 
                                             outline="")
                progress.update()
                import time
                time.sleep(0.02)
                i += 2
        
        def update_thread():
            try:
                success, message = updater.perform_update()
                
                if not progress.winfo_exists():
                    return
                
                progress.destroy()
                
                if success:
                    response = messagebox.showinfo(
                        "Update Successful",
                        f"{message}\n\n"
                        f"Click OK to restart the application."
                    )
                    
                    # Restart the application
                    import sys
                    import os
                    import subprocess
                    
                    # Close current instance
                    self.main_window.root.destroy()
                    
                    # Restart
                    if getattr(sys, 'frozen', False):
                        # Running as compiled executable
                        subprocess.Popen([sys.executable])
                    else:
                        # Running as script
                        subprocess.Popen([sys.executable] + sys.argv)
                    
                    sys.exit(0)
                else:
                    messagebox.showerror("Update Failed", message)
                    
            except Exception as e:
                if progress.winfo_exists():
                    progress.destroy()
                messagebox.showerror("Error", f"Update failed:\n{str(e)}")
        
        # Start animation and update in separate threads
        threading.Thread(target=animate_progress, daemon=True).start()
        threading.Thread(target=update_thread, daemon=True).start()
    
    def _disable_widget(self, widget):
        """Recursively disable all widgets"""
        try:
            widget.configure(state='disabled')
        except:
            pass
        for child in widget.winfo_children():
            self._disable_widget(child)
    
    def _enable_widget(self, widget):
        """Recursively enable all widgets"""
        try:
            widget.configure(state='normal')
        except:
            pass
        for child in widget.winfo_children():
            self._enable_widget(child)
