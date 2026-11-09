"""FL-087: Home and Planner sample attribution, 390/1280px, both themes.

Requires built site data and Playwright. Run with --out to choose the screenshot directory.
"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_check import serve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='layout-shots/captaincy-sample')
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    server, url = serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in (390, 1280):
            for theme in ('dark', 'light'):
                page = browser.new_page(viewport={'width': width, 'height': 900}, service_workers='block')
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url + '#week')
                page.wait_for_selector('.view-week')
                page.evaluate('theme => { THEME.set(theme); S.mode="balanced"; S.home="next"; }', theme)
                for case, label, pct in [('near', 'managers near your rank', 71), ('top', 'the top 10k', 19), ('none', None, None)]:
                    page.evaluate('''kind => {
                      const cap=myTeam().cap, gw=D.meta.cur_gw;
                      const sample=(n,pct)=>({n,cap:{[cap]:pct},eo:{[cap]:pct+10},own:{[cap]:pct},chips:{}});
                      D.crowd={gw,near:sample(kind==='near'?100:0,71),top10k:sample(kind==='none'?0:200,19),leagues:[]};
                      S.home='next'; $('#app').innerHTML='<div class="view-week">'+vHome()+'</div>';
                    }''', case)
                    captain = page.locator('article.dcard').nth(1).inner_text()
                    if label:
                        assert f'{pct}% of {label} captained' in captain, captain
                        assert ' in GW' in captain
                        assert 'last week' not in captain
                    else:
                        assert 'Captaincy sample unavailable' in captain
                        assert '% of ' not in captain
                    assert not page.locator('.state.error').count()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    page.screenshot(path=str(out/f'home-{case}-{width}-{theme}.png'), full_page=True, animations='disabled')
                    current = page.evaluate('vCurrent()')
                    if label:
                        assert f'Effective ownership among {label}' in current
                    else:
                        assert 'Ownership sample unavailable' in current
                    planner = page.evaluate('captainsHTML()')
                    compare = page.evaluate('pvCompare()')
                    if label:
                        assert f'share of {label} who captained' in planner
                        assert f'Effective ownership uses {label}' in compare
                    else:
                        assert 'Captaincy sample unavailable' in planner
                        assert '% field C' not in planner
                        assert 'Ownership sample unavailable' in compare
                        page.evaluate("S.field='near'; $('#app').innerHTML=vRivals()")
                        text=page.locator('#app').inner_text()
                        assert 'sample unavailable' in text
                        assert "Your XI's average ownership" not in text
                    print(f'PASS {case}: {width}px {theme}')
                assert not errors, errors
                page.close()
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
