import pandas as pd
import pytest


def pytest_addoption(parser):
    parser.addoption("--run-smoke", action="store_true", default=False,
                     help="run live Naver smoke tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: live network tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-smoke"):
        return
    skip = pytest.mark.skip(reason="need --run-smoke")
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip)


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
