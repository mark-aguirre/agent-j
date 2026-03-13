"""
Discord Signal Parser - Extracts trading signals from Discord messages
"""
import re
import logging
from dataclasses import dataclass
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)

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
    trade_id: Optional[str] = None  # Master's trade ID

@dataclass
class OrderModification:
    ticket: int
    symbol: str
    order_type: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    changes: list = None
    trade_id: Optional[str] = None  # Master's trade ID

@dataclass
class OrderClose:
    trade_id: str  # Master's trade ID (e.g., "ID#12345")
    ticket: int  # Master's ticket number

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
    
    def parse_close(self, message: str) -> Optional[OrderClose]:
        """Parse a close order message from Discord"""
        try:
            # Check if this is a close message
            if "CLOSE ORDER" not in message.upper() and "🔴" not in message:
                return None
            
            # Check for explicit CLOSE action
            if "ACTION: CLOSE" not in message.upper() and "Action: CLOSE" not in message:
                return None
            
            # Extract trade ID
            trade_id_match = re.search(r'Trade ID:\s*(ID#\d+)', message, re.IGNORECASE)
            if not trade_id_match:
                # Try alternative format
                trade_id_match = re.search(r'CLOSE ORDER\s*-\s*(ID#\d+)', message, re.IGNORECASE)
            
            if not trade_id_match:
                return None
            
            trade_id = trade_id_match.group(1)
            
            # Extract ticket number from trade ID
            ticket_match = re.search(r'ID#(\d+)', trade_id)
            ticket = int(ticket_match.group(1)) if ticket_match else 0
            
            logger.info(f"Parsed close order: {trade_id}")
            return OrderClose(trade_id=trade_id, ticket=ticket)
            
        except Exception as e:
            logger.error(f"Error parsing close order: {e}")
            return None
    
    def parse_modification(self, message: str) -> Optional[OrderModification]:
        """Parse an order modification message from Discord"""
        try:
            # Check if this is a modification message
            if "ORDER MODIFIED" not in message.upper() and "🔄" not in message:
                return None
            
            # Extract trade ID (preferred method)
            trade_id_match = re.search(r'ID#(\d+)', message, re.IGNORECASE)
            trade_id = trade_id_match.group(0) if trade_id_match else None
            ticket = int(trade_id_match.group(1)) if trade_id_match else None
            
            # Fallback: Extract ticket number if trade ID not found
            if not ticket:
                ticket_match = re.search(r'Ticket\s*#?(\d+)', message, re.IGNORECASE)
                if not ticket_match:
                    return None
                ticket = int(ticket_match.group(1))
                trade_id = f"ID#{ticket}"
            
            # Extract symbol
            symbol_match = re.search(r'Pair:\s*([A-Z0-9]+)', message, re.IGNORECASE)
            if not symbol_match:
                return None
            symbol = symbol_match.group(1).upper()
            
            # Extract order type (stop at newline or next field)
            type_match = re.search(r'Type:\s*([A-Z\s]+?)(?:\n|Entry:|$)', message, re.IGNORECASE)
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
                changes=changes,
                trade_id=trade_id
            )
        except Exception as e:
            logger.error(f"Error parsing modification: {e}")
            return None
    
    def parse(self, message: str) -> Optional[TradingSignal]:
        """Parse a Discord message and extract trading signal"""
        message_upper = message.upper()
        
        # Extract trade ID if present
        trade_id_match = re.search(r'TRADE ID:\s*(ID#\d+)', message, re.IGNORECASE)
        trade_id = trade_id_match.group(1) if trade_id_match else None
        
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
            raw_message=message,
            trade_id=trade_id
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
        """Calculate pip difference between two prices
        Uses same logic as mt5_trader.manage_positions for consistency"""
        diff = abs(price1 - price2)
        
        # Determine decimal places from price to calculate pip value
        price_str = str(price1)
        if '.' in price_str:
            decimals = len(price_str.split('.')[1])
        else:
            decimals = 2  # Default
        
        # Calculate pip value same way as MT5Trader does
        # For 3 or 5 decimals: pip = point * 10
        # For 2 or 4 decimals: pip = point
        if decimals in [3, 5]:
            # point = 0.001 for 3 decimals, pip = 0.01
            # point = 0.00001 for 5 decimals, pip = 0.0001
            point = 10 ** (-decimals)
            pip_value = point * 10
        else:
            # point = 0.01 for 2 decimals, pip = 0.01
            # point = 0.0001 for 4 decimals, pip = 0.0001
            point = 10 ** (-decimals)
            pip_value = point
        
        return diff / pip_value
