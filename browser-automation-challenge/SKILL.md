---
name: browser-automation-challenge
description: Selenium-based browser automation agent that solves browser navigation challenges including popups, modals, hidden DOM elements, scroll-to-reveal, and React input handling.
---

# Browser Automation Challenge Solver

A comprehensive Selenium-based automation agent designed to solve complex browser navigation challenges. This skill demonstrates advanced web automation techniques including React-compatible event handling, popup management, and DOM inspection.

## When to Use This Skill

Use this skill when you need to:
- Automate browser navigation through complex multi-step challenges
- Handle various popup types (cookie consent, notifications, modals)
- Interact with React applications using proper event dispatching
- Find hidden content in DOM attributes or through click-to-reveal mechanisms
- Navigate scrollable content to find specific elements
- Enter data into forms with React state management

## What This Skill Does

The solver handles 10 distinct challenge types:

1. **Popup Dismissal** - Automatically closes cookie consent, prize popups, newsletter signups, and limited time offers
2. **Modal Interaction** - Scrolls through modal content and selects correct options
3. **Hidden DOM Challenges** - Searches data attributes, aria-labels, and meta tags for hidden codes
4. **Click-to-Reveal** - Clicks elements multiple times to reveal hidden content
5. **Scroll-to-Reveal** - Scrolls page to find navigation buttons
6. **Input Field Challenges** - Uses React-compatible value setting with proper event bubbling
7. **Keyboard Sequences** - Handles keyboard-based navigation
8. **Hover Interactions** - Triggers mouseenter/mouseover events for hover reveals
9. **Memory Challenges** - Pattern recognition and repetition
10. **Delayed Reveals** - Waits for timed content

## How to Use

### Installation

```bash
cd browser-automation-challenge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run the Solver

```bash
# Headless mode (default)
python scripts/challenge_solver.py

# With visible browser for debugging
python scripts/challenge_solver.py --no-headless

# Save metrics to JSON
python scripts/challenge_solver.py --output metrics.json
```

### Key Implementation Details

For React applications, use the native value setter pattern:

```python
script = """
const valueSetter = Object.getOwnPropertyDescriptor(arguments[0], 'value')?.set;
const prototype = Object.getPrototypeOf(arguments[0]);
const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
if (valueSetter && valueSetter !== prototypeValueSetter) {
    prototypeValueSetter.call(arguments[0], arguments[1]);
} else {
    valueSetter.call(arguments[0], arguments[1]);
}
arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
"""
```

## Example

Running the solver against the Browser Navigation Challenge website:

```bash
$ python scripts/challenge_solver.py --output results.json

2024-01-15 10:30:00 - INFO - Starting Browser Navigation Challenge Solver
2024-01-15 10:30:01 - INFO - Chrome WebDriver initialized
2024-01-15 10:30:02 - INFO - Solving step 1
2024-01-15 10:30:03 - INFO - Found code: ABC123
2024-01-15 10:30:04 - INFO - Completed step 1
...
==================================================
CHALLENGE RESULTS
==================================================
Steps Completed: 30/30
Success Rate: 100.0%
Total Time: 180.45 seconds
Popups Dismissed: 12
Codes Found: 30
Navigation Clicks: 45
==================================================
```

## Anti-Looping Methodology

The solver implements strict failure thresholds:
- Maximum 5 iterations per step before progressing
- Comprehensive error logging for debugging
- Automatic timeout handling
