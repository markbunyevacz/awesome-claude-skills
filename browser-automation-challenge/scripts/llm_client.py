"""Multi-provider LLM client with token tracking."""

import os
import json
import logging
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SOLVER_SYSTEM_PROMPT = """You are a browser challenge solver. Your task is to analyze extracted page data and find the answer to submit.

IMPORTANT RULES:
1. The answer is often hidden - check ALL extraction categories carefully
2. DECODE any encoded values: base64, hex, ROT13, reversed strings, etc.
3. Look for patterns like 4-8 character alphanumeric codes
4. Check console logs, hidden elements, data attributes, comments, CSS variables
5. If you see encoded data (e.g., base64 like "SGVsbG8="), decode it before answering
6. Return ONLY the final decoded/processed answer

You must respond with valid JSON in this exact format:
{
  "answer": "THE_ANSWER_HERE",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation of where you found the answer",
  "interaction_needed": null or {"type": "click|hover|scroll|drag|keyboard", "selector": "css_selector"},
  "submit_selector": "css_selector_for_input_field",
  "submit_button": "css_selector_for_submit_button or null"
}

If you cannot find the answer, set answer to null and explain in reasoning."""

VISION_SYSTEM_PROMPT = """You are analyzing a screenshot of a browser challenge. Find the answer to submit.

Look for:
1. Text that looks like a code (4-8 alphanumeric characters)
2. Hidden or camouflaged text
3. Text in unusual places (corners, overlays, etc.)
4. Any visual puzzles or patterns

Respond with valid JSON:
{
  "answer": "THE_ANSWER_HERE",
  "confidence": 0.0 to 1.0,
  "reasoning": "Where you found the answer in the image"
}"""


@dataclass
class LLMStats:
    """Track LLM usage statistics."""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    calls_by_model: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "calls_by_model": self.calls_by_model,
        }


class LLMClient:
    """Multi-provider LLM client."""
    
    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
        "gpt-4o": {"input": 2.5, "output": 10.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    }
    
    def __init__(self, provider: str = "openrouter", model: Optional[str] = None):
        self.provider = provider
        self.stats = LLMStats()
        
        if provider == "openrouter":
            # Use Openrouter API (compatible with OpenAI format)
            api_key = os.environ.get("Openrouter") or os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("Openrouter environment variable not set")
            
            self.api_key = api_key
            self.base_url = "https://openrouter.ai/api/v1"
            self.model = model or "anthropic/claude-3.5-sonnet"
            self.client = None  # Will use requests directly
            
        elif provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise ImportError("anthropic not installed. Run: pip install anthropic")
            
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model or "claude-sonnet-4-20250514"
            
        elif provider == "openai":
            try:
                import openai
            except ImportError:
                raise ImportError("openai not installed. Run: pip install openai")
            
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            self.client = openai.OpenAI(api_key=api_key)
            self.model = model or "gpt-4o"
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        logger.info(f"LLM client initialized: {provider}/{self.model}")
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD."""
        pricing = self.PRICING.get(self.model, {"input": 3.0, "output": 15.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def _update_stats(self, input_tokens: int, output_tokens: int):
        """Update usage statistics."""
        self.stats.total_calls += 1
        self.stats.total_input_tokens += input_tokens
        self.stats.total_output_tokens += output_tokens
        self.stats.total_cost_usd += self._estimate_cost(input_tokens, output_tokens)
        self.stats.calls_by_model[self.model] = self.stats.calls_by_model.get(self.model, 0) + 1
    
    def analyze_page(self, page_data: Dict[str, Any], tried_answers: set = None) -> Dict[str, Any]:
        """Analyze extracted page data and return structured response."""
        
        # Build the prompt with page data
        prompt = f"Analyze this extracted page data and find the answer:\n\n{json.dumps(page_data, indent=2)[:15000]}"
        
        if tried_answers:
            prompt += f"\n\nIMPORTANT: These answers have already been tried and are WRONG: {list(tried_answers)}\nDo NOT return any of these. Find a DIFFERENT answer."
        
        return self._call_llm(SOLVER_SYSTEM_PROMPT, prompt)
    
    def analyze_screenshot(self, screenshot_base64: str, tried_answers: set = None) -> Dict[str, Any]:
        """Analyze screenshot using vision capabilities."""
        
        prompt = "Analyze this screenshot and find the answer to submit."
        if tried_answers:
            prompt += f"\n\nThese answers are WRONG: {list(tried_answers)}. Find a different answer."
        
        return self._call_llm_vision(VISION_SYSTEM_PROMPT, prompt, screenshot_base64)
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        
        try:
            if self.provider == "openrouter":
                # Use Openrouter API via requests
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/browser-challenge-agent",
                }
                
                payload = {
                    "model": self.model,
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                }
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                input_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                output_tokens = data.get("usage", {}).get("completion_tokens", 0)
                
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                
                content = response.content[0].text
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                
            else:  # openai
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                content = response.choices[0].message.content
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
            
            self._update_stats(input_tokens, output_tokens)
            
            # Parse JSON response
            return self._parse_json_response(content)
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {"answer": None, "confidence": 0, "reasoning": f"LLM error: {e}"}
    
    def _call_llm_vision(self, system_prompt: str, user_prompt: str, image_base64: str) -> Dict[str, Any]:
        """Call LLM with vision capabilities."""
        
        try:
            if self.provider == "openrouter":
                # Use Openrouter API via requests with vision
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/browser-challenge-agent",
                }
                
                payload = {
                    "model": self.model,
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                                }
                            ]
                        }
                    ]
                }
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                input_tokens = data.get("usage", {}).get("prompt_tokens", 0)
                output_tokens = data.get("usage", {}).get("completion_tokens", 0)
                
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            }
                        ]
                    }]
                )
                
                content = response.content[0].text
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                
            else:  # openai
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                                }
                            ]
                        }
                    ]
                )
                
                content = response.choices[0].message.content
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
            
            self._update_stats(input_tokens, output_tokens)
            
            return self._parse_json_response(content)
            
        except Exception as e:
            logger.error(f"Vision LLM call failed: {e}")
            return {"answer": None, "confidence": 0, "reasoning": f"Vision error: {e}"}
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        try:
            # Try to find JSON in the response
            content = content.strip()
            
            # Handle markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            # Find JSON object
            if "{" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {e}")
            # Try to extract answer from plain text
            import re
            answer_match = re.search(r'answer["\s:]+([A-Z0-9]{4,8})', content, re.IGNORECASE)
            if answer_match:
                return {"answer": answer_match.group(1), "confidence": 0.5, "reasoning": "Extracted from plain text"}
            return {"answer": None, "confidence": 0, "reasoning": f"JSON parse error: {e}"}


def get_client(provider: str = "openrouter", model: Optional[str] = None) -> LLMClient:
    """Factory function to create LLM client."""
    return LLMClient(provider, model)
