"""
Utilities for handling HTTP requests with anti-bot protection evasion.
Contains defensive strategies for bypassing website blocking mechanisms.
"""
import random
import time
import asyncio
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class RequestHeaderManager:
    """Manages rotating headers and user agents for defensive web scraping"""
    
    # Common realistic user agents from major browsers
    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
        
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0",
        
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0",
        
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    ]
    
    # Common languages weighted by usage
    ACCEPT_LANGUAGES = [
        "en-US,en;q=0.9",
        "en-US,en;q=0.9,es;q=0.8",
        "en-GB,en;q=0.9",
        "en-US,en;q=0.9,fr;q=0.8",
        "en-US,en;q=0.9,de;q=0.8",
        "en-US,en;q=0.9,it;q=0.8",
    ]
    
    # Common browser accept headers
    ACCEPT_HEADERS = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    ]
    
    # Common encoding
    ACCEPT_ENCODINGS = [
        "gzip, deflate, br",
        "gzip, deflate",
    ]
    
    def __init__(self):
        self._last_user_agent_index = 0
        
    def get_random_headers(self, url: str = None, referrer: str = None) -> Dict[str, str]:
        """Generate realistic browser headers with rotation"""
        user_agent = self._get_next_user_agent()
        
        headers = {
            "User-Agent": user_agent,
            "Accept": random.choice(self.ACCEPT_HEADERS),
            "Accept-Language": random.choice(self.ACCEPT_LANGUAGES),
            "Accept-Encoding": random.choice(self.ACCEPT_ENCODINGS),
            "DNT": "1",  # Do Not Track
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Add cache control occasionally
        if random.random() < 0.3:
            headers["Cache-Control"] = "no-cache"
        
        # Add referrer if provided or generate realistic one
        if referrer:
            headers["Referer"] = referrer
        elif url and random.random() < 0.4:  # 40% chance of adding referrer
            headers["Referer"] = self._generate_realistic_referrer(url)
        
        # Add sec headers for Chrome-like behavior
        if "Chrome" in user_agent:
            headers.update({
                "sec-ch-ua": self._get_sec_ch_ua(user_agent),
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": self._get_platform_from_ua(user_agent),
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none" if not referrer else "same-origin",
                "Sec-Fetch-User": "?1",
            })
        
        return headers
    
    def _get_next_user_agent(self) -> str:
        """Get next user agent in rotation to avoid patterns"""
        # Use round-robin with some randomization
        if random.random() < 0.8:  # 80% of time use rotation
            ua = self.USER_AGENTS[self._last_user_agent_index]
            self._last_user_agent_index = (self._last_user_agent_index + 1) % len(self.USER_AGENTS)
        else:  # 20% of time use random
            ua = random.choice(self.USER_AGENTS)
        
        return ua
    
    def _generate_realistic_referrer(self, url: str) -> str:
        """Generate a realistic referrer based on the target URL"""
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Common referrer patterns
        referrers = [
            f"https://www.google.com/",
            f"https://www.bing.com/",
            f"https://{domain}/",
            f"https://{domain}",
            "https://www.facebook.com/",
            "https://www.pinterest.com/",
        ]
        
        return random.choice(referrers)
    
    def _get_sec_ch_ua(self, user_agent: str) -> str:
        """Generate sec-ch-ua header based on user agent"""
        if "Chrome/119" in user_agent:
            return '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"'
        elif "Chrome/118" in user_agent:
            return '"Google Chrome";v="118", "Chromium";v="118", "Not=A?Brand";v="99"'
        elif "Chrome/117" in user_agent:
            return '"Google Chrome";v="117", "Chromium";v="117", "Not;A=Brand";v="8"'
        else:
            return '"Chromium";v="119", "Not?A_Brand";v="24"'
    
    def _get_platform_from_ua(self, user_agent: str) -> str:
        """Extract platform for sec-ch-ua-platform header"""
        if "Windows" in user_agent:
            return '"Windows"'
        elif "Macintosh" in user_agent:
            return '"macOS"'
        elif "Linux" in user_agent:
            return '"Linux"'
        else:
            return '"Unknown"'


class RateLimiter:
    """Per-domain rate limiting to avoid triggering anti-bot measures"""
    
    def __init__(self, default_delay: float = 2.0, max_delay: float = 30.0):
        self.default_delay = default_delay
        self.max_delay = max_delay
        self.domain_delays: Dict[str, float] = {}
        self.last_request_times: Dict[str, float] = {}
        self.consecutive_failures: Dict[str, int] = {}
        
    async def wait_for_domain(self, url: str) -> None:
        """Wait appropriate time before making request to domain"""
        domain = urlparse(url).netloc
        current_time = time.time()
        
        # Get delay for this domain
        delay = self.domain_delays.get(domain, self.default_delay)
        
        # Add randomization to avoid patterns
        jittered_delay = delay * (0.8 + random.random() * 0.4)  # ±20% jitter
        
        # Check if we need to wait
        last_request = self.last_request_times.get(domain, 0)
        time_since_last = current_time - last_request
        
        if time_since_last < jittered_delay:
            wait_time = jittered_delay - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
            await asyncio.sleep(wait_time)
        
        # Update last request time
        self.last_request_times[domain] = time.time()
    
    def record_success(self, url: str) -> None:
        """Record successful request to potentially reduce delay"""
        domain = urlparse(url).netloc
        
        # Reset failure count
        self.consecutive_failures[domain] = 0
        
        # Gradually reduce delay for successful domains
        current_delay = self.domain_delays.get(domain, self.default_delay)
        if current_delay > self.default_delay:
            new_delay = max(self.default_delay, current_delay * 0.8)
            self.domain_delays[domain] = new_delay
            logger.debug(f"Reduced delay for {domain} to {new_delay:.2f}s")
    
    def record_failure(self, url: str, is_rate_limited: bool = False) -> None:
        """Record failed request to increase delay"""
        domain = urlparse(url).netloc
        
        # Increment failure count
        failures = self.consecutive_failures.get(domain, 0) + 1
        self.consecutive_failures[domain] = failures
        
        # Increase delay based on failure type and count
        current_delay = self.domain_delays.get(domain, self.default_delay)
        
        if is_rate_limited:
            # Significant increase for rate limiting
            multiplier = 2.0 + (failures * 0.5)
        else:
            # Moderate increase for other failures
            multiplier = 1.2 + (failures * 0.1)
        
        new_delay = min(self.max_delay, current_delay * multiplier)
        self.domain_delays[domain] = new_delay
        
        logger.warning(f"Increased delay for {domain} to {new_delay:.2f}s after {failures} failures")
    
    def get_domain_stats(self) -> Dict[str, Dict]:
        """Get statistics for all domains"""
        stats = {}
        for domain in set(list(self.domain_delays.keys()) + list(self.last_request_times.keys())):
            stats[domain] = {
                "delay": self.domain_delays.get(domain, self.default_delay),
                "failures": self.consecutive_failures.get(domain, 0),
                "last_request": self.last_request_times.get(domain, 0),
            }
        return stats


class RetryManager:
    """Handles intelligent retry logic with exponential backoff"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic and exponential backoff"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
                    jittered_delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of delay
                    
                    logger.info(f"Retry attempt {attempt}/{self.max_retries} in {jittered_delay:.2f}s")
                    await asyncio.sleep(jittered_delay)
                
                return await func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Check if this is a retryable error
                if not self._is_retryable_error(e):
                    logger.debug(f"Non-retryable error: {e}")
                    raise e
                
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} retry attempts failed")
                    break
                
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
        
        # If we get here, all retries failed
        raise last_exception
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is worth retrying"""
        error_str = str(error).lower()
        
        # Don't retry on client errors that won't change
        non_retryable_patterns = [
            "404",
            "not found", 
            "invalid url",
            "malformed",
            "unauthorized access",  # Our custom error for auth walls
        ]
        
        if any(pattern in error_str for pattern in non_retryable_patterns):
            return False
        
        # Retry on server errors, timeouts, connection issues
        retryable_patterns = [
            "500", "502", "503", "504",
            "timeout",
            "connection",
            "rate limit",
            "forbidden",  # 403 might be temporary
            "too many requests",
        ]
        
        return any(pattern in error_str for pattern in retryable_patterns)


class ProxyManager:
    """Manages proxy rotation for avoiding IP-based blocking"""
    
    def __init__(self, proxies: List[str] = None):
        self.proxies = proxies or []
        self.current_proxy_index = 0
        self.proxy_failures: Dict[str, int] = {}
        self.max_failures = 3
        
    def add_proxy(self, proxy_url: str) -> None:
        """Add a proxy to the rotation list"""
        if proxy_url not in self.proxies:
            self.proxies.append(proxy_url)
            
    def remove_proxy(self, proxy_url: str) -> None:
        """Remove a proxy from the rotation list"""
        if proxy_url in self.proxies:
            self.proxies.remove(proxy_url)
            if proxy_url in self.proxy_failures:
                del self.proxy_failures[proxy_url]
    
    def get_next_proxy(self) -> Optional[str]:
        """Get next proxy in rotation, skipping failed ones"""
        if not self.proxies:
            return None
        
        # Find a working proxy (not failed too many times)
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            
            # Check if this proxy has failed too many times
            failures = self.proxy_failures.get(proxy, 0)
            if failures < self.max_failures:
                return proxy
            
            attempts += 1
        
        # All proxies have failed, reset failure counts and try again
        logger.warning("All proxies have failed, resetting failure counts")
        self.proxy_failures.clear()
        return self.proxies[0] if self.proxies else None
    
    def record_proxy_success(self, proxy_url: str) -> None:
        """Record successful proxy usage"""
        if proxy_url in self.proxy_failures:
            # Reduce failure count on success
            self.proxy_failures[proxy_url] = max(0, self.proxy_failures[proxy_url] - 1)
    
    def record_proxy_failure(self, proxy_url: str) -> None:
        """Record proxy failure"""
        self.proxy_failures[proxy_url] = self.proxy_failures.get(proxy_url, 0) + 1
        logger.warning(f"Proxy {proxy_url} failed {self.proxy_failures[proxy_url]} times")
    
    def get_proxy_stats(self) -> Dict[str, Dict]:
        """Get statistics for all proxies"""
        stats = {}
        for proxy in self.proxies:
            stats[proxy] = {
                "failures": self.proxy_failures.get(proxy, 0),
                "status": "failed" if self.proxy_failures.get(proxy, 0) >= self.max_failures else "active"
            }
        return stats


class SessionManager:
    """Manages HTTP sessions with cookie persistence and connection pooling"""
    
    def __init__(self):
        self.domain_sessions: Dict[str, Dict] = {}
    
    def get_session_data(self, url: str) -> Dict:
        """Get or create session data for domain"""
        domain = urlparse(url).netloc
        
        if domain not in self.domain_sessions:
            self.domain_sessions[domain] = {
                "cookies": {},
                "created_at": time.time(),
                "request_count": 0,
            }
        
        return self.domain_sessions[domain]
    
    def update_session(self, url: str, response_headers: Dict, response_cookies: Dict = None) -> None:
        """Update session data with response information"""
        session_data = self.get_session_data(url)
        session_data["request_count"] += 1
        session_data["last_request"] = time.time()
        
        # Update cookies if provided
        if response_cookies:
            session_data["cookies"].update(response_cookies)
    
    def get_session_headers(self, url: str) -> Dict[str, str]:
        """Get session-specific headers including cookies"""
        session_data = self.get_session_data(url)
        headers = {}
        
        # Add cookies if we have them
        if session_data["cookies"]:
            cookie_string = "; ".join([f"{k}={v}" for k, v in session_data["cookies"].items()])
            headers["Cookie"] = cookie_string
        
        return headers
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> None:
        """Remove old session data to prevent memory leaks"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        domains_to_remove = []
        for domain, session_data in self.domain_sessions.items():
            if current_time - session_data["created_at"] > max_age_seconds:
                domains_to_remove.append(domain)
        
        for domain in domains_to_remove:
            del self.domain_sessions[domain]
            logger.debug(f"Cleaned up old session for {domain}")