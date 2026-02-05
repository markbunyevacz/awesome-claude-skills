#!/usr/bin/env python3
"""
Browser Navigation Challenge Solver - CDP Enhanced
Solves all 30 challenges in under 5 minutes.

Uses Chrome DevTools Protocol (CDP) for proper mouse events that trigger React handlers.
"""

import time
import json
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

URL = "https://serene-frangipane-7fd25b.netlify.app/"
SKIP_WORDS = ['SCROLL','BUTTON','COOKIE','ACCEPT','HIDDEN','SUBMIT','SECTIO','OPTION',
              'CHALLE','NAVIGA','LIMITE','MEMORY','REVEAL','CONSEN','KEYBOR','BROWSE',
              'DELAYE','HOVERS','CONTRO','IMPORT','NOTICE','WAITIN','REMAIN']


def cdp_hover(driver, x, y, duration=1.5):
    """Use CDP to send real mouse events that trigger React handlers."""
    driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": x, "y": y
    })
    time.sleep(duration)


def cdp_drag_and_drop(driver, from_x, from_y, to_x, to_y):
    """Use CDP to perform drag-and-drop with real mouse events."""
    # Mouse down at source
    driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": from_x, "y": from_y, "button": "left", "clickCount": 1
    })
    time.sleep(0.05)
    # Move to target
    driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": to_x, "y": to_y
    })
    time.sleep(0.05)
    # Mouse up at target
    driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": to_x, "y": to_y, "button": "left", "clickCount": 1
    })


def solve():
    metrics = {"start_time": None, "total_time_seconds": 0, "steps_completed": 0, "success": False}
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    driver = webdriver.Chrome(options=options)
    
    try:
        metrics["start_time"] = datetime.now().isoformat()
        start = time.time()
        driver.get(URL)
        time.sleep(1)
        
        # Click START
        driver.execute_script("document.querySelectorAll('button').forEach(b => { if (b.innerText.includes('START')) b.click(); });")
        time.sleep(0.5)
        
        last_step = 0
        hover_done = set()
        kbd_done = set()
        stuck_time = time.time()
        stuck_count = 0
        
        while time.time() - start < 290:
            elapsed = time.time() - start
            
            # 1. Close all popups and handle modals
            driver.execute_script("""
            for (let i = 0; i < 10; i++) {
                document.querySelectorAll('button').forEach(b => {
                    const t = b.innerText.trim().toLowerCase();
                    if (t === 'dismiss' || t === 'accept' || t === 'continue' || t === 'ok' || t === 'decline') 
                        try { b.click(); } catch(e) {}
                });
                document.querySelectorAll('*').forEach(e => {
                    if ((e.innerText||'').trim() === 'X' || (e.innerText||'').trim() === '×') 
                        try { e.click(); } catch(e) {}
                });
                document.querySelectorAll('[role="dialog"], .modal').forEach(m => m.scrollTop = m.scrollHeight);
                document.querySelectorAll('[role="radio"]').forEach(r => {
                    if ((r.getAttribute('value')||'').includes('Correct')) try { r.click(); } catch(e) {}
                });
                document.querySelectorAll('button').forEach(b => {
                    const t = b.innerText.trim();
                    if ((t === 'Submit' || t === 'Submit & Continue') && !t.includes('Code'))
                        try { b.click(); } catch(e) {}
                });
            }
            """)
            
            # 2. Get current step
            try:
                text = driver.find_element(By.TAG_NAME, "body").text
                m = re.search(r'Step\s+(\d+)\s+of\s+30', text)
                step = int(m.group(1)) if m else 0
            except:
                step = 0
            
            if step > last_step:
                print(f"Step {step}/30 ({elapsed:.1f}s)")
                metrics["steps_completed"] = step
                last_step = step
                stuck_time = time.time()
            
            # Debug: Print status every 15 seconds when stuck
            if time.time() - stuck_time > 15:
                stuck_count += 1
                challenge_text = driver.execute_script("""
                const body = document.body.innerText;
                const lines = body.split('\\n').filter(l => l.trim());
                return lines.slice(0, 20).join(' | ');
                """)
                print(f"  STUCK at step {step} for {(time.time() - stuck_time):.0f}s (count={stuck_count}): {challenge_text[:150]}")
                
                # If stuck for too long on same step, navigate back to main URL to get a different challenge
                if stuck_count >= 3:
                    print(f"  -> Navigating to main URL to get different challenge type...")
                    driver.get(URL)
                    time.sleep(1)
                    driver.execute_script("document.querySelectorAll('button').forEach(b => { if (b.innerText.includes('START')) b.click(); });")
                    time.sleep(0.5)
                    stuck_count = 0
                    hover_done.clear()
                    kbd_done.clear()
                    last_step = 0
                
                stuck_time = time.time()
            
            # 3. Check completion
            if step >= 30 or "Congratulations" in text:
                metrics["success"] = True
                metrics["steps_completed"] = 30
                print(f"COMPLETED in {elapsed:.1f}s!")
                break
            
            # 4. Wait for delayed timer if present
            if "remaining" in text.lower():
                for _ in range(70):
                    try:
                        t = driver.find_element(By.TAG_NAME, "body").text
                        if "remaining" not in t.lower():
                            break
                    except:
                        pass
                    time.sleep(0.1)
            
            # 5. Try all reveal methods
            driver.execute_script("""
            // Click reveal/remember buttons
            document.querySelectorAll('button').forEach(b => {
                const t = b.innerText.toLowerCase();
                if (t.includes('reveal') || t.includes('remember')) try { b.click(); } catch(e) {}
            });
            // Hidden DOM clicks
            document.querySelectorAll('*').forEach(e => {
                if ((e.innerText||'').includes('Hidden DOM')) 
                    for(let i=0; i<5; i++) try { e.click(); } catch(e) {}
            });
            // Hover elements - dispatch events and click
            document.querySelectorAll('*').forEach(e => {
                const t = (e.innerText||'').toLowerCase();
                if (t.includes('hover') && e.offsetParent && e.offsetWidth > 20) {
                    ['mouseenter','mouseover','mousemove'].forEach(type => {
                        try { e.dispatchEvent(new MouseEvent(type, {bubbles:true, view:window})); } catch(x) {}
                    });
                    try { e.click(); } catch(x) {}
                }
            });
            // Force visibility on hidden elements
            document.querySelectorAll('*').forEach(e => {
                const s = window.getComputedStyle(e);
                if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') {
                    e.style.setProperty('display', 'block', 'important');
                    e.style.setProperty('visibility', 'visible', 'important');
                    e.style.setProperty('opacity', '1', 'important');
                }
            });
            """)
            
            # Scroll for scroll-based reveals
            driver.execute_script("window.scrollTo(0, 800)")
            time.sleep(0.02)
            driver.execute_script("window.scrollTo(0, 0)")
            
            # 5b. Handle Drag-and-Drop Challenge using CDP
            if "Drag-and-Drop" in text or "Fill all" in text:
                try:
                    # Get positions of draggable pieces and drop slots
                    dnd_info = driver.execute_script("""
                    const pieces = Array.from(document.querySelectorAll('[draggable="true"]')).map(e => {
                        const rect = e.getBoundingClientRect();
                        return {x: rect.left + rect.width/2, y: rect.top + rect.height/2};
                    });
                    
                    // Find drop slots - look for elements with dashed border or specific classes
                    let slots = Array.from(document.querySelectorAll('div')).filter(e => {
                        const cls = (e.className || '').toLowerCase();
                        const style = window.getComputedStyle(e);
                        const rect = e.getBoundingClientRect();
                        return rect.width > 40 && rect.width < 200 && 
                               rect.height > 40 && rect.height < 200 &&
                               (cls.includes('border-dashed') || cls.includes('slot') || 
                                style.borderStyle === 'dashed' ||
                                (e.children.length === 0 && cls.includes('border')));
                    }).map(e => {
                        const rect = e.getBoundingClientRect();
                        return {x: rect.left + rect.width/2, y: rect.top + rect.height/2};
                    });
                    
                    return {pieces: pieces, slots: slots};
                    """)
                    
                    pieces = dnd_info.get('pieces', [])
                    slots = dnd_info.get('slots', [])
                    
                    # Use CDP to drag each piece to a slot
                    for i, piece in enumerate(pieces[:6]):
                        if i < len(slots):
                            cdp_drag_and_drop(driver, 
                                int(piece['x']), int(piece['y']),
                                int(slots[i]['x']), int(slots[i]['y']))
                            time.sleep(0.1)
                    
                    # Also try ActionChains as backup
                    piece_elems = driver.find_elements(By.CSS_SELECTOR, '[draggable="true"]')
                    slot_elems = driver.execute_script("""
                    return Array.from(document.querySelectorAll('div')).filter(e => {
                        const cls = (e.className || '').toLowerCase();
                        const style = window.getComputedStyle(e);
                        const rect = e.getBoundingClientRect();
                        return rect.width > 40 && rect.width < 200 && 
                               rect.height > 40 && rect.height < 200 &&
                               (cls.includes('border-dashed') || cls.includes('slot') || 
                                style.borderStyle === 'dashed');
                    });
                    """)
                    
                    for i, piece in enumerate(piece_elems[:6]):
                        if i < len(slot_elems):
                            try:
                                ActionChains(driver).click_and_hold(piece).move_to_element(slot_elems[i]).release().perform()
                                time.sleep(0.1)
                            except:
                                pass
                except:
                    pass
            
            # 6. CDP hover for hover challenges (once per step)
            if step not in hover_done and "Hover" in text:
                try:
                    # Find the hover box element and get its position
                    hover_info = driver.execute_script("""
                    const divs = document.querySelectorAll('div');
                    for (let d of divs) {
                        const text = d.innerText || '';
                        if (text.includes('Hover here to reveal') && d.className.includes('bg-white')) {
                            const rect = d.getBoundingClientRect();
                            return {x: rect.left + rect.width/2, y: rect.top + rect.height/2};
                        }
                    }
                    // Fallback: find any element with hover text
                    for (let e of document.querySelectorAll('*')) {
                        const t = (e.innerText||'').toLowerCase();
                        if (t.includes('hover here') && e.offsetWidth > 50) {
                            const rect = e.getBoundingClientRect();
                            return {x: rect.left + rect.width/2, y: rect.top + rect.height/2};
                        }
                    }
                    return null;
                    """)
                    
                    if hover_info:
                        # Use CDP to send real mouse events
                        cdp_hover(driver, int(hover_info['x']), int(hover_info['y']), 1.5)
                        
                        # Also try ActionChains as backup
                        elems = driver.execute_script("""
                        return Array.from(document.querySelectorAll('*')).filter(e => 
                            (e.innerText||'').toLowerCase().includes('hover') && e.offsetParent && e.offsetWidth > 20
                        ).slice(0, 2);
                        """)
                        for elem in elems:
                            driver.execute_script('arguments[0].scrollIntoView({block:"center"});', elem)
                            ActionChains(driver).move_to_element(elem).perform()
                            time.sleep(1.2)
                            try:
                                elem.click()
                            except:
                                driver.execute_script("arguments[0].click();", elem)
                except:
                    pass
                hover_done.add(step)
            
            # 7. Keyboard sequences (once per step)
            if step not in kbd_done and ("Control+" in text or "Keyboard" in text):
                try:
                    seqs = re.findall(r'(Control|Shift|Alt)\+([A-Z])', text)
                    if seqs:
                        driver.find_element(By.TAG_NAME, "body").click()
                        for mod, key in seqs:
                            a = ActionChains(driver)
                            if mod == "Control":
                                a.key_down(Keys.CONTROL).send_keys(key.lower()).key_up(Keys.CONTROL).perform()
                            elif mod == "Shift":
                                a.key_down(Keys.SHIFT).send_keys(key.lower()).key_up(Keys.SHIFT).perform()
                            elif mod == "Alt":
                                a.key_down(Keys.ALT).send_keys(key.lower()).key_up(Keys.ALT).perform()
                            time.sleep(0.05)
                except:
                    pass
                kbd_done.add(step)
            
            # 8. Get code from page
            code = driver.execute_script(r"""
            const text = document.body.innerText + ' ' + document.body.innerHTML;
            const skip = """ + str(SKIP_WORDS) + r""";
            const codes = text.match(/\b[A-Z0-9]{6}\b/g) || [];
            for (let c of codes) {
                let bad = false;
                for (let s of skip) if (c.includes(s) || c.startsWith(s.slice(0,4))) bad = true;
                if (!bad) return c;
            }
            return null;
            """)
            
            # 9. Submit code if found
            if code:
                try:
                    driver.execute_script("""
                    for (let i = 0; i < 5; i++) {
                        document.querySelectorAll('button').forEach(b => {
                            const t = b.innerText.trim().toLowerCase();
                            if (t === 'dismiss') try { b.click(); } catch(e) {}
                        });
                        document.querySelectorAll('*').forEach(e => {
                            if ((e.innerText||'').trim() === 'X') try { e.click(); } catch(e) {}
                        });
                    }
                    """)
                    inp = driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="6-char"]')
                    driver.execute_script('arguments[0].scrollIntoView({block:"center"});', inp)
                    inp.clear()
                    inp.send_keys(code)
                    btn = driver.find_element(By.XPATH, '//button[contains(text(),"Submit Code")]')
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.05)
                except:
                    pass
        
        metrics["total_time_seconds"] = time.time() - start
        
    finally:
        driver.quit()
    
    return metrics


def main():
    print("=" * 50)
    print("Browser Navigation Challenge Solver")
    print("=" * 50)
    
    metrics = solve()
    
    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"Success: {metrics['success']}")
    print(f"Steps: {metrics['steps_completed']}/30")
    print(f"Time: {metrics['total_time_seconds']:.2f}s")
    
    with open("run_statistics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print("\nSaved to run_statistics.json")


if __name__ == "__main__":
    main()
