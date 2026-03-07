"""
Discord Signal Parser - Extracts trading signals from Discord messages
"""
import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class OrderType(Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_LIMIT = "buy_limit"
    SELL_LIMIT = "sell_limit"
    BUY_STOP = "buy_stop"
    SELL_STOP = "sell_stop"

@dataclass
class TradingSignal:
    symbol: str
    order_type: OrderType
    entry_price: float
    stop_loss: float
    take_profit: float
    timeframe: Optional[str] = None
    sl_pips: Optional[float] = None
    tp_pips: Optional[float] = None
    raw_message: str = ""

class SignalParser:
    """Parse trading signals from Discord messages"""
    
    # Common forex pairs
    FOREX_PAIRS = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "EURCHF", "GBPCHF",
        "AUDCAD", "AUDNZD", "CADJPY", "CHFJPY", "NZDJPY", "GBPAUD", "GBPCAD",
        "GBPNZD", "EURCAD", "EURNZD", "AUDCHF", "CADCHF", "NZDCAD", "NZDCHF",
        "XAUUSD", "XAGUSD", "US30", "NAS100", "SPX500", "BTCUSD", "ETHUSD"
    ]
    
    def parse(self, message: str) -> Optional[TradingSignal]:
        """Parse a Discord message and extract trading signal"""
        message_upper = message.upper()
        
        # Extract symbol
        symbol = self._extract_symbol(message_upper)
        if not symbol:
            return None
        
        # Extract order type
        order_type = self._extract_order_type(message_upper)
        if not order_type:
            return None
        
        # Extract prices
        entry = self._extract_price(message, ["ENTRY", "ENTRY:", "ENTRY PRICE", "@"])
        sl = self._extract_price(message, ["SL", "SL:", "STOP LOSS", "STOPLOSS"])
        tp = self._extract_price(message, ["TP", "TP:", "TAKE PROFIT", "TAKEPROFIT", "TP1"])
        
        # Entry is required, but SL and TP can be 0 (no stop loss/take profit)
        if entry is None:
            return None
        
        # Default to 0 if SL or TP not found
        if sl is None:
            sl = 0.0
        if tp is None:
            tp = 0.0
        
        # Extract timeframe if present
        timeframe = self._extract_timeframe(message_upper)
        
        # Calculate pips
        sl_pips = self._calculate_pips(symbol, entry, sl)
        tp_pips = self._calculate_pips(symbol, entry, tp)
        
        return TradingSignal(
            symbol=symbol,
            order_type=order_type,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            timeframe=timeframe,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            raw_message=message
        )
    
    def _extract_symbol(self, message: str) -> Optional[str]:
        """Extract trading symbol from message, handling broker suffixes"""
        import re
        
        # Try matching with broker suffixes (e.g., BTCUSDm, EURUSD.a, GBPUSD_sb, etc.)
        # Pattern: base pair + optional suffix (letters, dots, underscores, numbers)
        for pair in self.FOREX_PAIRS:
            # Look for the base pair followed by common broker suffixes
            pattern = rf'\b{pair}[a-z0-9._\-]*\b'
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # Return the full symbol as it appears in the broker (with suffix)
                return match.group(0).upper()
        
        return None
    
    def _extract_order_type(self, message: str) -> Optional[OrderType]:
        """Extract order type from message"""
        # Check for limit orders first
        if "LIMIT BUY" in message or "BUY LIMIT" in message:
            return OrderType.BUY_LIMIT
        if "LIMIT SELL" in message or "SELL LIMIT" in message:
            return OrderType.SELL_LIMIT
        
        # Check for stop orders
        if "STOP BUY" in message or "BUY STOP" in message:
            return OrderType.BUY_STOP
        if "STOP SELL" in message or "SELL STOP" in message:
            return OrderType.SELL_STOP
        
        # Check for market orders
        if "BUY" in message and "SELL" not in message:
            return OrderType.BUY
        if "SELL" in message and "BUY" not in message:
            return OrderType.SELL
        
        # Handle signals with both BUY and SELL - use context
        if "🟢" in message or "LONG" in message:
            return OrderType.BUY
        if "🔴" in message or "SHORT" in message:
            return OrderType.SELL
        
        return None
    
    def _extract_price(self, message: str, keywords: list) -> Optional[float]:
        """Extract price value following a keyword"""
        for keyword in keywords:
            # Pattern: keyword followed by optional colon/space, optional $, and a number (with optional commas)
            pattern = rf'{keyword}\s*:?\s*\$?\s*([\d,]+\.?\d*)'
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    # Remove commas from the number
                    price_str = match.group(1).replace(',', '')
                    return float(price_str)
                except ValueError:
                    continue
        return None
    
    def _extract_timeframe(self, message: str) -> Optional[str]:
        """Extract timeframe from message"""
        timeframes = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN"]
        for tf in timeframes:
            if tf in message:
                return tf
        return None
    
    def _calculate_pips(self, symbol: str, price1: float, price2: float) -> float:
        """Calculate pip difference between two prices"""
        diff = abs(price1 - price2)
        
        # JPY pairs have 2 decimal places
        if "JPY" in symbol:
            return diff * 100  # 0.01 = 1 pip
        # Crypto - use price difference directly (1 pip = $1 for BTC)
        elif "BTC" in symbol or "ETH" in symbol or "XRP" in symbol:
            return diff  # $2584 = 2584 pips
        # Gold
        elif "XAU" in symbol or "GOLD" in symbol:
            return diff * 10  # 0.1 = 1 pip for gold
        # Standard forex pairs
        else:
            return diff * 10000  # 0.0001 = 1 pip
