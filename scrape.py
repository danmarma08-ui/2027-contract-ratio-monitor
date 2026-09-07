import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# =========================
# 기본 설정
# =========================

JINHAK_URL = "https://addon.jinhakapply.com/RatioV1/RatioH/Ratio10810661.html"
UWAY_URL = "https://ratio.uwayapply.com/Sl5KQzphYCZNOFdKZiUmOiZKN2ZUZg=="

KST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "data.json"
ARTIFACTS = ROOT / "artifacts"


# =========================
# 진학어플라이 설정
# =========================

JINHAK_TARGET = "계약학과 채용조건형 특별전형 경쟁률 현황"

JINHAK_NAMES = [
    "헤어디자인학과-㈜준오뷰티",
    "헤어디자인학과-㈜피엔제이",
    "헤어디자인학과-㈜뷰티끄레아",
    "헤어디자인학과-미창조㈜",
    "헤어디자인학과-㈜커커",
    "헤어디자인학과-㈜브이오지코리아",
    "코스메틱뷰티매니지먼트학과-㈜블리비홀딩스",
    "코스메틱뷰티매니지먼트학과-㈜뷰티라운지",
]


# =========================
# 유웨이 설정
# =========================

UWAY_TARGET = "(충남형)리안헤어뷰티아트학과 미창조(주)리안헤어"


# =========================
# 공통 함수
# =========================

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def text_cells(tr):
    return [
        norm(c.inner_text())
        for c in tr.locator("th,td").all()
    ]


def clean_cell(s):
    return norm(s).replace("\u00a0", " ")


def wait_for_real_content(page, target, timeout=20000):
    try:
        page.get_by_text(
            target,
            exact=False
        ).first.wait_for(
            state="visible",
            timeout=timeout
        )
        return True

    except PlaywrightTimeoutError:
        return False


# =========================
# 진학어플라이
# =========================

def jinhak(page):

    print("진학어플라이 접속 시작")

    page.goto(
        JINHAK_URL,
        wait_until="domcontentloaded",
        timeout=120000
    )

    print("진학어플라이 최초 접속 완료")
    print("보안 확인을 위해 15초 대기")

    page.wait_for_timeout(15000)

    print("진학어플라이 페이지 새로고침")

    page.reload(
        wait_until="domcontentloaded",
        timeout=120000
    )

    print("새로고침 완료")
    print("보안 확인을 위해 추가 15초 대기")

    page.wait_for_timeout(15000)

    # 실제 페이지가 나타나는지 확인
    if not wait_for_real_content(
        page,
        JINHAK_TARGET,
        20000
    ):

        title = page.title()

        try:
            body = norm(
                page.locator("body").inner_text()
            )[:2000]
        except Exception:
            body = ""

        print("진학어플라이 실제 페이지 확인 실패")
        print(f"페이지 제목: {title}")
        print(f"페이지 내용: {body}")

        raise RuntimeError(
            "진학어플라이 보안 페이지 또는 "
            f"대상 표 미검출 "
            f"(title={title!r}, body={body!r})"
        )

    print("진학어플라이 실제 페이지 확인 성공")

    rows = []

    # =========================
    # 표에서 데이터 찾기
    # =========================

    tables = page.locator("table")

    print(f"페이지 내 table 개수: {tables.count()}")

    for i in range(tables.count()):

        table = tables.nth(i)

        try:
            table_text = norm(
                table.inner_text()
            )
        except Exception:
            continue

        if (
            JINHAK_TARGET in table_text
            or any(
                name in table_text
                for name in JINHAK_NAMES
            )
        ):

            for tr in table.locator("tr").all():

                cells = text_cells(tr)

                if (
                    len(cells) >= 4
                    and cells[0] in JINHAK_NAMES
                ):

                    rows.append(
                        {
                            "name": cells[0],
                            "recruit": cells[1],
                            "applicants": cells[2],
                            "ratio": cells[3],
                        }
                    )

            if rows:
                break

    # =========================
    # 표 검색 실패 시 전체 행 검색
    # =========================

    if len(rows) < len(JINHAK_NAMES):

        print(
            "표 검색으로 모든 모집단위를 찾지 못해 "
            "전체 행을 다시 검색합니다."
        )

        rows = []

        for tr in page.locator("tr").all():

            cells = text_cells(tr)

            if (
                len(cells) >= 4
                and cells[0] in JINHAK_NAMES
            ):

                rows.append(
                    {
                        "name": cells[0],
                        "recruit": cells[1],
                        "applicants": cells[2],
                        "ratio": cells[3],
                    }
                )

    # =========================
    # 누락 확인
    # =========================

    found_names = {
        row["name"]
        for row in rows
    }

    missing = [
        name
        for name in JINHAK_NAMES
        if name not in found_names
    ]

    if missing:

        raise RuntimeError(
            "진학어플라이 일부 모집단위를 찾지 못했습니다: "
            + ", ".join(missing)
        )

    print(
        f"진학어플라이 데이터 {len(rows)}개 확인 완료"
    )

    return rows


# =========================
# 유웨이
# =========================

def uway(page):

    print("유웨이 접속 시작")

    page.goto(
        UWAY_URL,
        wait_until="domcontentloaded",
        timeout=120000
    )

    page.wait_for_timeout(5000)

    if not wait_for_real_content(
        page,
        UWAY_TARGET,
        20000
    ):

        raise RuntimeError(
            "유웨이 대상 행을 찾지 못했습니다 "
            f"(title={page.title()!r})"
        )

    print("유웨이 실제 페이지 확인 성공")

    for tr in page.locator("tr").all():

        cells = text_cells(tr)

        if UWAY_TARGET in cells:

            if len(cells) >= 6:

                result = {
                    "name": cells[1],
                    "recruit": cells[3],
                    "applicants": cells[4],
                    "ratio": cells[5],
                }

                print("유웨이 데이터 확인 완료")

                return result

    raise RuntimeError(
        "유웨이 리안헤어 항목을 찾지 못했습니다."
    )


# =========================
# 메인
# =========================

def main():

    ARTIFACTS.mkdir(
        exist_ok=True
    )

    with sync_playwright() as p:

        print("Chromium 실행")

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(

            locale="ko-KR",

            timezone_id="Asia/Seoul",

            viewport={
                "width": 1440,
                "height": 1000
            },

            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 "
                "Safari/537.36"
            )
        )

        page = context.new_page()

        try:

            # 진학어플라이
            j = jinhak(page)

            # 유웨이
            u = uway(page)

        except Exception:

            print("스크래핑 실패")

            try:

                page.screenshot(
                    path=str(
                        ARTIFACTS / "failure.png"
                    ),
                    full_page=True
                )

                print(
                    "실패 화면을 "
                    "artifacts/failure.png에 저장했습니다."
                )

            except Exception as screenshot_error:

                print(
                    f"스크린샷 저장 실패: "
                    f"{screenshot_error}"
                )

            raise

        finally:

            browser.close()

    # =========================
    # 현재 데이터 생성
    # =========================

    current = {

        "updated_at": datetime.now(
            KST
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "sources": [

            {
                "id": "jinhak",
                "label": "진학어플라이",
                "url": JINHAK_URL,
                "note": JINHAK_TARGET
            },

            {
                "id": "uway",
                "label": "유웨이",
                "url": UWAY_URL,
                "note": UWAY_TARGET
            }
        ],

        "jinhak": j,

        "uway": [
            u
        ]
    }

    # =========================
    # 기존 데이터 읽기
    # =========================

    old = None

    if DATA.exists():

        try:

            old = json.loads(
                DATA.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            old = None

    jold = (
        old or {}
    ).get(
        "jinhak",
        []
    )

    uold = (
        old or {}
    ).get(
        "uway",
        []
    )

    # =========================
    # 진학어플라이 변경 여부
    # =========================

    for x in current["jinhak"]:

        ox = next(
            (
                z
                for z in jold
                if z.get("name")
                == x.get("name")
            ),
            None
        )

        x["changed"] = bool(

            ox

            and {

                k: v
                for k, v in ox.items()
                if k != "changed"

            }

            != {

                k: v
                for k, v in x.items()
                if k != "changed"

            }
        )

    # =========================
    # 유웨이 변경 여부
    # =========================

    for x in current["uway"]:

        ox = next(
            (
                z
                for z in uold
                if z.get("name")
                == x.get("name")
            ),
            None
        )

        x["changed"] = bool(

            ox

            and {

                k: v
                for k, v in ox.items()
                if k != "changed"

            }

            != {

                k: v
                for k, v in x.items()
                if k != "changed"

            }
        )

    # =========================
    # changed 제외 비교
    # =========================

    def values(rows):

        return [

            {
                k: v
                for k, v in x.items()
                if k != "changed"
            }

            for x in rows
        ]

    current["changed"] = (

        old is None

        or values(jold)
        != values(current["jinhak"])

        or values(uold)
        != values(current["uway"])
    )

    # =========================
    # 파일 저장
    # =========================

    DATA.parent.mkdir(
        exist_ok=True
    )

    DATA.write_text(

        json.dumps(
            current,
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8"
    )

    print(
        json.dumps(
            current,
            ensure_ascii=False,
            indent=2
        )
    )


# =========================
# 실행
# =========================

if __name__ == "__main__":
    main()
