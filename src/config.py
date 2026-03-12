"""
Configuration settings for the Discord Trading Bot
"""
import os
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RiskMode(Enum):
    FIXED_LOT = "fixed_lot"
    RISK_PERCENT = "risk_percent"
    FIXED_MONEY = "fixed_money"

def safe_int(value: str, default: int = 0) -> int:
    """Safely convert string to int"""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        logger.warning(f"Invalid int value '{value}', using default {default}")
        return default

def safe_float(value: str, default: float = 0.0) -> float:
    """Safely convert string to float"""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        logger.warning(f"Invalid float value '{value}', using default {default}")
        return default

def safe_bool(value: str, default: bool = False) -> bool:
    """Safely convert string to bool"""
    try:
        if not value:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
    except (ValueError, TypeError, AttributeError):
        logger.warning(f"Invalid bool value '{value}', using default {default}")
        return default

@dataclass
class TradingConfig:
    # Discord Settings
    discord_token: str = os.getenv("DISCORD_TOKEN", "")
    discord_channel_id: int = safe_int(os.getenv("DISCORD_CHANNEL_ID", "0"))
    discord_notification_channel_id: int = safe_int(os.getenv("DISCORD_NOTIFICATION_CHANNEL_ID", "0"))
    
    # MT5 Settings
    mt5_login: int = safe_int(os.getenv("MT5_LOGIN", "0"))
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "")
    mt5_path: str = os.getenv("MT5_PATH", "C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe")
    
    # Risk Management
    risk_mode: RiskMode = RiskMode.RISK_PERCENT
    risk_percent: float = 1.0
    fixed_lot: float = 0.1
    fixed_money_risk: float = 100.0
    min_lot: float = 0.01
    max_lot: float = 10.0
    
    # Trade Settings
    magic_number: int = 123456
    trade_comment: str = "Discord-Signal"
    max_spread_forex: int = 20
    max_spread_gold: int = 500
    max_spread_indices: int = 300
    max_spread_crypto: int = 5000
    max_slippage_points: int = 10
    max_open_trades: int = 3
    
    # Protection
    use_daily_limits: bool = True
    max_daily_loss_percent: float = 3.0
    max_daily_profit_percent: float = 5.0
    max_daily_trades: int = 5
    
    # Trailing Stop
    use_trailing_stop: bool = True
    trailing_start_pips: float = 500.0
    trailing_step_pips: float = 100.0
    
    # Break-Even
    use_break_even: bool = True
    break_even_at_pips: float = 300.0
    break_even_offset_pips: float = 100.0
    
    # Trading Sessions (Philippines Time UTC+8)
    enabled_sessions: list = None  # List of enabled session names
    
    def __post_init__(self):
        """Initialize default values after dataclass creation"""
        if self.enabled_sessions is None:
            self.enabled_sessions = []

def load_config() -> TradingConfig:
    """Load configuration from environment variables"""
    try:
        # Parse enabled sessions from comma-separated string
        sessions_str = os.getenv("ENABLED_SESSIONS", "")
        enabled_sessions = [s.strip() for s in sessions_str.split(",") if s.strip()]
        
        return TradingConfig(
            discord_token=os.getenv("DISCORD_TOKEN", ""),
            discord_channel_id=safe_int(os.getenv("DISCORD_CHANNEL_ID", "0")),
            discord_notification_channel_id=safe_int(os.getenv("DISCORD_NOTIFICATION_CHANNEL_ID", "0")),
            mt5_login=safe_int(os.getenv("MT5_LOGIN", "0")),
            mt5_password=os.getenv("MT5_PASSWORD", ""),
            mt5_server=os.getenv("MT5_SERVER", ""),
            mt5_path=os.getenv("MT5_PATH", ""),
            risk_percent=safe_float(os.getenv("RISK_PERCENT", "1.0")),
            min_lot=safe_float(os.getenv("MIN_LOT", "0.01")),
            max_lot=safe_float(os.getenv("MAX_LOT", "10.0")),
            max_open_trades=safe_int(os.getenv("MAX_OPEN_TRADES", "3")),
            max_daily_trades=safe_int(os.getenv("MAX_DAILY_TRADES", "5")),
            max_spread_forex=safe_int(os.getenv("MAX_SPREAD_FOREX", "20")),
            max_spread_gold=safe_int(os.getenv("MAX_SPREAD_GOLD", "500")),
            max_spread_indices=safe_int(os.getenv("MAX_SPREAD_INDICES", "300")),
            max_spread_crypto=safe_int(os.getenv("MAX_SPREAD_CRYPTO", "5000")),
            use_daily_limits=safe_bool(os.getenv("USE_DAILY_LIMITS", "true")),
            max_daily_loss_percent=safe_float(os.getenv("MAX_DAILY_LOSS_PERCENT", "3.0")),
            max_daily_profit_percent=safe_float(os.getenv("MAX_DAILY_PROFIT_PERCENT", "5.0")),
            use_break_even=safe_bool(os.getenv("USE_BREAK_EVEN", "true")),
            break_even_at_pips=safe_float(os.getenv("BREAK_EVEN_AT_PIPS", "300.0")),
            break_even_offset_pips=safe_float(os.getenv("BREAK_EVEN_OFFSET_PIPS", "100.0")),
            use_trailing_stop=safe_bool(os.getenv("USE_TRAILING_STOP", "true")),
            trailing_start_pips=safe_float(os.getenv("TRAILING_START_PIPS", "1000.0")),
            trailing_step_pips=safe_float(os.getenv("TRAILING_STEP_PIPS", "100.0")),
            enabled_sessions=enabled_sessions,
        )
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return TradingConfig()
