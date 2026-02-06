"""Per-challenge solver with anti-loop mechanisms."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass, field

from browser import BrowserController
from llm_client import LLMClient

logger = logging.getLogger(__name__)

# Anti-loop constants
MAX_ATTEMPTS_PER_CHALLENGE = 3
PER_CHALLENGE_TIMEOUT = 25  # seconds
MIN_ANSWER_LENGTH = 2
MAX_ANSWER_LENGTH = 20


@dataclass
class ChallengeResult:
    """Result of solving a single challenge."""
    success: bool
    answer_submitted: Optional[str] = None
    attempts: int = 0
    time_taken: float = 0.0
    error: Optional[str] = None
    tried_answers: Set[str] = field(default_factory=set)


class ChallengeSolver:
    """Solver for individual challenges with 3-attempt escalation."""
    
    def __init__(self, browser: BrowserController, llm: LLMClient, verbose: bool = True):
        self.browser = browser
        self.llm = llm
        self.verbose = verbose
    
    def log(self, msg: str, level: str = "info"):
        if self.verbose:
            getattr(logger, level)(msg)
    
    async def solve(self, challenge_number: int) -> ChallengeResult:
        """
        Solve a single challenge with 3-attempt escalation:
        1. Text extraction → LLM analysis → submit
        2. Detect interactions → perform them → re-extract → LLM → submit
        3. Screenshot → vision LLM → submit
        """
        result = ChallengeResult(success=False)
        start_time = time.time()
        tried_answers: Set[str] = set()
        
        self.log(f"=== Solving Challenge {challenge_number} ===")
        
        for attempt in range(1, MAX_ATTEMPTS_PER_CHALLENGE + 1):
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > PER_CHALLENGE_TIMEOUT:
                result.error = f"Timeout after {elapsed:.1f}s"
                self.log(f"Challenge {challenge_number} timed out", "warning")
                break
            
            self.log(f"Attempt {attempt}/{MAX_ATTEMPTS_PER_CHALLENGE}")
            result.attempts = attempt
            
            # Dismiss any blocking popups before each attempt
            try:
                dismissed = await self.browser.dismiss_popups()
                if dismissed > 0:
                    self.log(f"Dismissed {dismissed} popup(s)")
            except Exception as e:
                self.log(f"Popup dismissal error: {e}", "debug")
            
            try:
                if attempt == 1:
                    # Attempt 1: Text extraction only
                    answer = await self._attempt_text_extraction(tried_answers)
                elif attempt == 2:
                    # Attempt 2: Interactions + re-extraction (no page reload - causes 404 in SPA)
                    answer = await self._attempt_with_interactions(tried_answers)
                else:
                    # Attempt 3: Vision fallback (no page reload - causes 404 in SPA)
                    answer = await self._attempt_vision(tried_answers)
                
                if answer and self._is_valid_answer(answer):
                    if answer in tried_answers:
                        self.log(f"Answer '{answer}' already tried, skipping", "warning")
                        continue
                    
                    tried_answers.add(answer)
                    result.tried_answers = tried_answers
                    
                    # Submit the answer
                    submitted = await self._submit_answer(answer)
                    if submitted:
                        result.answer_submitted = answer
                        
                        # Check if successful
                        await asyncio.sleep(1.0)
                        check = await self.browser.check_result()
                        
                        if check.get("success"):
                            result.success = True
                            self.log(f"Challenge {challenge_number} SOLVED with '{answer}'")
                            break
                        elif check.get("failure"):
                            self.log(f"Answer '{answer}' was incorrect", "warning")
                        else:
                            # Ambiguous - check if we moved to next challenge
                            new_check = await self.browser.check_result()
                            if new_check.get("challengeNumber", 0) > challenge_number:
                                result.success = True
                                self.log(f"Challenge {challenge_number} SOLVED (detected progression)")
                                break
                else:
                    self.log(f"No valid answer found in attempt {attempt}", "warning")
                    
            except Exception as e:
                self.log(f"Attempt {attempt} error: {e}", "error")
                result.error = str(e)
        
        result.time_taken = time.time() - start_time
        result.tried_answers = tried_answers
        
        if not result.success:
            self.log(f"Challenge {challenge_number} FAILED after {result.attempts} attempts", "warning")
        
        return result
    
    async def _attempt_text_extraction(self, tried_answers: Set[str]) -> Optional[str]:
        """Attempt 1: Extract page data and analyze with LLM."""
        self.log("Extracting page data...")
        
        # Get all extraction data
        page_data = await self.browser.extract_page_data()
        console_logs = await self.browser.get_console_logs()
        
        # Add console logs to page data
        page_data["consoleLogs"] = console_logs
        
        # Log extraction summary
        self._log_extraction_summary(page_data)
        
        # Analyze with LLM
        self.log("Analyzing with LLM...")
        response = self.llm.analyze_page(page_data, tried_answers)
        
        answer = response.get("answer")
        confidence = response.get("confidence", 0)
        reasoning = response.get("reasoning", "")
        interaction_needed = response.get("interaction_needed")
        
        self.log(f"LLM response: answer='{answer}', confidence={confidence}")
        self.log(f"Reasoning: {reasoning[:100]}...")
        
        # If LLM says interaction is needed, try it
        if interaction_needed and not self._is_valid_answer(answer):
            int_type = interaction_needed.get("type")
            selector = interaction_needed.get("selector")
            self.log(f"LLM suggests interaction: {int_type} on {selector}")
            
            if int_type == "click" and selector:
                await self.browser.click(selector, timeout=3000)
                await asyncio.sleep(0.5)
                # Re-extract after interaction
                page_data = await self.browser.extract_page_data()
                response = self.llm.analyze_page(page_data, tried_answers)
                answer = response.get("answer")
                self.log(f"After interaction, answer='{answer}'")
        
        return answer
    
    async def _attempt_with_interactions(self, tried_answers: Set[str]) -> Optional[str]:
        """Attempt 2: Try interactions before extracting."""
        self.log("Detecting interactions...")
        
        interactions = await self.browser.detect_interactions()
        self.log(f"Found {len(interactions)} interactive elements")
        
        # First, try to click buttons that might reveal the code
        reveal_keywords = ['reveal', 'show', 'click', 'start', 'begin', 'open', 'unlock']
        for interaction in interactions:
            int_type = interaction.get("type")
            selector = interaction.get("selector")
            text = interaction.get("text", "").lower()
            
            if not selector:
                continue
            
            # Prioritize buttons with reveal-related text
            if int_type == "click" and any(kw in text for kw in reveal_keywords):
                try:
                    self.log(f"Clicking reveal button: {selector} ({text})")
                    await self.browser.click(selector, timeout=2000)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.log(f"Click failed: {e}", "debug")
        
        # Try common interactions
        for interaction in interactions[:5]:  # Limit to first 5
            int_type = interaction.get("type")
            selector = interaction.get("selector")
            
            if not selector:
                continue
            
            try:
                if int_type == "click":
                    self.log(f"Clicking: {selector}")
                    await self.browser.click(selector, timeout=2000)
                elif int_type == "hover":
                    self.log(f"Hovering: {selector}")
                    await self.browser.hover(selector, timeout=2000)
                elif int_type == "scroll":
                    self.log("Scrolling page")
                    await self.browser.scroll("down", 500)
                
                await asyncio.sleep(0.5)
            except Exception as e:
                self.log(f"Interaction failed: {e}", "debug")
        
        # Also try scrolling to reveal hidden content
        await self.browser.scroll("down", 1000)
        await asyncio.sleep(0.5)
        await self.browser.scroll("up", 500)
        
        # Now extract and analyze
        return await self._attempt_text_extraction(tried_answers)
    
    async def _attempt_vision(self, tried_answers: Set[str]) -> Optional[str]:
        """Attempt 3: Use screenshot + vision LLM."""
        self.log("Taking screenshot for vision analysis...")
        
        screenshot = await self.browser.take_screenshot_base64()
        if not screenshot:
            self.log("Failed to take screenshot", "error")
            return None
        
        self.log("Analyzing screenshot with vision LLM...")
        response = self.llm.analyze_screenshot(screenshot, tried_answers)
        
        answer = response.get("answer")
        confidence = response.get("confidence", 0)
        reasoning = response.get("reasoning", "")
        
        self.log(f"Vision response: answer='{answer}', confidence={confidence}")
        self.log(f"Reasoning: {reasoning[:100]}...")
        
        return answer
    
    async def _submit_answer(self, answer: str) -> bool:
        """Submit an answer to the challenge."""
        self.log(f"Submitting answer: '{answer}'")
        
        # Find input field
        page_data = await self.browser.extract_page_data()
        input_fields = page_data.get("inputFields", [])
        
        # Try to find the right input field
        input_selector = None
        for field in input_fields:
            selector = field.get("selector")
            if selector:
                input_selector = selector
                break
        
        # Fallback selectors
        if not input_selector:
            fallback_selectors = [
                "input[type='text']",
                "input[placeholder*='code' i]",
                "input[placeholder*='answer' i]",
                "input:not([type='hidden'])",
                "input",
            ]
            for selector in fallback_selectors:
                try:
                    if await self.browser.type_text(selector, answer):
                        input_selector = selector
                        break
                except:
                    continue
        
        if input_selector:
            await self.browser.type_text(input_selector, answer)
            await asyncio.sleep(0.3)
            
            # Submit
            submitted = await self.browser.submit_form(input_selector)
            return submitted
        
        self.log("Could not find input field", "warning")
        return False
    
    def _is_valid_answer(self, answer: Any) -> bool:
        """Check if answer is valid."""
        if answer is None:
            return False
        if not isinstance(answer, str):
            answer = str(answer)
        answer = answer.strip()
        
        # Reject common invalid responses from LLM
        invalid_answers = ['none', 'null', 'n/a', 'unknown', '404', 'error', 'undefined']
        if answer.lower() in invalid_answers:
            return False
        
        if len(answer) < MIN_ANSWER_LENGTH or len(answer) > MAX_ANSWER_LENGTH:
            return False
        return True
    
    def _log_extraction_summary(self, data: Dict[str, Any]):
        """Log a summary of extracted data."""
        summary = []
        
        if data.get("hiddenElements"):
            summary.append(f"Hidden elements: {len(data['hiddenElements'])}")
        if data.get("comments"):
            summary.append(f"Comments: {len(data['comments'])}")
        if data.get("dataAttributes"):
            summary.append(f"Data attrs: {len(data['dataAttributes'])}")
        if data.get("consoleLogs"):
            summary.append(f"Console logs: {len(data['consoleLogs'])}")
        if data.get("globalVars"):
            summary.append(f"Global vars: {len(data['globalVars'])}")
        if data.get("storage", {}).get("localStorage"):
            summary.append(f"LocalStorage: {len(data['storage']['localStorage'])}")
        if data.get("pseudoContent"):
            summary.append(f"Pseudo content: {len(data['pseudoContent'])}")
        if data.get("shadowDOM"):
            summary.append(f"Shadow DOM: {len(data['shadowDOM'])}")
        
        if summary:
            self.log(f"Extraction: {', '.join(summary)}")
        else:
            self.log("Extraction: No hidden content found")
