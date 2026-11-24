"""CoinGecko + alternative.me payloads → coins, market totals, candles, sentiment."""
from dataclasses import dataclass


@dataclass
class Coin:
    id: str
    symbol: str
    name: str
    price: float
    chg24: float | None
    chg7d: float | None
    hi24: float | None
    lo24: float | None
    mcap: float | None


@dataclass
class Global:
    total_mcap: float
    volume: float
    mcap_change_24h: float
    btc_dominance: float
    eth_dominance: float


@dataclass
class OHLC:
    times: list
    opens: list
    highs: list
    lows: list
    closes: list


@dataclass
class Sentiment:
    value: int
    label: str
    ts: int


def parse_markets(p):
    if not isinstance(p, list) or not p:
        raise ValueError("markets payload is not a list of coins")
    return [Coin(c["id"], c["symbol"].upper(), c["name"], float(c["current_price"]),
                 c.get("price_change_percentage_24h"), c.get("price_change_percentage_7d_in_currency"),
                 c.get("high_24h"), c.get("low_24h"), c.get("market_cap")) for c in p]


def parse_global(p):
    d = p["data"]
    return Global(float(d["total_market_cap"]["usd"]), float(d["total_volume"]["usd"]),
                  float(d["market_cap_change_percentage_24h_usd"]), float(d["market_cap_percentage"]["btc"]),
                  float(d["market_cap_percentage"].get("eth", 0.0)))


def parse_ohlc(p):
    if not isinstance(p, list) or not p:
        raise ValueError("ohlc payload is empty")
    rows = sorted(p)
    t, o, h, l, c = (list(x) for x in zip(*rows))
    return OHLC(t, o, h, l, c)


def parse_fng(p):
    out = [Sentiment(int(x["value"]), x["value_classification"].capitalize(), int(x["timestamp"])) for x in p["data"]]
    if not out:
        raise ValueError("no sentiment data")
    return out


def range_position(price, lo, hi):
    if hi is None or lo is None or hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (price - lo) / (hi - lo)))


def money(v):
    if v >= 1e12:
        return f"${v / 1e12:.2f}T"
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 10000:
        return f"${v:,.0f}"
    if v >= 1:
        return f"${v:,.2f}"
    if v >= 0.01:
        return f"${v:.4f}"
    return f"${v:.8f}"


STABLE_OR_WRAPPED = {"USDT", "USDC", "DAI", "USDE", "FDUSD", "USDS", "PYUSD", "TUSD", "USD1", "BSC-USD", "BUIDL",
                     "STETH", "WSTETH", "WBTC", "WETH", "WEETH", "CBBTC", "RETH", "WBETH", "USDTB", "USYC"}


def watchable(coins):
    """Coins worth watching: drop stablecoins, wrapped/staked copies and tokenized-asset tickers."""
    return [c for c in coins if c.symbol not in STABLE_OR_WRAPPED and "_" not in c.symbol and c.symbol.isalnum()]
