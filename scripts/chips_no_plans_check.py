"""FL-085: Chips renders without plans, at both widths and in both themes."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_check import serve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='layout-shots/chips-no-plans')
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    server, url = serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in (390, 1280):
            for theme in ('dark', 'light'):
                page = browser.new_page(viewport={'width': width, 'height': 900}, service_workers='block')
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url + '#chips')
                page.wait_for_selector('.view-chips .chips')
                page.evaluate('theme => THEME.set(theme)', theme)
                original = page.locator('.view-chips .chips').inner_html()
                original_page = page.evaluate('vChips()')
                for case in ('plans', 'empty', 'missing'):
                    page.evaluate('''kind => {
                      if (kind !== 'plans') {
                        D.plans = {};
                        if (kind === 'empty') D.gw_info = [];
                        else delete D.gw_info;
                      }
                      document.querySelector('.view-chips').innerHTML = vChips();
                    }''', case)
                    view = page.locator('.view-chips')
                    assert view.locator('.chips').inner_html() == original
                    if case == 'plans':
                        assert page.evaluate('vChips()') == original_page
                    message = view.get_by_text('No projection for the best week yet', exact=False)
                    assert message.count() == (0 if case == 'plans' else 1)
                    assert not page.locator('.state.error').count()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    page.screenshot(path=str(out / f'chips-{case}-{width}-{theme}.png'), full_page=True)
                    print(f'PASS {case}: {width}px {theme}')
                assert not errors, errors
                page.close()
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
