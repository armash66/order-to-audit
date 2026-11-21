"""Check the operator setup and first-use password flow on an isolated instance."""
import argparse
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8010')
    url = parser.parse_args().url
    suffix = uuid4().hex[:6]
    username = 'field_' + suffix
    customer_code = 'SHOP' + suffix.upper()
    pouch_code = 'P500' + suffix.upper()
    product_code = 'M500' + suffix.upper()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 360, 'height': 780})

        def login(username, password):
            page.goto(url)
            page.get_by_label('Username', exact=True).fill(username)
            page.get_by_label('Password', exact=True).fill(password)
            page.get_by_role('button', name='Sign in', exact=True).click()

        login('admin', 'DemoPass123!')
        expect(page.get_by_role('navigation', name='Workspace')).to_be_visible()
        assert 'FastAPI' not in page.locator('body').inner_text()
        assert 'PostgreSQL' not in page.locator('body').inner_text()
        page.get_by_role('navigation', name='Workspace').get_by_role('button', name='Setup').click()
        expect(page.get_by_role('heading', name='Staff access')).to_be_visible()
        page.locator('summary').filter(has_text='Create staff account').click()
        page.get_by_label('Full name').fill('Demo Field Three')
        page.get_by_label('Username', exact=True).fill(username)
        page.get_by_label('Role', exact=True).select_option('salesman')
        page.get_by_label('Temporary password (12+ characters)').fill('Temporary!2026')
        page.get_by_role('button', name='Create staff account').click()
        expect(page.get_by_role('table').first).to_contain_text(username)
        page.get_by_role('button', name='Sign out').click()

        login(username, 'Temporary!2026')
        expect(page.get_by_role('heading', name='Set your password')).to_be_visible()
        page.get_by_label('Temporary password', exact=True).fill('Temporary!2026')
        page.get_by_label('New password (at least 12 characters)').fill('OwnPassword!2026')
        page.get_by_label('Confirm new password').fill('OwnPassword!2026')
        page.get_by_role('button', name='Set password').click()
        expect(page.get_by_role('navigation', name='Workspace')).to_be_visible()
        page.get_by_role('button', name='Sign out').click()

        login('admin', 'DemoPass123!')
        page.get_by_role('navigation', name='Workspace').get_by_role('button', name='Setup').click()
        page.get_by_role('navigation', name='Setup areas').get_by_role('button', name='Customers & suppliers').click()
        page.locator('summary').filter(has_text='Add customer').click()
        page.get_by_label('Short code').first.fill(customer_code)
        page.get_by_label('Customer name').fill('Demo Market Shop')
        page.get_by_label('Two-digit GST state code').fill('33')
        page.get_by_label('GSTIN (15 characters)').fill('33EEEEE0000E1Z0')
        page.get_by_role('button', name='Add customer').click()
        expect(page.get_by_role('table').first).to_contain_text(customer_code)
        page.get_by_role('navigation', name='Setup areas').get_by_role('button', name='Materials & products').click()
        page.locator('summary').filter(has_text='Add material').click()
        page.get_by_label('Short code').fill(pouch_code)
        page.get_by_label('Material name').fill('Demo 500 g pouch')
        page.get_by_label('Type').select_option('packaging')
        page.get_by_label('Base unit').select_option('piece')
        page.get_by_role('button', name='Add material').click()
        expect(page.get_by_role('table').first).to_contain_text(pouch_code)
        page.locator('summary').filter(has_text='Add sellable product').click()
        page.get_by_label('Product code').fill(product_code)
        page.get_by_label('Product name').fill('Demo Murukku 500 g')
        page.get_by_label('Pack size in grams').fill('500')
        page.get_by_label('Selling price (₹)').fill('125.00')
        page.get_by_label('HSN code').fill('99999999')
        page.get_by_label('Packets per carton').fill('20')
        page.get_by_role('button', name='Add sellable product').click()
        expect(page.get_by_role('table').nth(1)).to_contain_text('Demo Murukku 500 g')
        page.get_by_role('navigation', name='Setup areas').get_by_role('button', name='Recipes').click()
        page.locator('summary').filter(has_text='Add BOM version').click()
        page.get_by_label('Product', exact=True).select_option(label='Demo Murukku 500 g')
        page.get_by_label('Expected good packets per batch').fill('80')
        page.get_by_label('Ingredient recipe').select_option(label='MURUKKU200-RECIPE · v1')
        page.locator('label').filter(has_text='Demo 500 g pouch · pieces per batch').locator('input').fill('80')
        page.locator('label').filter(has_text='Carton · pieces per batch').locator('input').fill('4')
        page.get_by_role('button', name='Add BOM version').click()
        expect(page.get_by_role('table').first).to_contain_text('Demo Murukku 500 g')
        browser.close()
    print('PASS: 360 px setup, staff, customer, product and shared-recipe BOM')


if __name__ == '__main__':
    main()
