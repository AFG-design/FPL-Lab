"""FL-086: Scores cards agree with Home captaincy, both widths and themes.

Needs built site data and Playwright. Run with --out to choose screenshot output.
"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_check import serve


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out', default='layout-shots/vice-match-cards')
    out=Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    server,url=serve()
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width in (390,1280):
            for theme in ('dark','light'):
                page=browser.new_page(viewport={'width':width,'height':900},service_workers='block')
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url+'#week')
                page.wait_for_selector('.view-week')
                page.evaluate('theme => THEME.set(theme)',theme)
                for case,expected in [('plays',6),('out',12),('pending',6),('tc',18)]:
                    ids=page.evaluate('''kind => {
                      const rows=D.live.rows.map((r,i)=>({...r,team:i+1,mins:90,pts:2,prov:0}));
                      rows.forEach(r=>P[r.id].team=r.team);
                      const cap=rows.find(r=>r.cap),vice=rows.find(r=>r.vice);
                      cap.mins=kind==='plays'?90:0; cap.pts=kind==='plays'?5:0;
                      vice.mins=90;vice.pts=5;vice.prov=1;
                      const fixtures=rows.map(r=>({h:r.team,a:20,started:true,done:true,hs:0,as:0,ko:'2026-11-08T15:00:00Z'}));
                      if(kind==='pending') Object.assign(fixtures.find(f=>f.h===cap.team),{done:false,started:false});
                      D.live={gw:11,rows,fixtures,chip:kind==='tc'?'3xc':null,in_play:true,finished:false,hits:0};
                      D.meta.cur_gw=11;D.meta.cur_finished=false;D.meta.deadline='2099-01-01';
                      S.home='current';$('#app').innerHTML='<div class="view-week">'+vHome()+'</div>';
                      return {cap:cap.id,vice:vice.id};
                    }''',case)
                    vice=page.locator(f'.mc-p[data-p="{ids["vice"]}"]')
                    assert vice.locator('b').inner_text()==str(expected)
                    assert ('(C)' in vice.inner_text()) == (case in ('out','tc'))
                    home=page.locator('.gwtiles .dash-tile').nth(1).inner_text().lower()
                    if case in ('out','tc'):
                        assert 'vice took over' in home and f'{expected} pts' in home,home
                    elif case=='plays':
                        assert '10 pts' in home and 'vice took over' not in home,home
                    else:
                        assert 'yet to play' in home and 'vice took over' not in home,home
                    assert not page.locator('.state.error').count()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    vice.scroll_into_view_if_needed()
                    page.screenshot(path=str(out/f'scores-{case}-{width}-{theme}.png'),animations='disabled')
                    print(f'PASS {case}: {width}px {theme}')
                assert not errors,errors
                page.close()
        browser.close()
    server.shutdown()


if __name__=='__main__':
    main()
