"""
Main Window - Trading Bot GUI
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import logging
import asyncio
import hashlib

from src.__version__ import __version__, __app_name__
from src.config import TradingConfig
from src.gui.dashboard import DashboardTab
from src.gui.positions import PositionsTab
from src.gui.logs import LogsTab
from src.gui.settings import SettingsTab
from main import TradingBot

class MainWindow:
    """Main application window"""
    
    def __init__(self, root: tk.Tk, config: TradingConfig):
        self.root = root
        self.config = config
        self.bot = None
        self.bot_thread = None
        self.running = False
        self.log_queue = queue.Queue()
        self.master_mode_unlocked = False
        
        # Master mode password hash (SHA-256 of "sdfddsfdfgdfsgfsdg")
        self.master_password_hash = "60ff6f71612bdb63559b53032844d172eba6928b77f688c0b2d94846104b80b8"
        
        # Setup window
        self.root.title(f"{__app_name__} v{__version__}")
        self.root.geometry("950x550")
        self.root.minsize(800, 450)
        
        # Ubuntu-inspired color scheme
        self.bg_primary = "#2c2c2c"      # Ubuntu dark gray
        self.bg_secondary = "#3c3c3c"    # Lighter gray
        self.bg_card = "#4a4a4a"         # Card background
        self.accent_orange = "#e95420"   # Ubuntu orange
        self.accent_green = "#77b300"    # Ubuntu green
        self.accent_red = "#c7162b"      # Ubuntu red
        self.accent_blue = "#19b6ee"     # Ubuntu blue
        self.text_primary = "#f2f1f0"    # Light text
        self.text_secondary = "#aea79f"  # Muted text
        self.border_color = "#5a5a5a"    # Border
        
        # Font
        self.font_family = "Segoe UI"
        
        self.root.configure(bg=self.bg_primary)
        
        # Setup logging to queue
        self._setup_logging()
        
        # Create UI
        self._create_ui()
        
        # Start log processor
        self._process_logs()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_logging(self):
        """Setup logging to redirect to GUI"""
        class QueueHandler(logging.Handler):
            def __init__(self, log_queue):
                super().__init__()
                self.log_queue = log_queue
            
            def emit(self, record):
                self.log_queue.put(self.format(record))
        
        # Add queue handler to root logger
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logging.getLogger().addHandler(queue_handler)
    
    def _create_ui(self):
        """Create the main UI layout"""
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure notebook tabs - Ubuntu style
        style.configure('TNotebook', background=self.bg_primary, borderwidth=0)
        style.configure('TNotebook.Tab', 
                       background=self.bg_secondary, 
                       foreground=self.text_secondary,
                       padding=[12, 6],
                       font=(self.font_family, 8),
                       borderwidth=0)
        style.map('TNotebook.Tab',
                 background=[('selected', self.bg_primary)],
                 foreground=[('selected', self.accent_orange)])
        
        # Top header bar - Ubuntu style
        header = tk.Frame(self.root, bg=self.bg_secondary, height=40)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Left side - Logo and title
        left_header = tk.Frame(header, bg=self.bg_secondary)
        left_header.pack(side=tk.LEFT, padx=12, pady=8)
        
        title_container = tk.Frame(left_header, bg=self.bg_secondary)
        title_container.pack(side=tk.LEFT)
        
        tk.Label(title_container, text="⚡ Agent J", 
                bg=self.bg_secondary, fg=self.accent_orange,
                font=(self.font_family, 11, "bold")).pack(side=tk.LEFT)
        
        tk.Label(title_container, text="  Trading Bot", 
                bg=self.bg_secondary, fg=self.text_secondary,
                font=(self.font_family, 11)).pack(side=tk.LEFT)
        
        # Center - Mode selector
        center_header = tk.Frame(header, bg=self.bg_secondary)
        center_header.pack(side=tk.LEFT, expand=True)
        
        mode_frame = tk.Frame(center_header, bg=self.bg_card, relief=tk.FLAT, bd=1)
        mode_frame.pack()
        
        self.mode_var = tk.StringVar(value="client")
        
        self.client_btn = tk.Button(mode_frame, text="Client", 
                                    command=lambda: self._set_mode("client"),
                                    bg=self.accent_orange, fg="white",
                                    font=(self.font_family, 8, "bold"),
                                    relief=tk.FLAT, padx=15, pady=4,
                                    cursor="hand2", borderwidth=0,
                                    activebackground="#d14010")
        self.client_btn.pack(side=tk.LEFT)
        
        self.master_btn = tk.Button(mode_frame, text="Master", 
                                    command=lambda: self._set_mode("master"),
                                    bg=self.bg_card, fg=self.text_secondary,
                                    font=(self.font_family, 8),
                                    relief=tk.FLAT, padx=15, pady=4,
                                    cursor="hand2", borderwidth=0,
                                    activebackground=self.bg_secondary)
        self.master_btn.pack(side=tk.LEFT)
        
        # Right side - Controls and status
        right_header = tk.Frame(header, bg=self.bg_secondary)
        right_header.pack(side=tk.RIGHT, padx=12, pady=8)
        
        # Status indicators
        status_frame = tk.Frame(right_header, bg=self.bg_secondary)
        status_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        conn_row = tk.Frame(status_frame, bg=self.bg_secondary)
        conn_row.pack()
        
        self.mt5_status = tk.Label(conn_row, text="● MT5", 
                                  bg=self.bg_secondary, fg=self.text_secondary,
                                  font=(self.font_family, 7))
        self.mt5_status.pack(side=tk.LEFT, padx=3)
        
        self.discord_status = tk.Label(conn_row, text="● Discord", 
                                      bg=self.bg_secondary, fg=self.text_secondary,
                                      font=(self.font_family, 7))
        self.discord_status.pack(side=tk.LEFT, padx=3)
        
        # Check for Updates button (hidden by default, shown only in Settings tab)
        self.update_btn = tk.Button(right_header, text="🔄 Check for Updates", 
                                    command=self._check_for_updates,
                                    bg=self.accent_blue, fg="white",
                                    font=(self.font_family, 8, "bold"),
                                    relief=tk.FLAT, padx=15, pady=4,
                                    cursor="hand2", borderwidth=0,
                                    activebackground="#0066cc")
        # Don't pack it yet - will be shown/hidden based on tab selection
        
        # Start/Stop button
        self.start_btn = tk.Button(right_header, text="▶ Start", 
                                   command=self._toggle_bot,
                                   bg=self.accent_green, fg="white",
                                   font=(self.font_family, 8, "bold"),
                                   relief=tk.FLAT, padx=15, pady=4,
                                   cursor="hand2", borderwidth=0,
                                   activebackground="#5f8c00")
        self.start_btn.pack(side=tk.LEFT)
        
        # Status label
        self.status_label = tk.Label(right_header, text="● Offline", 
                                     bg=self.bg_secondary, fg=self.text_secondary,
                                     font=(self.font_family, 8, "bold"),
                                     padx=8)
        self.status_label.pack(side=tk.LEFT)
        
        # Main content area
        content = tk.Frame(self.root, bg=self.bg_primary)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Notebook (tabs)
        notebook = ttk.Notebook(content)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Store notebook reference
        self.notebook = notebook
        
        # Create tabs
        self.dashboard_tab = DashboardTab(notebook, self)
        self.positions_tab = PositionsTab(notebook, self)
        self.logs_tab = LogsTab(notebook, self)
        self.settings_tab = SettingsTab(notebook, self, self.config)
        
        notebook.add(self.dashboard_tab.frame, text="Dashboard")
        notebook.add(self.positions_tab.frame, text="Positions")
        notebook.add(self.logs_tab.frame, text="Logs")
        notebook.add(self.settings_tab.frame, text="Settings")
        
        # Bind tab change event to show/hide update button
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _set_mode(self, mode):
        """Set trading mode"""
        # Check if trying to switch to master mode
        if mode == "master" and not self.master_mode_unlocked:
            if self._check_master_password():
                self.master_mode_unlocked = True
            else:
                return  # Don't switch mode if password check failed
        
        self.mode_var.set(mode)
        if mode == "client":
            self.client_btn.config(bg=self.accent_orange, fg="white", font=(self.font_family, 10, "bold"))
            self.master_btn.config(bg=self.bg_card, fg=self.text_secondary, font=(self.font_family, 10))
        else:
            self.master_btn.config(bg=self.accent_orange, fg="white", font=(self.font_family, 10, "bold"))
            self.client_btn.config(bg=self.bg_card, fg=self.text_secondary, font=(self.font_family, 10))
    
    def _check_master_password(self):
        """Show password dialog and verify master mode password"""
        # Create password dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Master Mode")
        dialog.geometry("350x150")
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_primary)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Track attempts
        attempts = [0]  # Use list to modify in nested function
        max_attempts = 3
        result = [False]  # Store result
        
        # Title
        tk.Label(dialog, text="🔐 Enter Master Password", 
                bg=self.bg_primary, fg=self.text_primary,
                font=(self.font_family, 10, "bold")).pack(pady=(15, 10))
        
        # Password entry
        password_entry = tk.Entry(dialog, 
                                 bg=self.bg_secondary, fg=self.text_primary,
                                 font=(self.font_family, 9),
                                 relief=tk.FLAT, insertbackground=self.text_primary,
                                 width=28, show="*")
        password_entry.pack(padx=20, pady=5)
        password_entry.focus()
        
        # Error label
        error_label = tk.Label(dialog, text="", 
                              bg=self.bg_primary, fg=self.accent_red,
                              font=(self.font_family, 8))
        error_label.pack(pady=2)
        
        def verify_password():
            entered = password_entry.get()
            entered_hash = hashlib.sha256(entered.encode()).hexdigest()
            
            if entered_hash == self.master_password_hash:
                result[0] = True
                dialog.destroy()
            else:
                attempts[0] += 1
                remaining = max_attempts - attempts[0]
                
                if remaining > 0:
                    error_label.config(text=f"Incorrect. {remaining} attempt(s) left.")
                    password_entry.delete(0, tk.END)
                    password_entry.focus()
                else:
                    messagebox.showerror("Access Denied", "Maximum attempts exceeded.")
                    dialog.destroy()
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_primary)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Cancel", 
                 command=dialog.destroy,
                 bg=self.bg_secondary, fg=self.text_primary,
                 font=(self.font_family, 8),
                 relief=tk.FLAT, padx=15, pady=4,
                 cursor="hand2", borderwidth=0).pack(side=tk.LEFT, padx=3)
        
        tk.Button(btn_frame, text="Submit", 
                 command=verify_password,
                 bg=self.accent_green, fg="white",
                 font=(self.font_family, 8, "bold"),
                 relief=tk.FLAT, padx=15, pady=4,
                 cursor="hand2", borderwidth=0).pack(side=tk.LEFT, padx=3)
        
        # Bind Enter key
        password_entry.bind('<Return>', lambda e: verify_password())
        
        # Wait for dialog to close
        self.root.wait_window(dialog)
        
        return result[0]
    
    def _on_tab_changed(self, event):
        """Handle tab change event to show/hide update button"""
        current_tab = self.notebook.index(self.notebook.select())
        
        # Show update button only on Settings tab (index 3)
        if current_tab == 3:
            self.update_btn.pack(side=tk.LEFT, padx=(0, 10))
        else:
            self.update_btn.pack_forget()
    
    def _check_for_updates(self):
        """Delegate update check to settings tab"""
        self.settings_tab._check_for_updates()
    
    def _toggle_bot(self):
        """Start or stop the bot"""
        if not self.running:
            self._start_bot()
        else:
            self._stop_bot()
    
    def _start_bot(self):
        """Start the trading bot"""
        try:
            mode = self.mode_var.get()
            
            # Validate config
            if mode == "client":
                if not self.config.discord_token:
                    messagebox.showerror("Error", "Discord token not configured")
                    return
                if not self.config.discord_channel_id:
                    messagebox.showerror("Error", "Discord channel ID not configured")
                    return
            
            # Create bot instance
            self.bot = TradingBot(self.config, mode=mode)
            
            # Start bot in separate thread
            self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
            self.bot_thread.start()
            
            # Update UI
            self.running = True
            self.start_btn.config(text="⏹ Stop", bg=self.accent_red, activebackground="#9f0f22")
            self.status_label.config(text="● Online", fg=self.accent_green)
            
            # Disable mode selection buttons
            self.client_btn.config(state=tk.DISABLED, cursor="arrow")
            self.master_btn.config(state=tk.DISABLED, cursor="arrow")
            
            logging.info(f"Bot started in {mode.upper()} mode")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start bot:\n{str(e)}")
            logging.error(f"Failed to start bot: {e}")
    
    def _stop_bot(self):
        """Stop the trading bot"""
        try:
            if self.bot:
                self.bot.running = False
            
            # Update UI
            self.running = False
            self.start_btn.config(text="▶ Start", bg=self.accent_green, activebackground="#5f8c00")
            self.status_label.config(text="● Offline", fg=self.text_secondary)
            self.mt5_status.config(text="● MT5", fg=self.text_secondary)
            self.discord_status.config(text="● Discord", fg=self.text_secondary)
            
            # Re-enable mode selection buttons
            self.client_btn.config(state=tk.NORMAL, cursor="hand2")
            self.master_btn.config(state=tk.NORMAL, cursor="hand2")
            
            logging.info("Bot stopped")
            
        except Exception as e:
            logging.error(f"Error stopping bot: {e}")
    
    def _run_bot(self):
        """Run the bot in a separate thread"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Update MT5 status
            self.root.after(0, lambda: self.mt5_status.config(text="● MT5", fg=self.accent_green))
            
            # Start monitoring Discord status
            if self.mode_var.get() in ["client", "master"]:
                self.root.after(100, self._check_discord_status)
            
            # Run the bot
            loop.run_until_complete(self.bot.run())
            
        except Exception as e:
            logging.error(f"Bot error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Bot Error", str(e)))
        finally:
            self.running = False
            self.root.after(0, lambda: self.start_btn.config(text="▶ Start", bg=self.accent_green))
            self.root.after(0, lambda: self.status_label.config(text="● Offline", fg=self.text_secondary))
            # Re-enable mode buttons
            self.root.after(0, lambda: self.client_btn.config(state=tk.NORMAL, cursor="hand2"))
            self.root.after(0, lambda: self.master_btn.config(state=tk.NORMAL, cursor="hand2"))
    
    def _check_discord_status(self):
        """Check if Discord bot is ready and update status"""
        try:
            if self.bot and hasattr(self.bot, 'discord_ready') and self.bot.discord_ready:
                self.discord_status.config(text="● Discord", fg=self.accent_green)
            elif self.running:
                # Keep checking if bot is still running
                self.root.after(100, self._check_discord_status)
        except Exception as e:
            logging.error(f"Error checking Discord status: {e}")
    
    def _process_logs(self):
        """Process log messages from queue"""
        try:
            while True:
                log_msg = self.log_queue.get_nowait()
                self.logs_tab.add_log(log_msg)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self._process_logs)
    
    def _on_closing(self):
        """Handle window close event"""
        if self.running:
            if messagebox.askokcancel("Quit", "Bot is running. Stop and quit?"):
                self._stop_bot()
                self.root.after(500, self.root.destroy)
        else:
            self.root.destroy()
    
    def get_bot(self):
        """Get the bot instance"""
        return self.bot
