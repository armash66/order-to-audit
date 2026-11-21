"""Run the nine-step scenario in React on a fresh, isolated Compose project."""
import argparse
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://localhost:8004')
    url=parser.parse_args().url
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        page=browser.new_page(viewport={'width':1280,'height':900})
        def login(user):
            page.goto(url)
            page.reload()
            page.get_by_label('Username',exact=True).fill(user)
            page.get_by_label('Password',exact=True).fill('DemoPass123!')
            page.get_by_role('button',name='Sign in',exact=True).click()
            expect(page.get_by_role('button',name='Sign out')).to_be_visible()
        def nav(name):
            page.get_by_role('navigation').get_by_role('button',name=name,exact=True).click()
        def form(title):
            panel=page.locator('details').filter(has=page.locator('summary',has_text=title)).first
            if panel.get_attribute('open') is None:panel.locator('summary').click()
            return panel
        def save(panel,title):
            panel.get_by_role('button',name=title,exact=True).click()
            expect(page.get_by_text('Saving…',exact=True)).to_have_count(0)
            expect(page.locator('[role=alert]')).to_have_count(0)
        login('production')
        p=form('Receive materials')
        p.get_by_label('Item',exact=True).select_option(label='Flour')
        p.get_by_label('Quantity in base units (g / ml / piece)').fill('60000')
        p.get_by_label('Total value (₹)').fill('2700')
        save(p,'Receive materials')
        p=form('Create production run');save(p,'Create production run')
        page.get_by_role('button',name='Open',exact=True).first.click()
        p=form('Issue raw materials')
        for name,value in [('Flour (g)','40000'),('Cooking oil (ml)','10500'),('Spice mix (g)','1200')]:p.get_by_label(name,exact=True).fill(value)
        save(p,'Issue raw materials')
        p=form('Complete production')
        p.get_by_label('Good packets',exact=True).fill('188')
        for inp in p.locator('input[name^="qty_"]').all(): inp.fill('194' if 'POUCH' in inp.get_attribute('name') else '9')
        p.locator('input[name="damage_POUCH"]').fill('6')
        save(p,'Complete production')
        login('salesman_a');page.set_viewport_size({'width':360,'height':900})
        p=form('Submit order');p.get_by_label('Customer',exact=True).select_option(label='Demo Retailer A')
        p.locator('input[name^="qty_"]').first.fill('150');save(p,'Submit order')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        login('admin');page.set_viewport_size({'width':1280,'height':900})
        page.get_by_role('button',name='Open',exact=True).first.click()
        p=form('Approve and reserve');save(p,'Approve and reserve')
        p=form('Post invoice');save(p,'Post invoice')
        expect(page.get_by_text('Total ₹7875.00',exact=False)).to_be_visible()
        with page.expect_download():page.get_by_role('button',name='Download invoice PDF').click()
        p=form('Dispatch remaining order');save(p,'Dispatch remaining order')
        p=form('Record payment');p.get_by_label('Amount (₹)').fill('4000');save(p,'Record payment')
        expect(page.get_by_text('Outstanding ₹3875.00',exact=False)).to_be_visible()
        login('salesman_b');p=form('Submit order');p.get_by_label('Customer',exact=True).select_option(label='Demo Distributor B')
        p.locator('input[name^="qty_"]').first.fill('120');save(p,'Submit order')
        page.get_by_role('button',name='Open',exact=True).first.click()
        expect(page.get_by_role('cell',name='32',exact=True)).to_be_visible()
        login('admin');nav('Production');page.get_by_role('button',name='Open',exact=True).first.click()
        for label,value in [('Labour','1200'),('Gas/power','600')]:
            p=form('Add overhead');p.get_by_label('Description',exact=True).fill(label);p.get_by_label('Amount (₹)').fill(value);save(p,'Add overhead')
        expect(page.get_by_text('₹31.14',exact=True)).to_be_visible()
        nav('Reports')
        expect(page.get_by_role('heading',name='Sales register')).to_be_visible()
        with page.expect_download():page.get_by_role('button',name='Export CSV').click()
        browser.close()
    print('PASS: React production, mobile order, approval, invoice/PDF, dispatch, shortage, payment, overhead and CSV')


if __name__=='__main__':main()
