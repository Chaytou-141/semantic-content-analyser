"""Exercise a running local demo without external website access.

Run against a disposable demo workspace: this script saves one link review.
"""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000")
parser.add_argument("--output", default="runtime/browser")
args = parser.parse_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="chromium", args=["--disable-gpu"])
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(args.url)
    expect(page.locator("#workspace")).to_be_visible()
    expect(page.locator("#view-home")).to_be_visible()
    page.locator("#home-explore").click()
    page.locator(".collection-details > summary").click()
    expect(page.locator("#collection-count")).to_have_text("21 articles in your collection")
    expect(page.locator("#collection-rail .topic-row")).to_have_count(4)
    expect(page.locator("#search-results .preview-row")).to_have_count(4)
    page.get_by_role("button", name="Browse coffee: 5 articles", exact=True).click()
    expect(page.locator("#article-table tr")).to_have_count(5)
    page.locator("#article-filter").fill("")
    expect(page.locator("#article-table tr")).to_have_count(21)
    page.get_by_role("link", name="Explore analysis", exact=True).click()
    page.keyboard.press("/")
    expect(page.locator("#search-query")).to_be_focused()
    page.locator("#search-query").blur()
    page.screenshot(path=str(output / "search-home.png"), full_page=True)

    page.locator("#search-query").fill("choosing a display fridge for a cafe")
    page.locator(".search-settings > summary").click()
    page.locator("#search-method").select_option("compare")
    page.locator("#search-form").get_by_role("button", name="Search articles").click()
    expect(page.locator("#search-results .result-card")).to_have_count(10, timeout=120000)
    expect(page.locator("#app-error")).to_be_hidden()
    page.screenshot(path=str(output / "search-results.png"), full_page=True)
    print("PASS: search and method comparison")

    page.get_by_role("link", name="Link opportunities", exact=False).click()
    page.locator("#links-source").select_option("A01")
    page.locator("#links-form").get_by_role("button", name="Find opportunities").click()
    expect(page.locator("#links-results .result-card")).to_have_count(5, timeout=60000)
    text = page.locator("#links-results .result-list").inner_text()
    assert "A04" not in text and "A20" not in text
    page.locator("#links-results .result-card").first.get_by_role("button", name="Useful candidate", exact=True).click()
    expect(page.locator("#links-results .review-label").first).to_contain_text("Review saved", timeout=10000)
    page.screenshot(path=str(output / "link-opportunities.png"), full_page=True)
    print("PASS: link exclusions, source/target evidence and saved review")

    page.get_by_role("link", name="Content overlap", exact=False).click()
    page.locator("#overlap-form").get_by_role("button", name="Review overlap").click()
    expect(page.locator("#overlap-results .result-card").first).to_be_visible(timeout=60000)
    page.screenshot(path=str(output / "overlap.png"), full_page=True)
    print("PASS: overlap review")

    page.locator(".masthead-actions").get_by_role("link", name="Articles", exact=False).click()
    expect(page.locator("#article-table tr")).to_have_count(21)
    page.locator("#article-filter").fill("A12")
    expect(page.locator("#article-table tr")).to_have_count(1)
    page.locator("#article-table").get_by_role("button", name="Edit", exact=True).click()
    expect(page.locator("#article-dialog")).to_be_visible()
    expect(page.locator("#article-details textarea")).to_contain_text("Arrange the espresso machine")
    page.locator('#article-details input[name="title"]').fill("Unsaved title for UI test")
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.locator("#article-dialog").get_by_role("button", name="Close article").click()
    expect(page.locator("#article-dialog")).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#article-dialog").get_by_role("button", name="Close article").click()
    expect(page.locator("#article-dialog")).to_be_hidden()
    page.locator("#article-filter").fill("")
    print("PASS: live topic filters, keyboard search, article editor and unsaved-change protection")

    page.locator(".utility-menu > summary").click()
    page.get_by_role("link", name="Development evaluation", exact=True).click()
    expect(page.locator(".metric-panel")).to_have_count(2, timeout=10000)
    expect(page.locator("#evaluation-content")).to_contain_text("assistant-proposed")
    page.screenshot(path=str(output / "evaluation.png"), full_page=True)
    print("PASS: evaluation results and limitations")

    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("link", name="Semantic Content Analyser home", exact=True).click()
    page.locator("#home-explore").click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(output / "mobile.png"), full_page=True)
    page.locator("#import-top").click()
    page.locator("#import-collection").click()
    expect(page.locator("#import-dialog")).to_be_visible()
    page.locator("#import-dialog").get_by_role("button", name="Close import").click()
    print("PASS: mobile layout and import dialog")
    assert not errors, errors
    browser.close()
print(f"Browser smoke checks passed. Screenshots: {output}")
