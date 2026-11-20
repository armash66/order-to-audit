"""Browser checks for optional features; run after browser_check on an isolated demo."""
import argparse
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8002')
    url = parser.parse_args().url
    profile = tempfile.mkdtemp(prefix='ota-offline-profile-')
    artifacts = Path(tempfile.mkdtemp(prefix='ota-extensions-'))
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(profile)
        page = context.new_page()

        def login(name):
            context.clear_cookies()
            page.goto(url + '/login/')
            page.get_by_label('Username').fill(name)
            page.get_by_label('Password').fill('DemoPass123!')
            page.get_by_role('button', name='Sign in').click()
            page.wait_for_url(url + '/')

        login('admin')
        for path in ('/pricing/', '/batches/', '/visits/'):
            assert page.goto(url + path).status == 200
        page.goto(url + '/production/?lang=ta')
        expect(page.get_by_role('heading', name='உற்பத்திப் பணித்தளம்')).to_be_visible()
        page.screenshot(path=str(artifacts / 'tamil.png'), full_page=True)
        page.goto(url + '/production/?lang=en')
        # Select the dispatched order rather than relying on database primary keys.
        page.goto(url + '/orders/')
        links = page.locator('a[href]').evaluate_all(r'(rows) => rows.map(row => row.href).filter(url => /\/orders\/\d+\/$/.test(url))')
        mock_url = None
        for link in links:
            page.goto(link)
            mock = page.locator('a[href$="/mock/"]')
            if mock.count():
                mock_url = mock.first.get_attribute('href')
                break
        assert mock_url, 'An invoiced order is required from the browser benchmark.'
        page.goto(url + mock_url)
        page.get_by_role('button', name='Create local mock').click()
        expect(page.get_by_text('ACCEPTED_BY_LOCAL_MOCK')).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role('link', name='Download MOCK JSON').first.click()
        download.value.save_as(str(artifacts / 'mock.json'))
        assert 'MOCK-' in (artifacts / 'mock.json').read_text(encoding='utf-8')

        login('salesman_a')
        context.grant_permissions(['geolocation'], origin=url)
        context.set_geolocation({'latitude': 13.0827, 'longitude': 80.2707})
        page.goto(url + '/visits/')
        page.get_by_label('Route / area').fill('Browser demo route')
        page.locator('#gps-consent').check()
        page.get_by_role('button', name='Capture location').click()
        expect(page.locator('#latitude')).to_have_value('13.082700')
        page.get_by_role('button', name='Record visit').click()
        expect(page.get_by_text('Recorded with consent').first).to_be_visible()

        page.goto(url + '/offline/')
        expect(page.locator('#capture')).to_be_enabled()
        page.evaluate('navigator.serviceWorker.ready')
        page.reload()
        expect(page.locator('#capture')).to_be_enabled()
        context.set_offline(True)
        page.locator('#quantity').fill('2')
        page.locator('#capture').click()
        expect(page.locator('#queue li')).to_have_count(1)
        context.set_offline(False)
        expect(page.locator('#queue li')).to_have_count(0, timeout=20000)
        context.set_offline(True)
        page.locator('#capture').click()
        expect(page.locator('#queue li')).to_have_count(1)
        context.close()
        context = playwright.chromium.launch_persistent_context(profile, offline=True)
        page = context.new_page()
        page.goto(url + '/offline/')
        expect(page.locator('#queue li')).to_have_count(1)
        context.set_offline(False)
        page.reload()
        # No Sync button click: reconnect must trigger automatic idempotent submission.
        try:
            expect(page.locator('#queue li')).to_have_count(0, timeout=20000)
        except AssertionError:
            print('Reconnect diagnostic:', page.locator('#status').inner_text(), page.evaluate('navigator.onLine'))
            raise
        expect(page.locator('#status')).to_contain_text('All orders synced')
        context.close()
    print('PASS: extension pages, Tamil, mock download, consented GPS, offline restart/automatic reconnect')
    print('Artifacts:', artifacts)


if __name__ == '__main__':
    main()
