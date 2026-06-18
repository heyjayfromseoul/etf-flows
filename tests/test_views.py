from etf_flows.views import view_investor, view_theme, view_flow, view_active


def test_view_investor_top_foreign(sample_df):
    res = view_investor(sample_df, top_n=2)
    assert res["foreign_top"][0]["name"] == "KODEX 200"        # +5e9 최대
    assert res["foreign_bottom"][0]["name"] == "TIGER 2차전지"   # -1e9 최소


def test_view_theme_aggregates(sample_df):
    res = view_theme(sample_df)
    themes = {r["theme"]: r for r in res}
    assert themes["반도체"]["foreign_netbuy"] == 3e9
    assert themes["코스피"]["flow"] == 1e10


def test_view_flow_top(sample_df):
    res = view_flow(sample_df, top_n=2)
    assert res["inflow"][0]["name"] == "KODEX 200"             # +1e10 최대 유입


def test_view_active_by_value(sample_df):
    res = view_active(sample_df, top_n=2)
    assert res["by_value"][0]["name"] == "KODEX 200"           # 8e10 최대
    assert res["gainers"][0]["name"] == "KODEX 반도체"          # +2.5% 최대
