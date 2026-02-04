# Browser Navigation Challenge Solver

A Selenium-based browser automation agent that solves all 30 challenges on the [Browser Navigation Challenge](https://serene-frangipane-7fd25b.netlify.app/) website in under 5 minutes.

## Challenge Types Handled

The solver handles the following challenge types:

1. **Popup Dismissal** - Cookie consent, prize popups, newsletter signups, limited time offers
2. **Modal Interaction** - Scrollable option selection with radio buttons
3. **Hidden DOM Challenges** - Finding codes in DOM attributes (aria-labels, data attributes, meta tags)
4. **Click-to-Reveal** - Clicking elements multiple times to reveal hidden content
5. **Scroll-to-Reveal** - Scrolling to find navigation buttons
6. **Input Field Challenges** - Entering 6-character codes with React-compatible event handling
7. **Keyboard Sequences** - Handling keyboard-based navigation challenges
8. **Hover Interactions** - Mouse hover to reveal content
9. **Memory Challenges** - Pattern recognition and repetition
10. **Delayed Reveals** - Waiting for timed content to appear

## Installation

### Prerequisites

- Python 3.8 or higher
- Google Chrome browser
- ChromeDriver (automatically managed by webdriver-manager)

### Setup

1. Create a virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage (Headless Mode)

```bash
python scripts/challenge_solver.py
```

### With Visible Browser

```bash
python scripts/challenge_solver.py --no-headless
```

### Save Metrics to File

```bash
python scripts/challenge_solver.py --output metrics.json
```

### All Options

```bash
python scripts/challenge_solver.py --help
```

## Output

The solver provides detailed metrics including:

- Steps completed out of 30
- Success rate percentage
- Total time taken
- Number of popups dismissed
- Number of codes found
- Navigation clicks performed
- Any errors encountered
- Time taken per step

Example output:

```
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

## Architecture

The solver uses a modular architecture with specialized handlers for each challenge type:

- `dismiss_popups()` - Handles all popup types
- `find_hidden_code()` - Searches DOM for hidden codes
- `click_to_reveal_code()` - Clicks elements to reveal codes
- `handle_scrollable_modal()` - Navigates scrollable modals
- `find_navigation_button()` - Locates correct navigation buttons
- `enter_code()` - Enters codes with React-compatible events
- `handle_keyboard_sequence()` - Processes keyboard challenges
- `handle_hover_challenge()` - Manages hover interactions

### React Event Handling

The solver uses a special technique to set input values in React applications:

```python
def set_react_input_value(self, element, value):
    # Uses native value setter to trigger React's onChange
    script = """
    const valueSetter = Object.getOwnPropertyDescriptor(arguments[0], 'value')?.set;
    const prototype = Object.getPrototypeOf(arguments[0]);
    const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    // ... triggers input and change events with bubbles: true
    """
```

## Anti-Looping Methodology

The solver implements strict failure thresholds to prevent infinite loops:

- Maximum 5 iterations per step before moving on
- Maximum 3 retry attempts for each action
- Comprehensive logging for debugging stuck states
- Automatic progression after timeout

## Troubleshooting

### ChromeDriver Issues

If you encounter ChromeDriver version mismatch errors, the webdriver-manager package should handle this automatically. If issues persist:

```bash
pip install --upgrade webdriver-manager
```

### Timeout Errors

Increase the timeout values in the `ChallengeSolver` class:

```python
POPUP_TIMEOUT = 3  # Increase from 2
ELEMENT_TIMEOUT = 10  # Increase from 5
```

### Headless Mode Issues

Some challenges may behave differently in headless mode. Try running with `--no-headless` for debugging.

## License

MIT License
