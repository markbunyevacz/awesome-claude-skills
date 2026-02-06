"""Orchestrator with route discovery, time budget management, and metrics."""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path

from browser import BrowserController
from llm_client import LLMClient
from solver import ChallengeSolver, ChallengeResult

logger = logging.getLogger(__name__)

TARGET_URL = "https://serene-frangipane-7fd25b.netlify.app"
MAX_TIME_SECONDS = 300  # 5 minutes
MAX_CHALLENGES = 30


@dataclass
class RunMetrics:
    """Track metrics for the entire run."""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    challenges_completed: int = 0
    challenges_failed: int = 0
    challenges_skipped: int = 0
    total_attempts: int = 0
    challenge_results: List[Dict[str, Any]] = field(default_factory=list)
    aborted: bool = False
    abort_reason: Optional[str] = None
    
    @property
    def elapsed_time(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def under_5_minutes(self) -> bool:
        return self.elapsed_time < MAX_TIME_SECONDS
    
    def finish(self, aborted: bool = False, reason: str = None):
        self.end_time = time.time()
        self.aborted = aborted
        self.abort_reason = reason
    
    def add_challenge_result(self, challenge_num: int, result: ChallengeResult):
        self.challenge_results.append({
            "challenge": challenge_num,
            "success": result.success,
            "answer": result.answer_submitted,
            "attempts": result.attempts,
            "time_taken": round(result.time_taken, 2),
            "error": result.error,
            "tried_answers": list(result.tried_answers),
        })
        
        self.total_attempts += result.attempts
        if result.success:
            self.challenges_completed += 1
        else:
            self.challenges_failed += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "elapsed_time_seconds": round(self.elapsed_time, 2),
            "under_5_minutes": self.under_5_minutes,
            "challenges_completed": self.challenges_completed,
            "challenges_failed": self.challenges_failed,
            "challenges_skipped": self.challenges_skipped,
            "total_attempts": self.total_attempts,
            "success_rate": round(self.challenges_completed / max(1, self.challenges_completed + self.challenges_failed), 2),
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "challenge_results": self.challenge_results,
        }
    
    def save(self, filepath: str, llm_stats: Dict = None):
        data = self.to_dict()
        if llm_stats:
            data["llm_stats"] = llm_stats
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Metrics saved to {filepath}")
    
    def print_summary(self, llm_stats: Dict = None):
        print("\n" + "=" * 50)
        print("RUN SUMMARY")
        print("=" * 50)
        print(f"Time: {self.elapsed_time:.1f}s / {MAX_TIME_SECONDS}s")
        print(f"Under 5 minutes: {'YES' if self.under_5_minutes else 'NO'}")
        print(f"Challenges completed: {self.challenges_completed}/{MAX_CHALLENGES}")
        print(f"Challenges failed: {self.challenges_failed}")
        print(f"Total attempts: {self.total_attempts}")
        
        if llm_stats:
            print(f"LLM calls: {llm_stats.get('total_calls', 0)}")
            print(f"LLM cost: ${llm_stats.get('total_cost_usd', 0):.4f}")
        
        if self.aborted:
            print(f"ABORTED: {self.abort_reason}")
        
        print("=" * 50)


class ChallengeRunner:
    """Main orchestrator for running all challenges."""
    
    def __init__(
        self,
        llm: LLMClient,
        headless: bool = True,
        timeout_seconds: int = MAX_TIME_SECONDS,
        verbose: bool = True,
    ):
        self.llm = llm
        self.headless = headless
        self.timeout = timeout_seconds
        self.verbose = verbose
        self.metrics = RunMetrics()
        
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def log(self, msg: str, level: str = "info"):
        if self.verbose:
            elapsed = time.time() - self.metrics.start_time
            prefix = f"[{elapsed:6.1f}s]"
            getattr(logger, level)(f"{prefix} {msg}")
    
    def time_remaining(self) -> float:
        return self.timeout - (time.time() - self.metrics.start_time)
    
    async def discover_route_pattern(self, browser: BrowserController) -> Optional[str]:
        """Discover the URL pattern for challenges."""
        self.log("Discovering route pattern...")
        
        # Strategy 1: Check if there's a START button
        try:
            page_text = await browser.get_text()
            if "START" in page_text.upper():
                self.log("Found START button, clicking...")
                await browser.click_text("START", timeout=5000)
                await asyncio.sleep(2.0)
                
                # Check new URL
                url = await browser.get_current_url()
                self.log(f"After START, URL: {url}")
                
                # Extract pattern
                if "/step" in url or "/challenge" in url:
                    return url
        except Exception as e:
            self.log(f"START button strategy failed: {e}", "debug")
        
        # Strategy 2: Look for links to challenges
        try:
            data = await browser.extract_page_data()
            body_text = data.get("bodyText", "")
            
            # Check for challenge/step links in page
            import re
            patterns = [
                r'href=["\']([^"\']*(?:challenge|step)[^"\']*)["\']',
                r'(\/(?:challenge|step)\/?\d+)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, body_text + str(data))
                if matches:
                    self.log(f"Found route pattern: {matches[0]}")
                    return matches[0]
        except Exception as e:
            self.log(f"Link discovery failed: {e}", "debug")
        
        # Strategy 3: Try common URL patterns
        base_url = TARGET_URL.rstrip("/")
        patterns_to_try = [
            f"{base_url}/step1",
            f"{base_url}/step/1",
            f"{base_url}/challenge/1",
            f"{base_url}/challenge1",
            f"{base_url}/1",
        ]
        
        for pattern in patterns_to_try:
            try:
                await browser.navigate(pattern, wait_for_idle=False)
                await asyncio.sleep(1.0)
                
                url = await browser.get_current_url()
                page_text = await browser.get_text()
                
                # Check if we're on a challenge page
                if "challenge" in page_text.lower() or "step" in page_text.lower():
                    self.log(f"Found working pattern: {pattern}")
                    return pattern
            except:
                continue
        
        self.log("Could not discover route pattern, using landing page", "warning")
        return None
    
    async def run(self) -> RunMetrics:
        """Run all challenges with timeout enforcement."""
        self.log(f"Starting challenge run (timeout: {self.timeout}s)")
        
        async with BrowserController(headless=self.headless) as browser:
            try:
                # Navigate to target
                self.log(f"Navigating to {TARGET_URL}")
                await browser.navigate(TARGET_URL)
                
                # Dismiss any initial popups
                dismissed = await browser.dismiss_popups()
                if dismissed > 0:
                    self.log(f"Dismissed {dismissed} initial popup(s)")
                
                # Discover route pattern
                route = await self.discover_route_pattern(browser)
                
                # Create solver
                solver = ChallengeSolver(browser, self.llm, verbose=self.verbose)
                
                current_challenge = 1
                consecutive_failures = 0
                max_consecutive_failures = 3
                
                while current_challenge <= MAX_CHALLENGES:
                    # Check timeout
                    if self.time_remaining() <= 0:
                        self.metrics.finish(aborted=True, reason="Time limit exceeded")
                        self.log("TIME LIMIT EXCEEDED", "warning")
                        break
                    
                    # Calculate adaptive timeout for this challenge
                    remaining = self.time_remaining()
                    challenges_left = MAX_CHALLENGES - current_challenge + 1
                    adaptive_timeout = min(25, remaining / max(1, challenges_left))
                    
                    self.log(f"\n{'='*40}")
                    self.log(f"Challenge {current_challenge}/{MAX_CHALLENGES} (timeout: {adaptive_timeout:.1f}s)")
                    self.log(f"Time remaining: {remaining:.1f}s")
                    
                    # Solve the challenge
                    result = await solver.solve(current_challenge)
                    self.metrics.add_challenge_result(current_challenge, result)
                    
                    if result.success:
                        consecutive_failures = 0
                        self.log(f"Challenge {current_challenge} COMPLETED")
                        
                        # Wait for page transition
                        await asyncio.sleep(1.0)
                        
                        # Check if we need to click "Next" or similar
                        await self._try_advance(browser)
                        
                    else:
                        consecutive_failures += 1
                        self.log(f"Challenge {current_challenge} FAILED ({consecutive_failures} consecutive)", "warning")
                        
                        if consecutive_failures >= max_consecutive_failures:
                            self.log("Too many consecutive failures, attempting to skip", "warning")
                            await self._try_advance(browser)
                            consecutive_failures = 0
                    
                    # Move to next challenge
                    current_challenge += 1
                    
                    # Check for completion
                    check = await browser.check_result()
                    if check.get("complete"):
                        self.log("ALL CHALLENGES COMPLETED!")
                        break
                
                self.metrics.finish()
                
            except Exception as e:
                self.log(f"Fatal error: {e}", "error")
                self.metrics.finish(aborted=True, reason=str(e))
                raise
        
        return self.metrics
    
    async def _try_advance(self, browser: BrowserController):
        """Try to advance to the next challenge."""
        advance_buttons = [
            "Next", "Continue", "Proceed", "Advance", "Go", "Submit",
            "Next Challenge", "Move On", "Keep Going"
        ]
        
        for btn_text in advance_buttons:
            try:
                if await browser.click_text(btn_text, timeout=1000):
                    self.log(f"Clicked '{btn_text}' to advance")
                    await asyncio.sleep(0.5)
                    return
            except:
                continue


def run_challenge(
    provider: str = "anthropic",
    model: Optional[str] = None,
    headless: bool = True,
    timeout: int = MAX_TIME_SECONDS,
    output_file: str = "run_stats.json",
    verbose: bool = True,
) -> RunMetrics:
    """Convenience function to run the full challenge."""
    from llm_client import get_client
    
    llm = get_client(provider, model)
    runner = ChallengeRunner(
        llm,
        headless=headless,
        timeout_seconds=timeout,
        verbose=verbose,
    )
    
    metrics = asyncio.run(runner.run())
    
    # Save metrics
    llm_stats = llm.stats.to_dict()
    metrics.save(output_file, llm_stats)
    metrics.print_summary(llm_stats)
    
    return metrics
