"""라이브 네이버 스모크 테스트. 네트워크 필요 → 평소엔 건너뜀.
실행: pytest tests/test_fetch_smoke.py --run-smoke -v"""
import pytest
from etf_flows import fetch


@pytest.mark.smoke
def test_universe_has_many_etfs():
    uni = fetch.fetch_universe()
    assert len(uni) > 500
    assert {"code", "name", "aum", "nav"} <= set(uni[0])


@pytest.mark.smoke
def test_trend_has_investor_fields():
    row = fetch.latest_trend_row("069500")  # KODEX 200
    assert row is not None
    for k in ("date", "foreign_qty", "organ_qty", "close", "change_pct", "volume"):
        assert k in row
    assert len(row["date"]) == 8  # YYYYMMDD


@pytest.mark.smoke
def test_bad_code_returns_none():
    assert fetch.latest_trend_row("000000ZZZ") is None
