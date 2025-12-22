"""
Rate Limiting Module
Prevents abuse by limiting requests per user.
"""

import time
from typing import Dict, Tuple
from collections import defaultdict


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        # {user_id: [(timestamp, count), ...]}
        self._requests: Dict[int, list] = defaultdict(list)
    
    def is_allowed(
        self, 
        user_id: int, 
        max_requests: int = 10, 
        window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if user is allowed to make a request.
        
        Args:
            user_id: User's Telegram ID
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Clean old entries
        self._requests[user_id] = [
            ts for ts in self._requests[user_id] 
            if ts > window_start
        ]
        
        # Check limit
        current_count = len(self._requests[user_id])
        
        if current_count >= max_requests:
            return False, 0
        
        # Add new request
        self._requests[user_id].append(now)
        
        return True, max_requests - current_count - 1
    
    def get_wait_time(self, user_id: int, window_seconds: int = 60) -> int:
        """Get seconds until user can make another request."""
        if not self._requests[user_id]:
            return 0
        
        oldest_request = min(self._requests[user_id])
        wait_time = int(oldest_request + window_seconds - time.time())
        return max(0, wait_time)


# Global rate limiter instance
_limiter = RateLimiter()


# Rate limit configurations
LIMITS = {
    'news': {'max': 5, 'window': 300},      # 5 per 5 minutes
    'search': {'max': 10, 'window': 60},    # 10 per minute
    'ai_chat': {'max': 5, 'window': 300},   # 5 per 5 minutes (reduced to save API costs)
    'save': {'max': 30, 'window': 60},      # 30 per minute
    'default': {'max': 30, 'window': 60}    # Default
}


def check_rate_limit(user_id: int, action: str = 'default') -> Tuple[bool, str]:
    """
    Check if user is rate limited for an action.
    
    Args:
        user_id: User's Telegram ID
        action: Action type ('news', 'search', 'ai_chat', 'save', 'default')
        
    Returns:
        Tuple of (is_allowed, message)
    """
    config = LIMITS.get(action, LIMITS['default'])
    key = f"{user_id}_{action}"
    
    allowed, remaining = _limiter.is_allowed(
        key, 
        max_requests=config['max'], 
        window_seconds=config['window']
    )
    
    if not allowed:
        wait_time = _limiter.get_wait_time(key, config['window'])
        return False, f"⏳ Rate limit reached. Please wait {wait_time} seconds."
    
    return True, f"Remaining: {remaining}"


def reset_limits(user_id: int):
    """Reset all limits for a user (admin only)."""
    for action in LIMITS.keys():
        key = f"{user_id}_{action}"
        _limiter._requests[key] = []
