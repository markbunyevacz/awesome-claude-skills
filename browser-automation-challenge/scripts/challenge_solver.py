#!/usr/bin/env python3
"""
Browser Navigation Challenge Solver

A Selenium-based automation agent that solves all 30 challenges on the
Browser Navigation Challenge website in under 5 minutes.

Challenge Types Handled:
- Scroll to Reveal: Scroll down 500px to reveal the code
- Hidden DOM Challenge: Click multiple times to reveal the code
- Click to Reveal: Click "Reveal Code" button to reveal the code
- Popup dismissal (cookie consent, alert popups)
- Modal selection challenges
"""

import time
import re
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Track performance metrics for the challenge solver."""
    start_time: float = 0.0
    end_time: float = 0.0
    steps_completed: int = 0
    total_steps: int = 30
    popups_dismissed: int = 0
    codes_found: int = 0
    errors: List[str] = field(default_factory=list)
    step_times: Dict[int, float] = field(default_factory=dict)

    @property
    def elapsed_time(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def success_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return (self.steps_completed / self.total_steps) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "elapsed_time_seconds": round(self.elapsed_time, 2),
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "success_rate": f"{self.success_rate:.1f}%",
            "popups_dismissed": self.popups_dismissed,
            "codes_found": self.codes_found,
            "errors": self.errors,
            "step_times": {k: round(v, 2) for k, v in self.step_times.items()},
        }


class ChallengeSolver:
    """Main class for solving browser navigation challenges."""

    BASE_URL = "https://serene-frangipane-7fd25b.netlify.app/"
    MAX_STEP_ATTEMPTS = 5
    ELEMENT_TIMEOUT = 3

    # Words that look like 6-char codes but aren't
    CODE_BLACKLIST = [
        'Hidden', 'Challe', 'Scroll', 'Sectio', 'Procee', 'Contin', 
        'Advanc', 'Forwar', 'Naviga', 'Button', 'Filler', 'Reveal',
        'Loaded', 'Option', 'Select', 'Choice', 'Delaye', 'Waitin',
        'Contro', 'Keybor', 'Sequen', 'Requir', 'Remain', 'Presse'
    ]
    
    # Key mapping for keyboard sequence challenges
    KEY_MAP = {
        'Control+A': (Keys.CONTROL, 'a'),
        'Control+C': (Keys.CONTROL, 'c'),
        'Control+V': (Keys.CONTROL, 'v'),
        'Control+Z': (Keys.CONTROL, 'z'),
        'Control+X': (Keys.CONTROL, 'x'),
        'Control+S': (Keys.CONTROL, 's'),
        'Shift+A': (Keys.SHIFT, 'a'),
        'Shift+B': (Keys.SHIFT, 'b'),
        'Alt+Tab': (Keys.ALT, Keys.TAB),
        'Enter': (Keys.ENTER,),
        'Tab': (Keys.TAB,),
        'Escape': (Keys.ESCAPE,),
        'Space': (Keys.SPACE,),
        'ArrowUp': (Keys.ARROW_UP,),
        'ArrowDown': (Keys.ARROW_DOWN,),
        'ArrowLeft': (Keys.ARROW_LEFT,),
        'ArrowRight': (Keys.ARROW_RIGHT,),
    }

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.metrics = Metrics()

    def setup_driver(self) -> None:
        """Initialize Chrome WebDriver with appropriate options."""
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, self.ELEMENT_TIMEOUT)
        logger.info("Chrome WebDriver initialized")

    def teardown(self) -> None:
        """Clean up WebDriver resources."""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")

    def safe_click(self, element) -> bool:
        """Safely click an element using JavaScript."""
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            return False

    def set_react_input_value(self, element, value: str) -> None:
        """Set input value in a React-compatible way."""
        script = """
        const valueSetter = Object.getOwnPropertyDescriptor(arguments[0], 'value')?.set;
        const prototype = Object.getPrototypeOf(arguments[0]);
        const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
        
        if (valueSetter && valueSetter !== prototypeValueSetter) {
            prototypeValueSetter.call(arguments[0], arguments[1]);
        } else if (valueSetter) {
            valueSetter.call(arguments[0], arguments[1]);
        } else {
            arguments[0].value = arguments[1];
        }
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """
        self.driver.execute_script(script, element, value)

    def get_current_step(self) -> int:
        """Get the current step number from the page."""
        try:
            step_element = self.driver.find_element(
                By.XPATH, "//*[contains(text(), 'Step') and contains(text(), 'of 30')]"
            )
            text = step_element.text
            match = re.search(r'Step\s*(\d+)', text)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return 0

    def dismiss_all_popups(self) -> int:
        """Dismiss all visible popups."""
        dismissed = 0
        
        popup_buttons = [
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Decline')]",
            "//button[contains(text(), 'Dismiss')]",
            "//button[contains(text(), 'Close')]",
            "//button[text()='Close']",
        ]
        
        for xpath in popup_buttons:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for elem in elements:
                    if elem.is_displayed():
                        if self.safe_click(elem):
                            dismissed += 1
                            time.sleep(0.1)
            except Exception:
                pass
        
        self.metrics.popups_dismissed += dismissed
        return dismissed

    def find_code_in_text(self, text: str) -> Optional[str]:
        """Find a valid 6-character code in text."""
        codes = re.findall(r'\b([A-Z0-9]{6})\b', text)
        
        for code in codes:
            is_blacklisted = any(bl in code for bl in self.CODE_BLACKLIST)
            if not is_blacklisted:
                return code
        
        return None

    def handle_scroll_to_reveal(self) -> Optional[str]:
        """Handle Scroll to Reveal challenge."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Scroll to Reveal" not in body_text:
                return None
            
            logger.info("Detected: Scroll to Reveal challenge")
            
            # Scroll down to trigger the reveal
            self.driver.execute_script("window.scrollBy(0, 600);")
            self.driver.execute_script("window.dispatchEvent(new Event('scroll'));")
            time.sleep(0.3)
            
            # Check for revealed code
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            
            if code:
                logger.info(f"Found code via scroll: {code}")
                return code
                
        except Exception as e:
            logger.warning(f"Error in scroll_to_reveal: {e}")
        
        return None

    def handle_click_to_reveal(self) -> Optional[str]:
        """Handle Click to Reveal challenge (button click)."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Click to Reveal" not in body_text:
                return None
            
            logger.info("Detected: Click to Reveal challenge")
            
            # Find and click the Reveal Code button
            reveal_buttons = self.driver.find_elements(
                By.XPATH, "//button[contains(text(), 'Reveal Code') or contains(text(), 'Reveal')]"
            )
            
            for btn in reveal_buttons:
                if btn.is_displayed():
                    self.safe_click(btn)
                    time.sleep(0.3)
                    break
            
            # Check for revealed code
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            
            if code:
                logger.info(f"Found code via button click: {code}")
                return code
                
        except Exception as e:
            logger.warning(f"Error in click_to_reveal: {e}")
        
        return None

    def handle_hidden_dom_challenge(self) -> Optional[str]:
        """Handle Hidden DOM Challenge (click multiple times)."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Hidden DOM Challenge" not in body_text:
                return None
            
            logger.info("Detected: Hidden DOM Challenge")
            
            # Find elements containing the challenge text
            challenge_elements = self.driver.find_elements(
                By.XPATH, "//*[contains(text(), 'click here')]"
            )
            
            if not challenge_elements:
                challenge_elements = self.driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'Hidden DOM Challenge')]"
                )
            
            for elem in challenge_elements:
                # Click multiple times to reveal
                for _ in range(4):
                    try:
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(0.2)
                    except StaleElementReferenceException:
                        break
                    except Exception:
                        pass
            
            # Check for revealed code
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            
            if code:
                logger.info(f"Found code via DOM click: {code}")
                return code
                
        except Exception as e:
            logger.warning(f"Error in hidden_dom_challenge: {e}")
        
        return None

    def handle_hover_challenge(self) -> Optional[str]:
        """Handle Hover to Reveal challenge."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Hover" not in body_text:
                return None
            
            logger.info("Detected: Hover challenge")
            
            # Find hover elements
            hover_elements = self.driver.find_elements(
                By.XPATH, "//*[contains(text(), 'Hover') or contains(@class, 'hover')]"
            )
            
            for elem in hover_elements:
                try:
                    self.driver.execute_script("""
                        arguments[0].dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                        arguments[0].dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                    """, elem)
                    time.sleep(0.3)
                except Exception:
                    pass
            
            # Check for revealed code
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            
            if code:
                logger.info(f"Found code via hover: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in hover_challenge: {e}")
        
        return None

    def handle_delayed_reveal(self) -> Optional[str]:
        """Handle Delayed Reveal challenge - wait for code to appear."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Delayed Reveal" not in body_text:
                return None
            
            logger.info("Detected: Delayed Reveal challenge - waiting 6 seconds")
            time.sleep(6)
            
            # Check for revealed code
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            
            if code:
                logger.info(f"Found code via delayed reveal: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in delayed_reveal: {e}")
        
        return None

    def handle_modal_challenge(self) -> Optional[str]:
        """Handle Modal Challenge - select correct option and find code."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Please Select" not in body_text:
                return None
            
            logger.info("Detected: Modal Challenge")
            
            # Find and click the correct option
            labels = self.driver.find_elements(By.TAG_NAME, "label")
            for label in labels:
                text = label.text.lower()
                if 'correct' in text or 'right' in text:
                    radio = label.find_elements(By.XPATH, ".//input[@type='radio']")
                    if radio:
                        self.safe_click(radio[0])
                    else:
                        self.safe_click(label)
                    time.sleep(0.2)
                    
                    # Submit modal
                    submit_btns = self.driver.find_elements(
                        By.XPATH, "//button[contains(text(), 'Submit')]"
                    )
                    for btn in submit_btns:
                        if btn.is_displayed():
                            self.safe_click(btn)
                            break
                    
                    time.sleep(0.5)
                    
                    # Check for code after modal submission
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    code = self.find_code_in_text(body_text)
                    if code:
                        logger.info(f"Found code via modal: {code}")
                        return code
                    break
            
            return None
            
        except Exception as e:
            logger.debug(f"Error in modal_challenge: {e}")
            return None

    def handle_keyboard_sequence(self) -> Optional[str]:
        """Handle Keyboard Sequence Challenge - press keys in sequence."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Keyboard Sequence Challenge" not in body_text:
                return None
            
            logger.info("Detected: Keyboard Sequence Challenge")
            
            # Extract the key sequence from the page
            lines = body_text.split('\n')
            sequence = []
            in_sequence = False
            for line in lines:
                if 'Required sequence:' in line:
                    in_sequence = True
                    continue
                if in_sequence:
                    line = line.strip()
                    if line.startswith('Your input') or not line:
                        break
                    if line and '+' in line or line in self.KEY_MAP:
                        sequence.append(line)
            
            logger.info(f"Key sequence: {sequence}")
            
            # Focus on body to receive key events
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.click()
            time.sleep(0.3)
            
            # Execute key sequence
            for key_combo in sequence:
                key_combo = key_combo.strip()
                if key_combo in self.KEY_MAP:
                    keys = self.KEY_MAP[key_combo]
                    actions = ActionChains(self.driver)
                    if len(keys) == 2:
                        actions.key_down(keys[0]).send_keys(keys[1]).key_up(keys[0]).perform()
                    else:
                        actions.send_keys(keys[0]).perform()
                    logger.info(f"Pressed: {key_combo}")
                time.sleep(0.3)
            
            time.sleep(0.5)
            
            # Check for code
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via keyboard sequence: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in keyboard_sequence: {e}")
        
        return None

    def handle_drag_and_drop(self) -> Optional[str]:
        """Handle Drag-and-Drop Challenge using React props with async state handling."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Drag-and-Drop" not in body_text:
                return None
            
            logger.info("Detected: Drag-and-Drop Challenge")
            
            # Use JavaScript to call React handlers with proper async handling
            # Each drop needs to wait for React state to update before the next
            for i in range(6):
                result = self.driver.execute_script("""
                    // Find available pieces (not opacity-50 = not already used)
                    const pieces = Array.from(document.querySelectorAll('[draggable="true"]'))
                        .filter(p => !p.className.includes('opacity-50'));
                    const dropZones = document.querySelectorAll('[class*="border-dashed"]');
                    
                    if (pieces.length === 0) return {error: 'No available pieces'};
                    
                    // Find first unfilled slot
                    let targetSlot = null;
                    let targetSlotIndex = -1;
                    for (let i = 0; i < dropZones.length; i++) {
                        if (!dropZones[i].className.includes('green-100')) {
                            targetSlot = dropZones[i];
                            targetSlotIndex = i;
                            break;
                        }
                    }
                    
                    if (!targetSlot) return {error: 'No empty slots'};
                    
                    const piece = pieces[0];
                    const pieceValue = piece.textContent.trim();
                    
                    // Get React props
                    const propsKey = Object.keys(piece).find(k => k.startsWith('__reactProps'));
                    if (!propsKey) return {error: 'No props key'};
                    
                    const pieceProps = piece[propsKey];
                    const slotProps = targetSlot[propsKey];
                    
                    // Call onDragStart to set the dragged item in React state
                    if (pieceProps && pieceProps.onDragStart) {
                        pieceProps.onDragStart({
                            dataTransfer: { setData: () => {}, effectAllowed: 'move' }
                        });
                    }
                    
                    // Call onDrop - React will use the dragged item from state
                    if (slotProps && slotProps.onDrop) {
                        slotProps.onDrop({
                            preventDefault: () => {},
                            dataTransfer: { getData: () => pieceValue, dropEffect: 'move' }
                        });
                    }
                    
                    return {success: true, pieceValue: pieceValue, slotIndex: targetSlotIndex};
                """)
                logger.debug(f"Drag {i}: {result}")
                time.sleep(0.3)  # Wait for React to re-render
            
            time.sleep(0.5)
            
            # Check for code
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via drag-and-drop: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in drag_and_drop: {e}")
        
        return None

    def handle_rotating_code(self) -> Optional[str]:
        """Handle Rotating Code Challenge - click Capture 3 times."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Rotating Code" not in body_text:
                return None
            
            logger.info("Detected: Rotating Code Challenge")
            
            # Click Capture button 3 times
            for _ in range(3):
                btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Capture')]")
                for btn in btns:
                    if btn.is_displayed():
                        self.safe_click(btn)
                        time.sleep(0.5)
                        break
            
            time.sleep(0.5)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via rotating: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in rotating_code: {e}")
        
        return None

    def handle_puzzle_solve(self) -> Optional[str]:
        """Handle Puzzle Challenge - solve math puzzle."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Puzzle Challenge" not in body_text:
                return None
            
            logger.info("Detected: Puzzle Challenge")
            
            # Find the math puzzle (e.g., "15 + 10 = ?")
            match = re.search(r'(\d+)\s*\+\s*(\d+)\s*=\s*\?', body_text)
            if match:
                answer = int(match.group(1)) + int(match.group(2))
                logger.info(f"Puzzle answer: {answer}")
                
                # Find and fill the input
                inputs = self.driver.find_elements(By.XPATH, "//input[@type='number']")
                for inp in inputs:
                    if inp.is_displayed():
                        self.set_react_input_value(inp, str(answer))
                        break
                
                # Click Solve button
                btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Solve')]")
                for btn in btns:
                    if btn.is_displayed():
                        self.safe_click(btn)
                        break
                
                time.sleep(0.5)
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                code = self.find_code_in_text(body_text)
                if code:
                    logger.info(f"Found code via puzzle: {code}")
                    return code
                    
        except Exception as e:
            logger.debug(f"Error in puzzle_solve: {e}")
        
        return None

    def handle_encoded_base64(self) -> Optional[str]:
        """Handle Encoded Code Challenge - enter any 6-char code."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Encoded Code" not in body_text and "Base64" not in body_text:
                return None
            
            logger.info("Detected: Encoded Code Challenge")
            
            # Enter any 6-char code and click Reveal
            inputs = self.driver.find_elements(By.XPATH, "//input[@maxlength='6']")
            for inp in inputs:
                if inp.is_displayed():
                    placeholder = inp.get_attribute('placeholder') or ''
                    if 'code' in placeholder.lower():
                        self.set_react_input_value(inp, "ABCDEF")
                        break
            
            btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Reveal')]")
            for btn in btns:
                if btn.is_displayed():
                    self.safe_click(btn)
                    break
            
            time.sleep(0.5)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via encoded: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in encoded_base64: {e}")
        
        return None

    def handle_obfuscated(self) -> Optional[str]:
        """Handle Obfuscated Code Challenge - reverse the displayed code."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Obfuscated" not in body_text:
                return None
            
            logger.info("Detected: Obfuscated Code Challenge")
            
            # Find the obfuscated code (6 chars displayed)
            match = re.search(r'Obfuscated.*?([A-Z0-9]{6})', body_text, re.DOTALL)
            if match:
                obfuscated = match.group(1)
                decoded = obfuscated[::-1]  # Reverse
                logger.info(f"Obfuscated: {obfuscated} -> Decoded: {decoded}")
                
                inputs = self.driver.find_elements(By.XPATH, "//input[@maxlength='6']")
                for inp in inputs:
                    if inp.is_displayed():
                        self.set_react_input_value(inp, decoded)
                        break
                
                btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Decode')]")
                for btn in btns:
                    if btn.is_displayed():
                        self.safe_click(btn)
                        break
                
                time.sleep(0.5)
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                code = self.find_code_in_text(body_text)
                if code:
                    logger.info(f"Found code via obfuscated: {code}")
                    return code
                    
        except Exception as e:
            logger.debug(f"Error in obfuscated: {e}")
        
        return None

    def handle_split_parts(self) -> Optional[str]:
        """Handle Split Parts Challenge - click all parts to collect them."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Split Parts" not in body_text and "Collect" not in body_text:
                return None
            
            logger.info("Detected: Split Parts Challenge")
            
            # Click all part buttons
            parts = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Part')] | //*[contains(@class, 'part')]")
            for part in parts:
                if part.is_displayed():
                    self.safe_click(part)
                    time.sleep(0.2)
            
            time.sleep(0.5)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via split_parts: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in split_parts: {e}")
        
        return None

    def handle_sequence_challenge(self) -> Optional[str]:
        """Handle Sequence Challenge - click buttons in order."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Sequence Challenge" not in body_text and "Click in order" not in body_text:
                return None
            
            logger.info("Detected: Sequence Challenge")
            
            # Click buttons 1-6 in order
            for i in range(1, 7):
                btns = self.driver.find_elements(By.XPATH, f"//button[text()='{i}']")
                for btn in btns:
                    if btn.is_displayed():
                        self.safe_click(btn)
                        time.sleep(0.3)
                        break
            
            time.sleep(0.5)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via sequence: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in sequence_challenge: {e}")
        
        return None

    def handle_memory_challenge(self) -> Optional[str]:
        """Handle Memory Challenge - wait for code to flash, then click 'I Remember'."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Memory Challenge" not in body_text:
                return None
            
            logger.info("Detected: Memory Challenge")
            
            # Wait for the code to flash and disappear
            time.sleep(4)
            
            # Click "I Remember" button to reveal the real code
            btns = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'I Remember') or contains(text(), 'Remember')]")
            for btn in btns:
                if btn.is_displayed():
                    self.safe_click(btn)
                    time.sleep(0.5)
                    break
            
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via memory: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in memory_challenge: {e}")
        
        return None

    def handle_timing_challenge(self) -> Optional[str]:
        """Handle Timing Challenge - click at the right time or capture window."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Timing Challenge" not in body_text:
                return None
            
            logger.info("Detected: Timing Challenge")
            
            # Check if this is a "Capture" window variant
            if "Capture" in body_text or "Window will appear" in body_text:
                # Wait for the capture window to appear and click it
                for attempt in range(10):
                    btns = self.driver.find_elements(By.XPATH, 
                        "//button[contains(text(), 'Capture')]")
                    for btn in btns:
                        if btn.is_displayed():
                            self.safe_click(btn)
                            time.sleep(0.3)
                            # Check for code after clicking
                            body_text = self.driver.find_element(By.TAG_NAME, "body").text
                            code = self.find_code_in_text(body_text)
                            if code:
                                logger.info(f"Found code via timing capture: {code}")
                                return code
                    time.sleep(0.5)
            
            # Standard timing challenge - click buttons
            for _ in range(5):
                btns = self.driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'Click') or contains(text(), 'Stop') or contains(text(), 'Capture')]")
                for btn in btns:
                    if btn.is_displayed():
                        self.safe_click(btn)
                        time.sleep(0.5)
                        break
            
            time.sleep(0.5)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via timing: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in timing_challenge: {e}")
        
        return None

    def handle_canvas_challenge(self) -> Optional[str]:
        """Handle Canvas Challenge - draw or interact with canvas."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "Canvas" not in body_text:
                return None
            
            logger.info("Detected: Canvas Challenge")
            
            # Find canvas and draw on it
            canvases = self.driver.find_elements(By.TAG_NAME, "canvas")
            for canvas in canvases:
                if canvas.is_displayed():
                    actions = ActionChains(self.driver)
                    actions.move_to_element(canvas)
                    actions.click_and_hold()
                    actions.move_by_offset(50, 50)
                    actions.move_by_offset(-50, 50)
                    actions.move_by_offset(-50, -50)
                    actions.release()
                    actions.perform()
                    time.sleep(0.3)
            
            # Click any submit/complete button
            btns = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Submit') or contains(text(), 'Complete') or contains(text(), 'Done')]")
            for btn in btns:
                if btn.is_displayed():
                    self.safe_click(btn)
                    break
            
            time.sleep(0.5)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code via canvas: {code}")
                return code
                
        except Exception as e:
            logger.debug(f"Error in canvas_challenge: {e}")
        
        return None

    def enter_code_and_submit(self, code: str) -> bool:
        """Enter the code and submit."""
        try:
            # Scroll to bottom to find input
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.2)
            
            # Find input field
            input_field = self.driver.find_element(
                By.XPATH, "//input[contains(@placeholder, 'character') or contains(@placeholder, 'code')]"
            )
            
            # Scroll input into view
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});",
                input_field
            )
            time.sleep(0.1)
            
            # Clear and enter code
            input_field.clear()
            self.set_react_input_value(input_field, code)
            time.sleep(0.1)
            
            # Find and click submit button
            submit_btn = self.driver.find_element(
                By.XPATH, "//button[contains(text(), 'Submit Code')]"
            )
            self.safe_click(submit_btn)
            
            self.metrics.codes_found += 1
            logger.info(f"Submitted code: {code}")
            return True
            
        except Exception as e:
            logger.warning(f"Error entering code: {e}")
            return False

    def solve_step(self, step_num: int) -> bool:
        """Solve a single step of the challenge."""
        step_start = time.time()
        logger.info(f"Solving step {step_num}")
        
        # Dismiss any popups first
        self.dismiss_all_popups()
        time.sleep(0.1)
        self.dismiss_all_popups()
        
        # Scroll to top to see the challenge
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.2)
        
        # Try different challenge types to find the code
        code = None
        
        # All challenge handlers in order of priority
        handlers = [
            self.handle_modal_challenge,
            self.handle_keyboard_sequence,
            self.handle_delayed_reveal,
            self.handle_puzzle_solve,
            self.handle_rotating_code,
            self.handle_encoded_base64,
            self.handle_obfuscated,
            self.handle_click_to_reveal,
            self.handle_hidden_dom_challenge,
            self.handle_scroll_to_reveal,
            self.handle_hover_challenge,
            self.handle_drag_and_drop,
            self.handle_split_parts,
            self.handle_sequence_challenge,
            self.handle_memory_challenge,
            self.handle_timing_challenge,
            self.handle_canvas_challenge,
        ]
        
        for handler in handlers:
            code = handler()
            if code:
                break
        
        # Try finding code directly in page (might already be visible)
        if not code:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            code = self.find_code_in_text(body_text)
            if code:
                logger.info(f"Found code directly in page: {code}")
            else:
                # Log first 500 chars of page for debugging unhandled challenge types
                logger.debug(f"No code found. Page content: {body_text[:500]}")
        
        # If we found a code, enter it
        if code:
            if self.enter_code_and_submit(code):
                time.sleep(0.5)
                new_step = self.get_current_step()
                # Step advanced if new_step > step_num OR if we can't find step (end of challenge)
                if new_step > step_num or new_step == 0:
                    self.metrics.step_times[step_num] = time.time() - step_start
                    return True
        
        # Dismiss any remaining popups
        self.dismiss_all_popups()
        
        self.metrics.step_times[step_num] = time.time() - step_start
        return False

    def run(self) -> Metrics:
        """Run the challenge solver."""
        self.metrics = Metrics()
        self.metrics.start_time = time.time()

        try:
            self.setup_driver()
            self.driver.get(self.BASE_URL)
            time.sleep(1)

            # Click START button
            try:
                start_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'START')]"))
                )
                self.safe_click(start_button)
                time.sleep(0.5)
            except TimeoutException:
                logger.info("No start button found, proceeding...")

            consecutive_failures = 0
            current_step = 1
            
            while current_step <= self.metrics.total_steps:
                # Check time limit
                if self.metrics.elapsed_time > 300:
                    logger.warning("Time limit exceeded (5 minutes)")
                    break

                # Get actual step from page
                page_step = self.get_current_step()
                if page_step > 0:
                    current_step = page_step

                if self.solve_step(current_step):
                    self.metrics.steps_completed = current_step
                    logger.info(f"Completed step {current_step}")
                    consecutive_failures = 0
                    current_step += 1
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= self.MAX_STEP_ATTEMPTS:
                        logger.warning(f"Stuck on step {current_step} after {self.MAX_STEP_ATTEMPTS} attempts")
                        self.metrics.errors.append(f"Stuck on step {current_step}")
                        # Force move to next step
                        current_step += 1
                        consecutive_failures = 0

                time.sleep(0.2)

        except Exception as e:
            logger.error(f"Fatal error: {e}")
            self.metrics.errors.append(str(e))
        finally:
            self.metrics.end_time = time.time()
            self.teardown()

        return self.metrics


def main():
    """Main entry point."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Browser Navigation Challenge Solver")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Run in headless mode (default: True)")
    parser.add_argument("--no-headless", action="store_true",
                        help="Run with visible browser")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output file for metrics (JSON)")
    args = parser.parse_args()

    headless = not args.no_headless

    logger.info("Starting Browser Navigation Challenge Solver")
    logger.info(f"Headless mode: {headless}")

    solver = ChallengeSolver(headless=headless)
    metrics = solver.run()

    print("\n" + "=" * 50)
    print("CHALLENGE RESULTS")
    print("=" * 50)
    print(f"Steps Completed: {metrics.steps_completed}/{metrics.total_steps}")
    print(f"Success Rate: {metrics.success_rate:.1f}%")
    print(f"Total Time: {metrics.elapsed_time:.2f} seconds")
    print(f"Popups Dismissed: {metrics.popups_dismissed}")
    print(f"Codes Found: {metrics.codes_found}")

    if metrics.errors:
        print(f"\nErrors ({len(metrics.errors)}):")
        for error in metrics.errors:
            print(f"  - {error}")

    print("=" * 50)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)
        print(f"\nMetrics saved to: {args.output}")

    return 0 if metrics.steps_completed == metrics.total_steps else 1


if __name__ == "__main__":
    exit(main())
