"""Exercise decision support through its normal UI at phone/desktop widths in both themes.
Uses published data; injects explicit edge-case snapshots for reviews and chip availability.
Run with the same Python Playwright environment as layout_check.py.
"""
from pathlib import Path
from behaviour_check import serve
from playwright.sync_api import sync_playwright


def main():
    server, url = serve()
    out = Path('/tmp/fpl-decision-shots')
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (390, 1280):
            for theme in ('dark', 'light'):
                ctx = browser.new_context(viewport={'width': width, 'height': 900}, service_workers='block')
                page = ctx.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.add_init_script(f"localStorage.setItem('fpl.theme', '{theme}'); if (!localStorage.getItem('fpl.home')) localStorage.setItem('fpl.home', JSON.stringify('next'))")
                page.goto(url + '#week')
                page.wait_for_selector('[data-decision="captain"]')
                # Published recommendation is currently Roll. Seed a legal suggested move for entry-point coverage.
                page.evaluate('''() => {
                    if (!myTeam().moves0.length) {
                        const move=planMoves(D.plans.roll).find(m => P[m.in].price <= sellPrice(m.out)+D.manager.bank);
                        if (!move) throw new Error('Fixture needs a legal alternative');
                        activatePlan({moves:[{...move,gw:PG[0]}],ov:{},chips:{},mode:'balanced'},'custom'); render();
                    }
                }''')
                assert page.evaluate('THEME.get()') == theme
                original = page.evaluate('JSON.stringify(completePlan())')
                # Compare the armband without touching squad, transfers, bank or any later week.
                page.locator('[data-decision="captain"]').click()
                page.wait_for_selector('#decisionCaptain')
                assert page.evaluate('DECISION.a.moves.length === DECISION.b.moves.length')
                assert page.evaluate('JSON.stringify(decisionScore(DECISION.a).weeks.map(w=>w.team.xi)) === JSON.stringify(decisionScore(DECISION.b).weeks.map(w=>w.team.xi))')
                assert page.evaluate('Math.abs((decisionScore(DECISION.a).tot-decisionScore(DECISION.b).tot) - (xpg(DECISION.cap,PG[0])-xpg(DECISION.selected,PG[0])) * (chipAt(PG[0],DECISION.a.chips)==="3xc"?2:1)) < 1e-8')
                page.screenshot(path=str(out / f'captain-{width}-{theme}.png'), full_page=False)
                page.locator('#decisionClose').click()
                assert page.evaluate('JSON.stringify(completePlan())') == original
                # Saving and keeping enter from Next deadline, using the real browser solver.
                page.locator('[data-decision="roll"]').click()
                page.wait_for_function('DECISION && !DECISION.busy', timeout=180000)
                assert page.evaluate('!DECISION.error'), page.evaluate('DECISION.error')
                assert page.evaluate('DECISION.b.moves.every(m=>m.gw!==PG[0])')
                page.screenshot(path=str(out / f'saving-{width}-{theme}.png'), full_page=False)
                page.locator('#decisionClose').click()
                assert page.evaluate('JSON.stringify(completePlan())') == original
                keep = page.locator('[data-decision="keep"]').first
                if keep.count():
                    keep.click()
                    page.wait_for_function('DECISION && !DECISION.busy', timeout=180000)
                    assert page.evaluate('!DECISION.error'), page.evaluate('DECISION.error')
                    assert page.evaluate('decisionScore(DECISION.b).weeks.every(w=>w.sq.includes(DECISION.keep))')
                    page.screenshot(path=str(out / f'keep-{width}-{theme}.png'), full_page=False)
                    page.locator('[data-decision-save="b"]').click()
                    assert page.evaluate('JSON.stringify(completePlan())') == original
                    page.locator('#decisionClose').click()
                else:
                    raise AssertionError('Fixture must have a suggested sale to check Keep')
                # Normal league/head-to-head pin controls, then Current GW.
                page.goto(url + '#rivals')
                page.wait_for_selector('[data-rvh2h]')
                page.locator('[data-rvh2h]').first.click()
                page.locator('[data-rvpin]').first.click()
                page.goto(url + '#week')
                page.locator('[data-home="current"]').click()
                page.get_by_role('heading', name='Pinned rivalry', exact=False).wait_for()
                page.screenshot(path=str(out / f'rivalry-{width}-{theme}.png'), full_page=False)
                page.reload()
                page.get_by_role('heading', name='Pinned rivalry', exact=False).wait_for()
                page.locator('[data-rivalry-remove]').click()
                assert not page.get_by_role('heading', name='Pinned rivalry', exact=False).count()
                page.goto(url + '#rivals')
                page.wait_for_selector('[data-rivalry-league]')
                page.locator('[data-rivalry-league]').click()
                page.goto(url + '#week')
                page.locator('[data-home="current"]').click()
                assert 'overall standings' in page.locator('#homepanel').inner_text()
                # Bench comparison: actual chip state (used this half), then future missing projection.
                page.goto(url + '#chips')
                page.wait_for_selector('[data-bbweek="a"]')
                page.locator('[data-bbweek="b"]').select_option('13')
                assert 'bench-total estimates' in page.locator('#app').inner_text()
                page.screenshot(path=str(out / f'bench-{width}-{theme}.png'), full_page=False)
                page.locator('[data-bbweek="b"]').select_option('30')
                assert 'No player projections for GW30' in page.locator('#app').inner_text()
                # Review an alternative via the normal Planner Drafts button.
                page.goto(url + '#planner')
                page.wait_for_selector('.view-planner')
                page.locator('[data-pview="edit"]').click()
                page.locator('[data-ptab="drafts"]').click()
                page.wait_for_selector('[data-plan-review]')
                # Price change makes this saved plan unaffordable, without changing unrelated players.
                page.evaluate('''() => {
                    const ds=getDrafts(), d=ds[0], m=d.moves[0];
                    if (!m) throw new Error('Review test requires a transfer');
                    d.review=planReviewSnapshot(d); setDrafts(ds);
                    P[m.in].price += 10; D.meta.built=new Date().toISOString();
                }''')
                page.locator('[data-plan-review]').first.click()
                assert 'unaffordable' in page.locator('#dlgBody').inner_text()
                page.screenshot(path=str(out / f'review-{width}-{theme}.png'), full_page=False)
                old = page.evaluate('JSON.stringify([...PLAN_REVIEWS.values()])')
                page.evaluate('openPlanReview(0)')
                assert page.evaluate('JSON.stringify([...PLAN_REVIEWS.values()])') == old
                assert 'unaffordable' in page.locator('#dlgBody').inner_text()
                assert not errors, errors
                assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1')
                print(f'PASS decision flows {width}px {theme}', flush=True)
                ctx.close()
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
