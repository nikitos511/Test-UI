import logging
import os
import pytest
from playwright.sync_api import sync_playwright

# Default target
DEFAULT_BASE_URL = os.getenv("BASE_URL", "https://effective-mobile.ru")

def pytest_addoption(parser):
    """Добавляем опции, но не падаем, если они уже добавлены где-то ещё."""
    try:
        parser.addoption(
            "--base-url",
            action="store",
            default=DEFAULT_BASE_URL,
            help="Base URL for tests"
        )
    except ValueError:
        pass

    try:
        parser.addoption(
            "--headless",
            action="store",
            default=os.getenv("HEADLESS", "1"),
            help="Run browser headless: 1 or 0"
        )
    except ValueError:
        pass

    try:
        parser.addoption("--viewport-width", action="store", default=os.getenv("VIEWPORT_WIDTH", "1280"))
    except ValueError:
        pass

    try:
        parser.addoption("--viewport-height", action="store", default=os.getenv("VIEWPORT_HEIGHT", "800"))
    except ValueError:
        pass


def _suppress_verbose_logs():
    logging.getLogger('playwright').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

@pytest.fixture(scope='session')
def playwright_instance():
    _suppress_verbose_logs()
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope='function')
def context(browser, request):
    width = int(request.config.getoption('--viewport-width'))
    height = int(request.config.getoption('--viewport-height'))
    context = browser.new_context(viewport={'width': width, 'height': height})
    yield context
    try:
        context.close()
    except Exception:
        pass

@pytest.fixture(scope='function')
def page(context):
    p = context.new_page()
    yield p
    try:
        p.close()
    except Exception:
        pass

@pytest.fixture(scope='session')
def base_url(request):
    # если опция плагина вернула пустую строку/None — используем DEFAULT_BASE_URL
    val = request.config.getoption('--base-url')
    if not val:
        val = DEFAULT_BASE_URL
    return val

