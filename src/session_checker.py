"""
Forex Session Checker - Validates if current time is within enabled trading sessions
All times are in Philippines Time (UTC+8)
"""
from datetime import datetime, time
from typing import List
import logging

logger = logging.getLogger(__name__)

class ForexSession:
    """Represents a forex trading session"""
    def __init__(self, name: str, country: str, emoji: str, start_hour: int, start_min: int, end_hour: int, end_min: int):
        self.name = name
        self.country = country
        self.emoji = emoji
        self.start_time = time(start_hour, start_min)
        self.end_time = time(end_hour, end_min)
    
    def is_active(self, current_time: time) -> bool:
        """Check if the session is currently active"""
        if self.start_time <= self.end_time:
            # Normal case: session doesn't cross midnight
            return self.start_time <= current_time <= self.end_time
        else:
            # Session crosses midnight (e.g., 9:00 PM - 6:00 AM)
            return current_time >= self.start_time or current_time <= self.end_time
    
    def __str__(self):
        return f"{self.emoji} {self.name} ({self.country}): {self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"

# Define all forex sessions (Philippines Time UTC+8)
FOREX_SESSIONS = {
    "Sydney": ForexSession("Sydney Session", "Australia", "🌏", 6, 0, 15, 0),
    "Tokyo": ForexSession("Tokyo Session (Asian)", "Japan", "🌏", 8, 0, 17, 0),
    "London": ForexSession("London Session", "United Kingdom", "🇬🇧", 16, 0, 1, 0),
    "New York": ForexSession("New York Session", "United States", "🇺🇸", 21, 0, 6, 0),
}

class SessionChecker:
    """Check if trading is allowed based on enabled sessions"""
    
    def __init__(self, enabled_sessions: List[str]):
        """
        Initialize session checker
        
        Args:
            enabled_sessions: List of session names to enable (e.g., ["London", "New York"])
        """
        self.enabled_sessions = enabled_sessions
        logger.info(f"Session checker initialized with sessions: {enabled_sessions}")
    
    def is_trading_allowed(self) -> tuple[bool, str]:
        """
        Check if trading is currently allowed based on enabled sessions
        
        Returns:
            tuple: (is_allowed, reason)
        """
        # If no sessions are enabled, allow all trading
        if not self.enabled_sessions:
            return True, "All sessions enabled"
        
        # Get current Philippines time
        current_time = datetime.now().time()
        
        # Check each enabled session
        active_sessions = []
        for session_name in self.enabled_sessions:
            session = FOREX_SESSIONS.get(session_name)
            if session and session.is_active(current_time):
                active_sessions.append(session_name)
        
        if active_sessions:
            return True, f"Active session: {', '.join(active_sessions)}"
        else:
            enabled_names = [f"{FOREX_SESSIONS[s].emoji} {s}" for s in self.enabled_sessions if s in FOREX_SESSIONS]
            return False, f"Outside trading hours. Enabled sessions: {', '.join(enabled_names)}"
    
    @staticmethod
    def get_all_sessions() -> dict:
        """Get all available forex sessions"""
        return FOREX_SESSIONS
    
    @staticmethod
    def get_session_info(session_name: str) -> ForexSession:
        """Get information about a specific session"""
        return FOREX_SESSIONS.get(session_name)
