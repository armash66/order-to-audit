"""Optional Playwright smoke check; use only a fresh seeded demo instance."""
import argparse
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8001")
    args = parser.parse_args()
    artifacts = Path(tempfile.mkdtemp(prefix="ota-ui-"))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def login(name):
            nonlocal page
            page.close()
            context.clear_cookies()
            page = context.new_page()
            page.goto(args.url + "/login/")
            page.get_by_label("Username").fill(name)
            page.get_by_label("Password").fill("DemoPass123!")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(args.url + "/")

        login("production")
        page.goto(args.url + "/production/")
        page.locator('select[name="item"]').select_option(label="Flour (base: g)")
        page.get_by_label("Quantity", exact=True).fill("60")
        page.locator('select[name="unit"]').select_option("kg")
        page.get_by_label("Total material value INR").fill("2700")
        page.get_by_role("button", name="Post receipt").click()
        expect(page.get_by_text("Receipt posted.")).to_be_visible()
        page.get_by_role("button", name="Create draft run").click()
        run_url = page.url
        page.get_by_label("Flour (g)", exact=True).fill("40000")
        page.get_by_label("Cooking oil (ml)", exact=True).fill("10500")
        page.get_by_label("Spice mix (g)", exact=True).fill("1200")
        page.get_by_role("button", name="Post raw issue").click()
        fields = page.locator('input[name^="actual_"]')
        # Seed packaging order is pouch, carton; identify labels rather than numeric IDs.
        for field in fields.all():
            label = field.locator("..").inner_text()
            field.fill("194" if "pouch" in label.lower() else "9")
        for field in page.locator('input[name^="damage_"]').all():
            label = field.locator("../..").inner_text()
            field.fill("6" if "pouch" in label.lower() else "0")
        page.get_by_label("Good packets", exact=True).fill("188")
        page.get_by_role("button", name="Post packaging and receive FG").click()
        expect(page.get_by_text("completed", exact=True)).to_be_visible()
        page.screenshot(path=str(artifacts / "production.png"), full_page=True)

        login("salesman_a")
        page.set_viewport_size({"width": 360, "height": 800})
        page.goto(args.url + "/orders/")
        page.locator('select[name="customer"]').select_option(label="Demo Retailer A")
        page.get_by_label("Packets", exact=True).fill("150")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(artifacts / "mobile-order.png"), full_page=True)
        page.get_by_role("button", name="Submit order", exact=True).click()
        a_url = page.url
        expect(page.get_by_text("submitted", exact=True)).to_be_visible()

        login("admin")
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(a_url)
        page.get_by_role("button", name="Approve & reserve").click()
        page.get_by_role("button", name="Post invoice", exact=True).click()
        expect(page.get_by_text("₹7,875.00", exact=True)).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role("link", name="Download PDF").click()
        download.value.save_as(str(artifacts / "invoice.pdf"))
        page.get_by_role("button", name="Dispatch full order").click()
        expect(page.get_by_text("dispatched", exact=True)).to_be_visible()

        login("salesman_b")
        page.goto(args.url + "/orders/")
        page.locator('select[name="customer"]').select_option(label="Demo Distributor B")
        page.get_by_label("Packets", exact=True).fill("120")
        page.get_by_role("button", name="Submit order", exact=True).click()
        b_url = page.url
        login("admin")
        page.goto(b_url)
        expect(page.get_by_text("MURUKKU200: 88 available · 32 short")).to_be_visible()
        page.get_by_role("button", name="Approve & reserve").click()
        expect(page.get_by_text("Insufficient available stock; order remains submitted.")).to_be_visible()
        page.goto(a_url)
        page.get_by_label("Payment amount ₹").fill("4000")
        page.get_by_role("button", name="Record payment").click()
        expect(page.get_by_text("Outstanding: ₹3,875.00")).to_be_visible()
        page.goto(run_url)
        for label, value in [("Labour", "1200"), ("Gas/power", "600")]:
            page.get_by_label("Overhead description").fill(label)
            page.get_by_label("Amount INR", exact=True).fill(value)
            page.get_by_role("button", name="Add overhead").click()
        expect(page.get_by_text("₹31.14 / good packet")).to_be_visible()
        page.goto(args.url + "/reports/")
        for kind in ["sales", "customers", "products", "gst", "purchases", "stock", "ledger", "production", "collections", "ageing"]:
            page.locator('select[name="report"]').select_option(kind)
            page.get_by_role("button", name="View", exact=True).click()
            with page.expect_download() as download:
                page.get_by_role("button", name="CSV", exact=True).click()
            download.value.save_as(str(artifacts / (kind + ".csv")))
        login("owner")
        expect(page.get_by_text("₹3,875.00", exact=True)).to_be_visible()
        page.screenshot(path=str(artifacts / "dashboard.png"), full_page=True)
        browser.close()
    print("PASS: nine-step screen workflow, mobile layout, invoice PDF, all report CSVs and owner totals")
    print("Artifacts:", artifacts)


if __name__ == "__main__":
    main()
