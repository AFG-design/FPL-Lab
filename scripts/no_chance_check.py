"""FL-077: reported/unknown FPL chances on every affected screen, both widths and themes.

Needs built site/data.json, site/data-extra.json and Playwright, like layout_check.py.
Usage: python3 scripts/no_chance_check.py --out layout-shots/no-chance
"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_check import serve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='layout-shots/no-chance')
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
                page.goto(url + '#players')
                page.wait_for_selector('.view-players')
                page.evaluate('() => new Promise(resolve => withExtra(resolve))')
                page.evaluate('''theme => {
                  THEME.set(theme);
                  const p = D.players.find(p => p.pos === 'GKP' && fxFor(p.team, D.meta.next_gw).length);
                  if (!p) throw Error('Need a keeper with a next-GW fixture');
                  D.players = [p]; p.status = 'd'; p.news = ''; p.p_start = 1;
                  p.s_min = [90,90,0]; p.ret = false;
                  STARS.ids = {[p.id]: {price: p.price}};
                  S.q = ''; S.pos = 'ALL'; S.team = 'ALL'; S.maxp = ''; S.xquick = 'all';
                }''', theme)
                for chance in (None, 0, 75):
                    page.evaluate('chance => { D.players[0].chance = chance; }', chance)
                    expected = '!' if chance is None else f'{chance}%'
                    for name, expression in (('players', 'vPlayers()'), ('xptable', 'vXpTable()'), ('watchlist', 'starsPanel()')):
                        page.evaluate("expression => { $('#app').innerHTML = eval(expression); }", expression)
                        assert page.locator('#app .pill.warn').first.inner_text() == expected, (name, chance)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), name
                        if chance is None:
                            page.screenshot(path=str(out / f'{name}-{width}-{theme}.png'), full_page=True, animations="disabled")
                    page.evaluate('openTeam(D.players[0].team)')
                    assert page.locator('#dlg .xi-lines .pill.warn').first.inner_text() == expected
                    if chance is None:
                        page.locator('#dlg .xi-lines').scroll_into_view_if_needed()
                        page.screenshot(path=str(out / f'team-{width}-{theme}.png'), full_page=True, animations="disabled")
                    page.evaluate("$('#dlg').close(); openPlayer(D.players[0].id)")
                    text = page.locator('#dlgBody').inner_text()
                    if chance is None:
                        assert 'no chance given' in text
                        assert 'FPL lists him at 0%' not in text
                        assert 'flagged at 0%' not in text
                        page.screenshot(path=str(out / f'player-{width}-{theme}.png'), full_page=True, animations="disabled")
                    else:
                        assert f'FPL lists him at {chance}%' in text
                    page.evaluate("$('#dlg').close()")
                assert not errors, errors
                print(f'PASS all affected screens: {width}px {theme}; null, 0%, 75%')
                page.close()
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
