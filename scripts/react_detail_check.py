"""Verify readable production details using mocked reads, without posting data."""
import argparse
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8000')
    args = parser.parse_args()
    screenshots = Path(tempfile.gettempdir()) / 'ota-detail-review'
    screenshots.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        draft = False

        # A stable report fixture tests UI formatting independently of the live database.
        def production(route):
            standards = [{'item__code': code, 'item__name': name, 'item__base_unit': unit} for code, name, unit in [('FLOUR','Flour','g'),('OIL','Cooking oil','ml'),('POUCH','200 g pouch','piece')]]
            report = {'expected_packets': '200', 'good_packets': None if draft else '188', 'yield': {'ratio': None if draft else {'numerator':'-3','denominator':'50'}, 'flagged': not draft}, 'unclassified_shortfall': None if draft else '12', 'tolerance_bps':'300', 'materials_paise':'405500', 'overhead_paise':'180000', 'total_paise':'585500', 'display_cost_paise':None if draft else '3114', 'margin_paise':None if draft else {'numerator':'88625','denominator':'47'}, 'damaged_packaging':{} if draft else {'POUCH':'6'}, 'consumption':{}}
            for code, planned, actual, numerator, denominator, flag in [('FLOUR','40000','40000','0','1',False),('OIL','10000','10500','1','20',True),('POUCH','200','194','-3','100',False)]:
                report['consumption'][code] = {'planned':planned,'actual':None if draft else actual,'ratio':None if draft else {'numerator':numerator,'denominator':denominator},'flagged':flag and not draft}
            route.fulfill(json={'id':'1','name':'Murukku 200 g','state':'draft' if draft else 'completed','standards':standards,'report':report,'loss_notes':[]})

        page.route('**/api/workspace/production', lambda route: route.fulfill(json=[{'id':'1','output_item__name':'Murukku 200 g','state':'completed'}]))
        page.route('**/api/workspace/production/1', production)
        page.goto(args.url)
        page.get_by_label('Username',exact=True).fill('admin')
        page.get_by_label('Password',exact=True).fill('DemoPass123!')
        page.get_by_role('button',name='Sign in',exact=True).click()
        nav = page.get_by_role('navigation',name='Workspace')
        nav.get_by_role('button',name='Production',exact=True).click()
        page.get_by_role('button',name='Open',exact=True).click()
        summary = page.get_by_role('region',name='Variance and costing')
        expect(summary.get_by_text('−6%',exact=True)).to_be_visible()
        expect(summary.get_by_text('₹31.14',exact=True)).to_be_visible()
        expect(summary.get_by_text('₹18.86',exact=True)).to_be_visible()
        oil = summary.get_by_role('row').filter(has_text='Cooking oil')
        expect(oil).to_contain_text('10.5 L')
        expect(oil).to_contain_text('+5%')
        expect(oil).to_contain_text('Flagged')
        pouch = summary.get_by_role('row').filter(has_text='200 g pouch')
        expect(pouch).to_contain_text('−3%')
        expect(pouch).to_contain_text('Within tolerance')
        for value in summary.locator('.cost-breakdown dd').all():
            assert value.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(screenshots/'production-desktop.png'),full_page=True)
        page.set_viewport_size({'width':360,'height':800})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        for value in summary.locator('.cost-breakdown dd').all():
            assert value.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
        page.screenshot(path=str(screenshots/'production-mobile.png'),full_page=True)
        draft = True
        nav.get_by_role('button',name='Orders',exact=True).click()
        nav.get_by_role('button',name='Production',exact=True).click()
        page.get_by_role('button',name='Open',exact=True).click()
        expect(summary.get_by_text('Not recorded',exact=True).first).to_be_visible()
        expect(summary.get_by_text('₹31.14',exact=True)).to_have_count(0)
        assert not errors, errors
        browser.close()
    print('PASS: production sections, exact costs/percentages, tolerance flags, pending output and mobile width')


if __name__ == '__main__':
    main()
