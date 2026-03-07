"""
Logs Tab - Real-time log viewer
"""
import tkinter as tk
from tkinter import ttk, scrolledtext

class LogsTab:
    """Logs tab showing real-time logs"""
    
    def __init__(self, parent, main_window):
        self.main_window = main_window
        self.frame = tk.Frame(parent, bg=main_window.bg_primary)
        self._create_ui()
    
    def _create_ui(self):
        """Create logs UI"""
        container = tk.Frame(self.frame, bg=self.main_window.bg_primary)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Toolbar
        toolbar = tk.Frame(container, bg=self.main_window.bg_primary)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        
        tk.Button(toolbar, text="✕ Clear Logs", command=self._clear_logs,
                 bg=self.main_window.bg_card, fg=self.main_window.text_primary,
                 font=("Segoe UI", 8), relief=tk.FLAT, padx=12, pady=4,
                 cursor="hand2", borderwidth=0).pack(side=tk.LEFT, padx=(0, 8))
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        check_frame = tk.Frame(toolbar, bg=self.main_window.bg_primary)
        check_frame.pack(side=tk.LEFT)
        
        tk.Checkbutton(check_frame, text="Auto-scroll", variable=self.auto_scroll_var,
                      bg=self.main_window.bg_primary, fg=self.main_window.text_primary,
                      selectcolor=self.main_window.bg_card,
                      activebackground=self.main_window.bg_primary,
                      activeforeground=self.main_window.text_primary,
                      font=("Segoe UI", 8)).pack()
        
        # Log text area
        log_container = tk.Frame(container, bg=self.main_window.bg_card, relief=tk.FLAT)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_container,
            wrap=tk.WORD,
            width=100,
            height=25,
            font=("Consolas", 8),
            bg=self.main_window.bg_card,
            fg=self.main_window.text_primary,
            insertbackground=self.main_window.text_primary,
            relief=tk.FLAT,
            padx=8,
            pady=8
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Configure tags for colored output
        self.log_text.tag_config("INFO", foreground=self.main_window.accent_blue)
        self.log_text.tag_config("WARNING", foreground="#ffa500")
        self.log_text.tag_config("ERROR", foreground=self.main_window.accent_red)
        self.log_text.tag_config("DEBUG", foreground=self.main_window.text_secondary)
    
    def add_log(self, message: str):
        """Add a log message"""
        try:
            # Determine log level
            tag = "INFO"
            if "WARNING" in message:
                tag = "WARNING"
            elif "ERROR" in message:
                tag = "ERROR"
            elif "DEBUG" in message:
                tag = "DEBUG"
            
            # Insert message
            self.log_text.insert(tk.END, message + "\n", tag)
            
            # Auto-scroll if enabled
            if self.auto_scroll_var.get():
                self.log_text.see(tk.END)
            
            # Limit log size (keep last 1000 lines)
            lines = int(self.log_text.index('end-1c').split('.')[0])
            if lines > 1000:
                self.log_text.delete('1.0', '2.0')
        except Exception as e:
            pass
    
    def _clear_logs(self):
        """Clear all logs"""
        self.log_text.delete('1.0', tk.END)
