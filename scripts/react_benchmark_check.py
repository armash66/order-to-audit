"""Run the nine-step scenario in React on a fresh, isolated Compose project."""
import argparse
from time import monotonic
from urllib.parse import urlparse, parse_qs
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
            expect(page.locator('.profile-identity')).to_be_visible()
        def nav(name):
            page.get_by_role('navigation').get_by_role('button',name=name,exact=True).click()
        def form(title):
            panel=page.get_by_role('dialog',name=title,exact=True)
            if not panel.is_visible():page.locator('button[data-action-title]').filter(has_text=title).first.click()
            return panel
        def save(panel,title):
            panel.get_by_role('button',name=title,exact=True).click()
            expect(page.get_by_text('Saving…',exact=True)).to_have_count(0)
            expect(page.locator('[role=alert]')).to_have_count(0)
        login('production')
        nav('Stock')
        page.get_by_role('row').filter(has=page.get_by_role('cell',name='FLOUR',exact=True)).get_by_role('button',name='Open',exact=True).click()
        expect(page.get_by_role('region',name='Stock valuation').get_by_text('₹42/kg',exact=True)).to_be_visible()
        nav('Production')
        p=form('Receive materials')
        p.get_by_role('group',name='Item',exact=True).get_by_role('radio',name='Flour',exact=True).check()
        p.locator('input[name=unit][value=kg]').check()
        p.get_by_label('Quantity',exact=True).fill('60')
        p.get_by_label('Rate (₹ per selected unit)').fill('45')
        expect(p.get_by_label('Total value (₹)')).to_have_value('2700.00')
        save(p,'Receive materials')
        nav('Stock')
        page.get_by_role('row').filter(has=page.get_by_role('cell',name='FLOUR',exact=True)).get_by_role('button',name='Open',exact=True).click()
        valuation = page.get_by_role('region',name='Stock valuation')
        expect(valuation.get_by_text('₹43.125/kg',exact=True)).to_be_visible()
        expect(valuation).to_contain_text('₹6900.00 ÷ 160 kg = ₹43.125/kg')
        expect(page.get_by_role('cell',name='₹42/kg',exact=True)).to_be_visible()
        expect(page.get_by_role('cell',name='₹45/kg',exact=True)).to_be_visible()
        nav('Production')
        p=form('Create production run');save(p,'Create production run')
        page.get_by_role('button',name='Open',exact=True).first.click()
        p=form('Issue raw materials')
        for code,value,unit in [('FLOUR','40','kg'),('OIL','10.5','L'),('SPICE','1.2','kg')]:
            p.locator(f'input[name="unit_{code}"][value="{unit}"]').check()
            p.locator(f'input[name="qty_{code}"]').fill(value)
        save(p,'Issue raw materials')
        p=form('Complete production')
        p.get_by_label('Good packets',exact=True).fill('188')
        for inp in p.locator('input[name^="qty_"]').all(): inp.fill('194' if 'POUCH' in inp.get_attribute('name') else '9')
        p.locator('input[name="damage_POUCH"]').fill('6')
        save(p,'Complete production')
        login('salesman_a');page.set_viewport_size({'width':360,'height':900})
        started=monotonic()
        p=form('Submit order');p.get_by_role('group',name='Customer',exact=True).get_by_role('radio',name='Demo Retailer A',exact=True).check()
        p.locator('input[name^="qty_"]').first.fill('150');save(p,'Submit order')
        print(f'Automated mobile order entry: {monotonic()-started:.1f}s (human trial still required)')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        login('admin');page.set_viewport_size({'width':1280,'height':900})
        page.get_by_role('button',name='Open',exact=True).first.click()
        p=form('Approve and reserve');save(p,'Approve and reserve')
        p=form('Post invoice');save(p,'Post invoice')
        # Totals are labelled definition-list entries, not a combined heading string.
        total = page.locator('.invoice-totals > div').filter(has=page.locator('dt', has_text='Total'))
        expect(total.locator('dd')).to_have_text('₹7875.00')
        with page.expect_download():page.get_by_role('button',name='Download invoice PDF').click()
        whatsapp=page.get_by_role('link',name='Share via WhatsApp').get_attribute('href')
        email=page.get_by_role('link',name='Share via email').get_attribute('href')
        assert urlparse(whatsapp).netloc == 'wa.me'
        assert '7875.00' in parse_qs(urlparse(whatsapp).query)['text'][0]
        assert email.startswith('mailto:') and '7875.00' in parse_qs(urlparse(email).query)['body'][0]
        assert 'Bearer' not in whatsapp + email and 'localhost' not in whatsapp + email
        # Inspect share drafts without contacting a customer or opening an external app.
        with page.expect_download():page.get_by_role('button',name='Share invoice PDF',exact=True).click()
        page.reload()
        login('admin');page.get_by_role('button',name='Open',exact=True).first.click()
        p=form('Dispatch remaining order');save(p,'Dispatch remaining order')
        p=form('Record payment');p.get_by_label('Amount (₹)').fill('4000');save(p,'Record payment')
        outstanding = page.locator('.invoice-totals > div').filter(has=page.locator('dt', has_text='Outstanding'))
        expect(outstanding.locator('dd')).to_have_text('₹3875.00')
        login('salesman_b');p=form('Submit order');p.get_by_role('group',name='Customer',exact=True).get_by_role('radio',name='Demo Distributor B',exact=True).check()
        p.locator('input[name^="qty_"]').first.fill('120');save(p,'Submit order')
        page.get_by_role('button',name='Open',exact=True).first.click()
        expect(page.get_by_role('cell',name='32',exact=True)).to_be_visible()
        login('admin');page.get_by_role('button',name='Open',exact=True).first.click()
        p=form('Edit order')
        expect(p.get_by_label('Price (₹)',exact=True)).to_have_value('50.00')
        save(p,'Edit order')
        nav('Production');page.get_by_role('button',name='Open',exact=True).first.click()
        for label,value in [('Labour','1200'),('Gas/power','600')]:
            p=form('Add overhead');p.get_by_label('Description',exact=True).fill(label);p.get_by_label('Amount (₹)').fill(value);save(p,'Add overhead')
        expect(page.get_by_text('₹31.14',exact=True)).to_be_visible()
        nav('Reports')
        expect(page.get_by_role('heading',name='Sales register')).to_be_visible()
        with page.expect_download():page.get_by_role('button',name='Export CSV').click()
        browser.close()
    print('PASS: React production, mobile order, approval, invoice/PDF, dispatch, shortage, payment, overhead and CSV')


if __name__=='__main__':main()
