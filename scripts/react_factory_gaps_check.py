"""Exercise the factory add-ons in a disposable Compose project."""
import argparse
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8010')
    url = parser.parse_args().url
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 360, 'height': 780})

        def login(name):
            page.goto(url)
            page.get_by_label('Username', exact=True).fill(name)
            page.get_by_label('Password', exact=True).fill('DemoPass123!')
            page.get_by_role('button', name='Sign in', exact=True).click()
            expect(page.get_by_role('navigation', name='Workspace')).to_be_visible()

        login('production')
        page.get_by_role('navigation').get_by_role('button', name='Batches').click()
        expect(page.get_by_role('heading', name='Lots and quality status')).to_be_visible()
        page.locator('tr').filter(has_text='RUN-1').get_by_role('button', name='Open').click()
        expect(page.get_by_role('heading', name='Trace lot', exact=False)).to_be_visible()
        page.get_by_label('Batch recall trace').get_by_role('row').filter(has_text='188').get_by_role('button', name='Open').click()
        expect(page.get_by_role('heading', name='Source posting', exact=False)).to_be_visible()
        page.locator('button[data-action-title=\"Hold or release finished lot\"]').click()
        page.get_by_label('Reason', exact=True).fill('Demo seal inspection')
        page.get_by_role('dialog').get_by_role('button', name='Hold or release finished lot', exact=True).click()
        expect(page.get_by_role('table').first.get_by_role('row').filter(has_text='RUN-1')).to_contain_text('held')
        page.locator('button[data-action-title=\"Hold or release finished lot\"]').click()
        page.locator('dialog[open] input[name=status][value=released]').check()
        page.get_by_label('Reason', exact=True).fill('Passed inspection')
        page.get_by_role('dialog').get_by_role('button', name='Hold or release finished lot', exact=True).click()
        expect(page.get_by_role('table').first.get_by_role('row').filter(has_text='RUN-1')).to_contain_text('released')
        page.get_by_role('button', name='Sign out').click()

        login('salesman_b')
        page.locator('button[data-action-title=\"Submit order\"]').click()
        page.get_by_role('dialog').get_by_role('group',name='Customer',exact=True).get_by_role('radio',name='Demo Distributor B',exact=True).check()
        page.get_by_label('Document date').fill('2026-11-19')
        page.get_by_label('Murukku 200 g · Quantity (0 to omit)').fill('120')
        page.get_by_role('dialog').get_by_role('button', name='Submit order', exact=True).click()
        expect(page.get_by_role('table').first).to_contain_text('Demo Distributor B')
        page.get_by_role('button', name='Sign out').click()

        login('admin')
        page.locator('tr').filter(has_text='Demo Distributor B').get_by_role('button', name='Open').first.click()
        expect(page.get_by_role('heading', name='Shortage resolution')).to_be_visible()
        expect(page.get_by_label('Shortage resolution')).to_contain_text('batches needed')
        expect(page.get_by_role('button', name='Open production and receipts')).to_be_visible()
        browser.close()
    print('PASS: mobile factory hold/release, recall and shortage-resolution screens')


if __name__ == '__main__':
    main()
