"""Check exact receipt calculations without posting transactions."""
import argparse
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8000')
    args = parser.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width':360,'height':800})
        page.goto(args.url)
        page.get_by_label('Username',exact=True).fill('production')
        page.get_by_label('Password',exact=True).fill('DemoPass123!')
        page.get_by_role('button',name='Sign in',exact=True).click()
        page.locator('button[data-action-title="Receive materials"]').click()
        form = page.get_by_role('dialog',name='Receive materials',exact=True)
        form.get_by_role('group',name='Item',exact=True).get_by_role('radio',name='Flour',exact=True).check()
        form.locator('input[name=unit][value=kg]').check()
        quantity = form.get_by_label('Quantity',exact=True)
        rate = form.get_by_label('Rate (₹ per selected unit)',exact=True)
        total = form.get_by_label('Total value (₹)',exact=True)
        for q, r, expected in [('60','45','2700.00'),('10.5','140','1470.00'),('0.001','5','0.01'),('0.001','4.99','0.00'),('9007199254740993','0.01','90071992547409.93')]:
            quantity.fill(q)
            rate.fill(r)
            expect(total).to_have_value(expected)
        rate.fill('bad')
        expect(total).to_have_value('')
        assert not rate.evaluate('input => input.checkValidity()')
        rate.fill('45')
        form.locator('input[name=unit][value=g]').check()
        expect(rate).to_have_value('')
        expect(total).to_have_value('')
        form.get_by_role('button',name='Invoice total',exact=True).click()
        total.fill('2700.00')
        expect(total).to_have_value('2700.00')
        assert form.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
        form.get_by_role('group',name='Item',exact=True).get_by_role('radio',name='Cooking oil',exact=True).check()
        expect(form.locator('input[name=unit][value=ml]')).to_be_checked()
        expect(rate).to_have_value('')
        browser.close()
    print('PASS: exact receipt totals, half-up rounding, large integers, invalid input, unit reset and manual totals')


if __name__ == '__main__':
    main()
