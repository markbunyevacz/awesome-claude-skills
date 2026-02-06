// JavaScript Injection Module for Browser Challenge Agent
// Contains 5 scripts for console capture, extraction, interaction detection, and result checking

const CONSOLE_CAPTURE_INIT = `
(function() {
  if (window.__consoleCaptured) return;
  window.__consoleCaptured = true;
  window.__capturedLogs = [];
  
  const originalLog = console.log;
  const originalWarn = console.warn;
  const originalError = console.error;
  const originalInfo = console.info;
  const originalDebug = console.debug;
  
  function capture(type, args) {
    try {
      const message = Array.from(args).map(arg => {
        if (typeof arg === 'object') {
          try { return JSON.stringify(arg); } catch { return String(arg); }
        }
        return String(arg);
      }).join(' ');
      window.__capturedLogs.push({ type, message, timestamp: Date.now() });
    } catch (e) {}
  }
  
  console.log = function(...args) { capture('log', args); return originalLog.apply(console, args); };
  console.warn = function(...args) { capture('warn', args); return originalWarn.apply(console, args); };
  console.error = function(...args) { capture('error', args); return originalError.apply(console, args); };
  console.info = function(...args) { capture('info', args); return originalInfo.apply(console, args); };
  console.debug = function(...args) { capture('debug', args); return originalDebug.apply(console, args); };
})();
`;

const GET_CONSOLE_LOGS = `
(function() {
  return window.__capturedLogs || [];
})();
`;

const EXTRACT_PAGE_DATA = `
(function() {
  const result = {
    url: window.location.href,
    title: document.title,
    bodyText: '',
    comments: [],
    hiddenElements: [],
    dataAttributes: [],
    titleAltAria: [],
    pseudoContent: [],
    cssVariables: [],
    camouflaged: [],
    microFont: [],
    offscreen: [],
    metaTags: [],
    inlineScripts: [],
    storage: { localStorage: {}, sessionStorage: {}, cookies: '' },
    shadowDOM: [],
    globalVars: [],
    inputFields: [],
    buttons: [],
    imageText: [],
    iframes: [],
    canvasElements: [],
    customElements: [],
    noscript: [],
    styleContent: [],
    structure: ''
  };
  
  // 1. Visible body text
  try {
    result.bodyText = document.body ? document.body.innerText.substring(0, 10000) : '';
  } catch (e) {}
  
  // 2. HTML comments
  try {
    const walker = document.createTreeWalker(document, NodeFilter.SHOW_COMMENT, null, false);
    let node;
    while (node = walker.nextNode()) {
      const text = node.textContent.trim();
      if (text && text.length < 1000) result.comments.push(text);
    }
  } catch (e) {}
  
  // 3. Hidden DOM elements (display:none, visibility:hidden, opacity:0, aria-hidden, clip-path, text-indent, transform:scale(0))
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
      const style = window.getComputedStyle(el);
      const isHidden = 
        style.display === 'none' ||
        style.visibility === 'hidden' ||
        style.opacity === '0' ||
        el.getAttribute('aria-hidden') === 'true' ||
        style.clipPath === 'inset(100%)' ||
        parseInt(style.textIndent) < -9000 ||
        style.transform === 'scale(0)' ||
        style.transform === 'scale(0, 0)';
      
      if (isHidden) {
        const text = el.textContent?.trim();
        if (text && text.length > 0 && text.length < 500) {
          result.hiddenElements.push({ tag: el.tagName, text, reason: 'hidden' });
        }
      }
    }
  } catch (e) {}
  
  // 4. Data attributes
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      for (const attr of el.attributes) {
        if (attr.name.startsWith('data-') && attr.value) {
          result.dataAttributes.push({ element: el.tagName, attr: attr.name, value: attr.value });
        }
      }
    }
  } catch (e) {}
  
  // 5. Title, alt, aria, placeholder attributes
  try {
    const selectors = '[title], [alt], [aria-label], [aria-describedby], [placeholder]';
    const elements = document.querySelectorAll(selectors);
    for (const el of elements) {
      const attrs = {};
      if (el.title) attrs.title = el.title;
      if (el.alt) attrs.alt = el.alt;
      if (el.getAttribute('aria-label')) attrs.ariaLabel = el.getAttribute('aria-label');
      if (el.placeholder) attrs.placeholder = el.placeholder;
      if (Object.keys(attrs).length > 0) {
        result.titleAltAria.push({ tag: el.tagName, ...attrs });
      }
    }
  } catch (e) {}
  
  // 6. CSS ::before/::after pseudo-content
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      const before = window.getComputedStyle(el, '::before').content;
      const after = window.getComputedStyle(el, '::after').content;
      if (before && before !== 'none' && before !== '""' && before !== "''") {
        result.pseudoContent.push({ element: el.tagName, type: 'before', content: before });
      }
      if (after && after !== 'none' && after !== '""' && after !== "''") {
        result.pseudoContent.push({ element: el.tagName, type: 'after', content: after });
      }
    }
  } catch (e) {}
  
  // 7. CSS custom properties (variables)
  try {
    const styles = document.querySelectorAll('style');
    for (const style of styles) {
      const text = style.textContent;
      const varMatches = text.matchAll(/--([a-zA-Z0-9-_]+)\\s*:\\s*["']?([^;"']+)["']?/g);
      for (const match of varMatches) {
        result.cssVariables.push({ name: match[1], value: match[2].trim() });
      }
    }
    // Also check inline styles
    const allElements = document.querySelectorAll('[style]');
    for (const el of allElements) {
      const style = el.getAttribute('style');
      const varMatches = style.matchAll(/--([a-zA-Z0-9-_]+)\\s*:\\s*["']?([^;"']+)["']?/g);
      for (const match of varMatches) {
        result.cssVariables.push({ name: match[1], value: match[2].trim() });
      }
    }
  } catch (e) {}
  
  // 8. Camouflaged text (same color as background)
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      if (!el.textContent?.trim()) continue;
      const style = window.getComputedStyle(el);
      const color = style.color;
      const bgColor = style.backgroundColor;
      if (color && bgColor && color === bgColor && color !== 'rgba(0, 0, 0, 0)') {
        const text = el.textContent.trim();
        if (text.length > 0 && text.length < 200) {
          result.camouflaged.push({ text, color });
        }
      }
    }
  } catch (e) {}
  
  // 9. Micro-font elements (<4px)
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      const style = window.getComputedStyle(el);
      const fontSize = parseFloat(style.fontSize);
      if (fontSize < 4 && el.textContent?.trim()) {
        result.microFont.push({ text: el.textContent.trim(), fontSize });
      }
    }
  } catch (e) {}
  
  // 10. Offscreen elements
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const left = parseFloat(style.left);
      const top = parseFloat(style.top);
      if ((left < -9000 || top < -9000 || rect.right < 0 || rect.bottom < 0) && el.textContent?.trim()) {
        const text = el.textContent.trim();
        if (text.length > 0 && text.length < 200) {
          result.offscreen.push({ text });
        }
      }
    }
  } catch (e) {}
  
  // 11. Meta tags
  try {
    const metas = document.querySelectorAll('meta');
    for (const meta of metas) {
      const name = meta.getAttribute('name') || meta.getAttribute('property');
      const content = meta.getAttribute('content');
      if (name && content) {
        result.metaTags.push({ name, content });
      }
    }
  } catch (e) {}
  
  // 12. Inline scripts (variable assignments)
  try {
    const scripts = document.querySelectorAll('script:not([src])');
    for (const script of scripts) {
      const text = script.textContent;
      // Look for variable assignments
      const patterns = [
        /(?:var|let|const)\\s+(\\w+)\\s*=\\s*["']([^"']+)["']/g,
        /window\\.(\\w+)\\s*=\\s*["']([^"']+)["']/g,
        /["']?answer["']?\\s*[=:]\\s*["']([^"']+)["']/gi,
        /["']?code["']?\\s*[=:]\\s*["']([^"']+)["']/gi,
        /["']?secret["']?\\s*[=:]\\s*["']([^"']+)["']/gi
      ];
      for (const pattern of patterns) {
        const matches = text.matchAll(pattern);
        for (const match of matches) {
          result.inlineScripts.push({ 
            variable: match[1] || 'answer', 
            value: match[2] || match[1] 
          });
        }
      }
    }
  } catch (e) {}
  
  // 13. localStorage/sessionStorage/cookies
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      result.storage.localStorage[key] = localStorage.getItem(key);
    }
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      result.storage.sessionStorage[key] = sessionStorage.getItem(key);
    }
    result.storage.cookies = document.cookie;
  } catch (e) {}
  
  // 14. Shadow DOM
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      if (el.shadowRoot) {
        const shadowText = el.shadowRoot.textContent?.trim();
        if (shadowText && shadowText.length < 1000) {
          result.shadowDOM.push({ host: el.tagName, content: shadowText });
        }
      }
    }
  } catch (e) {}
  
  // 15. Global JS variables
  try {
    const commonVars = ['answer', 'secret', 'code', 'key', 'password', 'token', 'flag', 'solution', 'result', 'data', 'value', 'hidden', 'challenge'];
    for (const varName of commonVars) {
      if (window[varName] !== undefined) {
        const val = window[varName];
        if (typeof val === 'string' || typeof val === 'number') {
          result.globalVars.push({ name: varName, value: String(val) });
        }
      }
      // Also check with common prefixes
      for (const prefix of ['_', '__', '$']) {
        const prefixedName = prefix + varName;
        if (window[prefixedName] !== undefined) {
          const val = window[prefixedName];
          if (typeof val === 'string' || typeof val === 'number') {
            result.globalVars.push({ name: prefixedName, value: String(val) });
          }
        }
      }
    }
  } catch (e) {}
  
  // 16. Input fields with context
  try {
    const inputs = document.querySelectorAll('input, textarea');
    for (const input of inputs) {
      const info = {
        type: input.type || 'text',
        name: input.name,
        id: input.id,
        placeholder: input.placeholder,
        value: input.value,
        selector: input.id ? '#' + input.id : (input.name ? '[name="' + input.name + '"]' : null)
      };
      // Find associated label
      if (input.id) {
        const label = document.querySelector('label[for="' + input.id + '"]');
        if (label) info.label = label.textContent.trim();
      }
      result.inputFields.push(info);
    }
  } catch (e) {}
  
  // 17. Buttons/links
  try {
    const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]');
    for (const btn of buttons) {
      result.buttons.push({
        text: btn.textContent?.trim() || btn.value,
        type: btn.type,
        id: btn.id,
        selector: btn.id ? '#' + btn.id : null
      });
    }
  } catch (e) {}
  
  // 18. Image alt text and SVG text
  try {
    const images = document.querySelectorAll('img');
    for (const img of images) {
      if (img.alt) result.imageText.push({ type: 'img-alt', text: img.alt });
    }
    const svgTexts = document.querySelectorAll('svg text, svg tspan');
    for (const svgText of svgTexts) {
      const text = svgText.textContent?.trim();
      if (text) result.imageText.push({ type: 'svg-text', text });
    }
  } catch (e) {}
  
  // 19. Iframes
  try {
    const iframes = document.querySelectorAll('iframe');
    for (const iframe of iframes) {
      try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
        if (iframeDoc) {
          const text = iframeDoc.body?.innerText?.trim();
          if (text && text.length < 2000) {
            result.iframes.push({ src: iframe.src, content: text });
          }
        }
      } catch (e) {
        result.iframes.push({ src: iframe.src, content: '[cross-origin]' });
      }
    }
  } catch (e) {}
  
  // 20. Canvas elements
  try {
    const canvases = document.querySelectorAll('canvas');
    result.canvasElements = canvases.length;
  } catch (e) {}
  
  // 21. Custom elements (web components)
  try {
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      if (el.tagName.includes('-')) {
        const text = el.textContent?.trim();
        if (text && text.length < 500) {
          result.customElements.push({ tag: el.tagName, content: text });
        }
      }
    }
  } catch (e) {}
  
  // 22. Noscript content
  try {
    const noscripts = document.querySelectorAll('noscript');
    for (const ns of noscripts) {
      const text = ns.textContent?.trim();
      if (text) result.noscript.push(text);
    }
  } catch (e) {}
  
  // 23. Style tag string content
  try {
    const styles = document.querySelectorAll('style');
    for (const style of styles) {
      const text = style.textContent;
      // Look for strings that might be answers
      const stringMatches = text.matchAll(/["']([A-Z0-9]{4,8})["']/g);
      for (const match of stringMatches) {
        result.styleContent.push(match[1]);
      }
    }
  } catch (e) {}
  
  // 24. Page structure summary
  try {
    const headings = document.querySelectorAll('h1, h2, h3');
    const headingTexts = Array.from(headings).map(h => h.textContent?.trim()).filter(Boolean);
    result.structure = headingTexts.join(' | ');
  } catch (e) {}
  
  return result;
})();
`;

const DETECT_INTERACTIONS = `
(function() {
  const interactions = [];
  
  // Clickable elements
  try {
    const clickables = document.querySelectorAll('button, [onclick], [role="button"], a[href="#"], .clickable, [data-click], [tabindex]');
    for (const el of clickables) {
      if (el.offsetParent !== null) { // visible
        interactions.push({
          type: 'click',
          selector: el.id ? '#' + el.id : (el.className ? '.' + el.className.split(' ')[0] : el.tagName.toLowerCase()),
          text: el.textContent?.trim()?.substring(0, 50)
        });
      }
    }
  } catch (e) {}
  
  // Draggable elements
  try {
    const draggables = document.querySelectorAll('[draggable="true"], .draggable, [data-drag]');
    for (const el of draggables) {
      interactions.push({
        type: 'drag',
        selector: el.id ? '#' + el.id : el.tagName.toLowerCase(),
        text: el.textContent?.trim()?.substring(0, 50)
      });
    }
  } catch (e) {}
  
  // Hoverable elements
  try {
    const hoverables = document.querySelectorAll('[onmouseover], [onmouseenter], .hover, [data-hover]');
    for (const el of hoverables) {
      interactions.push({
        type: 'hover',
        selector: el.id ? '#' + el.id : el.tagName.toLowerCase(),
        text: el.textContent?.trim()?.substring(0, 50)
      });
    }
  } catch (e) {}
  
  // Select elements
  try {
    const selects = document.querySelectorAll('select');
    for (const el of selects) {
      const options = Array.from(el.options).map(o => o.value);
      interactions.push({
        type: 'select',
        selector: el.id ? '#' + el.id : '[name="' + el.name + '"]',
        options
      });
    }
  } catch (e) {}
  
  // Keyboard-sensitive elements
  try {
    const keyElements = document.querySelectorAll('[onkeydown], [onkeyup], [onkeypress], [data-key]');
    for (const el of keyElements) {
      interactions.push({
        type: 'keyboard',
        selector: el.id ? '#' + el.id : el.tagName.toLowerCase()
      });
    }
  } catch (e) {}
  
  // Scroll containers
  try {
    const scrollables = document.querySelectorAll('[onscroll], .scroll, [data-scroll]');
    for (const el of scrollables) {
      interactions.push({
        type: 'scroll',
        selector: el.id ? '#' + el.id : el.tagName.toLowerCase()
      });
    }
  } catch (e) {}
  
  return interactions;
})();
`;

const CHECK_RESULT = `
(function() {
  const bodyText = document.body?.innerText?.toLowerCase() || '';
  const result = {
    success: false,
    failure: false,
    complete: false,
    message: ''
  };
  
  // Success patterns
  const successPatterns = [
    'correct', 'well done', 'success', 'passed', 'completed', 'great job',
    'congratulations', 'you got it', 'right answer', 'challenge complete',
    '✅', '🎉', 'next challenge', 'proceed'
  ];
  
  for (const pattern of successPatterns) {
    if (bodyText.includes(pattern)) {
      result.success = true;
      result.message = pattern;
      break;
    }
  }
  
  // Failure patterns
  const failurePatterns = [
    'incorrect', 'wrong', 'try again', 'failed', 'error', 'invalid',
    'not correct', 'nope', '❌', 'oops'
  ];
  
  for (const pattern of failurePatterns) {
    if (bodyText.includes(pattern)) {
      result.failure = true;
      result.message = pattern;
      break;
    }
  }
  
  // Completion patterns
  const completePatterns = [
    'all challenges complete', 'finished', 'you win', 'final score',
    'challenge 30', 'congratulations', 'all done'
  ];
  
  for (const pattern of completePatterns) {
    if (bodyText.includes(pattern)) {
      result.complete = true;
      break;
    }
  }
  
  // Extract challenge number
  try {
    const challengeMatch = bodyText.match(/challenge\s*(\d+)/i) || 
                           bodyText.match(/step\s*(\d+)/i) ||
                           bodyText.match(/(\d+)\s*\/\s*30/);
    if (challengeMatch) {
      result.challengeNumber = parseInt(challengeMatch[1]);
    }
  } catch (e) {
    // Ignore regex errors
  }
  
  return result;
})();
`;

// Export for Node.js / Python parsing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    CONSOLE_CAPTURE_INIT,
    GET_CONSOLE_LOGS,
    EXTRACT_PAGE_DATA,
    DETECT_INTERACTIONS,
    CHECK_RESULT
  };
}
