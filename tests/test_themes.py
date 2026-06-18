from etf_flows.themes import classify_theme


def test_semiconductor_before_us():
    # '미국+반도체'가 겹치면 반도체 우선
    assert classify_theme("SOL 미국AI반도체칩") == "반도체"


def test_us_bond_is_bond_not_us():
    assert classify_theme("KODEX 미국채30년") == "채권"


def test_battery():
    assert classify_theme("TIGER 2차전지테마") == "2차전지"


def test_us_equity():
    assert classify_theme("TIGER 미국S&P500") == "미국주식"


def test_kospi_and_etc():
    assert classify_theme("KODEX 200") == "코스피"
    assert classify_theme("ACE 알수없는테마xyz") == "기타"
