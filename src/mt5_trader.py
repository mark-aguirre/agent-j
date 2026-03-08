"""
MT5 Trading Module - Handles all MetaTrader 5 operations
"""
import MetaTrader5 as mt5
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from src.config import TradingConfig, RiskMode
from src.signal_parser import TradingSignal, OrderType

logger = logging.getLogger(__name__)

@dataclass
class TradeResult:
    success: bool
    ticket: Optional[int] = None
    message: str = ""
    lot_size: float = 0.0

class MT5Trader:
    """Handles all MT5 trading operations"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.connected = False
        self.daily_start_balance = 0.0
        self.daily_trade_count = 0
        self.last_daily_reset = datetime.now()
        self.known_orders = set()  # Track known order tickets
        self.order_snapshots = {}  # Track order details for change detection
    
    def connect(self) -> bool:
        """Initialize connection to MT5"""
        try:
            if not mt5.initialize(path=self.config.mt5_path if self.config.mt5_path else None):
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            
            # Login if credentials provided
            if self.config.mt5_login:
                if not mt5.login(
                    self.config.mt5_login,
                    password=self.config.mt5_password,
                    server=self.config.mt5_server
                ):
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    return False
            
            self.connected = True
            self.daily_start_balance = self.get_balance()
            
            # Initialize known orders with existing positions and orders
            self._initialize_known_orders()
            
            logger.info(f"Connected to MT5. Balance: {self.daily_start_balance}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to MT5: {e}")
            return False
    
    def find_symbol(self, base_symbol: str) -> Optional[str]:
        """Find the actual broker symbol (handles suffixes like 'm', '.r', etc.)"""
        try:
            # Try exact match first
            if mt5.symbol_info(base_symbol):
                return base_symbol
            
            # Common broker suffixes - expanded list
            suffixes = ["m", ".m", "M", ".r", ".R", "_m", "-m", ".pro", ".raw", 
                       "c", ".c", "C", ".a", ".b", "_sb", "-sb", ""]
            
            for suffix in suffixes:
                test_symbol = base_symbol + suffix
                if mt5.symbol_info(test_symbol):
                    logger.info(f"Symbol mapped: {base_symbol} -> {test_symbol}")
                    return test_symbol
            
            # Try searching all symbols with fuzzy matching
            symbols = mt5.symbols_get()
            if symbols:
                base_upper = base_symbol.upper()
                
                # First try: exact substring match
                for sym in symbols:
                    if base_upper == sym.name.upper():
                        logger.info(f"Symbol found (exact): {base_symbol} -> {sym.name}")
                        return sym.name
                
                # Second try: starts with base symbol
                for sym in symbols:
                    if sym.name.upper().startswith(base_upper):
                        logger.info(f"Symbol found (prefix): {base_symbol} -> {sym.name}")
                        return sym.name
                
                # Third try: contains base symbol
                for sym in symbols:
                    if base_upper in sym.name.upper():
                        logger.info(f"Symbol found (contains): {base_symbol} -> {sym.name}")
                        return sym.name
            
            return None
        except Exception as e:
            logger.error(f"Error finding symbol {base_symbol}: {e}")
            return None
    
    def disconnect(self):
        """Shutdown MT5 connection"""
        try:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")
        except Exception as e:
            logger.error(f"Error disconnecting from MT5: {e}")
    
    def get_balance(self) -> float:
        """Get account balance"""
        try:
            info = mt5.account_info()
            return info.balance if info else 0.0
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0
    
    def get_equity(self) -> float:
        """Get account equity"""
        try:
            info = mt5.account_info()
            return info.equity if info else 0.0
        except Exception as e:
            logger.error(f"Error getting equity: {e}")
            return 0.0

    def calculate_lot_size(self, symbol: str, sl_price_diff: float) -> float:
        """Calculate lot size based on risk settings
        
        Args:
            symbol: Trading symbol
            sl_price_diff: Stop loss distance in price (e.g., 0.0025 for 25 pips on EURUSD, or 2584 for BTC)
        """
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Symbol {symbol} not found")
            return self.config.min_lot
        
        # Get symbol properties
        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        lot_step = symbol_info.volume_step
        
        lot_size = self.config.fixed_lot
        
        if self.config.risk_mode == RiskMode.FIXED_LOT:
            lot_size = self.config.fixed_lot
            
        elif self.config.risk_mode == RiskMode.RISK_PERCENT:
            account_value = self.get_equity()
            risk_amount = account_value * (self.config.risk_percent / 100.0)
            
            if sl_price_diff > 0 and tick_size > 0 and tick_value > 0:
                # Calculate how many ticks in the SL
                ticks_in_sl = sl_price_diff / tick_size
                # Risk per 1 lot = ticks * tick_value
                risk_per_lot = ticks_in_sl * tick_value
                
                if risk_per_lot > 0:
                    lot_size = risk_amount / risk_per_lot
                    logger.info(f"Risk calc: Equity=${account_value:.2f}, Risk={self.config.risk_percent}%, "
                               f"Amount=${risk_amount:.2f}, SL_diff={sl_price_diff}, Lot={lot_size:.4f}")
                    
        elif self.config.risk_mode == RiskMode.FIXED_MONEY:
            if sl_price_diff > 0 and tick_size > 0 and tick_value > 0:
                ticks_in_sl = sl_price_diff / tick_size
                risk_per_lot = ticks_in_sl * tick_value
                
                if risk_per_lot > 0:
                    lot_size = self.config.fixed_money_risk / risk_per_lot
        
        # Apply limits
        lot_size = max(lot_size, self.config.min_lot)
        lot_size = min(lot_size, self.config.max_lot)
        lot_size = max(lot_size, min_lot)
        lot_size = min(lot_size, max_lot)
        
        # Round to lot step
        lot_size = int(lot_size / lot_step) * lot_step
        lot_size = max(lot_size, min_lot)
        
        return round(lot_size, 2)
    
    def check_spread(self, symbol: str) -> bool:
        """Check if spread is acceptable"""
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False
        
        symbol_info = mt5.symbol_info(symbol)
        spread = int((tick.ask - tick.bid) / symbol_info.point)
        
        # Determine max spread based on instrument type
        symbol_upper = symbol.upper()
        
        if any(crypto in symbol_upper for crypto in ["BTC", "ETH", "XRP", "ADA", "SOL", "DOT", "BNB", "DOGE", "MATIC", "AVAX", "LINK"]):
            max_spread = self.config.max_spread_crypto
        elif any(metal in symbol_upper for metal in ["XAU", "GOLD", "XAG", "SILVER"]):
            max_spread = self.config.max_spread_gold
        elif any(index in symbol_upper for index in ["US30", "NAS", "SPX", "US100", "DJ30", "SP500"]):
            max_spread = self.config.max_spread_indices
        else:
            # Default to forex spread for unknown symbols
            max_spread = self.config.max_spread_forex
        
        if spread > max_spread:
            logger.warning(f"Spread too high for {symbol}: {spread} points (max: {max_spread})")
            return False
        return True
    
    def count_open_positions(self, symbol: str = None) -> int:
        """Count open positions"""
        positions = mt5.positions_get()
        if not positions:
            return 0
        
        count = 0
        for pos in positions:
            if pos.magic == self.config.magic_number:
                if symbol is None or pos.symbol == symbol:
                    count += 1
        return count
    
    def check_daily_limits(self) -> bool:
        """Check if daily limits are exceeded"""
        # Reset daily counters if new day
        now = datetime.now()
        if now.date() != self.last_daily_reset.date():
            self.daily_start_balance = self.get_balance()
            self.daily_trade_count = 0
            self.last_daily_reset = now
            logger.info("Daily counters reset")
        
        if not self.config.use_daily_limits:
            return True
        
        # Check daily trade count
        if self.daily_trade_count >= self.config.max_daily_trades:
            logger.warning("Daily trade limit reached")
            return False
        
        # Check daily P/L
        current_balance = self.get_balance()
        daily_pnl_percent = ((current_balance - self.daily_start_balance) / self.daily_start_balance) * 100
        
        if daily_pnl_percent <= -self.config.max_daily_loss_percent:
            logger.warning(f"Daily loss limit reached: {daily_pnl_percent:.2f}%")
            return False
        
        if daily_pnl_percent >= self.config.max_daily_profit_percent:
            logger.warning(f"Daily profit target reached: {daily_pnl_percent:.2f}%")
            return False
        
        return True
    
    def is_trading_allowed(self, symbol: str) -> tuple[bool, str]:
        """Check if trading is allowed"""
        if not self.connected:
            return False, "Not connected to MT5"
        
        if not self.check_spread(symbol):
            return False, "Spread too high"
        
        if self.count_open_positions() >= self.config.max_open_trades:
            return False, "Max open trades reached"
        
        if not self.check_daily_limits():
            return False, "Daily limits exceeded"
        
        return True, "OK"

    def execute_signal(self, signal: TradingSignal) -> TradeResult:
        """Execute a trading signal"""
        try:
            # Find the actual broker symbol
            symbol = self.find_symbol(signal.symbol)
            if not symbol:
                return TradeResult(success=False, message=f"Symbol {signal.symbol} not found on broker")
            
            # Check if trading is allowed
            allowed, reason = self.is_trading_allowed(symbol)
            if not allowed:
                return TradeResult(success=False, message=reason)
            
            # Enable symbol if needed
            if not mt5.symbol_select(symbol, True):
                return TradeResult(success=False, message=f"Failed to select symbol {symbol}")
            
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return TradeResult(success=False, message=f"Symbol {symbol} not found")
            
            # Calculate lot size using actual price difference (not pips)
            sl_price_diff = abs(signal.entry_price - signal.stop_loss)
            lot_size = self.calculate_lot_size(symbol, sl_price_diff)
            
            # Get current prices
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return TradeResult(success=False, message="Failed to get price")
            
            # Determine order type and price
            order_type_map = {
                OrderType.BUY: mt5.ORDER_TYPE_BUY,
                OrderType.SELL: mt5.ORDER_TYPE_SELL,
                OrderType.BUY_LIMIT: mt5.ORDER_TYPE_BUY_LIMIT,
                OrderType.SELL_LIMIT: mt5.ORDER_TYPE_SELL_LIMIT,
                OrderType.BUY_STOP: mt5.ORDER_TYPE_BUY_STOP,
                OrderType.SELL_STOP: mt5.ORDER_TYPE_SELL_STOP,
            }
            
            mt5_order_type = order_type_map.get(signal.order_type)
            
            # Set price based on order type
            if signal.order_type in [OrderType.BUY]:
                price = tick.ask
            elif signal.order_type in [OrderType.SELL]:
                price = tick.bid
            else:
                price = signal.entry_price
            
            # Normalize prices
            digits = symbol_info.digits
            price = round(price, digits)
            sl = round(signal.stop_loss, digits)
            tp = round(signal.take_profit, digits)
            
            # Prepare request
            request = {
                "action": mt5.TRADE_ACTION_DEAL if signal.order_type in [OrderType.BUY, OrderType.SELL] else mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5_order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": self.config.max_slippage_points,
                "magic": self.config.magic_number,
                "comment": self.config.trade_comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result is None:
                return TradeResult(success=False, message=f"Order failed: {mt5.last_error()}")
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return TradeResult(
                    success=False, 
                    message=f"Order failed: {result.comment} (code: {result.retcode})"
                )
            
            self.daily_trade_count += 1
            
            logger.info(f"Trade executed: {signal.order_type.value} {symbol} | Lot: {lot_size} | SL: {sl_price_diff}")
            
            return TradeResult(
                success=True,
                ticket=result.order,
                message=f"Order placed successfully",
                lot_size=lot_size
            )
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return TradeResult(success=False, message=f"Error executing signal: {e}")
    
    def manage_positions(self):
        """Manage open positions - trailing stop and break-even"""
        try:
            positions = mt5.positions_get()
            if not positions:
                return
            
            for pos in positions:
                try:
                    # Manage ALL positions regardless of magic number
                    symbol_info = mt5.symbol_info(pos.symbol)
                    if not symbol_info:
                        continue
                    
                    tick = mt5.symbol_info_tick(pos.symbol)
                    if not tick:
                        continue
                    
                    point = symbol_info.point
                    digits = symbol_info.digits
                    pip_value = point * 10 if digits in [3, 5] else point
                    
                    # Calculate profit in pips
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        current_price = tick.bid
                        profit_pips = (current_price - pos.price_open) / pip_value
                    else:
                        current_price = tick.ask
                        profit_pips = (pos.price_open - current_price) / pip_value
                    
                    new_sl = None
                    
                    # Break-Even
                    if self.config.use_break_even and profit_pips >= self.config.break_even_at_pips:
                        if pos.type == mt5.POSITION_TYPE_BUY:
                            be_sl = pos.price_open + (self.config.break_even_offset_pips * pip_value)
                            if pos.sl < pos.price_open and be_sl > pos.sl:
                                new_sl = be_sl
                        else:
                            be_sl = pos.price_open - (self.config.break_even_offset_pips * pip_value)
                            if (pos.sl > pos.price_open or pos.sl == 0) and be_sl < pos.sl:
                                new_sl = be_sl
                    
                    # Trailing Stop
                    if self.config.use_trailing_stop and profit_pips >= self.config.trailing_start_pips:
                        if pos.type == mt5.POSITION_TYPE_BUY:
                            trail_sl = current_price - (self.config.trailing_step_pips * pip_value)
                            if trail_sl > pos.sl:
                                new_sl = trail_sl
                        else:
                            trail_sl = current_price + (self.config.trailing_step_pips * pip_value)
                            if trail_sl < pos.sl or pos.sl == 0:
                                new_sl = trail_sl
                    
                    # Modify position if needed
                    if new_sl:
                        new_sl = round(new_sl, digits)
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": new_sl,
                            "tp": pos.tp,
                        }
                        result = mt5.order_send(request)
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"SL updated for {pos.ticket}: {new_sl}")
                except Exception as e:
                    logger.error(f"Error managing position {pos.ticket}: {e}")
        except Exception as e:
            logger.error(f"Error in manage_positions: {e}")
    
    def close_all_positions(self) -> int:
        """Close all positions with our magic number"""
        try:
            positions = mt5.positions_get()
            if not positions:
                return 0
            
            closed = 0
            for pos in positions:
                try:
                    if pos.magic != self.config.magic_number:
                        continue
                    
                    tick = mt5.symbol_info_tick(pos.symbol)
                    if not tick:
                        continue
                    
                    price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": pos.ticket,
                        "symbol": pos.symbol,
                        "volume": pos.volume,
                        "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "price": price,
                        "deviation": self.config.max_slippage_points,
                        "magic": self.config.magic_number,
                        "comment": "Close all",
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    
                    result = mt5.order_send(request)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        closed += 1
                        logger.info(f"Closed position {pos.ticket}")
                except Exception as e:
                    logger.error(f"Error closing position {pos.ticket}: {e}")
            
            return closed
        except Exception as e:
            logger.error(f"Error in close_all_positions: {e}")
            return 0
    def close_position(self, ticket: int) -> bool:
        """Close a specific position by ticket number (works with any magic number)"""
        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                logger.error(f"Position {ticket} not found")
                return False

            pos = positions[0]

            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                logger.error(f"Failed to get tick data for {pos.symbol}")
                return False

            price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "price": price,
                "deviation": self.config.max_slippage_points,
                "magic": pos.magic,  # Use the position's magic number
                "comment": "Manual close",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Successfully closed position {ticket}")
                return True
            else:
                error_msg = f"retcode={result.retcode}" if result else "No result"
                logger.error(f"Failed to close position {ticket}: {error_msg}")
                return False
        except Exception as e:
            logger.error(f"Error closing position {ticket}: {e}")
            return False

    def cancel_order(self, ticket: int) -> bool:
        """Cancel a specific pending order by ticket number (works with any magic number)"""
        try:
            orders = mt5.orders_get(ticket=ticket)
            if not orders:
                logger.error(f"Order {ticket} not found")
                return False

            order = orders[0]

            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order.ticket,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Successfully cancelled order {ticket}")
                return True
            else:
                error_msg = f"retcode={result.retcode}" if result else "No result"
                logger.error(f"Failed to cancel order {ticket}: {error_msg}")
                return False
        except Exception as e:
            logger.error(f"Error cancelling order {ticket}: {e}")
            return False
    
    def modify_order(self, ticket: int, entry: Optional[float] = None, 
                     sl: Optional[float] = None, tp: Optional[float] = None) -> bool:
        """Modify an existing position or pending order"""
        try:
            # First check if it's a position
            positions = mt5.positions_get(ticket=ticket)
            if positions:
                pos = positions[0]
                symbol_info = mt5.symbol_info(pos.symbol)
                if not symbol_info:
                    logger.error(f"Symbol {pos.symbol} not found")
                    return False
                
                digits = symbol_info.digits
                
                # For positions, we can only modify SL and TP
                new_sl = round(sl, digits) if sl is not None else pos.sl
                new_tp = round(tp, digits) if tp is not None else pos.tp
                
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "sl": new_sl,
                    "tp": new_tp,
                }
                
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"✓ Position {ticket} modified: SL={new_sl}, TP={new_tp}")
                    return True
                else:
                    error_msg = f"retcode={result.retcode}" if result else "No result"
                    logger.error(f"Failed to modify position {ticket}: {error_msg}")
                    return False
            
            # Check if it's a pending order
            orders = mt5.orders_get(ticket=ticket)
            if orders:
                order = orders[0]
                symbol_info = mt5.symbol_info(order.symbol)
                if not symbol_info:
                    logger.error(f"Symbol {order.symbol} not found")
                    return False
                
                digits = symbol_info.digits
                
                # For pending orders, we can modify entry, SL, and TP
                new_entry = round(entry, digits) if entry is not None else order.price_open
                new_sl = round(sl, digits) if sl is not None else order.sl
                new_tp = round(tp, digits) if tp is not None else order.tp
                
                request = {
                    "action": mt5.TRADE_ACTION_MODIFY,
                    "order": order.ticket,
                    "price": new_entry,
                    "sl": new_sl,
                    "tp": new_tp,
                    "type_time": mt5.ORDER_TIME_GTC,
                }
                
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"✓ Order {ticket} modified: Entry={new_entry}, SL={new_sl}, TP={new_tp}")
                    return True
                else:
                    error_msg = f"retcode={result.retcode}" if result else "No result"
                    logger.error(f"Failed to modify order {ticket}: {error_msg}")
                    return False
            
            logger.error(f"Order/Position {ticket} not found")
            return False
            
        except Exception as e:
            logger.error(f"Error modifying order {ticket}: {e}")
            return False
    
    def find_order_by_symbol(self, symbol: str, order_type: str = None) -> Optional[int]:
        """Find an order ticket by symbol and optionally order type"""
        try:
            # Map the symbol to broker format
            broker_symbol = self.find_symbol(symbol)
            if not broker_symbol:
                logger.warning(f"Symbol {symbol} not found on broker")
                return None
            
            # Check positions first
            positions = mt5.positions_get(symbol=broker_symbol)
            if positions:
                for pos in positions:
                    if pos.magic == self.config.magic_number:
                        pos_type = 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'
                        if order_type is None or pos_type == order_type:
                            logger.info(f"Found position {pos.ticket} for {symbol}")
                            return pos.ticket
            
            # Check pending orders
            orders = mt5.orders_get(symbol=broker_symbol)
            if orders:
                for order in orders:
                    if order.magic == self.config.magic_number:
                        order_type_map = {
                            mt5.ORDER_TYPE_BUY_LIMIT: 'BUY LIMIT',
                            mt5.ORDER_TYPE_SELL_LIMIT: 'SELL LIMIT',
                            mt5.ORDER_TYPE_BUY_STOP: 'BUY STOP',
                            mt5.ORDER_TYPE_SELL_STOP: 'SELL STOP',
                        }
                        ord_type = order_type_map.get(order.type, 'UNKNOWN')
                        if order_type is None or ord_type == order_type:
                            logger.info(f"Found pending order {order.ticket} for {symbol}")
                            return order.ticket
            
            logger.warning(f"No order found for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding order by symbol: {e}")
            return None

    
    def _initialize_known_orders(self):
        """Initialize the set of known orders from existing positions and pending orders"""
        try:
            # Add existing positions
            positions = mt5.positions_get()
            if positions:
                for pos in positions:
                    self.known_orders.add(pos.ticket)
                    # Store snapshot for change detection
                    self.order_snapshots[pos.ticket] = {
                        'price': pos.price_open,
                        'sl': pos.sl,
                        'tp': pos.tp,
                        'volume': pos.volume
                    }
            
            # Add pending orders
            orders = mt5.orders_get()
            if orders:
                for order in orders:
                    self.known_orders.add(order.ticket)
                    # Store snapshot for change detection
                    self.order_snapshots[order.ticket] = {
                        'price': order.price_open,
                        'sl': order.sl,
                        'tp': order.tp,
                        'volume': order.volume_initial
                    }
            
            logger.info(f"Initialized with {len(self.known_orders)} known orders")
        except Exception as e:
            logger.error(f"Error initializing known orders: {e}")
    
    def check_for_new_orders(self) -> List[Dict]:
        """Check for new orders created in MT5 and return their info"""
        new_orders = []
        
        try:
            # Check positions
            positions = mt5.positions_get()
            if positions:
                for pos in positions:
                    if pos.ticket not in self.known_orders:
                        self.known_orders.add(pos.ticket)
                        
                        # Store snapshot
                        self.order_snapshots[pos.ticket] = {
                            'price': pos.price_open,
                            'sl': pos.sl,
                            'tp': pos.tp,
                            'volume': pos.volume
                        }
                        
                        order_info = {
                            'ticket': pos.ticket,
                            'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                            'symbol': pos.symbol,
                            'volume': pos.volume,
                            'price': pos.price_open,
                            'sl': pos.sl,
                            'tp': pos.tp,
                            'time': datetime.fromtimestamp(pos.time).strftime('%Y-%m-%d %H:%M:%S'),
                            'profit': pos.profit,
                            'comment': pos.comment
                        }
                        new_orders.append(order_info)
                        logger.info(f"New position detected: {pos.ticket} - {pos.symbol}")
            
            # Check pending orders
            orders = mt5.orders_get()
            if orders:
                for order in orders:
                    if order.ticket not in self.known_orders:
                        self.known_orders.add(order.ticket)
                        
                        # Store snapshot
                        self.order_snapshots[order.ticket] = {
                            'price': order.price_open,
                            'sl': order.sl,
                            'tp': order.tp,
                            'volume': order.volume_initial
                        }
                        
                        order_type_map = {
                            mt5.ORDER_TYPE_BUY_LIMIT: 'BUY LIMIT',
                            mt5.ORDER_TYPE_SELL_LIMIT: 'SELL LIMIT',
                            mt5.ORDER_TYPE_BUY_STOP: 'BUY STOP',
                            mt5.ORDER_TYPE_SELL_STOP: 'SELL STOP',
                            mt5.ORDER_TYPE_BUY_STOP_LIMIT: 'BUY STOP LIMIT',
                            mt5.ORDER_TYPE_SELL_STOP_LIMIT: 'SELL STOP LIMIT',
                        }
                        
                        order_info = {
                            'ticket': order.ticket,
                            'type': order_type_map.get(order.type, 'UNKNOWN'),
                            'symbol': order.symbol,
                            'volume': order.volume_initial,
                            'price': order.price_open,
                            'sl': order.sl,
                            'tp': order.tp,
                            'time': datetime.fromtimestamp(order.time_setup).strftime('%Y-%m-%d %H:%M:%S'),
                            'profit': 0.0,
                            'comment': order.comment
                        }
                        new_orders.append(order_info)
                        logger.info(f"New pending order detected: {order.ticket} - {order.symbol}")
            
        except Exception as e:
            logger.error(f"Error checking for new orders: {e}")
        
        return new_orders
    
    def check_for_order_modifications(self) -> List[Dict]:
        """Check for modifications to existing orders (entry, SL, TP changes)"""
        modified_orders = []
        
        try:
            # Check positions for modifications
            positions = mt5.positions_get()
            if positions:
                for pos in positions:
                    if pos.ticket in self.order_snapshots:
                        snapshot = self.order_snapshots[pos.ticket]
                        changes = []
                        
                        # Check for SL change
                        if abs(pos.sl - snapshot['sl']) > 0.00001:
                            changes.append(f"SL: {snapshot['sl']} → {pos.sl}")
                            snapshot['sl'] = pos.sl
                        
                        # Check for TP change
                        if abs(pos.tp - snapshot['tp']) > 0.00001:
                            changes.append(f"TP: {snapshot['tp']} → {pos.tp}")
                            snapshot['tp'] = pos.tp
                        
                        # Check for volume change (partial close)
                        if abs(pos.volume - snapshot['volume']) > 0.00001:
                            changes.append(f"Volume: {snapshot['volume']} → {pos.volume}")
                            snapshot['volume'] = pos.volume
                        
                        if changes:
                            order_info = {
                                'ticket': pos.ticket,
                                'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                                'symbol': pos.symbol,
                                'volume': pos.volume,
                                'price': pos.price_open,
                                'sl': pos.sl,
                                'tp': pos.tp,
                                'changes': changes,
                                'is_modification': True
                            }
                            modified_orders.append(order_info)
                            logger.info(f"Position modified: {pos.ticket} - {', '.join(changes)}")
            
            # Check pending orders for modifications
            orders = mt5.orders_get()
            if orders:
                for order in orders:
                    if order.ticket in self.order_snapshots:
                        snapshot = self.order_snapshots[order.ticket]
                        changes = []
                        
                        # Check for entry price change
                        if abs(order.price_open - snapshot['price']) > 0.00001:
                            changes.append(f"Entry: {snapshot['price']} → {order.price_open}")
                            snapshot['price'] = order.price_open
                        
                        # Check for SL change
                        if abs(order.sl - snapshot['sl']) > 0.00001:
                            changes.append(f"SL: {snapshot['sl']} → {order.sl}")
                            snapshot['sl'] = order.sl
                        
                        # Check for TP change
                        if abs(order.tp - snapshot['tp']) > 0.00001:
                            changes.append(f"TP: {snapshot['tp']} → {order.tp}")
                            snapshot['tp'] = order.tp
                        
                        # Check for volume change
                        if abs(order.volume_initial - snapshot['volume']) > 0.00001:
                            changes.append(f"Volume: {snapshot['volume']} → {order.volume_initial}")
                            snapshot['volume'] = order.volume_initial
                        
                        if changes:
                            order_type_map = {
                                mt5.ORDER_TYPE_BUY_LIMIT: 'BUY LIMIT',
                                mt5.ORDER_TYPE_SELL_LIMIT: 'SELL LIMIT',
                                mt5.ORDER_TYPE_BUY_STOP: 'BUY STOP',
                                mt5.ORDER_TYPE_SELL_STOP: 'SELL STOP',
                                mt5.ORDER_TYPE_BUY_STOP_LIMIT: 'BUY STOP LIMIT',
                                mt5.ORDER_TYPE_SELL_STOP_LIMIT: 'SELL STOP LIMIT',
                            }
                            
                            order_info = {
                                'ticket': order.ticket,
                                'type': order_type_map.get(order.type, 'UNKNOWN'),
                                'symbol': order.symbol,
                                'volume': order.volume_initial,
                                'price': order.price_open,
                                'sl': order.sl,
                                'tp': order.tp,
                                'changes': changes,
                                'is_modification': True
                            }
                            modified_orders.append(order_info)
                            logger.info(f"Pending order modified: {order.ticket} - {', '.join(changes)}")
            
            # Clean up snapshots for closed/cancelled orders
            current_tickets = set()
            if positions:
                current_tickets.update(pos.ticket for pos in positions)
            if orders:
                current_tickets.update(order.ticket for order in orders)
            
            closed_tickets = set(self.order_snapshots.keys()) - current_tickets
            for ticket in closed_tickets:
                del self.order_snapshots[ticket]
                if ticket in self.known_orders:
                    self.known_orders.remove(ticket)
                logger.info(f"Order {ticket} closed/cancelled, removed from tracking")
        
        except Exception as e:
            logger.error(f"Error checking for order modifications: {e}")
        
        return modified_orders
