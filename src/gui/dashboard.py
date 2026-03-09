"""
Dashboard Tab - Account overview and statistics
"""
import tkinter as tk

class DashboardTab:
    """Dashboard tab showing account info and stats"""
    
    def __init__(self, parent, main_window):
        self.main_window = main_window
        self.frame = tk.Frame(parent, bg=main_window.bg_primary)
        self._create_ui()
        self._update_data()
    
    def _create_ui(self):
        """Create dashboard UI"""
        container = tk.Frame(self.frame, bg=self.main_window.bg_primary)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top row - Main metrics
        top_row = tk.Frame(container, bg=self.main_window.bg_primary)
        top_row.pack(fill=tk.X, pady=(0, 8))
        
        # Balance
        balance_card = self._create_card(top_row, "Balance", "$0.00", self.main_window.accent_green, large=True)
        balance_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.balance_label = balance_card.winfo_children()[1]
        
        # Equity
        equity_card = self._create_card(top_row, "Equity", "$0.00", self.main_window.text_primary)
        equity_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        self.equity_label = equity_card.winfo_children()[1]
        
        # Daily P/L
        pnl_card = self._create_card(top_row, "Daily P/L", "$0.00", self.main_window.text_secondary)
        pnl_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.pnl_label = pnl_card.winfo_children()[1]
        
        # Stats row
        stats_row = tk.Frame(container, bg=self.main_window.bg_primary)
        stats_row.pack(fill=tk.X, pady=(0, 8))
        
        # Open Positions
        open_card = self._create_card(stats_row, "Open Positions", "0", self.main_window.accent_orange)
        open_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self.open_label = open_card.winfo_children()[1]
        
        # Daily Trades
        trades_card = self._create_card(stats_row, "Daily Trades", "0", self.main_window.accent_blue)
        trades_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.trades_label = trades_card.winfo_children()[1]
        
        # Config section
        config_card = tk.Frame(container, bg=self.main_window.bg_card, relief=tk.FLAT)
        config_card.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(config_card, text="Configuration", 
                bg=self.main_window.bg_card, fg=self.main_window.text_primary,
                font=(self.main_window.font_family, 10, "bold")).pack(anchor=tk.W, padx=12, pady=(10, 8))
        
        config = self.main_window.config
        
        config_items = [
            ("Risk Mode", config.risk_mode.value),
            ("Risk Per Trade", f"{config.risk_percent}%"),
            ("Max Open Trades", str(config.max_open_trades)),
            ("Break-Even", "Enabled" if config.use_break_even else "Disabled"),
            ("Trailing Stop", "Enabled" if config.use_trailing_stop else "Disabled"),
        ]
        
        for label, value in config_items:
            row = tk.Frame(config_card, bg=self.main_window.bg_card)
            row.pack(fill=tk.X, padx=12, pady=3)
            
            tk.Label(row, text=label, 
                    bg=self.main_window.bg_card, fg=self.main_window.text_secondary,
                    font=(self.main_window.font_family, 8)).pack(side=tk.LEFT)
            
            tk.Label(row, text=value, 
                    bg=self.main_window.bg_card, fg=self.main_window.text_primary,
                    font=(self.main_window.font_family, 8, "bold")).pack(side=tk.RIGHT)
        
        tk.Label(config_card, text="", bg=self.main_window.bg_card).pack(pady=6)
    
    def _create_card(self, parent, title, value, color, large=False):
        """Create a metric card"""
        card = tk.Frame(parent, bg=self.main_window.bg_card, relief=tk.FLAT, bd=1, 
                       highlightbackground=self.main_window.border_color, highlightthickness=1)
        height = 70 if large else 60
        card.pack_propagate(False)
        card.configure(height=height)
        
        tk.Label(card, text=title, 
                bg=self.main_window.bg_card, fg=self.main_window.text_secondary,
                font=(self.main_window.font_family, 7)).pack(anchor=tk.W, padx=10, pady=(8, 2))
        
        font_size = 16 if large else 14
        value_label = tk.Label(card, text=value, 
                              bg=self.main_window.bg_card, fg=color,
                              font=(self.main_window.font_family, font_size, "bold"))
        value_label.pack(anchor=tk.W, padx=10, pady=(0, 8))
        
        return card
    
    def _update_data(self):
        """Update dashboard data"""
        try:
            bot = self.main_window.get_bot()
            if bot and bot.trader and bot.trader.connected:
                # Update balance
                balance = bot.trader.get_balance()
                self.balance_label.config(text=f"${balance:,.2f}")
                
                # Update equity
                equity = bot.trader.get_equity()
                self.equity_label.config(text=f"${equity:,.2f}")
                
                # Update daily P/L
                daily_start = bot.trader.daily_start_balance
                if daily_start > 0:
                    pnl = equity - daily_start
                    pnl_percent = (pnl / daily_start) * 100
                    color = self.main_window.accent_green if pnl >= 0 else self.main_window.accent_red
                    
                    # Check if daily goal is enabled and reached
                    goal_text = ""
                    if bot.trader.config.use_daily_goal:
                        goal_percent = bot.trader.config.daily_goal_percent
                        if pnl_percent >= goal_percent:
                            goal_text = " 🎯 GOAL!"
                            color = self.main_window.accent_green
                        elif pnl_percent >= goal_percent * 0.8:  # 80% of goal
                            goal_text = f" (Goal: {goal_percent}%)"
                    
                    self.pnl_label.config(
                        text=f"${pnl:,.2f} ({pnl_percent:+.2f}%){goal_text}",
                        foreground=color
                    )
                
                # Update open positions
                open_count = bot.trader.count_open_positions()
                self.open_label.config(text=str(open_count))
                
                # Update daily trades
                self.trades_label.config(text=str(bot.trader.daily_trade_count))
        except Exception as e:
            pass
        
        # Schedule next update
        self.frame.after(1000, self._update_data)
