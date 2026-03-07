"""
Positions Tab - Live position monitoring
"""
import tkinter as tk
from tkinter import ttk
import MetaTrader5 as mt5

class PositionsTab:
    """Positions tab showing open trades"""
    
    def __init__(self, parent, main_window):
        self.main_window = main_window
        self.frame = tk.Frame(parent, bg=main_window.bg_primary)
        self._create_ui()
        self._update_positions()
    
    def _create_ui(self):
        """Create positions UI"""
        container = tk.Frame(self.frame, bg=self.main_window.bg_primary)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Toolbar
        toolbar = tk.Frame(container, bg=self.main_window.bg_primary)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        
        tk.Button(toolbar, text="↻ Refresh", command=self._refresh,
                 bg=self.main_window.bg_card, fg=self.main_window.text_primary,
                 font=("Segoe UI", 8), relief=tk.FLAT, padx=10, pady=4,
                 cursor="hand2", borderwidth=0).pack(side=tk.LEFT, padx=(0, 6))
        
        tk.Button(toolbar, text="✕ Close All", command=self._close_all,
                 bg=self.main_window.accent_red, fg="white",
                 font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=10, pady=4,
                 cursor="hand2", borderwidth=0).pack(side=tk.LEFT)
        
        # Table container
        table_frame = tk.Frame(container, bg=self.main_window.bg_card, relief=tk.FLAT)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Positions table
        columns = ("Ticket", "Symbol", "Type", "Volume", "Price", "SL", "TP", "Profit", "Action")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=18)
        
        # Style the treeview
        style = ttk.Style()
        style.configure("Treeview",
                       background=self.main_window.bg_card,
                       foreground=self.main_window.text_primary,
                       fieldbackground=self.main_window.bg_card,
                       borderwidth=0,
                       rowheight=20,
                       font=("Segoe UI", 8))
        style.configure("Treeview.Heading",
                       background=self.main_window.bg_secondary,
                       foreground=self.main_window.text_primary,
                       borderwidth=0,
                       font=("Segoe UI", 8, "bold"))
        style.map('Treeview', background=[('selected', self.main_window.accent_blue)])
        
        # Configure columns
        for col in columns:
            self.tree.heading(col, text=col)
        
        self.tree.column("Ticket", width=80)
        self.tree.column("Symbol", width=100)
        self.tree.column("Type", width=70)
        self.tree.column("Volume", width=60)
        self.tree.column("Price", width=80)
        self.tree.column("SL", width=80)
        self.tree.column("TP", width=80)
        self.tree.column("Profit", width=90)
        self.tree.column("Action", width=70)
        
        # Bind double-click to close position
        self.tree.bind("<Double-Button-1>", self._on_row_double_click)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _update_positions(self):
        """Update positions table"""
        try:
            bot = self.main_window.get_bot()
            if bot and bot.trader and bot.trader.connected:
                # Clear existing items
                for item in self.tree.get_children():
                    self.tree.delete(item)
                
                # Get open positions
                positions = mt5.positions_get()
                if positions:
                    for pos in positions:
                        pos_type = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                        profit_color = "green" if pos.profit >= 0 else "red"
                        
                        item = self.tree.insert("", tk.END, values=(
                            pos.ticket,
                            pos.symbol,
                            pos_type,
                            f"{pos.volume:.2f}",
                            f"{pos.price_open:.5f}",
                            f"{pos.sl:.5f}" if pos.sl else "-",
                            f"{pos.tp:.5f}" if pos.tp else "-",
                            f"${pos.profit:.2f}",
                            "✕ Close"
                        ), tags=(profit_color, "position"))
                        
                        # Color code profit
                        self.tree.tag_configure("green", foreground=self.main_window.accent_green)
                        self.tree.tag_configure("red", foreground=self.main_window.accent_red)
                
                # Get pending orders
                orders = mt5.orders_get()
                if orders:
                    for order in orders:
                        order_type_map = {
                            mt5.ORDER_TYPE_BUY_LIMIT: 'BUY LIMIT',
                            mt5.ORDER_TYPE_SELL_LIMIT: 'SELL LIMIT',
                            mt5.ORDER_TYPE_BUY_STOP: 'BUY STOP',
                            mt5.ORDER_TYPE_SELL_STOP: 'SELL STOP',
                            mt5.ORDER_TYPE_BUY_STOP_LIMIT: 'BUY STOP LIMIT',
                            mt5.ORDER_TYPE_SELL_STOP_LIMIT: 'SELL STOP LIMIT',
                        }
                        
                        order_type = order_type_map.get(order.type, 'PENDING')
                        
                        self.tree.insert("", tk.END, values=(
                            order.ticket,
                            order.symbol,
                            order_type,
                            f"{order.volume_initial:.2f}",
                            f"{order.price_open:.5f}",
                            f"{order.sl:.5f}" if order.sl else "-",
                            f"{order.tp:.5f}" if order.tp else "-",
                            "Pending",
                            "✕ Cancel"
                        ), tags=("pending", "order"))
                        
                        # Color code pending orders
                        self.tree.tag_configure("pending", foreground=self.main_window.accent_blue)
        except Exception as e:
            pass
        
        # Schedule next update
        self.frame.after(2000, self._update_positions)
    
    def _refresh(self):
        """Manual refresh"""
        self._update_positions()
    
    def _close_all(self):
        """Close all positions"""
        from tkinter import messagebox
        if messagebox.askyesno("Confirm", "Close all open positions?"):
            try:
                bot = self.main_window.get_bot()
                if bot and bot.trader:
                    closed = bot.trader.close_all_positions()
                    messagebox.showinfo("Success", f"Closed {closed} position(s)")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to close positions:\n{str(e)}")
    
    def _on_row_double_click(self, event):
        """Handle double-click on a row to close/cancel position"""
        from tkinter import messagebox
        
        # Get the clicked item
        item = self.tree.identify('item', event.x, event.y)
        if not item:
            return
        
        # Get the column
        column = self.tree.identify_column(event.x)
        
        # Get item values
        values = self.tree.item(item, 'values')
        if not values:
            return
        
        ticket = int(values[0])
        symbol = values[1]
        tags = self.tree.item(item, 'tags')
        
        # Determine if it's a position or pending order
        is_position = "position" in tags
        is_order = "order" in tags
        
        if not is_position and not is_order:
            return
        
        # Confirm action
        action = "close" if is_position else "cancel"
        if not messagebox.askyesno("Confirm", f"Do you want to {action} {symbol} (Ticket: {ticket})?"):
            return
        
        try:
            bot = self.main_window.get_bot()
            if not bot or not bot.trader:
                messagebox.showerror("Error", "Bot not connected")
                return
            
            if is_position:
                # Close position
                success = bot.trader.close_position(ticket)
                if success:
                    messagebox.showinfo("Success", f"Position {ticket} closed successfully")
                    self._refresh()
                else:
                    messagebox.showerror("Error", f"Failed to close position {ticket}")
            else:
                # Cancel pending order
                success = bot.trader.cancel_order(ticket)
                if success:
                    messagebox.showinfo("Success", f"Order {ticket} cancelled successfully")
                    self._refresh()
                else:
                    messagebox.showerror("Error", f"Failed to cancel order {ticket}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to {action}:\n{str(e)}")
