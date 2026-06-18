"""4개 화면용 결과를 DataFrame에서 계산. I/O 없음, 순수 함수.

입력 계약: index=티커, 컬럼 name, theme, close, change_pct, value(거래대금,원),
nav, foreign_netbuy(원), inst_netbuy(원), flow(설정환매 자금,원)."""
from __future__ import annotations
import pandas as pd


def _rows(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    out = df.reset_index().rename(columns={"index": "ticker"})
    keep = ["ticker"] + [c for c in cols if c in out.columns]
    return out[keep].to_dict("records")


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
    """B. 테마별 집계 (순매수 합, 자금흐름 합, 평균 등락, 거래대금 합).
    각 테마에 그 안에 묶인 ETF 목록(members)을 외국인 순매수 순으로 포함."""
    g = df.groupby("theme").agg(
        foreign_netbuy=("foreign_netbuy", "sum"),
        inst_netbuy=("inst_netbuy", "sum"),
        flow=("flow", "sum"),
        value=("value", "sum"),
        change_pct=("change_pct", "mean"),
        count=("name", "size"),
    )
    g = g.sort_values("foreign_netbuy", ascending=False).reset_index()
    mcols = ["name", "foreign_netbuy", "inst_netbuy", "value", "change_pct"]
    records = []
    for rec in g.to_dict("records"):
        sub = df[df["theme"] == rec["theme"]].sort_values("foreign_netbuy", ascending=False)
        rec["members"] = _rows(sub, mcols)
        records.append(rec)
    return records


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


def theme_trend(daily_results: list[dict], theme: str) -> list[tuple]:
    """여러 날 결과에서 특정 테마의 외국인 순매수 시계열을 뽑는다."""
    out = []
    for day in daily_results:
        val = next((t["foreign_netbuy"] for t in day["theme"] if t["theme"] == theme), 0.0)
        out.append((day["date"], val))
    return out
