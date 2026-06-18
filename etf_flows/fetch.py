"""ETF 원천 데이터 수집 (네이버 금융). 계산 없음 — 표만 가져온다.

왜 네이버인가: KRX 대량조회(및 pykrx)는 해외 서버(GitHub Actions·Streamlit Cloud)에서
빈 응답을 주지만, 네이버 금융 API는 국내·해외 어디서나 열린다. 따라서 클라우드 배포에
견고한 유일한 소스다.

두 엔드포인트:
- etfItemList: 전 ETF 1회 호출 → 종목코드·이름·순자산(marketSum)·NAV (유니버스/테마/자금)
- /api/stock/{code}/trend: 종목별 최근 10거래일 → 투자자별 순매수·종가·등락·거래량 (뷰 A·D·추세)
"""
from __future__ import annotations
import requests

_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"}
_TIMEOUT = 15

ETF_LIST_URL = "https://finance.naver.com/api/sise/etfItemList.nhn"
TREND_URL = "https://m.stock.naver.com/api/stock/{code}/trend"

# 네이버 등락 방향 코드 → 부호 (1 상한, 2 상승, 3 보합, 4 하한, 5 하락)
_SIGN = {"1": 1, "2": 1, "3": 0, "4": -1, "5": -1}


def _num(s) -> float:
    """'+12,289' / '-427,399' / '22.64%' / '16,301,201' → float. 빈값은 0."""
    if s is None:
        return 0.0
    t = str(s).replace(",", "").replace("%", "").replace("+", "").strip()
    if t in ("", "-"):
        return 0.0
    try:
        return float(t)
    except ValueError:
        return 0.0


def fetch_universe() -> list[dict]:
    """전 ETF 목록(1회 호출). 각 항목: code, name, aum(순자산, 원자료 단위), nav."""
    r = requests.get(ETF_LIST_URL, headers=_HDR, timeout=_TIMEOUT)
    r.raise_for_status()
    items = r.json().get("result", {}).get("etfItemList", [])
    out = []
    for it in items:
        out.append({
            "code": it["itemcode"],
            "name": it["itemname"],
            "aum": _num(it.get("marketSum")),
            "nav": _num(it.get("nav")),
        })
    return out


def fetch_trend(code: str) -> list[dict] | None:
    """종목의 최근 거래일별 투자자/시세 행 목록(최신순). 실패 시 None.
    각 행: date, foreign_qty, organ_qty, indiv_qty, close, change_pct, volume."""
    try:
        r = requests.get(TREND_URL.format(code=code), headers=_HDR, timeout=_TIMEOUT)
        r.raise_for_status()
        rows = r.json()
    except Exception:
        return None
    if not rows:
        return None
    out = []
    for row in rows:
        close = _num(row.get("closePrice"))
        chg_abs = _num(row.get("compareToPreviousClosePrice"))
        sign = _SIGN.get(str(row.get("compareToPreviousPrice", {}).get("code")), 0)
        change = sign * chg_abs
        prev = close - change
        change_pct = (change / prev * 100) if prev else 0.0
        out.append({
            "date": row.get("bizdate"),
            "foreign_qty": _num(row.get("foreignerPureBuyQuant")),  # _num이 음수 부호 보존
            "organ_qty": _num(row.get("organPureBuyQuant")),
            "indiv_qty": _num(row.get("individualPureBuyQuant")),
            "close": close,
            "change_pct": round(change_pct, 2),
            "volume": _num(row.get("accumulatedTradingVolume")),
        })
    return out


def latest_trend_row(code: str) -> dict | None:
    """가장 최근 거래일의 투자자/시세 행. 실패 시 None."""
    rows = fetch_trend(code)
    return rows[0] if rows else None
