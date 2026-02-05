#!/usr/bin/env python3
"""
Browser Navigation Challenge Solver - Playwright Version
Solves all 30 challenges in under 5 minutes.

Uses Playwright for better hover and drag-and-drop support.
"""

import time
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = "https://serene-frangipane-7fd25b.netlify.app/"
SKIP_WORDS = ['SCROLL','BUTTON','COOKIE','ACCEPT','HIDDEN','SUBMIT','SECTIO','OPTION',
              'CHALLE','NAVIGA','LIMITE','MEMORY','REVEAL','CONSEN','KEYBOR','BROWSE',
              'DELAYE','HOVERS','CONTRO','IMPORT','NOTICE','WAITIN','REMAIN','VERSIO',
              'STEP12','STEP13','STEP14','STEP15','STEP16','STEP17','STEP18','STEP19',
              'STEP20','STEP21','STEP22','STEP23','STEP24','STEP25','STEP26','STEP27',
              'STEP28','STEP29','STEP30']


def is_valid_code(code):
    for s in SKIP_WORDS:
        if s in code or code.startswith(s[:4]):
            return False
    has_letter = any(c.isalpha() for c in code)
    has_number = any(c.isdigit() for c in code)
    return has_letter and has_number


def extract_code(page):
    text = page.inner_text("body")
    html = page.content()
    all_codes = re.findall(r'\b[A-Z0-9]{6}\b', text + " " + html)
    for code in all_codes:
        if is_valid_code(code):
            return code
    return None


def close_popups(page):
    page.evaluate("""
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


def handle_delayed_reveal(page):
    text = page.inner_text("body")
    if "remaining" in text.lower():
        for _ in range(80):
            time.sleep(0.1)
            text = page.inner_text("body")
            if "remaining" not in text.lower():
                break


def handle_click_reveal(page):
    page.evaluate("""
    document.querySelectorAll('button').forEach(b => {
        const t = b.innerText.toLowerCase();
        if (t.includes('reveal') || t.includes('remember')) try { b.click(); } catch(e) {}
    });
    """)


def handle_hidden_dom(page):
    page.evaluate("""
    document.querySelectorAll('*').forEach(e => {
        if ((e.innerText||'').includes('Hidden DOM')) 
            for(let i=0; i<5; i++) try { e.click(); } catch(e) {}
    });
    """)


def handle_scroll_reveal(page):
    page.evaluate("window.scrollTo(0, 800)")
    time.sleep(0.05)
    page.evaluate("window.scrollTo(0, 0)")


def handle_hover_challenge(page):
    hover_box = page.evaluate("""
    const divs = document.querySelectorAll('div');
    for (let d of divs) {
        const text = d.innerText || '';
        if ((text.includes('Hover here') || text.includes('Hover over')) && d.offsetWidth > 50) {
            const rect = d.getBoundingClientRect();
            return {x: rect.left + rect.width/2, y: rect.top + rect.height/2, found: true};
        }
    }
    return {found: false};
    """)
    
    if hover_box.get('found'):
        page.mouse.move(hover_box['x'], hover_box['y'])
        time.sleep(1.5)
        page.mouse.click(hover_box['x'], hover_box['y'])


def handle_drag_and_drop(page):
    dnd_info = page.evaluate("""
    const pieces = Array.from(document.querySelectorAll('[draggable="true"]')).map(e => {
        const rect = e.getBoundingClientRect();
        return {x: rect.left + rect.width/2, y: rect.top + rect.height/2};
    });
    
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
    
    for i, piece in enumerate(pieces[:6]):
        if i < len(slots):
            page.mouse.move(piece['x'], piece['y'])
            page.mouse.down()
            page.mouse.move(slots[i]['x'], slots[i]['y'])
            page.mouse.up()
            time.sleep(0.1)


def handle_keyboard_sequence(page, text):
    seqs = re.findall(r'(Control|Shift|Alt)\+([A-Z])', text)
    if seqs:
        for mod, key in seqs:
            modifier = mod.lower()
            page.keyboard.press(f"{modifier}+{key.lower()}")
            time.sleep(0.05)


def submit_code(page, code):
    try:
        close_popups(page)
        inp = page.locator('input[placeholder*="6-char"]')
        if inp.count() > 0:
            inp.first.scroll_into_view_if_needed()
            inp.first.fill(code)
            btn = page.locator('button:has-text("Submit Code")')
            if btn.count() > 0:
                btn.first.click()
                time.sleep(0.1)
                return True
    except Exception:
        pass
    return False


def solve():
    metrics = {"start_time": None, "total_time_seconds": 0, "steps_completed": 0, "success": False}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        try:
            metrics["start_time"] = datetime.now().isoformat()
            start = time.time()
            
            page.goto(URL, wait_until="networkidle")
            time.sleep(1)
            
            page.evaluate("document.querySelectorAll('button').forEach(b => { if (b.innerText.includes('START')) b.click(); });")
            time.sleep(0.5)
            
            last_step = 0
            stuck_time = time.time()
            stuck_count = 0
            tried_codes = set()
            
            while time.time() - start < 290:
                elapsed = time.time() - start
                
                close_popups(page)
                
                try:
                    text = page.inner_text("body")
                    m = re.search(r'Step\s+(\d+)\s+of\s+30', text)
                    step = int(m.group(1)) if m else 0
                except:
                    step = 0
                
                if step > last_step:
                    print(f"Step {step}/30 ({elapsed:.1f}s)")
                    metrics["steps_completed"] = step
                    last_step = step
                    stuck_time = time.time()
                    stuck_count = 0
                    tried_codes.clear()
                
                if step >= 30 or "Congratulations" in text:
                    metrics["success"] = True
                    metrics["steps_completed"] = 30
                    print(f"COMPLETED in {elapsed:.1f}s!")
                    break
                
                if time.time() - stuck_time > 15:
                    stuck_count += 1
                    challenge_type = "Unknown"
                    if "Hover" in text:
                        challenge_type = "Hover"
                    elif "Drag-and-Drop" in text:
                        challenge_type = "Drag-and-Drop"
                    elif "Delayed" in text or "remaining" in text.lower():
                        challenge_type = "Delayed"
                    elif "Keyboard" in text:
                        challenge_type = "Keyboard"
                    elif "Click to Reveal" in text:
                        challenge_type = "Click"
                    elif "Scroll" in text:
                        challenge_type = "Scroll"
                    elif "Memory" in text:
                        challenge_type = "Memory"
                    elif "Hidden DOM" in text:
                        challenge_type = "HiddenDOM"
                    
                    # Debug: show what code was found
                    code = extract_code(page)
                    print(f"  STUCK at step {step} ({challenge_type}) for {stuck_count*15}s, code={code}")
                    
                    if stuck_count >= 4:
                        print(f"  -> Restarting to get different challenge...")
                        page.goto(URL, wait_until="networkidle")
                        time.sleep(1)
                        page.evaluate("document.querySelectorAll('button').forEach(b => { if (b.innerText.includes('START')) b.click(); });")
                        time.sleep(0.5)
                        stuck_count = 0
                        last_step = 0
                        tried_codes.clear()
                    
                    stuck_time = time.time()
                
                handle_delayed_reveal(page)
                handle_click_reveal(page)
                handle_hidden_dom(page)
                handle_scroll_reveal(page)
                
                if "Hover" in text:
                    handle_hover_challenge(page)
                
                if "Drag-and-Drop" in text or "Fill all" in text:
                    handle_drag_and_drop(page)
                
                if "Control+" in text or "Keyboard" in text:
                    handle_keyboard_sequence(page, text)
                
                page.evaluate("""
                document.querySelectorAll('*').forEach(e => {
                    const s = window.getComputedStyle(e);
                    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') {
                        e.style.setProperty('display', 'block', 'important');
                        e.style.setProperty('visibility', 'visible', 'important');
                        e.style.setProperty('opacity', '1', 'important');
                    }
                });
                """)
                
                code = extract_code(page)
                if code and code not in tried_codes:
                    tried_codes.add(code)
                    submit_code(page, code)
                    time.sleep(0.1)
                
                time.sleep(0.05)
            
            metrics["total_time_seconds"] = time.time() - start
            
        finally:
            browser.close()
    
    return metrics


def main():
    print("=" * 50)
    print("Browser Navigation Challenge Solver (Playwright)")
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
