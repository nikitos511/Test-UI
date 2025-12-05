from typing import List, Dict, Optional
from playwright.sync_api import Page
from .base_page import BasePage

class HomePage(BasePage):
    """Page object for the home page. Keep methods small and test-focused."""

    def __init__(self, page: Page, base_url: Optional[str] = None):
        super().__init__(page, base_url)

    # Anchors / links
    def list_anchors(self) -> List[Dict]:
        anchors = self.page.locator('a')
        out = []
        for i in range(anchors.count()):
            a = anchors.nth(i)
            out.append({
                'text': a.inner_text(),
                'href': a.get_attribute('href'),
                'outer': a.evaluate('el => el.outerHTML')
            })
        return out

    def click_anchor_by_href(self, href: str):
        try:
            self.page.click(f'a[href="{href}"]', timeout=3000)
            return True
        except Exception:
            selector = f"a[href=\\\"{href}\\\"]"
            try:
                el = self.page.locator(selector)
                if el.count():
                    el.first.click()
                    return True
            except Exception:
                pass
        raise RuntimeError(f"Could not click anchor by href={href}")

    # Buttons
    def list_buttons(self) -> List[Dict]:
        loc = self.page.locator("button, [role='button'], a[role='button']")
        out = []
        for i in range(loc.count()):
            b = loc.nth(i)
            out.append({
                'text': b.inner_text(),
                'outer': b.evaluate('el => el.outerHTML'),
                'id': b.get_attribute('id'),
                'class': b.get_attribute('class'),
                'aria': b.get_attribute('aria-label')
            })
        return out

    def click_button_by_selector(self, selector: str):
        return self.page.click(selector)

    def click_by_outer(self, outer_html: str):
        snippet = (outer_html or '').strip()[:300].replace('\n', ' ').replace('"', '\\"')
        if not snippet:
            raise RuntimeError('empty outer html')
        script = f'''() => {{
            const nodes = [...document.querySelectorAll('*')].filter(n=>n.outerHTML && n.outerHTML.includes("{snippet}"));
            if(!nodes.length) return {{ok:false, reason:'not_found'}};
            const el = nodes[0];
            try{{ el.scrollIntoView({{behavior:'auto', block:'center'}}); }}catch(e){{}}
            try{{ el.click(); return {{ok:true}}; }}catch(e){{
                try{{ el.dispatchEvent(new MouseEvent('click',{{bubbles:true,cancelable:true,view:window}})); return {{ok:true, reason:'dispatched'}}; }}catch(e2){{ return {{ok:false, reason:String(e2)}}; }}
            }}
        }}'''
        res = self.page.evaluate(script)
        if isinstance(res, dict) and res.get('ok'):
            return True
        raise RuntimeError(f'click_by_outer failed: {res}')
