"""Verify navigation, filtering and unsaved-form protection without posting business data."""
import argparse
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://localhost:8003')
    url=parser.parse_args().url
    artifacts=Path(tempfile.mkdtemp(prefix='ota-workspace-'))
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for user in ('admin','salesman_a','production','accountant','owner'):
            context=browser.new_context(viewport={'width':1366,'height':900})
            page=context.new_page()
            page.goto(url+'/login/')
            page.get_by_label('Username').fill(user)
            page.get_by_label('Password').fill('DemoPass123!')
            page.get_by_role('button',name='Sign in').click()
            page.wait_for_url(url+'/')
            expect(page.get_by_role('navigation',name='Main navigation')).to_be_visible()
            page.screenshot(path=str(artifacts/(user+'-home.png')),full_page=True)
            paths=['/production/','/stock/'] if user=='production' else ['/orders/','/reports/']
            for path in paths:
                page.goto(url+path)
                for width in (1366,360):
                    page.set_viewport_size({'width':width,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (user,path,width)
                page.screenshot(path=str(artifacts/(user+path.replace('/','-')+'.png')),full_page=True)
            if user=='admin':
                page.goto(url+'/orders/')
                page.get_by_label('Find order or customer').fill('not-a-real-customer')
                page.get_by_role('button',name='Filter orders').click()
                expect(page.get_by_text('No orders match this view.',exact=False)).to_be_visible()
            if user=='salesman_a':
                page.goto(url+'/orders/')
                page.get_by_label('Packets',exact=True).fill('7')
                def stay(dialog):
                    assert dialog.type=='beforeunload'
                    dialog.dismiss()
                page.on('dialog',stay)
                page.get_by_role('link',name='Home',exact=True).click()
                expect(page.get_by_label('Packets',exact=True)).to_have_value('7')
                page.remove_listener('dialog',stay)
            context.close()
        browser.close()
    print('PASS: five roles, desktop/mobile overflow, queue filtering, unsaved-form warning')
    print('Artifacts:',artifacts)


if __name__=='__main__':
    main()
