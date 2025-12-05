from playwright.sync_api import Page
from typing import Optional
from urllib.parse import urljoin

class BasePage:
    """Minimal base page with common utilities used by Page Objects."""

    def __init__(self, page: Page, base_url: Optional[str] = None):
        self.page = page
        self.base_url = base_url

    def goto(self, path: str = '/'):
        """
        Переход на страницу:
        - если path — абсолютный URL (http:// или https://), используем как есть;
        - иначе объединяем base_url + path; если base_url пуст — используем path as-is (но лучше, если base_url задан).
        """
        if path is None:
            path = '/'
        path = str(path)
        # Если path уже абсолютный URL — используем напрямую
        if path.startswith('http://') or path.startswith('https://') or path.startswith('//'):
            url = path
        else:
            # Используем base_url, если он задан; иначе fallback к DEFAULT_BASE_URL если есть
            base = getattr(self, "base_url", None) or None
            if not base:
                # если base отсутствует — пытаемся перейти по path если это полный путь (но Playwright требует валидный URL)
                raise RuntimeError("Base URL is not configured; cannot navigate to relative path: '{}'".format(path))
            url = urljoin(base.rstrip('/') + '/', path.lstrip('/'))
        self.page.goto(url)

    def current_url(self) -> str:
        return self.page.url

    def wait_for_network_idle(self, timeout: int = 30_000):
        try:
            self.page.wait_for_load_state('networkidle', timeout=timeout)
        except Exception:
            pass

    def click(self, selector: str, **kwargs):
        return self.page.click(selector, **kwargs)

    def find(self, selector: str):
        return self.page.locator(selector)

    def execute(self, script: str, *args):
        return self.page.evaluate(script, *args)

    def screenshot_of(self, path: str, **kwargs):
        return self.page.screenshot(path=path, **kwargs)
