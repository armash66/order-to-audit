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
        page.get_by_role('button',name='Save offline order').click()
        expect(page.get_by_text('1 queued orders',exact=True)).to_be_visible()
        context.set_offline(False)
        expect(page.get_by_text('0 queued orders',exact=True)).to_be_visible(timeout=15000)
        context.set_offline(True)
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
        context.close()
    print('PASS: React offline capture, automatic reconnect, browser restart and original-user sync')


if __name__=='__main__':main()
