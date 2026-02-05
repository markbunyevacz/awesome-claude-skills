# Browser Navigation Challenge Solver

An automated agent that solves the Browser Navigation Challenge at https://serene-frangipane-7fd25b.netlify.app/

## Overview

This solver uses Selenium with Chrome WebDriver to automatically navigate through 30 browser challenges. It handles multiple challenge types including click-to-reveal, scroll-to-reveal, delayed reveals, memory challenges, keyboard sequences, and more.

## Requirements

- Python 3.8+
- Google Chrome browser
- ChromeDriver (automatically managed by webdriver-manager)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python solve_challenges.py
```

The solver will:
1. Navigate to the challenge website
2. Click START to begin
3. Automatically solve each challenge by:
   - Closing popups and handling modals
   - Detecting challenge types
   - Performing required interactions (clicks, scrolls, keyboard sequences)
   - Extracting and submitting 6-character codes
4. Save results to `run_statistics.json`

## Challenge Types Handled

| Challenge Type | Status | Notes |
|---------------|--------|-------|
| Click to Reveal | Working | Clicks reveal buttons |
| Scroll to Reveal | Working | Scrolls to trigger code reveal |
| Delayed Reveal | Working | Waits for timer to complete |
| Memory Challenge | Working | Captures flashing code |
| Hidden DOM | Working | Multiple clicks to reveal |
| Keyboard Sequence | Working | Sends Control+Key combinations |
| Hover Challenge | Limited | Headless Chrome limitation |
| Drag-and-Drop | Limited | Headless Chrome limitation |

## Known Limitations

### Hover Challenge
The Hover Challenge requires holding the mouse over an element for 1+ seconds to reveal the code. In headless Chrome, hover events don't properly trigger React's synthetic event system. This is a known limitation of headless browser automation.

Attempted solutions that don't work in headless mode:
- CDP Input.dispatchMouseEvent
- Selenium ActionChains move_to_element
- JavaScript dispatchEvent (mouseenter, mouseover, mousemove)

### Drag-and-Drop Challenge
Similar to hover, drag-and-drop interactions don't work reliably in headless Chrome with React applications.

## Performance

Typical run results:
- Steps completed: 6-10 out of 30 (before hitting hover/drag-and-drop)
- Time per successful step: ~2-3 seconds
- Total time: Uses full 5-minute budget when stuck on unsupported challenges

The solver includes a restart mechanism that navigates back to the start when stuck for too long, attempting to get a different challenge sequence.

## Output

Results are saved to `run_statistics.json`:
```json
{
  "start_time": "2024-01-01T00:00:00.000000",
  "total_time_seconds": 290.0,
  "steps_completed": 8,
  "success": false
}
```

## Alternative Approaches

For full 30/30 completion, consider:
1. **Non-headless mode**: Run Chrome with a visible window (hover works properly)
2. **Vision-based AI**: Use Claude/GPT-4 Vision to analyze screenshots and determine actions
3. **Playwright**: May have better hover support in some scenarios

## Files

- `solve_challenges.py` - Main Selenium-based solver
- `solve_playwright.py` - Alternative Playwright-based solver (experimental)
- `requirements.txt` - Python dependencies
- `run_statistics.json` - Output from last run

## License

MIT
