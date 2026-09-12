#!/usr/bin/env python3
"""Azuma browser smoke test (Playwright, real Chromium).

Validates the zoneless change-detection contract end to end:

  1. The shell reports BACKEND ONLINE without any interaction (async HTTP).
  2. REST discovery renders forms / OAuth flows / session cookies without
     extra clicks after the request resolves.
  3. Live WebSocket discovery renders the terminal, phases and detail view.
  4. History lists persisted rows on entry and detail renders by URL.
  5. JSON/CSV exports download (client and server side).
  6. The EN/ES toggle re-renders labels while keeping the loaded data.
  7. No console errors and no uncaught page errors.

Requirements:
  * `./azuma.sh local` already running (frontend :4230, backend :8030)
  * Playwright + Chromium available in the interpreter running this script

Usage:
  python e2e/browser_smoke.py [--frontend http://127.0.0.1:4230]
                              [--fixture-port 8104] [--no-fixture] [--headed]

Exit code 0 means every check passed.
"""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

HERE = Path(__file__).resolve().parent
FIXTURE_SCRIPT = HERE / "fixture_server.py"


class CheckFailure(AssertionError):
    pass


def log(message: str) -> None:
    print(f"[azuma-smoke] {message}", flush=True)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)
    log(f"PASS {message}")


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_text(page: Page, selector: str, needle: str, timeout: int = 20000) -> None:
    try:
        page.wait_for_function(
            "([selector, needle]) => "
            "(document.querySelector(selector)?.textContent || '').includes(needle)",
            arg=[selector, needle],
            timeout=timeout,
        )
    except PlaywrightTimeoutError as exc:
        actual = page.locator(selector).first.text_content()
        raise CheckFailure(
            f"timed out waiting for {needle!r} in {selector!r} (actual: {actual!r})"
        ) from exc


def metric_values(page: Page) -> list[str]:
    return [
        (value.text_content() or "").strip()
        for value in page.locator("app-analysis-detail .metric-value").all()
    ]


def fixture_id_from_row(row_text: str) -> int:
    match = re.search(r"#(\d+)", row_text)
    if match:
        return int(match.group(1))
    raise CheckFailure(f"could not find an analysis id in row: {row_text!r}")


def run_checks(page: Page, frontend: str, fixture_url: str) -> list[str]:
    evidence: list[str] = []

    # ── 1. shell health, no clicks ────────────────────────────────────────
    page.goto(frontend + "/", wait_until="domcontentloaded")
    wait_text(page, ".status-label", "BACKEND ONLINE", timeout=20000)
    evidence.append("shell: [BACKEND ONLINE] rendered without interaction")
    check(page.locator(".nav-link").count() == 3, "sidebar navigation rendered")

    # ── 2. REST discovery ─────────────────────────────────────────────────
    page.fill("#target-input", fixture_url)
    page.click("button.btn-primary:has-text('ANALYZE')")
    page.wait_for_selector("app-analysis-detail .detail", timeout=30000)
    wait_text(page, "app-analysis-detail", "COMPLETED", timeout=20000)

    check(
        page.locator("app-analysis-detail .nothing-accordion").count() >= 2,
        "REST: two forms render without extra clicks",
    )
    form_summaries = " ".join(
        (node.text_content() or "")
        for node in page.locator("app-analysis-detail .nothing-accordion summary").all()
    )
    check("POST" in form_summaries and "/login" in form_summaries, "REST: POST /login form listed")
    check("GET" in form_summaries and "/search" in form_summaries, "REST: GET /search form listed")
    check(
        page.get_by_text("/oauth/authorize").count() >= 1,
        "REST: OAuth authorize endpoint renders",
    )
    check(page.get_by_text("sessionid").count() >= 1, "REST: session cookie renders")
    values = metric_values(page)
    check(len(values) >= 4, f"REST: metric cards rendered ({values})")
    check(values[0] == "2", f"REST: FORMS metric is 2 (got {values[0]!r})")
    check(values[1] == "4", f"REST: FIELDS metric is 4 (got {values[1]!r})")
    check(values[3] == "1", f"REST: COOKIES metric is 1 (got {values[3]!r})")
    check(
        page.locator(".text-warning", has_text="LOADING").count() == 0,
        "REST: [ LOADING... ] banner cleared",
    )
    evidence.append(
        f"rest discovery: forms=2 fields=4 oauth={values[2]} cookies=1 "
        f"(metric cards {values})"
    )

    # ── 3. live WebSocket discovery ───────────────────────────────────────
    page.fill("#target-input", fixture_url)
    page.click("button.btn-primary:has-text('LIVE STREAM')")
    wait_text(page, ".terminal-body", "OPEN /api/forms/live", timeout=10000)
    wait_text(page, ".terminal-body", "COMPLETED #", timeout=30000)
    page.wait_for_selector("app-analysis-detail .detail", timeout=20000)
    page.wait_for_selector(".phase-row .phase-done", timeout=20000)
    terminal_lines = page.locator(".terminal-line").count()
    check(terminal_lines >= 5, f"WS: terminal rendered {terminal_lines} event line(s)")
    check(
        "COOKIE sessionid" in "\n".join(
            (line.text_content() or "") for line in page.locator(".terminal-line").all()
        ),
        "WS: session cookie event streamed",
    )
    evidence.append(f"live ws discovery: {terminal_lines} terminal lines, phases done")

    # ── 4. history + detail by URL ────────────────────────────────────────
    page.goto(frontend + "/history", wait_until="domcontentloaded")
    page.wait_for_selector(".history-item", timeout=20000)
    rows = page.locator(".history-item")
    history_count = rows.count()
    check(history_count >= 1, "history: rows render on entry without clicks")
    row = page.locator(".history-item", has_text="127.0.0.1:8104").first
    check(row.count() == 1, "history: fixture analysis row present")
    analysis_id = fixture_id_from_row(row.text_content() or "")
    page.goto(f"{frontend}/history/{analysis_id}", wait_until="domcontentloaded")
    page.wait_for_selector("app-analysis-detail .detail", timeout=20000)
    check(
        page.get_by_text("sessionid").count() >= 1,
        "history: detail-by-URL renders the analysis",
    )
    evidence.append(f"history: {history_count} row(s); detail # {analysis_id} by URL")

    # ── 5. exports ────────────────────────────────────────────────────────
    with page.expect_download(timeout=20000) as client_json:
        page.click("app-export-actions button:has-text('JSON')")
    download = client_json.value
    check(
        download.suggested_filename.startswith(f"azuma-analysis-{analysis_id}")
        and download.suggested_filename.endswith(".json"),
        f"export: client JSON download ({download.suggested_filename})",
    )
    with page.expect_download(timeout=20000) as client_csv:
        page.click("app-export-actions button:has-text('CSV')")
    download = client_csv.value
    check(
        download.suggested_filename.endswith(".csv"),
        f"export: client CSV download ({download.suggested_filename})",
    )
    with page.expect_download(timeout=20000) as server_json:
        page.click("app-export-actions a:has-text('JSON')")
    check(
        server_json.value.suggested_filename.endswith(".json"),
        f"export: server JSON download ({server_json.value.suggested_filename})",
    )
    with page.expect_download(timeout=20000) as server_csv:
        page.click("app-export-actions a:has-text('CSV')")
    check(
        server_csv.value.suggested_filename.endswith(".csv"),
        f"export: server CSV download ({server_csv.value.suggested_filename})",
    )
    evidence.append("exports: client JSON/CSV + server JSON/CSV downloads")

    # ── 6. EN/ES toggle keeps data ────────────────────────────────────────
    page.goto(frontend + "/history", wait_until="domcontentloaded")
    page.wait_for_selector(".history-item", timeout=20000)
    before = page.locator(".history-item").count()
    locale_toggle = page.locator(".sidenav-foot button.side-btn").first
    locale_toggle.click()
    wait_text(page, ".nav", "HISTORIAL", timeout=10000)
    check(
        page.locator(".history-item").count() == before,
        "i18n: EN->ES keeps history rows (data preserved)",
    )
    locale_toggle.click()
    wait_text(page, ".nav", "HISTORY", timeout=10000)
    check(
        page.locator(".history-item").count() == before,
        "i18n: ES->EN keeps history rows (data preserved)",
    )
    evidence.append(f"i18n: EN/ES toggle preserved {before} history row(s)")

    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Azuma browser smoke test")
    parser.add_argument("--frontend", default="http://127.0.0.1:4230")
    parser.add_argument("--fixture-port", type=int, default=8104)
    parser.add_argument("--no-fixture", action="store_true", help="use an external fixture")
    parser.add_argument("--headed", action="store_true", help="run Chromium with a window")
    args = parser.parse_args()

    fixture_url = f"http://127.0.0.1:{args.fixture_port}"
    fixture_process: subprocess.Popen | None = None

    if not args.no_fixture and not port_open(args.fixture_port):
        log(f"starting fixture on {fixture_url}")
        fixture_process = subprocess.Popen(
            [sys.executable, str(FIXTURE_SCRIPT), str(args.fixture_port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for _ in range(50):
            if port_open(args.fixture_port):
                break
            time.sleep(0.1)
        else:
            log("fixture did not come up")
            return 2

    if not port_open(4230) and "4230" in args.frontend:
        log(f"frontend not reachable at {args.frontend}; run ./azuma.sh local first")
        return 2

    console_errors: list[str] = []
    page_errors: list[str] = []
    evidence: list[str] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.on("pageerror", lambda error: page_errors.append(str(error)))

            try:
                evidence = run_checks(page, args.frontend, fixture_url)
            finally:
                context.close()
                browser.close()
    finally:
        if fixture_process is not None:
            fixture_process.terminate()
            try:
                fixture_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                fixture_process.kill()

    check(not console_errors, f"console errors empty (got {console_errors[:3]})")
    check(not page_errors, f"page errors empty (got {page_errors[:3]})")

    print()
    print("=" * 72)
    print("AZUMA BROWSER SMOKE: OK")
    for line in evidence:
        print(f"  - {line}")
    print("  - console/page errors: empty")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as failure:
        log(f"FAIL {failure}")
        raise SystemExit(1)
