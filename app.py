"""ETF 수급 대시보드 — data/ 의 JSON을 읽어 4개 뷰 + 추세를 보여준다 (수집 안 함)."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="ETF 수급 대시보드", layout="wide", page_icon="📊")

# 표시용 한글 헤더 / 억원 환산 대상
MONEY_COLS = {"foreign_netbuy", "inst_netbuy", "value", "flow", "aum"}
LABELS = {
    "ticker": "코드", "name": "종목명", "theme": "테마",
    "foreign_netbuy": "외국인순매수(억)", "inst_netbuy": "기관순매수(억)",
    "change_pct": "등락률(%)", "value": "거래대금(억)",
    "flow": "추정자금(억)", "count": "종목수",
}


@st.cache_data(ttl=600)
def load_latest():
    return json.loads((DATA / "latest.json").read_text(encoding="utf-8"))


@st.cache_data(ttl=600)
def load_history():
    days = []
    for f in sorted(DATA.glob("20*.json")):
        try:
            days.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return days


def show(records, cols, sort_hint=None):
    """list[dict] → 억원 환산·한글 헤더로 표 출력."""
    if not records:
        st.info("데이터 없음")
        return
    df = pd.DataFrame(records)
    df = df[[c for c in cols if c in df.columns]].copy()
    for c in df.columns:
        if c in MONEY_COLS:
            df[c] = (df[c] / 1e8).round(1)
        elif c == "change_pct":
            df[c] = df[c].round(2)
    df = df.rename(columns=LABELS)
    st.dataframe(df, width="stretch", hide_index=True)


d = load_latest()
st.title("📊 ETF 수급 대시보드")
flow_note = "" if d.get("flow_available") else " · 설정/환매는 전일 데이터 누적 후 표시"
st.caption(f"기준일: **{d['date']}** · 출처: {d.get('source','Naver')} · "
           f"순자산 상위 {d.get('universe_size','?')}개 · 직전 거래일 확정치{flow_note}")

t1, t2, t3, t4, t5 = st.tabs(
    ["① 투자자별 순매수", "② 테마별 자금", "③ 설정/환매", "④ 거래대금·등락", "⑤ 추세"])

with t1:
    inv = d["investor"]
    cols = ["name", "theme", "foreign_netbuy", "inst_netbuy", "change_pct"]
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🟦 외국인 순매수 TOP")
        show(inv["foreign_top"], cols)
        st.subheader("🟦 기관 순매수 TOP")
        show(inv["inst_top"], cols)
    with c2:
        st.subheader("🟥 외국인 순매도 TOP")
        show(inv["foreign_bottom"], cols)
        st.subheader("🟥 기관 순매도 TOP")
        show(inv["inst_bottom"], cols)

with t2:
    st.subheader("테마별 수급·자금 (외국인 순매수 순)")
    show(d["theme"], ["theme", "foreign_netbuy", "inst_netbuy", "flow", "value",
                      "change_pct", "count"])
    st.caption("거래대금/순매수 합계와 평균 등락률. 테마는 ETF '이름' 키워드로 분류. "
               "'기타'는 분류 키워드에 안 걸린 종목 묶음.")
    st.markdown("##### 🔍 테마 안에 어떤 ETF가 묶였나 (펼쳐보기)")
    for rec in d["theme"]:
        members = rec.get("members", [])
        label = f"{rec['theme']} · {int(rec.get('count', len(members)))}종목 · " \
                f"외국인 {rec['foreign_netbuy']/1e8:,.0f}억"
        with st.expander(label):
            show(members, ["name", "foreign_netbuy", "inst_netbuy", "value", "change_pct"])

with t3:
    if not d.get("flow_available"):
        st.info("설정/환매(자금 유입·유출) 추정은 **전일 데이터가 쌓인 뒤**부터 표시됩니다. "
                "내일부터 정상 표시돼요.")
    else:
        st.caption("추정식: 자금 = 순자산_당일 − 순자산_전일 × (1 + 당일수익률). "
                   "가격으로 설명 안 되는 순자산 증감 = 설정/환매로 추정.")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🟦 자금 유입(설정) TOP")
            show(d["flow"]["inflow"], ["name", "theme", "flow", "change_pct"])
        with c2:
            st.subheader("🟥 자금 유출(환매) TOP")
            show(d["flow"]["outflow"], ["name", "theme", "flow", "change_pct"])

with t4:
    st.subheader("거래대금 TOP")
    show(d["active"]["by_value"], ["name", "theme", "value", "change_pct"])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🟦 상승률 TOP")
        show(d["active"]["gainers"], ["name", "theme", "change_pct", "value"])
    with c2:
        st.subheader("🟥 하락률 TOP")
        show(d["active"]["losers"], ["name", "theme", "change_pct", "value"])

with t5:
    hist = load_history()
    if len(hist) < 2:
        st.info(f"추세는 데이터가 2거래일 이상 쌓이면 표시됩니다. (현재 {len(hist)}일)")
    else:
        st.subheader("테마별 외국인 순매수 추이 (억원)")
        themes = sorted({t["theme"] for day in hist for t in day["theme"]})
        pick = st.multiselect("테마 선택", themes,
                              default=[t for t in ["반도체", "미국주식", "2차전지"] if t in themes])
        series = {}
        for day in hist:
            row = {t["theme"]: t["foreign_netbuy"] / 1e8 for t in day["theme"]}
            series[day["date"]] = {th: row.get(th, 0.0) for th in pick}
        chart_df = pd.DataFrame(series).T.sort_index()
        st.line_chart(chart_df)
