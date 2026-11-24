import json, os

import pytest

from modules.crypto import data

D = os.path.join(os.path.dirname(__file__), "fixtures")
L = lambda n: json.load(open(os.path.join(D, n + ".json")))


def test_parse_markets():
    coins = data.parse_markets(L("markets"))
    btc = coins[0]
    assert btc.id == "bitcoin" and btc.symbol == "BTC" and btc.name == "Bitcoin"
    assert btc.lo24 <= btc.price <= btc.hi24 or btc.hi24 is None
    assert len(coins) == 12 and all(c.symbol.isupper() for c in coins)


def test_parse_markets_rejects_error_object():
    with pytest.raises((TypeError, ValueError, KeyError)):
        data.parse_markets({"status": {"error_code": 429, "error_message": "rate limited"}})


def test_parse_global():
    g = data.parse_global(L("global"))
    assert g.total_mcap > 1e12 and g.volume > 0 and 30 < g.btc_dominance < 80
    assert isinstance(g.mcap_change_24h, float)


def test_parse_ohlc():
    o = data.parse_ohlc(L("ohlc"))
    assert len(o.closes) == 48 and o.times == sorted(o.times)
    assert all(h >= l for h, l in zip(o.highs, o.lows))


def test_parse_fng():
    f = data.parse_fng(L("fng"))
    assert f[0].value == 11 and f[0].label == "Extreme fear" and len(f) == 30
    assert all(0 <= x.value <= 100 for x in f)


@pytest.mark.parametrize("price,lo,hi,frac", [(5, 0, 10, 0.5), (0, 0, 10, 0.0), (12, 0, 10, 1.0), (5, 5, 5, 0.5)])
def test_range_position(price, lo, hi, frac):
    assert data.range_position(price, lo, hi) == frac


@pytest.mark.parametrize("v,s", [(61515.0, "$61,515"), (1725.4, "$1,725.40"), (0.94, "$0.9400"),
                                 (0.0000123, "$0.00001230"), (2.42e12, "$2.42T"), (94.2e9, "$94.2B")])
def test_money(v, s):
    assert data.money(v) == s


def test_watchable_drops_stablecoins_and_wrappers():
    coins = data.parse_markets(L("markets"))
    syms = [c.symbol for c in data.watchable(coins)]
    assert "USDT" not in syms and "USDC" not in syms and not any("_" in s for s in syms)
    assert "ETH" in syms and "BTC" in syms
