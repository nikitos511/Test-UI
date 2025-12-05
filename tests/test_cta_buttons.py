# tests/test_cta_buttons.py
import os
import time
import json
import uuid
import datetime
import allure

from typing import Optional, Tuple, Dict, Any

from pages.home_page import HomePage
from utils.soft_assert import SoftAssert
from utils.trackers import INJECT_SCROLL_MONKEY, CLEAR_SCROLL_TARGETS, GET_SCROLL_TARGETS
from utils.locator_utils import get_closest_section_by_scroll
from utils.helpers import wait_for_scroll_finished, device_pixel_ratio

SCREENSHOT_DIR = "screenshots/cta"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _unique_name(prefix: str, idx: int, ext: str = "png") -> str:
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S.%f")[:-3]
    return f"{prefix}_{idx}_{ts}_{uuid.uuid4().hex[:6]}.{ext}"


def _save_meta(path: str, data: Dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _is_carousel_button(btn_locator) -> bool:
    try:
        slot = None
        try:
            slot = btn_locator.get_attribute("data-slot")
        except Exception:
            slot = None
        if slot and ("carousel" in slot or "swiper" in slot or "slide" in slot):
            return True
        # check class tokens
        try:
            cls = btn_locator.get_attribute("class") or ""
            if any(k in cls for k in ("carousel", "swiper", "splide", "slick", "glide", "track")):
                return True
        except Exception:
            pass
        # check aria label text
        try:
            txt = btn_locator.inner_text() or ""
            if "slide" in txt.lower() or "previous" in txt.lower() or "next" in txt.lower():
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def _is_positioned_absolute_or_fixed(locator) -> bool:
    try:
        pos = locator.evaluate("el => getComputedStyle(el).position")
        return pos in ("absolute", "fixed")
    except Exception:
        return False


def _locator_screenshot_with_fallbacks(page, locator, shot_path: str) -> Tuple[Optional[str], Optional[dict]]:
    """
    Robust screenshot for locator with special handling for absolute/fixed elements.
    Returns (shot_path, meta) or (None, None).
    """
    # if element is absolutely/fixed positioned — prefer element_handle.screenshot without scroll
    try:
        positioned = _is_positioned_absolute_or_fixed(locator)
    except Exception:
        positioned = False

    # 1) If positioned absolutely/fixed -> try element_handle.screenshot first
    if positioned:
        try:
            el = locator.element_handle()
            if el:
                try:
                    el.screenshot(path=shot_path)
                    meta = {"method": "element_handle.screenshot (absolute/fixed)"}
                    return shot_path, meta
                except Exception:
                    pass
        except Exception:
            pass

    # 2) locator.screenshot (preferred for normal inline elements)
    try:
        try:
            # avoid forcing scroll for absolute elements (we handled above)
            if not positioned:
                locator.scroll_into_view_if_needed(timeout=1200)
        except Exception:
            pass
        try:
            page.wait_for_timeout(120)
        except Exception:
            time.sleep(0.12)
        locator.screenshot(path=shot_path)
        meta = {"method": "locator.screenshot", "positioned": positioned}
        return shot_path, meta
    except Exception:
        pass

    # 3) element_handle.screenshot with temp style
    try:
        el = locator.element_handle()
    except Exception:
        el = None

    if el:
        try:
            el.screenshot(path=shot_path)
            meta = {"method": "element_handle.screenshot"}
            return shot_path, meta
        except Exception:
            # try temp style
            try:
                tmp_id = f"pw_tmp_{int.from_bytes(os.urandom(4), 'little') & 0xffff}"
                applied = el.evaluate(
                    """(el, tmpId) => {
                        try {
                            el.__pw_old_style = el.getAttribute('style') || '';
                            el.setAttribute('data-pw-tmp-id', tmpId);
                            el.style.visibility = 'visible';
                            el.style.opacity = '1';
                            el.style.transform = 'none';
                            el.style.zIndex = '2147483647';
                            return true;
                        } catch(e) { return false; }
                    }""",
                    tmp_id,
                )
                if applied:
                    try:
                        el2 = el._page.query_selector(f'[data-pw-tmp-id="{tmp_id}"]')
                    except Exception:
                        el2 = None
                    if el2:
                        try:
                            page.wait_for_timeout(120)
                        except Exception:
                            time.sleep(0.12)
                        el2.screenshot(path=shot_path)
                        meta = {"method": "element_handle.screenshot_temp_style"}
                        try:
                            page.evaluate("() => document.querySelectorAll('[data-pw-tmp-id]').forEach(n=>n.removeAttribute('data-pw-tmp-id'))")
                        except Exception:
                            pass
                        return shot_path, meta
            except Exception:
                pass

    # 4) page.clip using bounding box (DPR-aware)
    box = None
    if el:
        try:
            box = el.bounding_box()
        except Exception:
            box = None

    if box:
        try:
            dpr = device_pixel_ratio(page) or 1.0
            pad = 6
            clip = {
                "x": max(0, int(box["x"] * dpr) - pad),
                "y": max(0, int(box["y"] * dpr) - pad),
                "width": max(1, int(box["width"] * dpr) + pad * 2),
                "height": max(1, int(box["height"] * dpr) + pad * 2),
            }
            # don't center if absolute: we trust bounding coords
            try:
                if not positioned:
                    locator.evaluate("el => el.scrollIntoView({block:'center', inline:'center'})")
            except Exception:
                pass
            try:
                page.wait_for_timeout(120)
            except Exception:
                time.sleep(0.12)
            page.screenshot(path=shot_path, clip=clip)
            meta = {"method": "page.clip", "clip": clip, "bounding": box}
            return shot_path, meta
        except Exception:
            pass

    # 5) full page fallback
    try:
        page.screenshot(path=shot_path, full_page=True)
        meta = {"method": "page.full"}
        return shot_path, meta
    except Exception:
        return None, None


def _find_button_locator(page, b: dict, idx: Optional[int] = None):
    """
    Find a reliable locator for a button dict returned from page object.
    Priority: data-pw-idx -> id -> visible text -> first class token -> outerHTML
    """
    # prefer data-pw-idx if present (we sometimes add it)
    if idx is not None:
        try:
            l = page.locator(f'[data-pw-idx="{idx}"]')
            if l.count() > 0:
                return l.first
        except Exception:
            pass

    # by id
    el_id = b.get("id")
    if el_id:
        try:
            l = page.locator(f"#{el_id}")
            if l.count() > 0:
                return l.first
        except Exception:
            pass

    # by exact visible text (button)
    txt = (b.get("text") or "").strip()
    if txt:
        try:
            l = page.locator(f'button:has-text("{txt}")')
            if l.count() > 0:
                return l.first
        except Exception:
            pass

    # by first class token
    cls = (b.get("class") or "").strip()
    if cls:
        for part in cls.split()[:3]:
            if not part:
                continue
            try:
                l = page.locator(f".{part}")
                if l.count() > 0:
                    return l.first
            except Exception:
                pass

    # outerHTML fallback: mark first matching node with data attr then return it
    outer = (b.get("outer") or "").strip()
    if outer:
        snippet = outer[:240].replace('"', '\\"').replace("\n", " ")
        try:
            ok = page.evaluate(
                """(snippet) => {
                    const nodes = [...document.querySelectorAll('*')].filter(n => n.outerHTML && n.outerHTML.includes(snippet));
                    if (!nodes.length) return false;
                    nodes[0].setAttribute('data-pw-found', '1');
                    return true;
                }""",
                snippet,
            )
            if ok:
                l = page.locator('[data-pw-found="1"]')
                if l.count() > 0:
                    # cleanup attribute but return the locator
                    try:
                        page.evaluate("() => document.querySelectorAll('[data-pw-found]').forEach(n=>n.removeAttribute('data-pw-found'))")
                    except Exception:
                        pass
                    return l.first
        except Exception:
            pass

    return None


def _get_target_id_from_button_locator(btn_locator) -> Optional[Dict[str, str]]:
    """
    Inspect button and ancestors to find an explicit target id (href="#id", data-target, aria-controls...).
    Returns dict {'id': id, 'source': source} or None.
    """
    try:
        info = btn_locator.evaluate(
            """el => {
                try {
                    let n = el;
                    while (n) {
                        try {
                            if (n.tagName && n.tagName.toLowerCase() === 'a') {
                                const href = n.getAttribute('href');
                                if (href && href.startsWith('#') && href.length>1) return {id: href.slice(1), source: 'href'};
                            }
                            const attrs = ['data-target','data-href','aria-controls','data-bs-target','data-target-id'];
                            for (const a of attrs) {
                                try {
                                    const v = n.getAttribute && n.getAttribute(a);
                                    if (v) {
                                        if (v.startsWith('#')) return {id: v.replace(/^#/,'') , source: a};
                                        const m = String(v).match(/#([A-Za-z0-9-_]+)/);
                                        if (m) return {id: m[1], source: a};
                                    }
                                } catch(e){}
                            }
                        } catch(e){}
                        n = n.parentElement;
                    }
                } catch(e){}
                return null;
            }"""
        )
        return info
    except Exception:
        return None


def _click_button(hp: HomePage, page, b: dict, btn_locator=None) -> Tuple[bool, Optional[str]]:
    """
    Clicks button: prefer btn_locator; fallback by outerHTML via page.evaluate.
    Returns (ok, reason).
    """
    clicked = False
    
    # ПРОВЕРКА DISABLED КНОПКИ (ДОБАВЛЯЕМ ТОЛЬКО ЭТО)
    if btn_locator is not None:
        # Простая проверка: есть ли атрибут disabled
        disabled_attr = btn_locator.get_attribute("disabled")
        if disabled_attr is not None:
            return False, "disabled"
    
    if btn_locator is not None:
        try:
            # attempt click via locator
            try:
                enabled = True
                try:
                    enabled = btn_locator.is_enabled()
                except Exception:
                    enabled = True
                if not enabled:
                    return False, "disabled"
            except Exception:
                pass
            btn_locator.click(timeout=5000)
            clicked = True
        except Exception:
            # fallback to outer click
            try:
                hp.click_by_outer(b.get("outer") or "")
                clicked = True
            except Exception as e:
                return False, str(e)
    else:
        # fallback: outerHTML click
        try:
            hp.click_by_outer(b.get("outer") or "")
            clicked = True
        except Exception as e:
            return False, str(e)

    if clicked:
        wait_for_scroll_finished(page, timeout=6000)
        return True, None
    return False, "not_clicked"


# ----------------- helper: wait for element animations / transforms to finish -----------------
def wait_for_element_animations_and_transform(page, locator, timeout: int = 3000):
    """
    Wait until element animations (Web Animations API) are not running and computed
    transform/opacity/filter values stabilize for a short period.
    """
    try:
        # wait for no running animations (best-effort)
        try:
            page.wait_for_function(
                "(el) => { try { return !(el.getAnimations && el.getAnimations().some(a=>a.playState==='running')); } catch(e){ return true; } }",
                locator,
                timeout=timeout,
            )
        except Exception:
            pass

        # now wait until transform/opacity/filter stop changing for short period
        try:
            page.wait_for_function(
                """(el) => {
                    try {
                        const getState = () => {
                            const s = getComputedStyle(el);
                            return s.transform + '|' + s.opacity + '|' + s.filter;
                        };
                        let prev = getState();
                        return new Promise((resolve) => {
                            let checks = 0;
                            const id = setInterval(() => {
                                const cur = getState();
                                if (cur === prev) {
                                    checks += 1;
                                    if (checks >= 3) {
                                        clearInterval(id);
                                        resolve(true);
                                    }
                                } else {
                                    checks = 0;
                                    prev = cur;
                                }
                            }, 60);
                            // safety timeout handled by Playwright wait_for_function timeout
                        });
                    } catch(e) { return true; }
                }""",
                locator,
                timeout=timeout,
            )
        except Exception:
            pass
    except Exception:
        pass
# -----------------------------------------------------------------------------------------------


def test_cta_buttons_scroll(page, base_url):
    soft = SoftAssert()
    hp = HomePage(page, base_url)

    # open page
    hp.goto("/")
    hp.wait_for_network_idle(timeout=60_000)

    # inject simple tracker that records scrollIntoView calls
    try:
        page.evaluate(INJECT_SCROLL_MONKEY)
    except Exception:
        pass

    # collect buttons snapshot from page object
    buttons = hp.list_buttons()

    # optionally tag nodes with index attribute to help locate exact node later
    try:
        page.evaluate(
            """
            () => {
                const nodes = [...document.querySelectorAll("button, [role='button'], a[role='button']")];
                nodes.forEach((n,i) => { try { n.setAttribute('data-pw-idx', String(i)); } catch(e) {} });
                return nodes.length;
            }
            """
        )
    except Exception:
        pass

    for idx, b in enumerate(buttons):
        btn_text = (b.get("text") or "").strip()[:80] or f"NO_TEXT_{idx}"
        step_title = f'CTA #{idx} "{btn_text}"'

        with allure.step(step_title):
            try:
                # clear previous tracked targets
                try:
                    page.evaluate(CLEAR_SCROLL_TARGETS)
                except Exception:
                    pass

                # find locator for this button (prefer indexed locator)
                btn_locator = _find_button_locator(page, b, idx=idx)

                # attach outerHTML for debug
                try:
                    outer_html = b.get("outer") or ""
                    if outer_html:
                        allure.attach(outer_html, name=f"clicked_outer_{idx}", attachment_type=allure.attachment_type.TEXT)
                    if btn_locator:
                        # attach the evaluated outerHTML as well if available
                        try:
                            val = btn_locator.evaluate("el => el.outerHTML")
                            allure.attach(val, name=f"clicked_outer_evaluated_{idx}", attachment_type=allure.attachment_type.TEXT)
                        except Exception:
                            pass
                except Exception:
                    pass

                # special-case: carousel controls -> click and screenshot viewport / slide container
                is_carousel = False
                try:
                    if btn_locator:
                        is_carousel = _is_carousel_button(btn_locator)
                    else:
                        # if no locator but outer mentions carousel slot
                        outer = (b.get("outer") or "").lower()
                        if "carousel" in outer or "swiper" in outer or "carousel-prev" in outer or "carousel-next" in outer:
                            is_carousel = True
                except Exception:
                    is_carousel = False

                if is_carousel:
                    ok, reason = _click_button(hp, page, b, btn_locator=btn_locator)
                    try:
                        tg = page.evaluate(GET_SCROLL_TARGETS) or []
                        allure.attach(json.dumps(tg, ensure_ascii=False, indent=2), name=f"GET_SCROLL_TARGETS_after_click_{idx}", attachment_type=allure.attachment_type.JSON)
                    except Exception:
                        pass

                    if not ok:
                        soft.add(f"Carousel button '{btn_text}' click failed: {reason}")
                        continue

                    # Try to find slider container nearby (heuristic)
                    shot_name = _unique_name("carousel_view", idx)
                    shot_path = os.path.join(SCREENSHOT_DIR, shot_name)

                    # Prefer the outermost carousel element first
                    carousel = None
                    try:
                        candidate = page.locator("[data-slot='carousel']").first
                        try:
                            if candidate.count() > 0:
                                carousel = candidate
                        except Exception:
                            # in some cases .count may fail; assume candidate exists
                            carousel = candidate
                    except Exception:
                        carousel = None

                    # fallback: try ancestor of the button (legacy)
                    if not carousel and btn_locator:
                        try:
                            candidate2 = btn_locator.locator(
                                "xpath=ancestor::*[contains(@class,'carousel') or contains(@data-slot,'carousel')][1]"
                            )
                            try:
                                if candidate2.count() > 0:
                                    carousel = candidate2
                            except Exception:
                                carousel = candidate2
                        except Exception:
                            carousel = None

                    # final fallback: generic .carousel class
                    if not carousel:
                        try:
                            cand3 = page.locator(".carousel").first
                            try:
                                if cand3.count() > 0:
                                    carousel = cand3
                            except Exception:
                                carousel = cand3
                        except Exception:
                            carousel = None

                    # If we have a carousel element — center it, wait for animations to finish, then take viewport screenshot
                    if carousel:
                        try:
                            # scroll carousel into center of viewport if possible
                            try:
                                carousel.evaluate("el => el.scrollIntoView({block:'center', inline:'center'})")
                            except Exception:
                                try:
                                    carousel.scroll_into_view_if_needed(timeout=1200)
                                except Exception:
                                    pass

                            # wait for animations/transforms to finish on carousel
                            wait_for_element_animations_and_transform(page, carousel, timeout=3000)

                            # slight extra pause to let compositing finish
                            try:
                                page.wait_for_timeout(120)
                            except Exception:
                                time.sleep(0.12)

                            # TAKE VIEWPORT SCREENSHOT (consistent with other screenshots)
                            try:
                                page.screenshot(path=shot_path)
                                try:
                                    allure.attach.file(shot_path, name=f"{step_title} - carousel_viewport", attachment_type=allure.attachment_type.PNG)
                                except Exception:
                                    pass
                            except Exception:
                                # fallback to full page if viewport shot fails
                                try:
                                    page.screenshot(path=shot_path, full_page=True)
                                    try:
                                        allure.attach.file(shot_path, name=f"{step_title} - carousel_fullpage_fallback", attachment_type=allure.attachment_type.PNG)
                                    except Exception:
                                        pass
                                except Exception:
                                    soft.add(f"Carousel '{btn_text}' clicked but screenshot failed.")
                        except Exception as e:
                            soft.add(f"Carousel '{btn_text}' screenshot flow error: {e}")
                        continue  # go to next button after carousel handling

                    # if no carousel locator found, do a safe viewport screenshot anyway
                    try:
                        page.screenshot(path=shot_path)
                        try:
                            allure.attach.file(shot_path, name=f"{step_title} - carousel_viewport_no_container", attachment_type=allure.attachment_type.PNG)
                        except Exception:
                            pass
                    except Exception:
                        pass

                    continue

                # click the button (normal flow)
                ok, reason = _click_button(hp, page, b, btn_locator=btn_locator)

                # attach tracker snapshot right after click
                try:
                    tg = page.evaluate(GET_SCROLL_TARGETS) or []
                    allure.attach(json.dumps(tg, ensure_ascii=False, indent=2), name=f"GET_SCROLL_TARGETS_after_click_{idx}", attachment_type=allure.attachment_type.JSON)
                except Exception:
                    pass

                if not ok:
                    # Если кнопка disabled - пропускаем без ошибки
                    if "disabled" in reason:
                        with allure.step(f"Пропускаем disabled кнопку: '{btn_text}'"):
                            allure.attach(
                                f"Кнопка '{btn_text}' отключена (disabled)",
                                name="Пропуск disabled кнопки",
                                attachment_type=allure.attachment_type.TEXT
                            )
                        continue
                    # Все остальные ошибки записываем
                    soft.add(f"Button '{btn_text}' click failed: {reason}")
                    continue

                # Attempt to resolve target id via several heuristics (priority order)
                target_locator = None
                selected_info = None

                # 1) from button attributes / ancestors
                if btn_locator:
                    try:
                        info = _get_target_id_from_button_locator(btn_locator)
                        if info and info.get("id"):
                            tid = info.get("id")
                            exists = False
                            try:
                                exists = page.evaluate("id => !!document.getElementById(id)", tid)
                            except Exception:
                                exists = False
                            if exists:
                                target_locator = page.locator(f"#{tid}")
                                selected_info = {"id": tid, "source": info.get("source")}
                    except Exception:
                        pass

                # 2) GET_SCROLL_TARGETS (js tracker)
                if target_locator is None:
                    try:
                        tg = page.evaluate(GET_SCROLL_TARGETS) or []
                    except Exception:
                        tg = []
                    if tg and isinstance(tg, list) and len(tg) > 0:
                        first = tg[0]
                        if isinstance(first, dict) and first.get("id"):
                            tid = first.get("id")
                            exists = False
                            try:
                                exists = page.evaluate("id => !!document.getElementById(id)", tid)
                            except Exception:
                                exists = False
                            if exists:
                                target_locator = page.locator(f"#{tid}")
                                selected_info = {"id": tid, "via": "scrollIntoView_tracker", "targets": tg}

                # 3) ancestor section id heuristic
                if target_locator is None and btn_locator:
                    try:
                        anc = btn_locator.evaluate(
                            """
                            el => {
                                let n = el;
                                while (n && n !== document.documentElement) {
                                    try {
                                        if (n.id && (n.tagName.toLowerCase()==='section' || n.tagName.toLowerCase()==='main' || (n.getAttribute && n.getAttribute('role')==='region'))) {
                                            return n.id;
                                        }
                                    } catch(e){}
                                    n = n.parentElement;
                                }
                                return null;
                            }
                            """
                        )
                        if anc:
                            exists = False
                            try:
                                exists = page.evaluate("id => !!document.getElementById(id)", anc)
                            except Exception:
                                exists = False
                            if exists:
                                target_locator = page.locator(f"#{anc}")
                                selected_info = {"id": anc, "via": "ancestor_section"}
                    except Exception:
                        pass

                # 4) nearest section by scroll fallback
                if target_locator is None:
                    try:
                        nearest = get_closest_section_by_scroll(page)
                        if nearest and nearest.get("id"):
                            target_locator = page.locator(f'#{nearest.get("id")}')
                            selected_info = nearest
                    except Exception:
                        pass

                # attach selected info for debugging
                try:
                    if selected_info:
                        allure.attach(json.dumps(selected_info, ensure_ascii=False, indent=2), name=f"selected_info_{idx}", attachment_type=allure.attachment_type.JSON)
                except Exception:
                    pass

                # capture screenshot of target or fallback to full-page
                if target_locator and target_locator.count() > 0:
                    shot_name = _unique_name("btn_target", idx)
                    shot_path = os.path.join(SCREENSHOT_DIR, shot_name)
                    path, meta = _locator_screenshot_with_fallbacks(page, target_locator.first, shot_path)
                    if path:
                        try:
                            allure.attach.file(path, name=f"{step_title} - target_shot", attachment_type=allure.attachment_type.PNG)
                        except Exception:
                            pass
                        if meta:
                            mpath = shot_path + ".meta.json"
                            _save_meta(mpath, meta)
                            try:
                                allure.attach(json.dumps(meta, ensure_ascii=False, indent=2), name=f"{step_title} - meta", attachment_type=allure.attachment_type.JSON)
                            except Exception:
                                pass
                    else:
                        # final fallback: full page
                        full = os.path.join(SCREENSHOT_DIR, f"btn_fallback_full_{idx}.png")
                        try:
                            page.screenshot(path=full)
                            allure.attach.file(full, name=f"{step_title} - fallback_full", attachment_type=allure.attachment_type.PNG)
                        except Exception:
                            pass
                        soft.add(f"Target for button '{btn_text}' found but screenshot attempts failed.")
                else:
                    # no target found -> attach full page and record soft error
                    full = os.path.join(SCREENSHOT_DIR, f"btn_no_target_{idx}.png")
                    try:
                        page.screenshot(path=full)
                        allure.attach.file(full, name=f"{step_title} - no_target_full", attachment_type=allure.attachment_type.PNG)
                    except Exception:
                        pass
                    soft.add(f"No target found for CTA '{btn_text}'")

            except AssertionError as ae:
                p = os.path.join(SCREENSHOT_DIR, f"btn_error_{idx}.png")
                try:
                    page.screenshot(path=p)
                    allure.attach.file(p, name=f"{step_title} - error_screenshot", attachment_type=allure.attachment_type.PNG)
                except Exception:
                    pass
                soft.add(f"CTA '{btn_text}': {ae}")

            except Exception as e:
                p = os.path.join(SCREENSHOT_DIR, f"btn_exception_{idx}.png")
                try:
                    page.screenshot(path=p)
                    allure.attach.file(p, name=f"{step_title} - exception_screenshot", attachment_type=allure.attachment_type.PNG)
                except Exception:
                    pass
                soft.add(f"CTA '{btn_text}' unexpected exception: {e}")

    # final summary (fail test if any collected errors)
    soft.assert_all()
