INJECT_SCROLL_MONKEY = """
(() => {
  if (window.__playwright_scroll_targets) return;
  window.__playwright_scroll_targets = [];
  const original = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function() {
    try {
      const info = { id: this.id || null, classes: this.className || null, tag: this.tagName, text: (this.innerText||'').slice(0,120) };
      window.__playwright_scroll_targets.push(info);
    } catch (e) {}
    try { original.apply(this, arguments); } catch(e) {}
  };
})();
"""

GET_SCROLL_TARGETS = "(() => window.__playwright_scroll_targets || [])();"
CLEAR_SCROLL_TARGETS = "(() => { window.__playwright_scroll_targets = []; })();"
