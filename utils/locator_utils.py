import os
import time
from playwright.sync_api import Locator
from typing import Optional, Dict

def is_element_visible(locator: Locator, fraction: float = 0.1) -> bool:
    return locator.evaluate(
        "el => { const rect = el.getBoundingClientRect(); const vh = window.innerHeight || document.documentElement.clientHeight; if (!rect.height) return false; const visibleHeight = Math.min(rect.bottom, vh) - Math.max(rect.top, 0); return visibleHeight > (rect.height * %f); }" % fraction
    )

def take_element_screenshot(locator: Locator, path: str, ensure_visible: bool = True):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    try:
        if ensure_visible:
            try:
                locator.scroll_into_view_if_needed(timeout=2000)
                time.sleep(0.08)
            except Exception:
                pass
        locator.screenshot(path=path)
    except Exception:
        raise

def get_closest_section_by_scroll(page) -> Optional[Dict]:
    script = '''() => {
        try {
            const sections = [...document.querySelectorAll('section, [role=region], main, header, footer')];
            const top = window.innerHeight/4;
            let best = null;
            let bestDist = 1e9;
            for (const s of sections) {
                const r = s.getBoundingClientRect();
                const dist = Math.abs(r.top - top);
                if (r.height && dist < bestDist) {
                    bestDist = dist; best = s;
                }
            }
            if (!best) return null;
            return { id: best.id || null, classes: best.className || null, text: (best.innerText||'').slice(0,200) };
        } catch(e) { return null; }
    }'''
    try:
        return page.evaluate(script)
    except Exception:
        return None
