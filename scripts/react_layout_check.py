"""Exercise record navigation, exact sorting and account controls in the React workspace."""
import argparse
import json
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8017")
    args = parser.parse_args()
    screenshots = Path(tempfile.gettempdir()) / "ota-layout-review"
    screenshots.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.get_by_label("Username", exact=True).fill("admin")
        page.get_by_label("Password", exact=True).fill("DemoPass123!")
        page.get_by_role("button", name="Sign in", exact=True).click()
        nav = page.get_by_role("navigation", name="Workspace")
        expect(nav).to_be_visible()
        expect(page.get_by_role("button", name="Sign out", exact=True)).to_be_visible()
        page.get_by_role("button", name="Change password", exact=True).click()
        expect(page.get_by_label("Current password", exact=True)).to_be_visible()
        page.get_by_role("button", name="Close", exact=True).click()
        expect(page.get_by_label("Current password", exact=True)).to_have_count(0)

        # Mock only the list response to exercise more than one page without writing orders.
        records = [{"id": str(9007199254740992 + i), "customer__name": f"Fictional retailer {i:02}",
                    "status": "submitted" if i % 2 else "approved", "document_date": "2026-11-27"}
                   for i in range(45)]
        page.route("**/api/workspace/orders", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(records)))
        nav.get_by_role("button", name="Stock", exact=True).click()
        nav.get_by_role("button", name="Orders", exact=True).click()
        expect(page.locator("tbody tr")).to_have_count(20)
        page.get_by_role("button", name="Next", exact=True).click()
        expect(page.get_by_role("cell", name="Fictional retailer 20", exact=True)).to_be_visible()
        page.get_by_role("button", name="Previous", exact=True).click()
        page.get_by_role("columnheader", name="Reference").get_by_role("button").click()
        expect(page.locator("tbody tr").first).to_contain_text("9007199254740992")
        page.get_by_role("columnheader", name="Reference").get_by_role("button").click()
        expect(page.locator("tbody tr").first).to_contain_text("9007199254741036")
        page.get_by_role("group", name="Filter status").get_by_role("button", name="submitted").click()
        expect(page.locator("tbody .status-badge")).to_have_text(["submitted"] * 20)
        page.get_by_label("Search records").fill("retailer 03")
        expect(page.locator("tbody tr")).to_have_count(1)
        page.get_by_role("button", name="Clear filters", exact=True).click()
        page.screenshot(path=str(screenshots / "orders-desktop.png"), full_page=True)

        nav.get_by_role("button", name="Setup", exact=True).click()
        row = page.get_by_role("row").filter(has=page.get_by_role("cell", name="salesman_a", exact=True))
        row.get_by_role("button", name="Open", exact=True).click()
        panel = page.locator("#staff-actions")
        expect(panel.get_by_role("heading", name="salesman_a", exact=True)).to_be_visible()
        expect(panel.locator('select[name="id"]')).to_have_count(0)
        panel.locator('button[data-action-title="Reset temporary password"]').click()
        expect(page.get_by_role("dialog").get_by_label("New temporary password", exact=True)).to_be_visible()
        page.get_by_role("dialog").get_by_role("button",name="Close",exact=True).click()
        nav.get_by_role("button", name="Reports", exact=True).click()
        page.get_by_role("group", name="Report").get_by_role("button", name="Purchase register", exact=True).click()
        expect(page.get_by_role("heading", name="Purchase register", exact=True)).to_be_visible()
        for width in (1440, 768, 360):
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(screenshots / "reports-mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print(f"PASS: profile, pagination, exact sorting, filters, staff context and reports; screenshots: {screenshots}")


if __name__ == "__main__":
    main()
