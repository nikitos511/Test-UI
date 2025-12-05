# tests/test_anchors_and_links.py
import os
import json
import uuid
import datetime
import allure

from pages.home_page import HomePage
from utils.soft_assert import SoftAssert
from utils.trackers import INJECT_SCROLL_MONKEY, GET_SCROLL_TARGETS, CLEAR_SCROLL_TARGETS
from utils.locator_utils import take_element_screenshot, get_closest_section_by_scroll
from utils.helpers import sanitize_href, is_email_or_telegram, wait_for_scroll_finished
from playwright.sync_api import TimeoutError as PWTimeoutError

SCREENSHOT_DIR = "screenshots/anchors"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _unique_name(prefix: str, idx: int, ext: str = "png") -> str:
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S.%f")[:-3]
    return f"{prefix}_{idx}_{ts}_{uuid.uuid4().hex[:6]}.{ext}"


def _find_anchor_locator(page, href: str):
    try:
        l = page.locator(f'a[href="{href}"]')
        if l.count():
            return l.first
    except Exception:
        pass
    try:
        token = href.split("/")[-1]
        if token:
            l = page.locator(f'a[href*="{token}"]')
            if l.count():
                return l.first
    except Exception:
        pass
    try:
        l = page.locator(f'a').filter(has_text=token if token else "")
        if l.count():
            return l.first
    except Exception:
        pass
    return None


def test_anchors_and_links(page, base_url):
    soft = SoftAssert()
    hp = HomePage(page, base_url)
    hp.goto("/")
    hp.wait_for_network_idle(timeout=60_000)

    try:
        page.evaluate(INJECT_SCROLL_MONKEY)
    except Exception:
        pass

    anchors = hp.list_anchors()

    for idx, a in enumerate(anchors):
        href = sanitize_href(a.get("href"))
        text = (a.get("text") or "").strip()[:120]
        outer_html = a.get("outer", "")

        if not href or is_email_or_telegram(href):
            continue

        step_title = f'Anchor #{idx} "{text}" -> {href}'

        try:
            with allure.step(step_title):
                try:
                    page.evaluate(CLEAR_SCROLL_TARGETS)
                except Exception:
                    pass

                if outer_html:
                    try:
                        allure.attach(outer_html, name=f"anchor_outer_{idx}", attachment_type=allure.attachment_type.TEXT)
                    except Exception:
                        pass

                try:
                    loc = _find_anchor_locator(page, href)
                    if loc:
                        try:
                            evaluated_html = loc.evaluate("el => el.outerHTML")
                            allure.attach(evaluated_html, name=f"anchor_evaluated_{idx}", attachment_type=allure.attachment_type.TEXT)
                        except Exception:
                            pass
                except Exception:
                    pass

                # --- internal anchor handling ---
                if href.startswith("#"):
                    target_id = href[1:]
                    exists = False
                    try:
                        exists = page.evaluate("id => !!document.getElementById(id)", target_id)
                    except Exception:
                        exists = False
                    if not exists:
                        raise AssertionError(f"Target id '{target_id}' not found")

                    try:
                        try:
                            hp.click_anchor_by_href(href)
                        except Exception:
                            hp.click_by_outer(outer_html)
                        wait_for_scroll_finished(page, timeout=3000)
                    except Exception as e:
                        raise AssertionError(f"Clicking anchor failed: {e}")

                    try:
                        scroll_targets = page.evaluate(GET_SCROLL_TARGETS) or []
                        if scroll_targets:
                            allure.attach(json.dumps(scroll_targets, ensure_ascii=False, indent=2),
                                          name=f"GET_SCROLL_TARGETS_after_click_{idx}", attachment_type=allure.attachment_type.JSON)
                    except Exception:
                        pass

                    try:
                        section_info = get_closest_section_by_scroll(page)
                        if section_info:
                            allure.attach(json.dumps(section_info, ensure_ascii=False, indent=2),
                                          name=f"selected_section_info_{idx}", attachment_type=allure.attachment_type.JSON)
                    except Exception:
                        pass

                    try:
                        locator = page.locator(f"#{target_id}")
                        shot = os.path.join(SCREENSHOT_DIR, _unique_name(f"target_{idx}_{target_id}", idx))
                        take_element_screenshot(locator, shot, ensure_visible=True)
                        # attach only on success
                        try:
                            allure.attach.file(shot, name=f'Anchor #{idx} screenshot', attachment_type=allure.attachment_type.PNG)
                        except Exception:
                            pass
                    except Exception as e:
                        raise AssertionError(f"Failed to capture target screenshot: {e}")

                else:
                    # --- external link handling ---
                    original_url = page.url
                    original_domain = base_url.split("//")[-1].split("/")[0] if base_url else ""
                    locator = _find_anchor_locator(page, href)
                    success = False
                    last_err = None

                    # strategy A: popup
                    if locator:
                        try:
                            with page.context.expect_page(timeout=5000) as new_page_info:
                                try:
                                    locator.click(timeout=4000)
                                except Exception:
                                    locator.click(timeout=4000, force=True)
                            new_page = new_page_info.value
                            try:
                                new_page.wait_for_load_state("networkidle", timeout=10000)
                            except Exception:
                                pass
                            new_url = new_page.url or ""
                            new_domain = new_url.split("//")[-1].split("/")[0] if new_url else ""
                            if (new_domain and original_domain and original_domain not in new_domain) or (new_url and new_url != original_url):
                                success = True
                                try:
                                    new_page.close()
                                except Exception:
                                    pass
                            else:
                                try:
                                    new_page.close()
                                except Exception:
                                    pass
                                last_err = AssertionError(f"External link opened in popup but did not navigate: {href}")
                        except Exception as e:
                            last_err = e

                    # strategy B: same-tab click
                    if not success:
                        try:
                            if locator:
                                try:
                                    locator.click(timeout=3000)
                                except Exception:
                                    locator.click(timeout=3000, force=True)
                            else:
                                try:
                                    page.evaluate(
                                        """(h) => {
                                            const el = document.querySelector(`a[href="${h}"]`) || [...document.querySelectorAll('a')].find(x => x.href && x.href.includes(h));
                                            if (el) { el.click(); return true; } return false;
                                        }""",
                                        href,
                                    )
                                except Exception:
                                    pass

                            try:
                                page.wait_for_function("old => location.href !== old", arg=original_url, timeout=7000)
                                new_url = page.url
                                if new_url != original_url:
                                    success = True
                                    try:
                                        page.goto(original_url)
                                        page.wait_for_load_state("networkidle", timeout=10000)
                                    except Exception:
                                        pass
                                else:
                                    last_err = AssertionError(f"Link clicked but URL did not change from {original_url}")
                            except PWTimeoutError:
                                last_err = PWTimeoutError("Same-tab navigation did not change URL in time")
                        except Exception as e:
                            last_err = e

                    # strategy C: manual goto
                    if not success:
                        newp = None
                        try:
                            newp = page.context.new_page()
                            try:
                                newp.goto(href, wait_until="networkidle", timeout=15000)
                            except Exception:
                                pass
                            new_url = newp.url or ""
                            new_domain = new_url.split("//")[-1].split("/")[0] if new_url else ""
                            if (new_domain and original_domain and original_domain not in new_domain) or (new_url and new_url != original_url):
                                success = True
                                try:
                                    newp.close()
                                except Exception:
                                    pass
                            else:
                                try:
                                    newp.close()
                                except Exception:
                                    pass
                                last_err = AssertionError(f'External link target appears unreachable or stayed same URL: {href}')
                        except Exception as e:
                            try:
                                if newp:
                                    newp.close()
                            except Exception:
                                pass
                            last_err = e

                    if not success:
                        raise AssertionError(str(last_err) if last_err else f"External link unknown failure: {href}")

        except AssertionError as ae:
            try:
                allure.attach(str(ae), name="Step Error", attachment_type=allure.attachment_type.TEXT)
            except Exception:
                pass
            soft.add(f'Anchor #{idx} "{text}" -> {href}: {ae}')
            continue

    soft.assert_all()
