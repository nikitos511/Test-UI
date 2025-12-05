from typing import Optional
import time

def sanitize_href(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    return href.strip()

def is_email_or_telegram(href: Optional[str]) -> bool:
    if not href:
        return False
    l = href.lower()
    return l.startswith('mailto:') or l.startswith('tg:') or l.startswith('tel:')

def wait_for_scroll_finished(page, timeout: int = 2000, poll: float = 0.1):
    start = time.time()
    prev = page.evaluate('() => window.scrollY')
    while True:
        time.sleep(poll)
        curr = page.evaluate('() => window.scrollY')
        if curr == prev:
            return curr
        prev = curr
        if (time.time() - start) * 1000 > timeout:
            return curr

def device_pixel_ratio(page) -> float:
    try:
        return float(page.evaluate('() => window.devicePixelRatio || 1'))
    except Exception:
        return 1.0

def is_button_disabled(button_locator) -> bool:
    """
    Проверяет, отключена ли кнопка.
    Возвращает True, если кнопка имеет любой из признаков отключения.
    """
    try:
        # 1. Проверка атрибута disabled
        disabled_attr = button_locator.get_attribute("disabled")
        if disabled_attr is not None:
            return True
        
        # 2. Проверка класса disabled
        class_attr = button_locator.get_attribute("class") or ""
        class_lower = class_attr.lower()
        disabled_classes = ["disabled", "inactive", "btn-disabled", "is-disabled"]
        if any(disabled_class in class_lower for disabled_class in disabled_classes):
            return True
        
        # 3. Проверка aria-disabled
        aria_disabled = button_locator.get_attribute("aria-disabled")
        if aria_disabled and aria_disabled.lower() == "true":
            return True
        
        # 4. Проверка через computed style (полупрозрачность)
        opacity = button_locator.evaluate("""
            el => {
                const style = window.getComputedStyle(el);
                return parseFloat(style.opacity);
            }
        """)
        if opacity < 0.5:  # Сильно прозрачный элемент может быть неактивным
            return True
            
        # 5. Проверка курсора
        cursor = button_locator.evaluate("""
            el => {
                const style = window.getComputedStyle(el);
                return style.cursor;
            }
        """)
        if cursor in ["not-allowed", "default"]:
            return True
            
    except Exception:
        # Если не смогли проверить, считаем что кнопка активна
        pass
    
    return False
