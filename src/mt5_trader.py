"""
MT5 Trading Module - Handles all MetaTrader 5 operations
"""
import MetaTrader5 as mt5
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import json
import os
from pathlib import Path

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
        self.auto_modified_tickets = set()  # Track tickets modified by bot (trailing/breakeven)
        self.recent_signals = {}  # Track recent signals to prevent duplicates: {signal_hash: timestamp}
        self.daily_goal_notified = False  # Track if daily goal notification was sent
        
        # Loss recovery tracking
        self.recovery_file = Path("_internal/loss_recovery.json")
        self.cumulative_loss = self._load_cumulative_loss()
    
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
    def _load_cumulative_loss(self) -> float:
        """Load cumulative loss from file"""
        try:
            if self.recovery_file.exists():
                with open(self.recovery_file, 'r') as f:
                    data = json.load(f)
                    loss = data.get('cumulative_loss', 0.0)
                    logger.info(f"Loaded cumulative loss: ${loss:.2f}")
                    return loss
        except Exception as e:
            logger.error(f"Error loading cumulative loss: {e}")
        return 0.0

    def _save_cumulative_loss(self):
        """Save cumulative loss to file"""
        try:
            self.recovery_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.recovery_file, 'w') as f:
                json.dump({
                    'cumulative_loss': self.cumulative_loss,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
            logger.info(f"Saved cumulative loss: ${self.cumulative_loss:.2f}")
        except Exception as e:
            logger.error(f"Error saving cumulative loss: {e}")

    def _update_cumulative_loss(self, profit: float):
        """Update cumulative loss with closed trade profit/loss"""
        if profit < 0:
            # Add to cumulative loss
            self.cumulative_loss += abs(profit)
            logger.info(f"Loss detected: ${profit:.2f}, Cumulative loss now: ${self.cumulative_loss:.2f}")
        elif profit > 0 and self.cumulative_loss > 0:
            # Reduce cumulative loss with profit
            recovered = min(profit, self.cumulative_loss)
            self.cumulative_loss -= recovered
            logger.info(f"Profit ${profit:.2f} recovered ${recovered:.2f}, Remaining loss: ${self.cumulative_loss:.2f}")

        self._save_cumulative_loss()

    def _calculate_recovery_lots(self, symbol: str, base_lot: float) -> float:
        """Calculate additional lot size needed to recover losses at recovery pips
        
        Args:
            symbol: Trading symbol
            base_lot: Base lot size before recovery adjustment
        """
        if not self.config.use_loss_recovery or self.cumulative_loss <= 0:
            return 0.0
        
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 0.0
        
        # Get pip value for 1 lot
        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        
        # Calculate pip size based on symbol type
        # For XAUUSD (Gold): 1 pip = 0.01
        # For Forex pairs with 5 digits: 1 pip = 10 points (0.0001)
        # For Forex pairs with 3 digits (JPY): 1 pip = 10 points (0.01)
        # For standard pairs: 1 pip = point
        point = symbol_info.point
        if "XAU" in symbol or "GOLD" in symbol:
            pip_size = 0.01
        elif symbol_info.digits in [3, 5]:
            pip_size = point * 10
        else:
            pip_size = point
        
        # Calculate how many ticks in recovery pips
        ticks_in_recovery = (self.config.recovery_pips * pip_size) / tick_size
        value_per_lot = ticks_in_recovery * tick_value
        
        if value_per_lot <= 0:
            return 0.0
        
        # Calculate recovery lots needed
        recovery_lots = self.cumulative_loss / value_per_lot
        
        # Round up to 0.01 (2 decimals)
        recovery_lots = round(recovery_lots + 0.005, 2)
        
        # Apply maximum recovery lot limit from config
        if recovery_lots > self.config.max_recovery_lots:
            logger.warning(f"Recovery lots {recovery_lots:.2f} exceeds max limit {self.config.max_recovery_lots:.2f}, capping")
            recovery_lots = self.config.max_recovery_lots
        
        # Calculate total lot size
        total_lots = base_lot + recovery_lots
        
        # Check if we have enough margin for the total lot size
        account_info = mt5.account_info()
        if account_info:
            # Get current price for margin calculation
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                price = tick.ask  # Use ask price for margin calculation
                
                # Calculate required margin
                margin_rate = symbol_info.margin_initial if hasattr(symbol_info, 'margin_initial') else 1.0
                required_margin = total_lots * symbol_info.trade_contract_size * price * margin_rate / account_info.leverage
                
                # Get available margin (free margin)
                free_margin = account_info.margin_free
                
                logger.info(f"Margin check: Required=${required_margin:.2f}, Available=${free_margin:.2f}, "
                           f"Total lots={total_lots:.2f} (Base={base_lot:.2f} + Recovery={recovery_lots:.2f})")
                
                # If not enough margin, reduce recovery lots
                if required_margin > free_margin * 0.9:  # Use 90% of free margin as safety buffer
                    # Calculate maximum affordable recovery lots
                    max_affordable_margin = free_margin * 0.9
                    max_total_lots = (max_affordable_margin * account_info.leverage) / (symbol_info.trade_contract_size * price * margin_rate)
                    max_recovery_lots = max(0, max_total_lots - base_lot)
                    
                    # Apply lot step rounding
                    lot_step = symbol_info.volume_step
                    max_recovery_lots = int(max_recovery_lots / lot_step) * lot_step
                    
                    if max_recovery_lots < recovery_lots:
                        logger.warning(f"Insufficient margin for full recovery. Reducing recovery lots: "
                                     f"{recovery_lots:.2f} -> {max_recovery_lots:.2f}")
                        recovery_lots = max_recovery_lots
        
        logger.info(f"Recovery calculation: Loss=${self.cumulative_loss:.2f}, "
                   f"Recovery target={self.config.recovery_pips} pips, "
                   f"Recovery lots={recovery_lots:.2f}")
        
        return recovery_lots

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
        
        # Apply initial limits to base lot
        lot_size = max(lot_size, self.config.min_lot)
        lot_size = min(lot_size, self.config.max_lot)
        lot_size = max(lot_size, min_lot)
        lot_size = min(lot_size, max_lot)
        
        # Round base lot to lot step
        lot_size = int(lot_size / lot_step) * lot_step
        lot_size = max(lot_size, min_lot)
        
        # Add recovery lots if loss recovery is enabled (pass base lot for margin check)
        recovery_lots = self._calculate_recovery_lots(symbol, lot_size)
        if recovery_lots > 0:
            logger.info(f"Adding recovery lots: {recovery_lots:.2f} to base lot: {lot_size:.2f}")
            lot_size += recovery_lots
            
            # Apply final limits after adding recovery
            lot_size = min(lot_size, self.config.max_lot)
            lot_size = min(lot_size, max_lot)
            
            # Round final lot to lot step
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
            self.daily_goal_notified = False  # Reset notification flag
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
        
        # Check daily goal
        if self.config.use_daily_goal and daily_pnl_percent >= self.config.daily_goal_percent:
            logger.info(f"Daily goal reached: {daily_pnl_percent:.2f}% (Target: {self.config.daily_goal_percent}%)")
            return False
        
        return True
    
    def get_daily_goal_status(self) -> tuple[bool, float, float]:
        """Check if daily goal is reached and return status
        Returns: (goal_reached, current_percent, pnl_amount)
        """
        if not self.config.use_daily_goal or self.daily_start_balance <= 0:
            return False, 0.0, 0.0
        
        current_balance = self.get_balance()
        pnl_amount = current_balance - self.daily_start_balance
        daily_pnl_percent = (pnl_amount / self.daily_start_balance) * 100
        
        goal_reached = daily_pnl_percent >= self.config.daily_goal_percent
        return goal_reached, daily_pnl_percent, pnl_amount
    
    def is_trading_allowed(self, symbol: str, order_type: str = None, entry_price: float = None) -> tuple[bool, str]:
        """Check if trading is allowed"""
        if not self.connected:
            return False, "Not connected to MT5"
        
        if not self.check_spread(symbol):
            return False, "Spread too high"
        
        if self.count_open_positions() >= self.config.max_open_trades:
            return False, "Max open trades reached"
        
        # Check for duplicate order (same symbol, order type, and entry price)
        if order_type and entry_price:
            existing_order = self.find_order_by_symbol_ordertype_and_entry(symbol, order_type, entry_price)
            if existing_order:
                return False, f"Duplicate order exists: {symbol} {order_type} @ {entry_price}"
        
        if not self.check_daily_limits():
            return False, "Daily limits exceeded"
        
        return True, "OK"

    def execute_signal(self, signal: TradingSignal) -> TradeResult:
        """Execute a trading signal"""
        try:
            # Create a hash of the signal to detect duplicates
            signal_hash = f"{signal.symbol}_{signal.order_type.value}_{signal.entry_price}_{signal.stop_loss}_{signal.take_profit}"
            
            # Check if we've seen this exact signal recently (within last 60 seconds)
            current_time = datetime.now()
            if signal_hash in self.recent_signals:
                last_time = self.recent_signals[signal_hash]
                time_diff = (current_time - last_time).total_seconds()
                if time_diff < 60:
                    logger.warning(f"Duplicate signal detected (seen {time_diff:.1f}s ago), skipping: {signal.symbol} {signal.order_type.value}")
                    return TradeResult(success=False, message="Duplicate signal ignored")
            
            # Store this signal
            self.recent_signals[signal_hash] = current_time
            
            # Clean up old signals (older than 5 minutes)
            old_signals = [k for k, v in self.recent_signals.items() if (current_time - v).total_seconds() > 300]
            for old_signal in old_signals:
                del self.recent_signals[old_signal]
            
            # Find the actual broker symbol
            symbol = self.find_symbol(signal.symbol)
            if not symbol:
                return TradeResult(success=False, message=f"Symbol {signal.symbol} not found on broker")
            
            # Check if trading is allowed
            allowed, reason = self.is_trading_allowed(symbol, signal.order_type.value, signal.entry_price)
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
            
            # Send order with automatic lot size reduction on insufficient margin
            max_retries = 10
            retry_count = 0
            
            # Get symbol lot constraints
            lot_step = symbol_info.volume_step
            min_lot = symbol_info.volume_min
            
            while retry_count < max_retries:
                result = mt5.order_send(request)
                
                if result is None:
                    return TradeResult(success=False, message=f"Order failed: {mt5.last_error()}")
                
                # Check if order succeeded
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    self.daily_trade_count += 1
                    logger.info(f"Trade executed: {signal.order_type.value} {symbol} | Lot: {lot_size} | SL: {sl_price_diff}")
                    return TradeResult(
                        success=True,
                        ticket=result.order,
                        message=f"Order placed successfully",
                        lot_size=lot_size
                    )
                
                # Check if it's a "no money" error
                if result.retcode == 10019:  # TRADE_RETCODE_NO_MONEY
                    retry_count += 1
                    
                    # If we're already at minimum lot, can't reduce further
                    if lot_size <= min_lot:
                        return TradeResult(
                            success=False,
                            message=f"Insufficient margin even with minimum lot size {min_lot}"
                        )
                    
                    # Reduce lot size by 50% each retry for faster convergence
                    new_lot_size = lot_size * 0.5
                    
                    # Round down to lot step
                    new_lot_size = (new_lot_size // lot_step) * lot_step
                    
                    # Ensure we don't go below minimum
                    new_lot_size = max(new_lot_size, min_lot)
                    
                    # If reduction didn't change the lot size, we're stuck
                    if new_lot_size == lot_size:
                        return TradeResult(
                            success=False,
                            message=f"Cannot reduce lot size further (current: {lot_size}, min: {min_lot})"
                        )
                    
                    logger.warning(f"Insufficient margin with {lot_size:.2f} lots. Reducing to {new_lot_size:.2f} (attempt {retry_count}/{max_retries})")
                    
                    lot_size = new_lot_size
                    request["volume"] = lot_size
                else:
                    # Other error, don't retry
                    return TradeResult(
                        success=False,
                        message=f"Order failed: {result.comment} (code: {result.retcode})"
                    )
            
            # Max retries reached
            return TradeResult(
                success=False,
                message=f"Failed to place order after {max_retries} attempts to reduce lot size"
            )
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return TradeResult(success=False, message=f"Error executing signal: {e}")
    
    def manage_positions(self):
        """Manage open positions - trailing stop, break-even, and recovery mode auto-close"""
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
                    
                    # Calculate pip value based on symbol type
                    # For XAUUSD (Gold): 1 pip = 0.01 (e.g., 5180.00 to 5180.01)
                    # For Forex pairs with 5 digits: 1 pip = 10 points (0.0001)
                    # For Forex pairs with 3 digits (JPY): 1 pip = 10 points (0.01)
                    # For Forex pairs with 2/4 digits: 1 pip = 1 point
                    if "XAU" in pos.symbol or "GOLD" in pos.symbol:
                        pip_value = 0.01  # Gold: 1 pip = 0.01
                    elif digits in [3, 5]:
                        pip_value = point * 10
                    else:
                        pip_value = point
                    
                    # Calculate profit in pips
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        current_price = tick.bid
                        profit_pips = (current_price - pos.price_open) / pip_value
                    else:
                        current_price = tick.ask
                        profit_pips = (pos.price_open - current_price) / pip_value
                    
                    # Enhanced logging for debugging
                    logger.debug(f"Position {pos.ticket} ({pos.symbol}): "
                               f"Type={'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'}, "
                               f"Entry={pos.price_open}, Current={current_price}, "
                               f"Profit={profit_pips:.1f} pips, "
                               f"point={point}, digits={digits}, pip_value={pip_value}")
                    
                    # Recovery Mode Auto-Close: Close position if it reaches recovery target
                    if self.config.use_loss_recovery and self.cumulative_loss > 0:
                        if profit_pips >= self.config.recovery_pips:
                            logger.info(f"🎯 Recovery target reached! Position {pos.ticket}: "
                                      f"Profit={profit_pips:.1f} pips >= Target={self.config.recovery_pips} pips. "
                                      f"Closing position to lock in recovery profit.")
                            if self.close_position(pos.ticket):
                                logger.info(f"✓ Position {pos.ticket} closed successfully for recovery")
                            else:
                                logger.error(f"✗ Failed to close position {pos.ticket} for recovery")
                            continue  # Skip other modifications since we're closing
                    
                    new_sl = None
                    modification_type = None
                    
                    # Break-Even
                    if self.config.use_break_even and profit_pips >= self.config.break_even_at_pips:
                        logger.info(f"Position {pos.ticket}: Break-even triggered! "
                                  f"Profit={profit_pips:.1f} pips >= Threshold={self.config.break_even_at_pips} pips")
                        if pos.type == mt5.POSITION_TYPE_BUY:
                            be_sl = pos.price_open + (self.config.break_even_offset_pips * pip_value)
                            # Only move SL if it's below entry (or zero) and new BE SL is better
                            if (pos.sl < pos.price_open or pos.sl == 0) and be_sl > pos.sl:
                                new_sl = be_sl
                                modification_type = "breakeven"
                                logger.info(f"Position {pos.ticket}: Moving SL to break-even: {pos.sl} -> {be_sl}")
                        else:  # SELL position
                            be_sl = pos.price_open - (self.config.break_even_offset_pips * pip_value)
                            # Only move SL if it's above entry (or zero) and new BE SL is better (lower)
                            if (pos.sl > pos.price_open or pos.sl == 0) and (be_sl < pos.sl or pos.sl == 0):
                                new_sl = be_sl
                                modification_type = "breakeven"
                                logger.info(f"Position {pos.ticket}: Moving SL to break-even: {pos.sl} -> {be_sl}")
                    
                    # Trailing Stop
                    if self.config.use_trailing_stop and profit_pips >= self.config.trailing_start_pips:
                        logger.info(f"Position {pos.ticket}: Trailing stop triggered! "
                                  f"Profit={profit_pips:.1f} pips >= Threshold={self.config.trailing_start_pips} pips, "
                                  f"Step={self.config.trailing_step_pips} pips")
                        if pos.type == mt5.POSITION_TYPE_BUY:
                            trail_sl = current_price - (self.config.trailing_step_pips * pip_value)
                            logger.info(f"Position {pos.ticket}: Calculated trail_sl={trail_sl}, current_sl={pos.sl}")
                            if trail_sl > pos.sl:
                                new_sl = trail_sl
                                modification_type = "trailing"
                                logger.info(f"Position {pos.ticket}: Moving SL (trailing): {pos.sl} -> {trail_sl}")
                        else:
                            trail_sl = current_price + (self.config.trailing_step_pips * pip_value)
                            logger.info(f"Position {pos.ticket}: Calculated trail_sl={trail_sl}, current_sl={pos.sl}")
                            if trail_sl < pos.sl or pos.sl == 0:
                                new_sl = trail_sl
                                modification_type = "trailing"
                                logger.info(f"Position {pos.ticket}: Moving SL (trailing): {pos.sl} -> {trail_sl}")
                    
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
                            # Mark this ticket as automatically modified
                            self.auto_modified_tickets.add(pos.ticket)
                            logger.info(f"✓ SL updated for {pos.ticket}: {new_sl} ({modification_type})")
                        else:
                            logger.error(f"✗ Failed to update SL for {pos.ticket}: {result.comment if result else 'No result'}")
                except Exception as e:
                    logger.error(f"Error managing position {pos.ticket}: {e}")
        except Exception as e:
            logger.error(f"Error in manage_positions: {e}")
    
    def track_closed_positions(self):
        """Track closed positions and update cumulative loss"""
        try:
            # Get deals from today
            from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            deals = mt5.history_deals_get(from_date, datetime.now())
            
            if not deals:
                return
            
            # Track processed deals to avoid duplicates
            if not hasattr(self, 'processed_deals'):
                self.processed_deals = set()
            
            for deal in deals:
                # Only process OUT deals (position close) with our magic number
                if deal.entry == mt5.DEAL_ENTRY_OUT and deal.magic == self.config.magic_number:
                    if deal.ticket not in self.processed_deals:
                        self.processed_deals.add(deal.ticket)
                        
                        # Update cumulative loss with the profit/loss
                        if deal.profit != 0:
                            self._update_cumulative_loss(deal.profit)
                            logger.info(f"Closed position {deal.position_id}: Profit=${deal.profit:.2f}")
        
        except Exception as e:
            logger.error(f"Error tracking closed positions: {e}")
    
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
                     sl: Optional[float] = None, tp: Optional[float] = None,
                     master_ticket: Optional[int] = None) -> bool:
        """Modify an existing position or pending order
        
        Args:
            ticket: The order/position ticket to modify
            entry: New entry price (pending orders only)
            sl: New stop loss
            tp: New take profit
            master_ticket: Master's ticket number to store in comment (for client mode)
        """
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
                
                # Update comment with master ticket if provided
                new_comment = order.comment
                if master_ticket:
                    new_comment = f"Master#{master_ticket}"
                    logger.info(f"Storing master ticket {master_ticket} in comment")
                
                request = {
                    "action": mt5.TRADE_ACTION_MODIFY,
                    "order": order.ticket,
                    "price": new_entry,
                    "sl": new_sl,
                    "tp": new_tp,
                    "comment": new_comment,
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
    
    def find_order_by_symbol_ordertype_and_entry(self, symbol: str, order_type: str = None, 
                                                  entry_price: float = None) -> Optional[int]:
        """Find an order ticket by symbol, order type, and optionally entry price"""
        try:
            # Map the symbol to broker format
            broker_symbol = self.find_symbol(symbol)
            if not broker_symbol:
                logger.warning(f"Symbol {symbol} not found on broker")
                return None
            
            # Normalize order type for comparison (remove extra spaces, make uppercase)
            normalized_order_type = None
            if order_type:
                normalized_order_type = ' '.join(order_type.upper().split())
            
            # Check positions first
            positions = mt5.positions_get(symbol=broker_symbol)
            if positions:
                for pos in positions:
                    if pos.magic == self.config.magic_number:
                        pos_type = 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'
                        
                        # Check order type match
                        if normalized_order_type and pos_type not in normalized_order_type:
                            continue
                        
                        # Check entry price match (with tolerance for price differences)
                        if entry_price is not None:
                            price_diff = abs(pos.price_open - entry_price)
                            # Use a tolerance based on symbol digits
                            symbol_info = mt5.symbol_info(broker_symbol)
                            tolerance = 10 * symbol_info.point if symbol_info else 0.0001
                            if price_diff > tolerance:
                                continue
                        
                        logger.info(f"Found position {pos.ticket} for {symbol} (entry: {pos.price_open})")
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
                        
                        # Check order type match
                        if normalized_order_type and ord_type != normalized_order_type:
                            continue
                        
                        # Check entry price match (with tolerance)
                        if entry_price is not None:
                            price_diff = abs(order.price_open - entry_price)
                            # Use a tolerance based on symbol digits
                            symbol_info = mt5.symbol_info(broker_symbol)
                            tolerance = 10 * symbol_info.point if symbol_info else 0.0001
                            if price_diff > tolerance:
                                continue
                        
                        logger.info(f"Found pending order {order.ticket} for {symbol} (entry: {order.price_open})")
                        return order.ticket
            
            logger.warning(f"No order found for {symbol} with type={order_type} and entry={entry_price}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding order by symbol/type/entry: {e}")
            return None
    
    def find_order_by_master_ticket(self, master_ticket: int) -> Optional[int]:
        """Find a client order by master ticket stored in comment"""
        try:
            # Check pending orders
            orders = mt5.orders_get()
            if orders:
                for order in orders:
                    if order.magic == self.config.magic_number:
                        if order.comment and f"Master#{master_ticket}" in order.comment:
                            logger.info(f"Found order {order.ticket} with master ticket {master_ticket}")
                            return order.ticket
            
            # Check positions (in case order was already triggered)
            positions = mt5.positions_get()
            if positions:
                for pos in positions:
                    if pos.magic == self.config.magic_number:
                        if pos.comment and f"Master#{master_ticket}" in pos.comment:
                            logger.info(f"Found position {pos.ticket} with master ticket {master_ticket}")
                            return pos.ticket
            
            logger.warning(f"No order found with master ticket {master_ticket}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding order by master ticket: {e}")
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
        """Check for modifications to existing orders (entry, SL, TP changes)
        Only returns MANUAL modifications, not automatic ones from trailing stop/breakeven"""
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
                            # Check if this was an automatic modification
                            if pos.ticket in self.auto_modified_tickets:
                                # Remove from tracking set and skip reporting
                                self.auto_modified_tickets.discard(pos.ticket)
                                logger.info(f"Position modified (AUTO): {pos.ticket} - {', '.join(changes)}")
                                continue
                            
                            # This is a manual modification - report it
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
                            logger.info(f"Position modified (MANUAL): {pos.ticket} - {', '.join(changes)}")
            
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
                            # Check if this was an automatic modification
                            if order.ticket in self.auto_modified_tickets:
                                # Remove from tracking set and skip reporting
                                self.auto_modified_tickets.discard(order.ticket)
                                logger.info(f"Pending order modified (AUTO): {order.ticket} - {', '.join(changes)}")
                                continue
                            
                            # This is a manual modification - report it
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
                            logger.info(f"Pending order modified (MANUAL): {order.ticket} - {', '.join(changes)}")
            
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
                # Also clean up auto_modified_tickets
                self.auto_modified_tickets.discard(ticket)
                logger.info(f"Order {ticket} closed/cancelled, removed from tracking")
        
        except Exception as e:
            logger.error(f"Error checking for order modifications: {e}")
        
        return modified_orders
