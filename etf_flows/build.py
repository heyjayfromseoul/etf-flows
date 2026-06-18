"""수집 → 단일 df 조립 → 4개 뷰 계산 → data/{date}.json + latest.json 저장.

실행: python -m etf_flows.build [YYYYMMDD]
  - 인자는 '기준 오늘' (없으면 시스템 날짜). 실제 기준일은 네이버가 주는 최신 거래일.

설정/환매 자금(뷰 C)은 표준 추정식으로 계산한다:
    flow_t = AUM_t − AUM_{t-1} × (1 + 당일수익률)
  즉 '순자산 증가분 중 가격상승으로 설명되지 않는 부분'을 설정/환매로 추정.
  전일 AUM은 직전 실행이 저장한 data 파일에서 읽는다(첫 실행엔 0).
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
from etf_flows import fetch, views
from etf_flows.themes import classify_theme

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TOP_N = 250            # 투자자별 조회 대상 (순자산 상위 N개 = 의미있는 유동 ETF)
MAX_WORKERS = 8


def _prior_aum(before_date: str) -> dict:
    """before_date 이전 가장 최신 data 파일의 종목별 AUM(억원) 맵. 없으면 빈 dict."""
    best = None
    for f in sorted(DATA_DIR.glob("20*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("date") and d["date"] < before_date and d.get("aum_by_code"):
            best = d
    return best.get("aum_by_code", {}) if best else {}


def assemble(top_n: int = TOP_N) -> pd.DataFrame:
    """순자산 상위 top_n ETF의 당일 수급/시세를 단일 df로 조립."""
    uni = [u for u in fetch.fetch_universe() if u["aum"] > 0]
    uni.sort(key=lambda u: u["aum"], reverse=True)
    target = uni[:top_n]

    def grab(u):
        return u, fetch.latest_trend_row(u["code"])

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(grab, target))

    rows = [(u, r) for u, r in results if r]
    if not rows:
        raise RuntimeError("no trend data fetched")
    # 기준일 = 가장 많은 종목이 공유하는 최신 거래일 (휴장/미거래 종목 배제)
    ref_date = Counter(r["date"] for _, r in rows).most_common(1)[0][0]

    recs = []
    for u, r in rows:
        if r["date"] != ref_date:
            continue
        close = r["close"]
        recs.append({
            "ticker": u["code"],
            "name": u["name"],
            "theme": classify_theme(u["name"]),
            "close": close,
            "change_pct": r["change_pct"],
            "value": r["volume"] * close,            # 거래대금(원)
            "nav": u["nav"],
            "foreign_netbuy": r["foreign_qty"] * close,  # 순매수 금액(원)
            "inst_netbuy": r["organ_qty"] * close,
            "aum": u["aum"],                          # 순자산총액(억원)
        })
    df = pd.DataFrame(recs).set_index("ticker")
    df.attrs["date"] = ref_date
    return df


def build(today: str | None = None) -> dict:
    df = assemble()
    date = df.attrs["date"]

    # --- 뷰 C: 설정/환매 자금 추정 ---
    prior = _prior_aum(date)
    ret = df["change_pct"] / 100.0
    aum_won = df["aum"] * 1e8
    prior_won = pd.Series([float(prior.get(t, 0.0)) for t in df.index],
                          index=df.index) * 1e8
    has_prior = prior_won > 0
    df["flow"] = (aum_won - prior_won * (1 + ret)).where(has_prior, 0.0)

    result = {
        "date": date,
        "source": "Naver Finance",
        "universe_size": int(len(df)),
        "flow_available": bool(has_prior.any()),
        "investor": views.view_investor(df),
        "theme": views.view_theme(df),
        "flow": views.view_flow(df),
        "active": views.view_active(df),
        "aum_by_code": {t: float(df.at[t, "aum"]) for t in df.index},
    }

    DATA_DIR.mkdir(exist_ok=True)
    payload = json.dumps(result, ensure_ascii=False, default=float)
    (DATA_DIR / f"{date}.json").write_text(payload, encoding="utf-8")
    (DATA_DIR / "latest.json").write_text(payload, encoding="utf-8")
    return result


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    r = build(arg)
    print(f"built {r['date']} | {r['universe_size']} ETFs | flow={'on' if r['flow_available'] else 'off(첫 실행)'}")
