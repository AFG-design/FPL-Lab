"""FL-064: Home live auto-subs at 390/1280px in both themes. Needs built site data and Playwright."""
import argparse
from layout_check import serve
from playwright.sync_api import sync_playwright
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--out', default='layout-shots/live-autosub')
out = Path(ap.parse_args().out); out.mkdir(parents=True, exist_ok=True)
server, url = serve()
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width in (390, 1280):
        for theme in ('dark', 'light'):
            page = browser.new_page(viewport={'width': width, 'height': 900}, service_workers='block')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(url + '#week'); page.wait_for_selector('.view-week')
            page.evaluate('''theme => {
              THEME.set(theme);
              const positions = ['GKP','DEF','DEF','DEF','MID','MID','MID','MID','FWD','FWD','FWD','GKP','MID','DEF','FWD'];
              const used = new Set();
              const rows = positions.map((pos, i) => {
                const p = Object.values(P).find(p => p.pos === pos && !used.has(p.id)); used.add(p.id);
                p.team = i + 1;
                return {id:p.id,team:i+1,pos:i+1,mins:90,pts:2,prov:0,bps:10,bonus:0,mult:i<11?(i===8?2:1):0,cap:i===8,vice:i===9};
              });
              const fixtures = rows.map(r => ({h:r.team,a:20,started:true,done:true,hs:0,as:0,ko:'2026-11-08T15:00:00Z'}));
              rows[4].mins=rows[4].pts=0; rows[12].mins=rows[12].pts=0; rows[13].pts=7;
              fixtures[12].done=fixtures[12].started=false;
              D.live={gw:11,rows,fixtures,hits:4,points:999,in_play:true,finished:false,total_before:100,rank_curve:[[10,150],[100,140],[1000,130],[10000,120],[100000,110],[1000000,100]]};
              D.meta.cur_gw=11; D.meta.cur_finished=false;
              document.querySelector('#app').innerHTML = '<div class="view-week">'+vCurrent()+'</div>';
            }''', theme)
            text = page.locator('#app').inner_text()
            assert 'Auto-sub if he plays' in text, text
            assert 'Auto-sub: counts' not in text
            assert page.evaluate('liveState().total') == 18
            assert page.locator('.live-panel .kpi').first.locator('b').inner_text() == '18'
            assert page.locator('.gwtiles .dash-big b').first.inner_text() == '22'  # Home displays gross points, with the hit separately labelled.
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert not errors, errors
            page.screenshot(path=str(out / f'home-{width}-{theme}.png'), full_page=True)
            page.evaluate('''() => {D.live.rows[12].mins=90;D.live.rows[12].pts=5;D.live.fixtures[12].started=true;
              document.querySelector('#app').innerHTML='<div class="view-week">'+vCurrent()+'</div>'; }''')
            assert 'Auto-sub: counts' in page.locator('#app').inner_text()
            assert page.evaluate('liveState().total') == 23
            print('PASS Home pending and confirmed', width, theme)
            page.close()
    browser.close()
server.shutdown()
