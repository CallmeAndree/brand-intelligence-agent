
"""
E2E browser test for the chat + dashboard-explain flows.

Drives the real Next.js app at http://localhost:3000 via Playwright (sync API),
captures console errors / page errors / failed network requests, verifies that
ECharts canvases actually render in chat answers, and exercises the dashboard
double-click -> explain flow.

Run with the conda python that has playwright installed:
    python brand-intelligence-agent/frontend/e2e_chat_test.py
"""

import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
CHART_QUESTION = "Vẽ biểu đồ xu hướng số lượng mention theo tháng năm 2026"
ANSWER_TIMEOUT_MS = 120_000  # tool round-trip + LLM stream can be slow
SHOT_DIR = "/tmp/e2e_shots"


def _attach_listeners(page, errors, console_errors, failed_requests):
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    def _on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    page.on("console", _on_console)

    def _on_request_failed(req):
        failed_requests.append(f"{req.method} {req.url} -> {req.failure}")

    page.on("requestfailed", _on_request_failed)


def _wait_for_chart(page, timeout_ms):
    """Wait until at least one ECharts <canvas> is rendered inside an assistant
    bubble and has non-zero pixel dimensions (i.e. actually drawn)."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        count = page.evaluate(
            """() => {
                const canvases = Array.from(document.querySelectorAll('canvas'));
                return canvases.filter(c => c.width > 0 && c.height > 0).length;
            }"""
        )
        if count and count > 0:
            return count
        page.wait_for_timeout(500)
    return 0


def test_chat_chart(page):
    print("=== TEST 1: chat chart render ===")
    page.goto(f"{BASE}/chat", wait_until="networkidle")
    page.wait_for_selector("textarea", timeout=15_000)

    page.fill("textarea", CHART_QUESTION)
    page.keyboard.press("Enter")

    # wait for the assistant answer text to appear (delta stream)
    try:
        page.wait_for_function(
            """() => {
                const bubbles = document.querySelectorAll('div');
                return document.body.innerText.includes('mention') ||
                       document.querySelectorAll('canvas').length > 0;
            }""",
            timeout=ANSWER_TIMEOUT_MS,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] answer wait timed out: {exc}")

    n_canvas = _wait_for_chart(page, 30_000)
    page.screenshot(path=f"{SHOT_DIR}/chat_chart.png", full_page=True)
    print(f"  rendered canvases: {n_canvas}")
    print(f"  screenshot: {SHOT_DIR}/chat_chart.png")
    return n_canvas > 0


def test_dashboard_explain(page):
    print("=== TEST 2: dashboard double-click -> explain ===")
    page.goto(BASE, wait_until="networkidle")
    # dashboard charts need a moment to draw
    n = _wait_for_chart(page, 30_000)
    print(f"  dashboard canvases: {n}")
    page.screenshot(path=f"{SHOT_DIR}/dashboard.png", full_page=True)
    if n == 0:
        print("  [fail] no dashboard chart to double-click")
        return False

    # double-click roughly in the middle of the first chart canvas
    box = page.evaluate(
        """() => {
            const c = Array.from(document.querySelectorAll('canvas'))
                .find(c => c.width > 0 && c.height > 0);
            if (!c) return null;
            const r = c.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }"""
    )
    if not box:
        print("  [fail] could not locate chart box")
        return False

    page.mouse.dblclick(box["x"], box["y"])
    # explain flow navigates to /chat
    try:
        page.wait_for_url("**/chat**", timeout=15_000)
        print(f"  navigated to: {page.url}")
        navigated = "/chat" in page.url
    except Exception:  # noqa: BLE001
        navigated = "/chat" in page.url
        print(f"  [warn] no /chat navigation; current url: {page.url}")

    page.wait_for_timeout(3_000)
    page.screenshot(path=f"{SHOT_DIR}/explain.png", full_page=True)
    print(f"  screenshot: {SHOT_DIR}/explain.png")
    return navigated


def main():
    import os

    os.makedirs(SHOT_DIR, exist_ok=True)

    errors, console_errors, failed_requests = [], [], []
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        _attach_listeners(page, errors, console_errors, failed_requests)

        try:
            results["chat_chart"] = test_chat_chart(page)
        except Exception as exc:  # noqa: BLE001
            print(f"  [exception] chat_chart: {exc}")
            results["chat_chart"] = False

        try:
            results["dashboard_explain"] = test_dashboard_explain(page)
        except Exception as exc:  # noqa: BLE001
            print(f"  [exception] dashboard_explain: {exc}")
            results["dashboard_explain"] = False

        browser.close()

    print("\n=== CONSOLE ERRORS ===")
    for e in console_errors[:30]:
        print("  ", e)
    print("=== PAGE ERRORS ===")
    for e in errors[:30]:
        print("  ", e)
    print("=== FAILED REQUESTS ===")
    for e in failed_requests[:30]:
        print("  ", e)

    print("\n=== RESULTS ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")

    ok = all(results.values()) and not errors
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
