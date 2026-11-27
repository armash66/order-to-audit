"""Check localized role screens and offline capture in a real browser."""

import argparse
import json
from pathlib import Path
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--width", type=int, default=360)
    args = parser.parse_args()
    url = args.url
    words = json.loads((Path(__file__).parents[1] / "frontend/src/translations.json").read_text(encoding="utf-8"))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": 780})
        page.goto(url)
        page.get_by_test_id("language-switch").locator("button[data-language=" + "hi" + "]").click()
        expect(page.get_by_role("heading", name="साइन इन करें")).to_be_visible()
        page.get_by_label("उपयोगकर्ता नाम").fill("admin")
        page.get_by_label("पासवर्ड", exact=True).fill("wrong-password")
        page.get_by_role("button", name="साइन इन करें").click()
        expect(page.get_by_role("alert")).to_have_text(words["hi"]["Incorrect username or password."])
        page.get_by_test_id("language-switch").locator("button[data-language=" + "ta" + "]").click()
        expect(page.get_by_role("alert")).to_have_text(words["ta"]["Incorrect username or password."])
        page.get_by_test_id("language-switch").locator("button[data-language=" + "hi" + "]").click()
        page.get_by_label("पासवर्ड", exact=True).fill("DemoPass123!")
        page.get_by_role("button", name="साइन इन करें").click()
        expect(page.get_by_role("navigation", name="कार्यस्थान")).to_be_visible()

        screens = {
            "hi": ("सेटअप", "कर्मचारी पहुँच", "ग्राहक और आपूर्तिकर्ता", "कारखाना संचालन"),
            "mr": ("मांडणी", "कर्मचारी प्रवेश", "ग्राहक आणि पुरवठादार", "कारखाना कामकाज"),
            "ta": ("அமைப்பு", "பணியாளர் அணுகல்", "வாடிக்கையாளர்கள் மற்றும் வழங்குநர்கள்", "தொழிற்சாலை செயல்பாடுகள்"),
        }
        for language, (setup, staff, partners, factory) in screens.items():
            page.get_by_test_id("language-switch").locator("button[data-language=" + language + "]").click()
            expect(page.locator("html")).to_have_attribute("lang", language)
            expect(page.locator("aside")).to_contain_text(factory)
            page.get_by_role("navigation").first.get_by_role("button", name=setup, exact=True).click()
            expect(page.get_by_role("heading", name=setup, exact=True)).to_be_visible()
            expect(page.get_by_role("navigation", name={
                "hi": "सेटअप के भाग", "mr": "मांडणीचे विभाग", "ta": "அமைப்புப் பகுதிகள்"
            }[language])).to_be_visible()
            page.get_by_role("navigation").last.get_by_role("button", name={
                "hi": "कर्मचारी", "mr": "कर्मचारी", "ta": "பணியாளர்கள்"
            }[language], exact=True).click()
            workspace = page.get_by_role("navigation", name=words[language]["Workspace"])
            for english in ["Orders", "Production", "Stock", "Reports", "Batches", "Audit", "Visits", "Offline", "Prices", "Dashboard"]:
                title = words[language][english]
                workspace.get_by_role("button", name=title, exact=True).click()
                expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()
                if english == "Orders":
                    expect(page.locator("button[data-action-title]").filter(has_text=words[language]["Submit order"])).to_be_visible()
                if english == "Production":
                    expect(page.locator("button[data-action-title]").filter(has_text=words[language]["Create production run"])).to_be_visible()
                if english == "Reports":
                    expect(page.get_by_role("group", name=words[language]["Report"]).get_by_role("button", name=words[language]["Sales register"], exact=True)).to_be_attached()
                if english == "Stock":
                    expect(page.get_by_role("columnheader", name=words[language]["name"])).to_be_visible()
            workspace.get_by_role("button", name=setup, exact=True).click()
            expect(page.get_by_role("heading", name=staff)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            expect(page.get_by_role("heading", name=staff)).to_be_visible()
            page.get_by_role("navigation").last.get_by_role("button", name=partners).click()
            expect(page.get_by_role("heading", name={
                "hi": "ग्राहक", "mr": "ग्राहक", "ta": "வாடிக்கையாளர்கள்"
            }[language], exact=True)).to_be_visible()
            assert "Set up staff, trading partners" not in page.locator("main").inner_text()
            page.get_by_role("navigation").last.get_by_role("button", name={
                "hi": "कर्मचारी", "mr": "कर्मचारी", "ta": "பணியாளர்கள்"
            }[language], exact=True).click()

        page.get_by_test_id("language-switch").locator("button[data-language=" + "en" + "]").click()
        page.get_by_role("button", name="Sign out").click()
        for username, language, tab, action in [
            ("salesman_a", "ta", "Orders", "Submit order"),
            ("production", "mr", "Production", "Create production run"),
            ("accountant", "hi", "Reports", "Sales register"),
        ]:
            page.get_by_test_id("language-switch").locator("button[data-language=" + language + "]").click()
            page.get_by_label(words[language]["Username"]).fill(username)
            page.get_by_label(words[language]["Password"], exact=True).fill("DemoPass123!")
            page.get_by_role("button", name=words[language]["Sign in"]).click()
            workspace = page.get_by_role("navigation", name=words[language]["Workspace"])
            workspace.get_by_role("button", name=words[language][tab], exact=True).click()
            if tab == "Reports":
                expect(page.get_by_role("group", name=words[language]["Report"]).get_by_role("button", name=words[language][action], exact=True)).to_be_attached()
            else:
                expect(page.locator("button[data-action-title]").filter(has_text=words[language][action])).to_be_visible()
            page.get_by_role("button", name=words[language]["Sign out"]).click()
        page.goto(url + "/offline")
        page.get_by_test_id("language-switch").locator("button[data-language=" + "ta" + "]").click()
        expect(page.get_by_role("heading", name="இணையமற்ற ஆர்டர்கள்")).to_be_visible()
        assert "Offline orders" not in page.locator("body").inner_text()
        def check_clear_confirmation(dialog):
            assert dialog.message == words["ta"]["Remove the cached customer list and all unsynced orders from this device?"]
            dialog.dismiss()
        page.once("dialog", check_clear_confirmation)
        page.get_by_role("button", name=words["ta"]["Clear this device"]).click()
        page.get_by_test_id("language-switch").locator("button[data-language=" + "en" + "]").click()
        browser.close()
    print(f"Language browser check: {args.width}px, three languages, four roles, all tabs and offline passed")


if __name__ == "__main__":
    main()
