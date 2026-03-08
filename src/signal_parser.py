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

@dataclass
class OrderModification:
    ticket: int
    symbol: str
    order_type: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    changes: list = None

class SignalParser:
    """Parse trading signals from Discord messages"""
    
    # Common forex pairs
    FOREX_PAIRS = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "EURCHF", "GBPCHF",
        "AUDCAD", "AUDNZD", "CADJPY", "CHFJPY", "NZDJPY", "GBPAUD", "GBPCAD",
        "GBPNZD", "EURCAD", "EURNZD", "AUDCHF", "CADCHF", "NZDCAD", "NZDCHF",
        # Metals
        "XAUUSD", "XAUUSDC", "XAUUSDT", "XAGUSD", "XAGUSDC", "XAGUSDT",
        # Indices
        "US30", "NAS100", "SPX500", "US100", "DJ30", "SP500",
        # Crypto
        "BTCUSD", "BTCUSDC", "BTCUSDT", "ETHUSD", "ETHUSDC", "ETHUSDT",
        "XRPUSD", "XRPUSDC", "XRPUSDT", "ADAUSD", "SOLUSD", "DOTUSD",
        "BNBUSD", "DOGEUSD", "MATICUSD", "AVAXUSD", "LINKUSD"
    ]
    
    def parse_modification(self, message: str) -> Optional[OrderModification]:
        """Parse an order modification message from Discord"""
        try:
            # Check if this is a modification message
            if "ORDER MODIFIED" not in message.upper() and "🔄" not in message:
                return None
            
            # Extract ticket number
            ticket_match = re.search(r'Ticket\s*#?(\d+)', message, re.IGNORECASE)
            if not ticket_match:
                return None
            ticket = int(ticket_match.group(1))
            
            # Extract symbol
            symbol_match = re.search(r'Pair:\s*([A-Z0-9]+)', message, re.IGNORECASE)
            if not symbol_match:
                return None
            symbol = symbol_match.group(1).upper()
            
            # Extract order type
            type_match = re.search(r'Type:\s*([A-Z\s]+)', message, re.IGNORECASE)
            order_type = type_match.group(1).strip() if type_match else "UNKNOWN"
            
            # Extract current prices
            entry_match = re.search(r'Entry:\s*([\d.]+)', message, re.IGNORECASE)
            sl_match = re.search(r'SL:\s*([\d.]+)', message, re.IGNORECASE)
            tp_match = re.search(r'TP:\s*([\d.]+)', message, re.IGNORECASE)
            
            entry = float(entry_match.group(1)) if entry_match else None
            sl = float(sl_match.group(1)) if sl_match else None
            tp = float(tp_match.group(1)) if tp_match else None
            
            # Extract changes list
            changes = []
            changes_section = re.search(r'Changes:(.*)', message, re.IGNORECASE | re.DOTALL)
            if changes_section:
                change_lines = changes_section.group(1).strip().split('\n')
                for line in change_lines:
                    if '→' in line or '->' in line:
                        changes.append(line.strip().lstrip('•').strip())
            
            return OrderModification(
                ticket=ticket,
                symbol=symbol,
                order_type=order_type,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                changes=changes
            )
        except Exception as e:
            import logging
            logging.error(f"Error parsing modification: {e}")
            return None
    
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
        
        # First try: Match known pairs with optional broker suffixes
        for pair in self.FOREX_PAIRS:
            # Look for the base pair followed by common broker suffixes
            pattern = rf'\b{pair}[a-z0-9._\-]*\b'
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # Return the full symbol as it appears in the broker (with suffix)
                return match.group(0).upper()
        
        # Second try: Generic pattern for any trading symbol
        # Matches patterns like: BTCUSDC, XAUUSDT, EURUSD.m, GBPUSD_sb, etc.
        # Pattern: 6-10 uppercase letters optionally followed by suffix
        generic_pattern = r'\b([A-Z]{6,10}(?:[a-z0-9._\-]+)?)\b'
        matches = re.findall(generic_pattern, message)
        
        if matches:
            # Return the first match that looks like a trading symbol
            for match in matches:
                # Filter out common words that aren't symbols
                if match not in ['ENTRY', 'LIMIT', 'MARKET', 'PENDING', 'SIGNAL']:
                    return match.upper()
        
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
        # Crypto - use price difference directly (1 pip = $1)
        elif any(crypto in symbol.upper() for crypto in ["BTC", "ETH", "XRP", "ADA", "SOL", "DOT", "BNB", "DOGE", "MATIC", "AVAX", "LINK"]):
            return diff  # Direct price difference
        # Gold and Silver
        elif any(metal in symbol.upper() for metal in ["XAU", "GOLD", "XAG", "SILVER"]):
            return diff * 10  # 0.1 = 1 pip for metals
        # Indices
        elif any(index in symbol.upper() for index in ["US30", "NAS", "SPX", "US100", "DJ30", "SP500"]):
            return diff  # Direct price difference for indices
        # Standard forex pairs (default)
        else:
            return diff * 10000  # 0.0001 = 1 pip
