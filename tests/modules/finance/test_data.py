import json, os

import pytest

from modules.finance import data

D = os.path.join(os.path.dirname(__file__), "fixtures")
SPARK = json.load(open(os.path.join(D, "spark.json")))
CHARTS = json.load(open(os.path.join(D, "charts.json")))


def test_parse_spark_quote():
    q = data.parse_spark(SPARK)
    spx = q["^GSPC"]
    assert len(q) == 15
    assert spx.price == 7237.17 and abs(spx.change_pct - 4.729) < 1e-6 and abs(spx.change - 326.78) < 1e-6
    assert spx.day_lo <= spx.price <= spx.day_hi and len(spx.series) > 5
    assert spx.trading_period["regular"]["start"] < spx.trading_period["regular"]["end"]


def test_parse_spark_skips_symbol_errors():
    bad = {"spark": {"result": [{"symbol": "NOPE", "response": [{"meta": {}}]},
                                SPARK["spark"]["result"][0]]}}
    assert list(data.parse_spark(bad)) == [SPARK["spark"]["result"][0]["symbol"]]


def test_parse_spark_garbage_raises():
    with pytest.raises((KeyError, TypeError, ValueError)):
        data.parse_spark({"finance": {"error": "x"}})


def test_parse_chart_candles():
    c = data.parse_charts(CHARTS)["NVDA"]
    assert c.name == "NVIDIA Corporation" and len(c.closes) == len(c.opens) == len(c.highs) > 40
    assert all(h >= l for h, l in zip(c.highs, c.lows))
    assert c.price == 165.05


def test_change_pct():
    assert data.change_pct(110, 100) == 10.0 and data.change_pct(90, 100) == -10.0
    assert data.change_pct(1, 0) is None


@pytest.mark.parametrize("now,state", [
    (1795444200 - 60, "pre"), (1795444200 + 60, "open"), (1795467600 + 60, "after hours"),
    (1795482000 + 60, "closed"), (1795424400 - 60, "closed"),
])
def test_market_state(now, state):
    tp = data.parse_spark(SPARK)["^GSPC"].trading_period
    assert data.market_state(now, tp) == state


def test_moving_average():
    assert data.moving_average([1, 2, 3, 4, 5], 2) == [None, 1.5, 2.5, 3.5, 4.5]
