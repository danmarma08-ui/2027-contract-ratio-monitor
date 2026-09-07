import json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

JINHAK_URL='https://addon.jinhakapply.com/RatioV1/RatioH/Ratio10810661.html'
UWAY_URL='https://ratio.uwayapply.com/Sl5KQzphYCZNOFdKZiUmOiZKN2ZUZg=='
KST=timezone(timedelta(hours=9))
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'/'data.json'
ARTIFACTS=ROOT/'artifacts'

JINHAK_TARGET='계약학과 채용조건형 특별전형 경쟁률 현황'
JINHAK_NAMES=[
 '헤어디자인학과-㈜준오뷰티',
 '헤어디자인학과-㈜피엔제이',
 '헤어디자인학과-㈜뷰티끄레아',
 '헤어디자인학과-미창조㈜',
 '헤어디자인학과-㈜커커',
 '헤어디자인학과-㈜브이오지코리아',
 '코스메틱뷰티매니지먼트학과-㈜블리비홀딩스',
 '코스메틱뷰티매니지먼트학과-㈜뷰티라운지',
]
UWAY_TARGET='(충남형)리안헤어뷰티아트학과 미창조(주)리안헤어'


def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip()

def text_cells(tr):
    return [norm(c.inner_text()) for c in tr.locator('th,td').all()]

def clean_cell(s):
    return norm(s).replace('\u00a0',' ')


def wait_for_real_content(page, target, timeout=20000):
    try:
        page.get_by_text(target, exact=False).first.wait_for(state='visible', timeout=timeout)
        return True
    except PlaywrightTimeoutError:
        return False


def jinhak(page):
    page.goto(JINHAK_URL, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(5000)
    if not wait_for_real_content(page, JINHAK_TARGET, 20000):
        title=page.title()
        body=norm(page.locator('body').inner_text())[:1000]
        raise RuntimeError(f'진학어플라이 보안 페이지 또는 대상 표 미검출 (title={title!r}, body={body!r})')

    rows=[]
    # Find the table containing the target heading. The exact markup can change, so search all tables.
    tables=page.locator('table')
    for i in range(tables.count()):
        table=tables.nth(i)
        table_text=norm(table.inner_text())
        if JINHAK_TARGET in table_text or any(n in table_text for n in JINHAK_NAMES):
            for tr in table.locator('tr').all():
                cells=text_cells(tr)
                if len(cells)>=4 and cells[0] in JINHAK_NAMES:
                    rows.append({'name':cells[0], 'recruit':cells[1], 'applicants':cells[2], 'ratio':cells[3]})
            if rows:
                break
    if len(rows) < len(JINHAK_NAMES):
        # Fallback: scan every row on the page for exact target names.
        rows=[]
        for tr in page.locator('tr').all():
            cells=text_cells(tr)
            if len(cells)>=4 and cells[0] in JINHAK_NAMES:
                rows.append({'name':cells[0], 'recruit':cells[1], 'applicants':cells[2], 'ratio':cells[3]})
    missing=[n for n in JINHAK_NAMES if n not in {r['name'] for r in rows}]
    if missing:
        raise RuntimeError('진학어플라이 일부 모집단위를 찾지 못했습니다: '+', '.join(missing))
    return rows


def uway(page):
    page.goto(url, wait_until="domcontentloaded", timeout=120000)
page.wait_for_timeout(15000)
page.reload(wait_until="domcontentloaded", timeout=120000)
page.wait_for_timeout(15000)
    page.wait_for_timeout(3000)
    if not wait_for_real_content(page, UWAY_TARGET, 20000):
        raise RuntimeError(f'유웨이 대상 행을 찾지 못했습니다 (title={page.title()!r})')
    for tr in page.locator('tr').all():
        cells=text_cells(tr)
        if UWAY_TARGET in cells:
            if len(cells)>=6:
                return {'name':cells[1], 'recruit':cells[3], 'applicants':cells[4], 'ratio':cells[5]}
    raise RuntimeError('유웨이 리안헤어 항목을 찾지 못했습니다.')


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context=browser.new_context(
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            viewport={'width':1440,'height':1000},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
        )
        page=context.new_page()
        try:
            j=jinhak(page)
            u=uway(page)
        except Exception:
            try: page.screenshot(path=str(ARTIFACTS/'failure.png'), full_page=True)
            except Exception: pass
            raise
        finally:
            browser.close()

    current={
      'updated_at':datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'),
      'sources':[
        {'id':'jinhak','label':'진학어플라이','url':JINHAK_URL,'note':JINHAK_TARGET},
        {'id':'uway','label':'유웨이','url':UWAY_URL,'note':UWAY_TARGET}
      ],
      'jinhak':j,
      'uway':[u]
    }
    old=None
    if DATA.exists():
        try: old=json.loads(DATA.read_text(encoding='utf-8'))
        except Exception: pass
    jold=(old or {}).get('jinhak',[]); uold=(old or {}).get('uway',[])
    for x in current['jinhak']:
        ox=next((z for z in jold if z.get('name')==x.get('name')),None)
        x['changed']=bool(ox and {k:v for k,v in ox.items() if k!='changed'} != {k:v for k,v in x.items() if k!='changed'})
    for x in current['uway']:
        ox=next((z for z in uold if z.get('name')==x.get('name')),None)
        x['changed']=bool(ox and {k:v for k,v in ox.items() if k!='changed'} != {k:v for k,v in x.items() if k!='changed'})
    def values(rows): return [{k:v for k,v in x.items() if k!='changed'} for x in rows]
    current['changed']=old is None or values(jold)!=values(current['jinhak']) or values(uold)!=values(current['uway'])
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(current,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
