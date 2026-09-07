import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# =========================
# 기본 설정
# =========================

JINHAK_URL = (
    "https://addon.jinhakapply.com/"
    "RatioV1/RatioH/Ratio10810661.html"
)

UWAY_URL = (
    "https://ratio.uwayapply.com/"
    "Sl5KQzphYCZNOFdKZiUmOiZKN2ZUZg=="
)

KST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "data.json"
ARTIFACTS = ROOT / "artifacts"


# =========================
# 진학어플라이
# =========================

JINHAK_TARGET = "계약학과 채용조건형 특별전형"

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
# 유웨이
# =========================

UWAY_TARGET = "(충남형)리안헤어뷰티아트학과 미창조(주)리안헤어"


# =========================
# 공통 함수
# =========================

def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_session():
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )

    return session


def fetch_html(session, url):
    print(f"페이지 요청: {url}")

    response = session.get(
        url,
        timeout=60,
        allow_redirects=True,
    )

    print(f"HTTP 상태코드: {response.status_code}")
    print(f"최종 URL: {response.url}")
    print(f"응답 길이: {len(response.text)}")

    response.raise_for_status()

    return response.text


# =========================
# 진학어플라이
# =========================

def jinhak(session):

    print("")
    print("===== 진학어플라이 =====")

    html = fetch_html(
        session,
        JINHAK_URL
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    page_text = norm(
        soup.get_text(" ", strip=True)
    )

    # 보안 페이지인지 확인
    security_words = [
        "사람인지 확인",
        "안전한 접속 확인",
        "접속 환경을 확인하고 있습니다",
        "잠시만 기다리십시오",
    ]

    security_found = [
        word
        for word in security_words
        if word in page_text
    ]

    if security_found:

        print(
            "진학어플라이 보안 페이지가 "
            "응답되었습니다."
        )

        raise RuntimeError(
            "진학어플라이가 GitHub Actions의 "
            "HTTP 요청에 보안 확인 페이지를 반환했습니다: "
            + ", ".join(security_found)
        )

    # 대상 전형 확인
    if JINHAK_TARGET not in page_text:

        raise RuntimeError(
            "진학어플라이 페이지에서 "
            f"'{JINHAK_TARGET}'을 찾지 못했습니다."
        )

    rows = []

    # 모든 table을 검사
    for table in soup.find_all("table"):

        table_text = norm(
            table.get_text(" ", strip=True)
        )

        # 계약학과 표가 아닌 경우 건너뜀
        if JINHAK_TARGET not in table_text:

            # 표 안에 모집단위 이름이 있는 경우도 허용
            if not any(
                name in table_text
                for name in JINHAK_NAMES
            ):
                continue

        for tr in table.find_all("tr"):

            cells = [
                norm(td.get_text(" ", strip=True))
                for td in tr.find_all(
                    ["th", "td"]
                )
            ]

            if len(cells) < 4:
                continue

            name = cells[0]

            if name not in JINHAK_NAMES:
                continue

            rows.append(
                {
                    "name": name,
                    "recruit": cells[1],
                    "applicants": cells[2],
                    "ratio": cells[3],
                }
            )

    # 혹시 table 구조가 특이한 경우 전체 tr 검색
    if len(rows) < len(JINHAK_NAMES):

        print(
            "표 단위 검색에서 일부 항목이 없어 "
            "전체 행을 다시 검색합니다."
        )

        rows = []

        for tr in soup.find_all("tr"):

            cells = [
                norm(td.get_text(" ", strip=True))
                for td in tr.find_all(
                    ["th", "td"]
                )
            ]

            if len(cells) < 4:
                continue

            if cells[0] in JINHAK_NAMES:

                rows.append(
                    {
                        "name": cells[0],
                        "recruit": cells[1],
                        "applicants": cells[2],
                        "ratio": cells[3],
                    }
                )

    # 중복 제거
    unique = {}

    for row in rows:
        unique[row["name"]] = row

    rows = list(unique.values())

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
            "진학어플라이에서 다음 모집단위를 "
            "찾지 못했습니다: "
            + ", ".join(missing)
        )

    # 원하는 순서대로 정렬
    rows.sort(
        key=lambda row:
        JINHAK_NAMES.index(row["name"])
    )

    print(
        f"진학어플라이 {len(rows)}개 항목 수집 완료"
    )

    for row in rows:
        print(
            f"{row['name']} | "
            f"{row['recruit']} | "
            f"{row['applicants']} | "
            f"{row['ratio']}"
        )

    return rows


# =========================
# 유웨이
# =========================

def uway(session):

    print("")
    print("===== 유웨이 =====")

    html = fetch_html(
        session,
        UWAY_URL
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    page_text = norm(
        soup.get_text(" ", strip=True)
    )

    if UWAY_TARGET not in page_text:

        raise RuntimeError(
            "유웨이 페이지에서 "
            f"'{UWAY_TARGET}'을 찾지 못했습니다."
        )

    for tr in soup.find_all("tr"):

        cells = [
            norm(td.get_text(" ", strip=True))
            for td in tr.find_all(
                ["th", "td"]
            )
        ]

        if UWAY_TARGET not in cells:
            continue

        if len(cells) >= 6:

            result = {
                "name": cells[1],
                "recruit": cells[3],
                "applicants": cells[4],
                "ratio": cells[5],
            }

            print(
                "유웨이 데이터 수집 완료:"
            )

            print(result)

            return result

    raise RuntimeError(
        "유웨이 리안헤어 항목을 찾았지만 "
        "필요한 데이터 열을 찾지 못했습니다."
    )


# =========================
# 메인
# =========================

def main():

    ARTIFACTS.mkdir(
        exist_ok=True
    )

    session = get_session()

    try:

        # 진학어플라이
        j = jinhak(session)

        # 유웨이
        u = uway(session)

    except Exception as error:

        print("")
        print("===== 스크래핑 실패 =====")
        print(str(error))

        # 실패한 HTML 저장
        try:

            debug_file = (
                ARTIFACTS
                / "failure.txt"
            )

            debug_file.write_text(
                str(error),
                encoding="utf-8"
            )

            print(
                "실패 내용을 "
                f"{debug_file}에 저장했습니다."
            )

        except Exception:
            pass

        raise

    # =========================
    # 현재 데이터
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
                "note": JINHAK_TARGET,
            },

            {
                "id": "uway",
                "label": "유웨이",
                "url": UWAY_URL,
                "note": UWAY_TARGET,
            },
        ],

        "jinhak": j,

        "uway": [
            u
        ],
    }

    # =========================
    # 기존 데이터
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
    # 변경 여부
    # =========================

    for row in current["jinhak"]:

        old_row = next(
            (
                item
                for item in jold
                if item.get("name")
                == row.get("name")
            ),
            None,
        )

        row["changed"] = bool(
            old_row
            and {
                k: v
                for k, v in old_row.items()
                if k != "changed"
            }
            != {
                k: v
                for k, v in row.items()
                if k != "changed"
            }
        )

    for row in current["uway"]:

        old_row = next(
            (
                item
                for item in uold
                if item.get("name")
                == row.get("name")
            ),
            None,
        )

        row["changed"] = bool(
            old_row
            and {
                k: v
                for k, v in old_row.items()
                if k != "changed"
            }
            != {
                k: v
                for k, v in row.items()
                if k != "changed"
            }
        )

    def values(rows):

        return [
            {
                k: v
                for k, v in row.items()
                if k != "changed"
            }
            for row in rows
        ]

    current["changed"] = (
        old is None
        or values(jold)
        != values(current["jinhak"])
        or values(uold)
        != values(current["uway"])
    )

    # =========================
    # 저장
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

    print("")
    print("===== 최종 데이터 =====")

    print(
        json.dumps(
            current,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
