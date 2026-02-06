"""Browser Controller using Playwright with SPA awareness."""

import asyncio
import re
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
except ImportError:
    raise ImportError("playwright not installed. Run: pip install playwright && playwright install chromium")

logger = logging.getLogger(__name__)

# Load JavaScript from extractor.js
def load_js_scripts():
    js_path = Path(__file__).parent / "extractor.js"
    with open(js_path, "r") as f:
        js_source = f.read()
    
    def extract_js_block(name):
        pattern = rf'const {name} = `(.*?)`\s*;'
        match = re.search(pattern, js_source, re.DOTALL)
        if match:
            return match.group(1)
        raise ValueError(f"Could not find {name} in extractor.js")
    
    return {
        "CONSOLE_CAPTURE_INIT": extract_js_block("CONSOLE_CAPTURE_INIT"),
        "GET_CONSOLE_LOGS": extract_js_block("GET_CONSOLE_LOGS"),
        "EXTRACT_PAGE_DATA": extract_js_block("EXTRACT_PAGE_DATA"),
        "DETECT_INTERACTIONS": extract_js_block("DETECT_INTERACTIONS"),
        "CHECK_RESULT": extract_js_block("CHECK_RESULT"),
    }

JS_SCRIPTS = load_js_scripts()


class BrowserController:
    """Playwright-based browser controller with SPA awareness."""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.dialog_messages: List[str] = []
    
    async def start(self):
        """Launch browser and set up page with console capture."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Install console capture BEFORE any page loads
        await self.context.add_init_script(JS_SCRIPTS["CONSOLE_CAPTURE_INIT"])
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)
        
        # Handle dialogs (alerts, confirms, prompts)
        self.page.on("dialog", self._handle_dialog)
        
        logger.info("Browser started successfully")
    
    async def _handle_dialog(self, dialog):
        """Capture and dismiss dialogs."""
        message = dialog.message
        self.dialog_messages.append(message)
        logger.info(f"Dialog captured: {message}")
        await dialog.accept()
    
    async def close(self):
        """Close browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed")
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def navigate(self, url: str, wait_for_idle: bool = True):
        """Navigate to URL with proper waiting."""
        logger.info(f"Navigating to: {url}")
        
        try:
            await self.page.goto(url, wait_until="networkidle" if wait_for_idle else "domcontentloaded")
        except Exception as e:
            logger.warning(f"Navigation timeout, continuing anyway: {e}")
        
        # Extra render delay for SPAs
        await asyncio.sleep(1.5)
        
        # Wait for any spinners to disappear
        await self._wait_for_no_spinners()
    
    async def _wait_for_no_spinners(self, timeout: int = 5000):
        """Wait for loading spinners to disappear."""
        spinner_selectors = [
            ".loading", ".spinner", "[class*='loading']", "[class*='spinner']",
            ".loader", "[class*='loader']", "[aria-busy='true']"
        ]
        
        for selector in spinner_selectors:
            try:
                await self.page.wait_for_selector(selector, state="hidden", timeout=timeout)
            except:
                pass
    
    async def reload_page(self):
        """Full page reload to clear stale state."""
        logger.info("Reloading page")
        await self.page.reload(wait_until="networkidle")
        await asyncio.sleep(1.0)
    
    async def extract_page_data(self) -> Dict[str, Any]:
        """Run the 25-category extractor."""
        try:
            data = await self.page.evaluate(JS_SCRIPTS["EXTRACT_PAGE_DATA"])
            data["dialog_messages"] = self.dialog_messages.copy()
            self.dialog_messages.clear()
            return data
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"error": str(e), "dialog_messages": self.dialog_messages.copy()}
    
    async def get_console_logs(self) -> List[Dict]:
        """Get captured console output."""
        try:
            return await self.page.evaluate(JS_SCRIPTS["GET_CONSOLE_LOGS"])
        except Exception as e:
            logger.error(f"Failed to get console logs: {e}")
            return []
    
    async def detect_interactions(self) -> List[Dict]:
        """Find interactive elements."""
        try:
            return await self.page.evaluate(JS_SCRIPTS["DETECT_INTERACTIONS"])
        except Exception as e:
            logger.error(f"Failed to detect interactions: {e}")
            return []
    
    async def check_result(self) -> Dict[str, Any]:
        """Check for success/failure/completion indicators."""
        try:
            return await self.page.evaluate(JS_SCRIPTS["CHECK_RESULT"])
        except Exception as e:
            logger.error(f"Failed to check result: {e}")
            return {"success": False, "failure": False, "complete": False}
    
    async def click(self, selector: str, timeout: int = 5000, force: bool = False) -> bool:
        """Click an element."""
        try:
            await self.page.click(selector, timeout=timeout, force=force)
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            logger.debug(f"Click failed on {selector}: {e}")
            # Try with force if normal click failed
            if not force:
                try:
                    await self.page.click(selector, timeout=timeout, force=True)
                    await asyncio.sleep(0.3)
                    return True
                except:
                    pass
            return False
    
    async def click_text(self, text: str, timeout: int = 5000) -> bool:
        """Click element containing text."""
        try:
            await self.page.click(f"text={text}", timeout=timeout)
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            logger.debug(f"Click text failed for '{text}': {e}")
            return False
    
    async def type_text(self, selector: str, text: str, clear_first: bool = True) -> bool:
        """Type text into an input field."""
        try:
            if clear_first:
                await self.page.fill(selector, "")
            await self.page.fill(selector, text)
            return True
        except Exception as e:
            logger.debug(f"Type failed on {selector}: {e}")
            return False
    
    async def submit_form(self, input_selector: str = None) -> bool:
        """Submit form by pressing Enter or clicking submit button."""
        try:
            if input_selector:
                await self.page.press(input_selector, "Enter")
            else:
                # Try to find and click submit button
                submit_selectors = [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button:has-text('Submit')",
                    "button:has-text('Enter')",
                    "button:has-text('Go')",
                ]
                for selector in submit_selectors:
                    if await self.click(selector, timeout=1000):
                        return True
                # Fallback: press Enter on focused element
                await self.page.keyboard.press("Enter")
            return True
        except Exception as e:
            logger.debug(f"Submit failed: {e}")
            return False
    
    async def hover(self, selector: str, timeout: int = 5000) -> bool:
        """Hover over an element."""
        try:
            await self.page.hover(selector, timeout=timeout)
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.debug(f"Hover failed on {selector}: {e}")
            return False
    
    async def press_key(self, key: str) -> bool:
        """Press a keyboard key."""
        try:
            await self.page.keyboard.press(key)
            return True
        except Exception as e:
            logger.debug(f"Key press failed for {key}: {e}")
            return False
    
    async def scroll(self, direction: str = "down", amount: int = 500) -> bool:
        """Scroll the page."""
        try:
            if direction == "down":
                await self.page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                await self.page.evaluate(f"window.scrollBy(0, -{amount})")
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            logger.debug(f"Scroll failed: {e}")
            return False
    
    async def select_option(self, selector: str, value: str) -> bool:
        """Select an option from a dropdown."""
        try:
            await self.page.select_option(selector, value)
            return True
        except Exception as e:
            logger.debug(f"Select failed on {selector}: {e}")
            return False
    
    async def drag(self, source_selector: str, target_selector: str) -> bool:
        """Drag element from source to target."""
        try:
            await self.page.drag_and_drop(source_selector, target_selector)
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            logger.debug(f"Drag failed: {e}")
            return False
    
    async def take_screenshot_base64(self) -> str:
        """Take screenshot and return as base64."""
        try:
            screenshot = await self.page.screenshot(type="png")
            import base64
            return base64.b64encode(screenshot).decode("utf-8")
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ""
    
    async def execute_js(self, script: str) -> Any:
        """Execute arbitrary JavaScript."""
        try:
            return await self.page.evaluate(script)
        except Exception as e:
            logger.error(f"JS execution failed: {e}")
            return None
    
    async def get_text(self) -> str:
        """Get all visible text on page."""
        try:
            return await self.page.inner_text("body")
        except Exception as e:
            logger.error(f"Get text failed: {e}")
            return ""
    
    async def wait_for_dom_stable(self, timeout: int = 2000):
        """Wait for DOM to stabilize."""
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            await asyncio.sleep(0.5)
        except:
            pass
    
    async def find_data_attributes(self, attr_name: str) -> Dict[str, str]:
        """Find all elements with a specific data attribute."""
        try:
            return await self.page.evaluate(f"""
                (function() {{
                    const result = {{}};
                    const elements = document.querySelectorAll('[{attr_name}]');
                    elements.forEach((el, i) => {{
                        result['element_' + i] = el.getAttribute('{attr_name}');
                    }});
                    return result;
                }})();
            """)
        except Exception as e:
            logger.error(f"Find data attributes failed: {e}")
            return {}
    
    async def get_current_url(self) -> str:
        """Get current page URL."""
        return self.page.url
    
    async def dismiss_popups(self) -> int:
        """Dismiss any visible popups/modals."""
        dismissed = 0
        
        # Use JavaScript to remove ALL blocking overlays and modals
        try:
            removed = await self.page.evaluate("""
                (() => {
                    let removed = 0;
                    
                    // Remove fixed overlays with high z-index
                    const fixedElements = document.querySelectorAll('.fixed');
                    fixedElements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        const zIndex = parseInt(style.zIndex) || 0;
                        // Remove elements with z-index > 9000 (likely modals/overlays)
                        if (zIndex > 9000) {
                            el.remove();
                            removed++;
                        }
                    });
                    
                    // Remove common overlay patterns
                    const overlaySelectors = [
                        '[class*="overlay"]',
                        '[class*="modal"]',
                        '[class*="popup"]',
                        '.bg-black\\\\/70',
                        '.bg-black\\\\/80',
                        '[class*="z-[999"]',
                        '[class*="z-[1000"]'
                    ];
                    
                    overlaySelectors.forEach(selector => {
                        try {
                            document.querySelectorAll(selector).forEach(el => {
                                if (el.classList.contains('fixed') || 
                                    window.getComputedStyle(el).position === 'fixed') {
                                    el.remove();
                                    removed++;
                                }
                            });
                        } catch (e) {}
                    });
                    
                    return removed;
                })()
            """)
            dismissed += removed
        except Exception as e:
            logger.debug(f"Failed to remove overlays via JS: {e}")
        
        # Then try close buttons
        close_selectors = [
            "[aria-label='Close']",
            ".close-button",
            ".modal-close",
            "button:has-text('Close')",
            "button:has-text('×')",
            "button:has-text('X')",
            ".dismiss",
            "[data-dismiss]",
        ]
        
        for selector in close_selectors:
            try:
                if await self.click(selector, timeout=500, force=True):
                    dismissed += 1
                    await asyncio.sleep(0.2)
            except:
                pass
        
        return dismissed
