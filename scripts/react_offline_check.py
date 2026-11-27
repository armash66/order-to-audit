"""Verify React offline persistence/reconnect against an isolated rehearsal instance."""
import argparse
import tempfile
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://localhost:8006')
    url=parser.parse_args().url
    profile=tempfile.mkdtemp(prefix='ota-react-offline-')
    with sync_playwright() as pw:
        context=pw.chromium.launch_persistent_context(profile)
        page=context.new_page()
        def login():
            page.goto(url)
            page.get_by_label('Username',exact=True).fill('salesman_a')
            page.get_by_label('Password',exact=True).fill('DemoPass123!')
            page.get_by_role('button',name='Sign in',exact=True).click()
            page.get_by_role('navigation').get_by_role('button',name='Offline',exact=True).click()
            expect(page.get_by_role('button',name='Save offline order')).to_be_visible()
        login()
        page.evaluate('navigator.serviceWorker.ready')
        page.wait_for_function("localStorage.getItem('ota-react-catalog') !== null")
        context.set_offline(True)
        page.get_by_label('Packets',exact=True).fill('2')
        page.get_by_role('button',name='Add another product').click()
        second_product = page.get_by_role('group',name='Another product',exact=True)
        has_second_sku = second_product.get_by_role('radio').count() > 1
        if has_second_sku:
            second_product.get_by_role('radio').nth(1).check()
        page.get_by_label('Packets',exact=True).nth(1).fill('3')
        page.get_by_role('button',name='Save offline order').click()
        expect(page.get_by_text('1 queued orders',exact=True)).to_be_visible()
        if has_second_sku:
            expect(page.get_by_text('2 packets',exact=False)).to_be_visible()
            expect(page.get_by_text('3 packets',exact=False)).to_be_visible()
        else:
            expect(page.get_by_text('5 packets',exact=False)).to_be_visible()
        context.set_offline(False)
        expect(page.get_by_text('0 queued orders',exact=True)).to_be_visible(timeout=15000)
        context.set_offline(True)
        page.get_by_label('Packets',exact=True).fill('1')
        page.get_by_role('button',name='Save offline order').click()
        expect(page.get_by_text('1 queued orders',exact=True)).to_be_visible()
        context.close()
        context=pw.chromium.launch_persistent_context(profile,offline=True)
        page=context.new_page()
        page.goto(url+'/offline')
        expect(page.get_by_text('1 queued orders',exact=True)).to_be_visible()
        context.set_offline(False)
        login()
        expect(page.get_by_text('0 queued orders',exact=True)).to_be_visible(timeout=15000)
        page.once('dialog',lambda dialog:dialog.accept())
        page.get_by_role('button',name='Clear this device').click()
        page.wait_for_load_state()
        assert page.evaluate("localStorage.getItem('ota-react-catalog')") is None
        assert page.evaluate("localStorage.getItem('ota-react-orders-v1')") is None
        context.close()
    print('PASS: React multi-line offline capture, automatic reconnect/reopen sync and device clear')


if __name__=='__main__':main()
