"""Check setup discovery, searchable records and real staff provisioning on an isolated demo."""
import argparse
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8009')
    url = parser.parse_args().url
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 360, 'height': 900})
        page.goto(url)
        page.get_by_label('Username', exact=True).fill('admin')
        page.get_by_label('Password', exact=True).fill('DemoPass123!')
        page.get_by_role('button', name='Sign in', exact=True).click()
        checklist = page.get_by_label('Factory setup checklist', exact=True)
        checklist.get_by_role('button', name='Staff', exact=True).click()
        page.get_by_label('Search records').fill('no_such_staff_938')
        expect(page.get_by_text('No matching records.', exact=True)).to_be_visible()
        page.get_by_role('button', name='Clear filters', exact=True).click()
        page.get_by_role('group', name='Filter status').get_by_role('button', name='Active').click()
        expect(page.get_by_role('cell', name='admin', exact=True).first).to_be_visible()
        page.locator('button[data-action-title="Create staff account"]').click()
        panel = page.get_by_role('dialog',name='Create staff account',exact=True)
        username = 'field_' + uuid4().hex[:10]
        panel.get_by_label('Full name').fill('Fictional field operator')
        panel.get_by_label('Username', exact=True).fill(username)
        panel.locator('input[name=role][value=salesman]').check()
        panel.get_by_label('Temporary password (12+ characters)').fill('PrivateDemo!2026')
        panel.get_by_role('button', name='Create staff account', exact=True).click()
        expect(page.locator('.notice[role="status"]')).to_contain_text('Staff account created.')
        page.get_by_label('Search records').fill(username)
        expect(page.get_by_role('cell', name=username, exact=True)).to_be_visible()
        page.get_by_role('navigation', name='Setup areas').get_by_role('button', name='Customers & suppliers').click()
        page.get_by_label('Search records').fill('retailer')
        expect(page.get_by_role('cell', name='Demo Retailer A', exact=True)).to_be_visible()
        expect(page.get_by_role('cell', name='Demo Distributor B', exact=True)).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()
    print('PASS: mobile setup discovery, staff creation, search and access filter')


if __name__ == '__main__':
    main()
