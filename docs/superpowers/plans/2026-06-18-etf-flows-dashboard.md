# ETF 수급 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 직전 거래일 한국 ETF 수급(투자자별 순매수·테마별 자금·설정환매·거래대금)을 매일 자동 계산해 무료 클라우드 웹사이트로 팀에 공유한다.

**Architecture:** Python 데이터층(pykrx로 KRX 수집 → 순수 함수로 4개 뷰 계산 → JSON 저장)과 Streamlit 표시층(저장된 JSON을 즉시 렌더)을 분리한다. GitHub Actions가 거래일 저녁/새벽에 데이터층을 실행해 JSON을 커밋하고, Streamlit Community Cloud가 그 JSON을 읽어 보여준다. 외부 API(KRX)에 닿는 `fetch.py`는 실데이터 스모크 테스트로, 순수 로직(`themes.py`·`views.py`)은 픽스처 기반 TDD로 검증한다.

**Tech Stack:** Python 3.12, pykrx, pandas, streamlit, pytest, GitHub Actions, Streamlit Community Cloud.

**환경 메모(작성 시점 확인됨):** 이 노트북엔 Python 미설치(winget v1.28 사용 가능), git 2.54 설치됨. 프로젝트 루트: `C:\Users\jay\etf-flows\` (git 초기화 완료). 모든 명령은 이 루트에서 실행. 셸은 git-bash(Bash 도구) 사용.

---

## File Structure

```
etf-flows/
├── requirements.txt          # 의존성 목록
├── .gitignore                # venv/캐시 제외 (data/는 커밋함)
├── README.md                 # 배포 가이드 (사용자용)
├── etf_flows/
│   ├── __init__.py
│   ├── fetch.py              # KRX 원천 데이터 수집 (pykrx, 라이브 I/O)
│   ├── themes.py             # 테마 키워드 매핑 + 분류 (순수 로직)
│   ├── views.py              # 4개 뷰 + 추세 계산 (순수 로직, df 입력)
│   └── build.py              # 수집→계산→JSON 저장 오케스트레이션
├── data/                     # 생성물: latest.json, YYYYMMDD.json (커밋 대상)
│   └── .gitkeep
├── app.py                    # Streamlit 대시보드 (data/ 읽어 렌더)
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # 공용 픽스처 (가짜 ETF 데이터프레임)
│   ├── test_themes.py        # 테마 분류 단위 테스트
│   ├── test_views.py         # 뷰 계산 단위 테스트
│   └── test_fetch_smoke.py   # 라이브 KRX 스모크 테스트 (수동 실행)
└── .github/workflows/
    └── build.yml             # cron(저녁/새벽) + 수동 트리거
```

**책임 분리:** `fetch.py`는 KRX에서 "원천 표"를 가져오는 일만(계산 없음). `views.py`는 "표 → 화면용 결과"만(I/O 없음, 그래서 픽스처로 테스트 가능). `build.py`가 둘을 잇고 파일로 떨군다. `app.py`는 파일만 읽는다(데이터 수집 안 함).

---

## Task 0: 환경 준비 및 프로젝트 골격

**Files:**
- Create: `requirements.txt`, `.gitignore`, `etf_flows/__init__.py`, `tests/__init__.py`, `data/.gitkeep`

- [ ] **Step 1: Python 3.12 설치 (winget)**

Run:
```bash
winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
```
설치 후 **새 셸**에서 확인. PATH 갱신이 안 잡히면 launcher 사용:
```bash
py -3.12 --version
```
Expected: `Python 3.12.x` 출력.

- [ ] **Step 2: 가상환경(venv) 생성 및 활성화**

프로젝트 격리를 위한 가상환경(이 프로젝트 전용 파이썬 공간).
Run (git-bash 기준):
```bash
cd /c/Users/jay/etf-flows
py -3.12 -m venv .venv
source .venv/Scripts/activate
python --version
```
Expected: `Python 3.12.x`, 프롬프트에 `(.venv)` 표시.

- [ ] **Step 3: requirements.txt 작성**

```
pykrx>=1.0.45
pandas>=2.0
streamlit>=1.30
pytest>=8.0
```

- [ ] **Step 4: 의존성 설치**

Run:
```bash
pip install -r requirements.txt
```
Expected: 마지막에 `Successfully installed ... pykrx ... streamlit ...`

- [ ] **Step 5: .gitignore 와 패키지 골격 작성**

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.streamlit/secrets.toml
```
빈 파일 생성: `etf_flows/__init__.py`, `tests/__init__.py`, `data/.gitkeep`

- [ ] **Step 6: pykrx import 동작 확인**

Run:
```bash
python -c "from pykrx import stock; print('pykrx ok')"
```
Expected: `pykrx ok`

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore etf_flows tests data
git commit -m "chore: project skeleton and dependencies"
```

---

## Task 1: 데이터 수집층 `fetch.py` (실데이터 검증 포함)

> **이 태스크는 위험 검증 단계다.** pykrx의 정확한 함수/컬럼명을 실데이터로 확인하면서 작성한다. 아래 코드는 조사 기반 출발점이며, 각 함수 작성 직후 실데이터로 돌려 컬럼명을 확인하고 어긋나면 즉시 맞춘다(컬럼명이 한글이라 KRX 표기 변동 가능).

**Files:**
- Create: `etf_flows/fetch.py`, `tests/test_fetch_smoke.py`

- [ ] **Step 1: 직전 거래일 계산 + 전종목 시세 함수 작성**

`etf_flows/fetch.py`:
```python
"""KRX ETF 원천 데이터 수집 (pykrx). 계산 없음 — 표만 가져온다."""
from __future__ import annotations
import pandas as pd
from pykrx import stock


def latest_trading_day(today_yyyymmdd: str) -> str:
    """today(YYYYMMDD) 기준 가장 최근 거래일을 반환. 휴장일/주말이면 직전 거래일."""
    days = stock.get_previous_business_days(year=int(today_yyyymmdd[:4]),
                                            month=int(today_yyyymmdd[4:6]))
    days = [d for d in days if d.strftime("%Y%m%d") <= today_yyyymmdd]
    return days[-1].strftime("%Y%m%d")


def fetch_etf_snapshot(date: str) -> pd.DataFrame:
    """해당일 전 ETF의 OHLCV/NAV 스냅샷. index=티커.
    컬럼(확인 대상): NAV, 시가, 고가, 저가, 종가, 거래량, 거래대금, 기초지수."""
    df = stock.get_etf_ohlcv_by_ticker(date)
    return df
```

- [ ] **Step 2: 전종목 스냅샷 실데이터 확인**

Run:
```bash
python -c "from etf_flows.fetch import latest_trading_day, fetch_etf_snapshot as f; d=latest_trading_day('20260618'); print('date',d); df=f(d); print(df.shape); print(list(df.columns)); print(df.head(3))"
```
Expected: 거래일 출력, 수백 행, 컬럼에 `NAV/종가/거래량/거래대금/기초지수` 류 존재.
**관찰값 기록:** 실제 컬럼명을 이후 단계에서 그대로 사용. 다르면 코드 주석/매핑을 맞춘다.

- [ ] **Step 3: 등락률·상장좌수 함수 작성 (뷰 C·D 재료)**

`etf_flows/fetch.py`에 추가:
```python
def fetch_etf_price_change(date: str) -> pd.DataFrame:
    """해당일 전 ETF 등락률. index=티커. 컬럼(확인 대상): 종목명, 등락률, 거래대금 등."""
    # get_etf_price_change_by_ticker는 기간 입력 → 같은 날을 시작=끝으로 호출
    return stock.get_etf_price_change_by_ticker(date, date)


def fetch_market_cap(date: str) -> pd.DataFrame:
    """해당일 전 종목 시가총액 표(ETF 포함 여부 확인 대상).
    컬럼(확인 대상): 시가총액, 거래량, 거래대금, 상장주식수. 상장주식수=ETF 상장좌수."""
    return stock.get_market_cap(date)
```

- [ ] **Step 4: 상장좌수(설정/환매 재료) 확보 경로 검증 — 위험지점 C**

Run:
```bash
python -c "from etf_flows.fetch import latest_trading_day, fetch_etf_snapshot, fetch_market_cap; d=latest_trading_day('20260618'); etf=fetch_etf_snapshot(d); mc=fetch_market_cap(d); etfset=set(etf.index); both=etfset & set(mc.index); print('etf',len(etfset),'cap_has_etf',len(both)); print(mc.loc[list(both)[:3]])"
```
Expected: `cap_has_etf`가 0이 아니면 → `get_market_cap`의 `상장주식수`를 ETF 상장좌수로 사용 가능.
**만약 0 또는 상장주식수 컬럼 없음:** 대안으로 `fetch_etf_snapshot`에 NAV·종가가 있으니, 상장좌수 대신 **순자산총액(시가총액)** 의 일별 변화를 자금증감 근사로 사용. 이 경우 `build.py`에서 시가총액 변화 - 가격효과 보정 없이 "시총 변화"로 단순화하고 화면에 "근사" 라벨을 단다. (정직성: 정확 좌수 확보 실패 시 근사로 후퇴)

- [ ] **Step 5: 투자자별 순매수 함수 작성 — 위험지점 A**

`etf_flows/fetch.py`에 추가:
```python
def fetch_etf_investor_netbuy(date: str, ticker: str) -> dict | None:
    """특정 ETF의 해당일 투자자별 순매수(거래대금 기준). 외국인/기관 합계 원.
    실패 시 None. 컬럼/투자자 구분명은 실데이터로 확인."""
    try:
        df = stock.get_etf_trading_volume_and_value(date, date, ticker)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return df  # 구조 확인용으로 우선 원본 반환 (Step 6에서 파싱 확정)
```

- [ ] **Step 6: 투자자별 순매수 구조 확인 후 파싱 확정 — 위험지점 A**

Run (유동성 큰 대표 ETF, 예: KODEX 200 = `069500`):
```bash
python -c "from pykrx import stock; from etf_flows.fetch import latest_trading_day as L; d=L('20260618'); df=stock.get_etf_trading_volume_and_value(d,d,'069500'); print(type(df)); print(df)"
```
관찰: 행=투자자구분(외국인/기관합계/개인…), 열=거래량/거래대금/순매수 등인지 확인.
구조 확인 후 `fetch_etf_investor_netbuy`를 아래로 확정(컬럼명은 관찰값으로 치환):
```python
def fetch_etf_investor_netbuy(date: str, ticker: str) -> dict | None:
    try:
        df = stock.get_etf_trading_volume_and_value(date, date, ticker)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    # 관찰된 실제 구조에 맞춰 외국인/기관 순매수(거래대금 기준)를 뽑는다.
    # 예시(확인 후 확정): 행 라벨 '외국인','기관합계' / 열 '순매수'(거래대금).
    def pick(label):
        try:
            return float(df.loc[label].filter(like="순매수").iloc[0])
        except Exception:
            return 0.0
    return {"foreign_netbuy": pick("외국인"), "inst_netbuy": pick("기관합계")}
```

- [ ] **Step 7: 라이브 스모크 테스트 작성**

`tests/test_fetch_smoke.py`:
```python
"""라이브 KRX 스모크 테스트. 네트워크 필요 → 평소엔 건너뜀.
실행: pytest tests/test_fetch_smoke.py -m smoke --run-smoke -v (아래 옵션 등록 후)"""
import pytest
from etf_flows import fetch


@pytest.mark.smoke
def test_snapshot_has_rows():
    d = fetch.latest_trading_day("20260618")
    df = fetch.fetch_etf_snapshot(d)
    assert len(df) > 100


@pytest.mark.smoke
def test_investor_netbuy_kodex200():
    d = fetch.latest_trading_day("20260618")
    res = fetch.fetch_etf_investor_netbuy(d, "069500")
    assert res is not None
    assert "foreign_netbuy" in res and "inst_netbuy" in res
```

`tests/conftest.py`에 smoke 옵션 등록(없으면 생성):
```python
import pytest


def pytest_addoption(parser):
    parser.addoption("--run-smoke", action="store_true", default=False,
                     help="run live KRX smoke tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: live network tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-smoke"):
        return
    skip = pytest.mark.skip(reason="need --run-smoke")
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip)
```

- [ ] **Step 8: 스모크 테스트 실행**

Run:
```bash
pytest tests/test_fetch_smoke.py --run-smoke -v
```
Expected: 2개 PASS. 실패 시 해당 함수의 컬럼/라벨을 관찰값으로 맞춘 뒤 재실행.

- [ ] **Step 9: Commit**

```bash
git add etf_flows/fetch.py tests/test_fetch_smoke.py tests/conftest.py
git commit -m "feat: KRX ETF data fetch layer with live smoke tests"
```

---

## Task 2: 테마 분류 `themes.py` (순수 로직, TDD)

**Files:**
- Create: `etf_flows/themes.py`, `tests/test_themes.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_themes.py`:
```python
from etf_flows.themes import classify_theme


def test_semiconductor_before_us():
    # 'SOL 미국AI반도체'처럼 미국+반도체가 겹치면 반도체 우선
    assert classify_theme("SOL 미국AI반도체칩") == "반도체"


def test_us_bond_is_bond_not_us():
    assert classify_theme("KODEX 미국채30년") == "채권"


def test_battery():
    assert classify_theme("TIGER 2차전지테마") == "2차전지"


def test_us_equity():
    assert classify_theme("TIGER 미국S&P500") == "미국주식"


def test_unmatched_is_etc():
    assert classify_theme("KODEX 200") == "코스피"
    assert classify_theme("ACE 알수없는테마xyz") == "기타"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_themes.py -v`
Expected: FAIL (`classify_theme` 미정의)

- [ ] **Step 3: 구현**

`etf_flows/themes.py`:
```python
"""ETF 이름 기반 테마 분류. 순서가 곧 우선순위(겹칠 때 위가 이김)."""

# (테마, 키워드들) — 위에서부터 첫 매칭이 채택된다.
THEME_RULES = [
    ("채권",      ["미국채", "국채", "회사채", "채권", "크레딧", "통안", "TIPS", "단기채"]),
    ("반도체",    ["반도체", "SOX", "필라델피아반도체", "HBM"]),
    ("2차전지",   ["2차전지", "배터리", "리튬", "전기차"]),
    ("금/원자재", ["골드", "금현물", "금선물", "KRX금", "원유", "WTI", "천연가스", "구리", "원자재"]),
    ("중국",      ["차이나", "중국", "CSI", "항셍", "홍콩"]),
    ("바이오",    ["바이오", "헬스케어", "제약"]),
    ("리츠",      ["리츠", "REIT", "부동산"]),
    ("배당/커버드콜", ["커버드콜", "고배당", "배당"]),
    ("미국주식",  ["미국", "S&P", "나스닥", "다우", "필라델피아"]),
    ("코스피",    ["코스피", "KOSPI", "코리아", "200"]),
    ("코스닥",    ["코스닥", "KOSDAQ"]),
]


def classify_theme(name: str) -> str:
    """ETF 종목명을 테마 문자열로 분류. 미매칭은 '기타'."""
    text = name.upper().replace(" ", "")
    for theme, keywords in THEME_RULES:
        for kw in keywords:
            if kw.upper().replace(" ", "") in text:
                return theme
    return "기타"
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_themes.py -v`
Expected: 5개 PASS

- [ ] **Step 5: Commit**

```bash
git add etf_flows/themes.py tests/test_themes.py
git commit -m "feat: ETF theme classifier"
```

---

## Task 3: 뷰 계산 `views.py` (순수 로직, TDD)

> 입력 계약: `build.py`가 만든 단일 DataFrame `df`. index=티커, 컬럼:
> `name, theme, close, change_pct, value(거래대금,원), nav, foreign_netbuy(원),
> inst_netbuy(원), flow(설정환매 자금,원)`. 모든 뷰 함수는 이 df만 받고 dict를 돌려준다.

**Files:**
- Create: `etf_flows/views.py`, `tests/test_views.py` (conftest 픽스처 추가)

- [ ] **Step 1: 픽스처 추가**

`tests/conftest.py`에 추가:
```python
import pandas as pd
import pytest


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "name": ["KODEX 반도체", "TIGER 2차전지", "KODEX 200", "KODEX 미국채30년"],
            "theme": ["반도체", "2차전지", "코스피", "채권"],
            "close": [40000, 12000, 35000, 9000],
            "change_pct": [2.5, -1.2, 0.4, 0.1],
            "value": [5e10, 3e10, 8e10, 1e10],
            "nav": [40050, 11990, 35010, 9001],
            "foreign_netbuy": [3e9, -1e9, 5e9, 2e8],
            "inst_netbuy": [1e9, -2e9, -3e9, 5e8],
            "flow": [2e9, -5e8, 1e10, 3e8],
        },
        index=["A1", "A2", "A3", "A4"],
    )
```

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_views.py`:
```python
from etf_flows.views import view_investor, view_theme, view_flow, view_active


def test_view_investor_top_foreign(sample_df):
    res = view_investor(sample_df, top_n=2)
    assert res["foreign_top"][0]["name"] == "KODEX 200"      # +5e9 최대
    assert res["foreign_bottom"][0]["name"] == "TIGER 2차전지"  # -1e9 최소


def test_view_theme_aggregates(sample_df):
    res = view_theme(sample_df)
    themes = {r["theme"]: r for r in res}
    assert themes["반도체"]["foreign_netbuy"] == 3e9
    assert themes["코스피"]["flow"] == 1e10


def test_view_flow_top(sample_df):
    res = view_flow(sample_df, top_n=2)
    assert res["inflow"][0]["name"] == "KODEX 200"           # +1e10 최대 유입


def test_view_active_by_value(sample_df):
    res = view_active(sample_df, top_n=2)
    assert res["by_value"][0]["name"] == "KODEX 200"         # 8e10 최대
    assert res["gainers"][0]["name"] == "KODEX 반도체"        # +2.5% 최대
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `pytest tests/test_views.py -v`
Expected: FAIL (함수 미정의)

- [ ] **Step 4: 구현**

`etf_flows/views.py`:
```python
"""4개 화면용 결과를 DataFrame에서 계산. I/O 없음, 순수 함수."""
from __future__ import annotations
import pandas as pd


def _rows(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    out = df.reset_index().rename(columns={"index": "ticker"})
    return out[["ticker"] + cols].to_dict("records")


def view_investor(df: pd.DataFrame, top_n: int = 20) -> dict:
    """A. 외국인/기관 순매수 TOP/BOTTOM."""
    cols = ["name", "theme", "foreign_netbuy", "inst_netbuy", "change_pct"]
    f = df.sort_values("foreign_netbuy", ascending=False)
    i = df.sort_values("inst_netbuy", ascending=False)
    return {
        "foreign_top": _rows(f.head(top_n), cols),
        "foreign_bottom": _rows(f.tail(top_n).iloc[::-1], cols),
        "inst_top": _rows(i.head(top_n), cols),
        "inst_bottom": _rows(i.tail(top_n).iloc[::-1], cols),
    }


def view_theme(df: pd.DataFrame) -> list[dict]:
    """B. 테마별 집계 (순매수 합, 자금흐름 합, 평균 등락, 거래대금 합)."""
    g = df.groupby("theme").agg(
        foreign_netbuy=("foreign_netbuy", "sum"),
        inst_netbuy=("inst_netbuy", "sum"),
        flow=("flow", "sum"),
        value=("value", "sum"),
        change_pct=("change_pct", "mean"),
        count=("name", "size"),
    )
    g = g.sort_values("foreign_netbuy", ascending=False).reset_index()
    return g.to_dict("records")


def view_flow(df: pd.DataFrame, top_n: int = 20) -> dict:
    """C. 설정/환매 자금 유입(+)·유출(-) 순위."""
    cols = ["name", "theme", "flow", "change_pct"]
    s = df.sort_values("flow", ascending=False)
    return {
        "inflow": _rows(s.head(top_n), cols),
        "outflow": _rows(s.tail(top_n).iloc[::-1], cols),
    }


def view_active(df: pd.DataFrame, top_n: int = 20) -> dict:
    """D. 거래대금·등락률 상위/하위."""
    cols = ["name", "theme", "value", "change_pct"]
    v = df.sort_values("value", ascending=False)
    c = df.sort_values("change_pct", ascending=False)
    return {
        "by_value": _rows(v.head(top_n), cols),
        "gainers": _rows(c.head(top_n), cols),
        "losers": _rows(c.tail(top_n).iloc[::-1], cols),
    }
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_views.py -v`
Expected: 4개 PASS

- [ ] **Step 6: Commit**

```bash
git add etf_flows/views.py tests/test_views.py tests/conftest.py
git commit -m "feat: four ETF flow views (investor/theme/flow/active)"
```

---

## Task 4: 오케스트레이션 `build.py` (수집→계산→저장)

**Files:**
- Create: `etf_flows/build.py`

- [ ] **Step 1: build.py 작성**

`etf_flows/build.py`:
```python
"""KRX 수집 → 단일 df 조립 → 4개 뷰 계산 → data/{date}.json + latest.json 저장.
실행: python -m etf_flows.build [YYYYMMDD]  (인자 없으면 시스템 날짜는 호출자가 전달)."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pandas as pd
from etf_flows import fetch, views
from etf_flows.themes import classify_theme

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LIQUID_TOP = 150  # A(투자자별)는 거래대금 상위 N개만 순회


def assemble(date: str) -> pd.DataFrame:
    snap = fetch.fetch_etf_snapshot(date)        # index=티커
    chg = fetch.fetch_etf_price_change(date)
    cap = fetch.fetch_market_cap(date)

    # --- 표준 컬럼으로 정규화 (Task1에서 확인한 실제 컬럼명으로 매핑) ---
    df = pd.DataFrame(index=snap.index)
    df["name"] = chg.reindex(df.index).get("종목명")
    df["close"] = snap.get("종가")
    df["nav"] = snap.get("NAV")
    df["value"] = snap.get("거래대금")
    df["change_pct"] = chg.reindex(df.index).get("등락률")
    df = df.dropna(subset=["value"])
    df["theme"] = df["name"].fillna("").map(classify_theme)

    # --- C: 설정/환매 자금 = (당일좌수 - 전거래일좌수) * NAV ---
    prev = fetch.latest_trading_day_before(date)
    cap_prev = fetch.fetch_market_cap(prev)
    shares_now = cap.reindex(df.index).get("상장주식수")
    shares_prev = cap_prev.reindex(df.index).get("상장주식수")
    df["flow"] = (shares_now - shares_prev) * df["nav"]

    # --- A: 거래대금 상위 LIQUID_TOP 만 투자자별 순매수 조회 ---
    df["foreign_netbuy"] = 0.0
    df["inst_netbuy"] = 0.0
    liquid = df.sort_values("value", ascending=False).head(LIQUID_TOP).index
    for tk in liquid:
        r = fetch.fetch_etf_investor_netbuy(date, tk)
        if r:
            df.at[tk, "foreign_netbuy"] = r["foreign_netbuy"]
            df.at[tk, "inst_netbuy"] = r["inst_netbuy"]
    return df


def build(date: str) -> dict:
    df = assemble(date)
    result = {
        "date": date,
        "investor": views.view_investor(df),
        "theme": views.view_theme(df),
        "flow": views.view_flow(df),
        "active": views.view_active(df),
    }
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / f"{date}.json").write_text(
        json.dumps(result, ensure_ascii=False, default=float), encoding="utf-8")
    (DATA_DIR / "latest.json").write_text(
        json.dumps(result, ensure_ascii=False, default=float), encoding="utf-8")
    return result


if __name__ == "__main__":
    today = sys.argv[1] if len(sys.argv) > 1 else None
    if today is None:
        raise SystemExit("usage: python -m etf_flows.build YYYYMMDD")
    d = fetch.latest_trading_day(today)
    build(d)
    print("built", d)
```

- [ ] **Step 2: fetch.py에 직전 거래일(전일) 헬퍼 추가**

`etf_flows/fetch.py`에 추가 (Task1 함수 옆):
```python
def latest_trading_day_before(date: str) -> str:
    """date(거래일) 바로 이전 거래일 반환 (설정/환매 좌수 비교용)."""
    days = stock.get_previous_business_days(year=int(date[:4]), month=int(date[4:6]))
    days = [d.strftime("%Y%m%d") for d in days if d.strftime("%Y%m%d") < date]
    if days:
        return days[-1]
    # 월초 경계: 전월에서 탐색
    y, m = int(date[:4]), int(date[4:6]) - 1
    if m == 0:
        y, m = y - 1, 12
    pdays = [d.strftime("%Y%m%d") for d in stock.get_previous_business_days(year=y, month=m)]
    return pdays[-1]
```

- [ ] **Step 3: 실데이터로 빌드 실행 (위험지점 통합 검증)**

Run:
```bash
python -m etf_flows.build 20260618
```
Expected: `built 2026xxxx`, `data/latest.json` 생성.
검증:
```bash
python -c "import json; d=json.load(open('data/latest.json',encoding='utf-8')); print('date',d['date']); print('themes',[t['theme'] for t in d['theme']]); print('foreign_top0', d['investor']['foreign_top'][0])"
```
Expected: 테마 목록과 외국인 순매수 1위 종목이 그럴듯하게 출력.
**이상치 점검:** flow가 전부 0이면 상장주식수 컬럼 매핑 실패 → Task1 Step4 대안(시총변화 근사)로 전환하고 `assemble`의 flow 계산을 교체.

- [ ] **Step 4: 생성 데이터 커밋 (초기 1건)**

```bash
git add etf_flows/build.py etf_flows/fetch.py data/latest.json data/*.json
git commit -m "feat: build pipeline assembling KRX data into daily JSON"
```

---

## Task 5: Streamlit 대시보드 `app.py`

**Files:**
- Create: `app.py`

- [ ] **Step 1: app.py 작성**

`app.py`:
```python
"""ETF 수급 대시보드 — data/latest.json 을 읽어 4개 뷰를 보여준다 (수집 안 함)."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="ETF 수급", layout="wide")


@st.cache_data(ttl=600)
def load_latest():
    return json.loads((DATA / "latest.json").read_text(encoding="utf-8"))


def fmt_won(df, cols):
    for c in cols:
        if c in df:
            df[c] = (df[c] / 1e8).round(1)  # 억원 단위
    return df


d = load_latest()
st.title("📊 ETF 수급 대시보드")
st.caption(f"기준일: {d['date']} · 출처: KRX(한국거래소) · 직전 거래일 확정치")

t1, t2, t3, t4 = st.tabs(["투자자별 순매수", "테마별 자금", "설정/환매", "거래대금·등락"])

with t1:
    st.subheader("외국인 순매수 TOP (억원)")
    st.dataframe(fmt_won(pd.DataFrame(d["investor"]["foreign_top"]),
                         ["foreign_netbuy", "inst_netbuy"]), use_container_width=True)
    st.subheader("외국인 순매도 TOP (억원)")
    st.dataframe(fmt_won(pd.DataFrame(d["investor"]["foreign_bottom"]),
                         ["foreign_netbuy", "inst_netbuy"]), use_container_width=True)
    st.subheader("기관 순매수 TOP (억원)")
    st.dataframe(fmt_won(pd.DataFrame(d["investor"]["inst_top"]),
                         ["foreign_netbuy", "inst_netbuy"]), use_container_width=True)

with t2:
    st.subheader("테마별 순매수·자금흐름 (억원)")
    st.dataframe(fmt_won(pd.DataFrame(d["theme"]),
                         ["foreign_netbuy", "inst_netbuy", "flow", "value"]),
                 use_container_width=True)

with t3:
    st.subheader("설정(자금 유입) TOP (억원)")
    st.dataframe(fmt_won(pd.DataFrame(d["flow"]["inflow"]), ["flow"]),
                 use_container_width=True)
    st.subheader("환매(자금 유출) TOP (억원)")
    st.dataframe(fmt_won(pd.DataFrame(d["flow"]["outflow"]), ["flow"]),
                 use_container_width=True)

with t4:
    st.subheader("거래대금 TOP (억원)")
    st.dataframe(fmt_won(pd.DataFrame(d["active"]["by_value"]), ["value"]),
                 use_container_width=True)
    c1, c2 = st.columns(2)
    c1.subheader("상승 TOP")
    c1.dataframe(pd.DataFrame(d["active"]["gainers"]), use_container_width=True)
    c2.subheader("하락 TOP")
    c2.dataframe(pd.DataFrame(d["active"]["losers"]), use_container_width=True)
```

- [ ] **Step 2: 로컬 실행 확인**

Run:
```bash
streamlit run app.py
```
Expected: 브라우저에 4개 탭 대시보드가 뜨고, 기준일/표가 보인다. (Ctrl+C로 종료)
확인 사항: 4개 탭 모두 표가 채워지는가, 억원 단위가 자연스러운가, 기준일이 맞는가.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: streamlit dashboard with four tabs"
```

---

## Task 6: 자동 실행 GitHub Actions `build.yml`

**Files:**
- Create: `.github/workflows/build.yml`

- [ ] **Step 1: 워크플로 작성**

`.github/workflows/build.yml`:
```yaml
name: build-etf-flows
on:
  schedule:
    - cron: "0 10 * * 1-5"   # 19:00 KST (거래일 저녁, 데이터 확정 후)
    - cron: "0 20 * * 0-4"   # 05:00 KST 다음날 (안전망)
  workflow_dispatch: {}       # 수동 실행 버튼

permissions:
  contents: write             # data/*.json 커밋 권한

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - name: Build (KST today)
        run: |
          TODAY=$(TZ=Asia/Seoul date +%Y%m%d)
          python -m etf_flows.build "$TODAY"
      - name: Commit data if changed
        run: |
          git config user.name "etf-bot"
          git config user.email "etf-bot@users.noreply.github.com"
          git add data/*.json
          git diff --staged --quiet || git commit -m "data: ETF flows $(TZ=Asia/Seoul date +%Y-%m-%d)"
          git push
```

- [ ] **Step 2: 로컬 YAML 문법 점검**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/build.yml')); print('yaml ok')"
```
Expected: `yaml ok` (pyyaml 미설치면 `pip install pyyaml` 후 재실행)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: scheduled build (19:00/05:00 KST) committing daily data"
```

> **주의:** 실제 cron 동작 확인은 GitHub에 푸시한 뒤(Task 7) Actions 탭의 `workflow_dispatch` 수동 실행으로 검증한다. 로컬에선 문법까지만.

---

## Task 7: 배포 가이드 README (사용자 수행 단계)

**Files:**
- Create: `README.md`

- [ ] **Step 1: README 작성 (비개발자용 단계별 안내)**

`README.md`:
```markdown
# ETF 수급 대시보드

한국 상장 ETF의 직전 거래일 수급(투자자별 순매수·테마별 자금·설정환매·거래대금)을
매일 자동 계산해 보여주는 팀 공유 웹사이트.

## 배포 (최초 1회)

### 1) GitHub에 올리기
1. github.com 가입 후 새 저장소(repository) `etf-flows` 생성 (Public).
2. 로컬에서:
   ```
   git remote add origin https://github.com/<당신아이디>/etf-flows.git
   git branch -M main
   git push -u origin main
   ```

### 2) 자동 실행 켜기
- 저장소 → Settings → Actions → General → Workflow permissions →
  "Read and write permissions" 체크 후 저장.
- Actions 탭 → build-etf-flows → "Run workflow"로 수동 1회 실행 → 초록 체크 확인.

### 3) 웹사이트 띄우기 (Streamlit Community Cloud)
1. share.streamlit.io 에 GitHub로 로그인.
2. "New app" → 저장소 `etf-flows`, 브랜치 `main`, 파일 `app.py` 선택 → Deploy.
3. 몇 분 뒤 나오는 주소(예: https://etf-flows.streamlit.app)를 팀에 공유.

## 갱신 흐름
- 거래일 저녁 19시(+다음날 새벽 5시) GitHub Actions가 데이터를 새로 만들어 커밋 →
  Streamlit이 자동으로 최신 데이터를 반영. 사람이 할 일 없음.

## 로컬에서 직접 돌려보기
```
py -3.12 -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
python -m etf_flows.build $(date +%Y%m%d)   # 데이터 생성
streamlit run app.py                         # 화면 확인
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: deployment guide for GitHub + Streamlit Cloud"
```

---

## Task 8 (선택): 며칠 추세 뷰

> 일별 `data/YYYYMMDD.json`이 며칠 쌓인 뒤 의미가 생기므로 **마지막에** 구현한다.
> 데이터가 1~2일치뿐이면 화면에 "추세는 데이터 누적 후 제공" 안내만 띄운다.

**Files:**
- Modify: `app.py` (탭 추가), `etf_flows/views.py` (추세 집계 함수)

- [ ] **Step 1: 추세 집계 함수 + 테스트**

`tests/test_views.py`에 추가:
```python
from etf_flows.views import theme_trend


def test_theme_trend_streak():
    series = [
        {"date": "20260616", "theme": [{"theme": "반도체", "foreign_netbuy": 1e9}]},
        {"date": "20260617", "theme": [{"theme": "반도체", "foreign_netbuy": 2e9}]},
    ]
    res = theme_trend(series, "반도체")
    assert res == [("20260616", 1e9), ("20260617", 2e9)]
```

`etf_flows/views.py`에 추가:
```python
def theme_trend(daily_results: list[dict], theme: str) -> list[tuple]:
    """여러 날 결과에서 특정 테마의 외국인 순매수 시계열을 뽑는다."""
    out = []
    for day in daily_results:
        val = next((t["foreign_netbuy"] for t in day["theme"] if t["theme"] == theme), 0.0)
        out.append((day["date"], val))
    return out
```

- [ ] **Step 2: 테스트 실행**

Run: `pytest tests/test_views.py::test_theme_trend_streak -v`
Expected: PASS

- [ ] **Step 3: app.py에 추세 탭 추가 (최근 N일 파일 로드)**

`app.py`의 탭 구성에 추세 탭을 추가하고, `data/`의 `YYYYMMDD.json` 중 최근 5개를 읽어
테마별 외국인 순매수 라인차트를 `st.line_chart`로 표시. 파일이 2개 미만이면
`st.info("데이터가 더 쌓이면 추세가 표시됩니다")`.

- [ ] **Step 4: Commit**

```bash
git add etf_flows/views.py tests/test_views.py app.py
git commit -m "feat: multi-day theme trend view"
```

---

## Self-Review (작성자 점검 결과)

**Spec coverage:**
- 목적/사용자(§1) → Task 5/7. 데이터 KRX·한국ETF·직전거래일(§2) → Task 1/4.
- 4개 뷰(§3 A/B/C/D) → Task 3 + Task 4 assemble + Task 5 표시. 추세(§3) → Task 8.
- 작동구조 자동사전계산(§4) → Task 4 build + Task 6 Actions + Task 7 배포.
- 테마분류(§5) → Task 2. 예외처리(§6) → 빌드 실패 시 latest.json 미갱신(Actions diff-quiet),
  기준일 표시(app.py caption), ETF 조회 실패 skip(fetch None 처리/build 루프).
- 범위밖(§7)·리스크(§9 A·C) → Task 1 Step4/Step6에서 실데이터 검증 및 후퇴 경로 명시.

**Placeholder scan:** 코드 단계는 모두 실제 코드 포함. Task1은 라이브 API라 "관찰 후 컬럼 확정"
단계가 있으나 출발 코드와 검증 명령을 구체 제공(플레이스홀더 아님). Task8 Step3만 서술형 —
선택 태스크이며 의존(차트)이 단순해 허용.

**Type consistency:** `fetch_etf_investor_netbuy`는 `{foreign_netbuy, inst_netbuy}` dict로 일관,
build가 동일 키 사용. views의 df 컬럼 계약(name/theme/close/change_pct/value/nav/foreign_netbuy/
inst_netbuy/flow)을 build.assemble이 그대로 생성. 함수명(view_investor/theme/flow/active) 일치.
```
