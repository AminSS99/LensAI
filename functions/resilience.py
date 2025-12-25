"""
Resilience Utilities
Provides retry logic, exponential backoff, and error handling for external API calls.
"""

import time
import asyncio
from typing import Callable, Any, TypeVar, Optional
from functools import wraps


T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff (default 2.0)
        exceptions: Tuple of exceptions to catch and retry
        
    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def my_api_call():
            response = requests.get(url)
            return response.json()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Final attempt failed, raise the exception
                        print(f"❌ {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    print(f"⚠️ {func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Final attempt failed, raise the exception
                        print(f"❌ {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    print(f"⚠️ {func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def safe_call(func: Callable[..., T], *args, default: Optional[T] = None, **kwargs) -> T:
    """
    Call a function safely and return a default value if it fails.
    
    Args:
        func: Function to call
        *args: Arguments to pass to function
        default: Default value to return on failure
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Function result or default value
        
    Usage:
        result = safe_call(risky_function, arg1, arg2, default=[])
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"⚠️ {func.__name__} failed: {e}. Returning default value.")
        return default


async def safe_call_async(func: Callable[..., T], *args, default: Optional[T] = None, **kwargs) -> T:
    """
    Call an async function safely and return a default value if it fails.
    
    Args:
        func: Async function to call
        *args: Arguments to pass to function
        default: Default value to return on failure
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Function result or default value
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        print(f"⚠️ {func.__name__} failed: {e}. Returning default value.")
        return default


class TimeoutError(Exception):
    """Raised when an operation times out."""
    pass


def with_timeout(timeout_seconds: float):
    """
    Decorator to add timeout to synchronous functions.
    
    Args:
        timeout_seconds: Timeout in seconds
        
    Note: This uses a simple time-based check, not true interruption.
    For async functions, use asyncio.wait_for instead.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"{func.__name__} timed out after {timeout_seconds}s")
            
            # Set the signal handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Restore the old signal handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            return result
        
        return wrapper
    
    return decorator
