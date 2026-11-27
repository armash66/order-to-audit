"""Check exact display units and guided, searchable forms without posting business data."""
import argparse
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8018")
    args = parser.parse_args()
    screenshots = Path(tempfile.gettempdir()) / "ota-guidance-review"
    screenshots.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # Extend only a read response so search is exercised with a longer customer list.
        def catalogue(route):
            response = route.fetch()
            data = response.json()
            data["customers"] += [{"id": str(10000+i), "name": f"Practice customer {i:02}"} for i in range(12)]
            route.fulfill(response=response, json=data)

        def dashboard(route):
            response = route.fetch()
            data = response.json()
            data["stock"]["FLOUR"]["quantity"] = "120001"
            data["stock"]["OIL"]["quantity"] = "19500"
            route.fulfill(response=response, json=data)

        page.route("**/api/workspace/catalog", catalogue)
        page.route("**/api/workspace/dashboard", dashboard)
        page.goto(args.url)
        page.get_by_label("Username", exact=True).fill("admin")
        page.get_by_label("Password", exact=True).fill("DemoPass123!")
        page.get_by_role("button", name="Sign in", exact=True).click()
        nav = page.get_by_role("navigation", name="Workspace")
        expect(page.get_by_role("region", name="Next step")).to_be_visible()
        page.get_by_role("button", name="New order", exact=True).click()
        dialog = page.get_by_role("dialog", name="Submit order", exact=True)
        expect(dialog).to_be_visible()
        expect(dialog.locator("select")).to_have_count(0)
        customers = dialog.get_by_role("group", name="Customer", exact=True)
        customers.get_by_label("Search choices").fill("customer 11")
        customers.get_by_role("radio", name="Practice customer 11", exact=True).check()
        expect(customers.get_by_role("radio", name="Practice customer 11", exact=True)).to_be_checked()
        for _ in range(12):
            page.keyboard.press("Tab")
            assert dialog.evaluate("dialog => dialog.contains(document.activeElement)")
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()

        nav.get_by_role("button", name="Production", exact=True).click()
        page.get_by_role("region", name="Next step").get_by_role("button", name="Receive materials", exact=True).click()
        dialog = page.get_by_role("dialog", name="Receive materials", exact=True)
        dialog.get_by_role("group", name="Item", exact=True).get_by_role("radio", name="Cooking oil", exact=True).check()
        units = dialog.get_by_role("group", name="Unit", exact=True)
        units.get_by_role("radio", name="L", exact=True).check()
        expect(units.get_by_role("radio", name="kg", exact=True)).to_have_count(0)
        expect(units.get_by_role("radio", name="L", exact=True)).to_be_checked()
        page.screenshot(path=str(screenshots / "receipt-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 360, "height": 800})
        assert dialog.evaluate("element => element.scrollWidth <= element.clientWidth + 1")
        page.screenshot(path=str(screenshots / "receipt-mobile.png"), full_page=True)
        dialog.get_by_role("button", name="Close", exact=True).click()

        nav.get_by_role("button", name="Dashboard", exact=True).click()
        expect(page.get_by_text("120.001 kg", exact=True)).to_be_visible()
        expect(page.get_by_text("120001 g", exact=True)).to_have_count(0)
        page.get_by_role("group", name="g / kg", exact=True).get_by_role("button", name="g", exact=True).click()
        expect(page.get_by_text("120001 g", exact=True)).to_be_visible()
        expect(page.get_by_text("120.001 kg", exact=True)).to_have_count(0)
        page.get_by_role("group", name="g / kg", exact=True).get_by_role("button", name="kg", exact=True).click()
        page.get_by_role("group", name="ml / L", exact=True).get_by_role("button", name="ml", exact=True).click()
        expect(page.get_by_text("19500 ml", exact=True)).to_be_visible()
        expect(page.get_by_text("19.5 L", exact=True)).to_have_count(0)
        page.get_by_role("group", name="ml / L", exact=True).get_by_role("button", name="L", exact=True).click()
        expect(page.get_by_text("19.5 L", exact=True)).to_be_visible()
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.screenshot(path=str(screenshots / "dashboard-desktop.png"), full_page=True)

        # A one-gram reversal must remain signed and visible, not round down to zero.
        def ledger(route):
            response = route.fetch()
            data = response.json()
            data["movements"] = [{"id": 1, "posting_id": 1, "quantity": "-1", "value_paise": "-4"}]
            route.fulfill(response=response, json=data)
        page.route("**/api/stock/FLOUR/ledger", ledger)
        nav.get_by_role("button", name="Stock", exact=True).click()
        page.get_by_role("row").filter(has=page.get_by_role("cell", name="FLOUR", exact=True)).get_by_role("button", name="Open", exact=True).click()
        expect(page.locator(".record-list").get_by_text("−0.001 kg", exact=True)).to_be_visible()
        expect(page.get_by_text("-1 g", exact=True)).to_have_count(0)
        page.get_by_role("group", name="g / kg", exact=True).get_by_role("button", name="g", exact=True).click()
        expect(page.get_by_text("-1 g", exact=True)).to_be_visible()
        assert page.locator("select, details").count() == 0
        assert not errors, errors
        browser.close()
    print(f"PASS: exact kg/L/signed units, next task, searchable choices, dependent units, modal focus and mobile layout; screenshots: {screenshots}")


if __name__ == "__main__":
    main()
