"""
Browser automation fallback using Playwright for heavily protected websites.
Used when traditional HTTP requests fail due to JavaScript requirements or anti-bot protection.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Playwright not available: {e}")
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = None
    BrowserContext = None
    Page = None


class BrowserAutomation:
    """Handles browser automation for sites that block traditional scraping"""
    
    def __init__(self):
        self.browser: Optional['Browser'] = None
        self.context: Optional['BrowserContext'] = None
        self._playwright = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required for browser automation. Install with: pip install playwright")
        
        self._playwright = await async_playwright().start()
        
        # Launch browser with realistic settings
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-default-apps',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
            ]
        )
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
        )
        
        # Add realistic browser behavior
        await self.context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Intl.DateTimeFormat().resolvedOptions().timeZone === 'Asia/Kolkata' ? 'denied' : 'granted' }) :
                    originalQuery(parameters)
            );
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def fetch_page_content(self, url: str, wait_for_content: bool = True) -> tuple[str, str]:
        """
        Fetch page content using browser automation
        
        Returns:
            tuple: (page_html, page_title)
        """
        if not self.context:
            raise RuntimeError("Browser automation not initialized. Use async context manager.")
        
        page = await self.context.new_page()
        
        try:
            logger.info(f"Loading page with Playwright: {url}")
            
            # Navigate to page with realistic timing
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait a bit for any dynamic content
            await asyncio.sleep(2)
            
            # Check if we hit a blocking page
            page_text = await page.text_content('body') or ""
            if self._is_blocked_page(page_text.lower()):
                logger.warning(f"Detected blocking page for {url}")
                
                # Try some basic evasion techniques
                await self._try_bypass_techniques(page)
                
                # Wait and check again
                await asyncio.sleep(3)
                page_text = await page.text_content('body') or ""
                if self._is_blocked_page(page_text.lower()):
                    raise Exception("Page appears to be blocking automated access even with browser automation")
            
            # Wait for recipe-specific content if requested
            if wait_for_content:
                await self._wait_for_recipe_content(page)
            
            # Get final page content
            html_content = await page.content()
            page_title = await page.title()
            
            logger.debug(f"Successfully loaded page: {page_title[:50]}...")
            
            return html_content, page_title
            
        except Exception as e:
            logger.error(f"Browser automation failed for {url}: {e}")
            raise
        finally:
            await page.close()
    
    async def _wait_for_recipe_content(self, page: 'Page') -> None:
        """Wait for recipe content to load"""
        try:
            # Wait for common recipe selectors to appear
            recipe_selectors = [
                'script[type="application/ld+json"]',
                '[itemprop="recipeIngredient"]',
                '.recipe-ingredients',
                '.wprm-recipe',
                '.recipe-card',
                '.ingredients',
                '.recipe'
            ]
            
            # Try to wait for any recipe content (with timeout)
            for selector in recipe_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    logger.debug(f"Found recipe content: {selector}")
                    break
                except:
                    continue
            
            # Wait for any lazy-loaded images
            await page.wait_for_load_state('networkidle', timeout=10000)
            
        except Exception as e:
            logger.debug(f"Recipe content wait completed with timeout: {e}")
            # Don't fail if we can't find recipe content - page might still be parseable
    
    async def _try_bypass_techniques(self, page: 'Page') -> None:
        """Try basic techniques to bypass blocking pages"""
        try:
            # Look for and click "Continue" or similar buttons
            continue_buttons = [
                'button:has-text("Continue")',
                'button:has-text("Proceed")',
                'a:has-text("Continue")',
                'a:has-text("Proceed")',
                '[id*="continue"]',
                '[class*="continue"]'
            ]
            
            for selector in continue_buttons:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.debug(f"Clicking continue button: {selector}")
                        await element.click()
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            # Try scrolling (some sites require it)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            await asyncio.sleep(1)
            
            # Try mouse movement (appear more human-like)
            await page.mouse.move(100, 100)
            await asyncio.sleep(0.5)
            await page.mouse.move(200, 200)
            
        except Exception as e:
            logger.debug(f"Bypass techniques failed: {e}")
    
    def _is_blocked_page(self, page_text: str) -> bool:
        """Check if page content indicates blocking"""
        blocking_indicators = [
            'access denied', 'forbidden', 'blocked',
            'verify you are human', 'captcha', 'are you a robot',
            'cloudflare', 'ddos protection', 'rate limit',
            'security check', 'suspicious activity', 'bot detected',
            'checking your browser', 'moment please',
            'error 1020', 'error 1015', 'error 1012',
            'please enable javascript',
            'service unavailable', 'temporarily unavailable'
        ]
        
        return any(indicator in page_text for indicator in blocking_indicators)
    
    async def test_browser_availability(self) -> bool:
        """Test if browser automation is working"""
        if not PLAYWRIGHT_AVAILABLE:
            return False
        
        try:
            async with BrowserAutomation() as browser:
                html, title = await browser.fetch_page_content("https://httpbin.org/user-agent")
                return "Mozilla" in html
        except Exception as e:
            logger.error(f"Browser automation test failed: {e}")
            return False


async def get_page_with_browser(url: str) -> tuple[str, str]:
    """
    Standalone function to get page content using browser automation
    
    Returns:
        tuple: (page_html, page_title)
    """
    async with BrowserAutomation() as browser:
        return await browser.fetch_page_content(url)


# Utility function for testing
async def test_browser_automation():
    """Test browser automation functionality"""
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright not available")
        return False
    
    try:
        async with BrowserAutomation() as browser:
            test_available = await browser.test_browser_availability()
            print(f"Browser automation test: {'PASSED' if test_available else 'FAILED'}")
            return test_available
    except Exception as e:
        print(f"Browser automation test failed: {e}")
        return False


if __name__ == "__main__":
    # Run test if called directly
    asyncio.run(test_browser_automation())