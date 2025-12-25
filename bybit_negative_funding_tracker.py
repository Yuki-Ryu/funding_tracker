#// This Script® code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

BYBIT_REST = os.getenv("BYBIT_REST", "https://api.bybit.com")
COINGECKO_REST = os.getenv("COINGECKO_REST", "https://api.coingecko.com/api/v3")

MARKET_CAP_MIN_USD = float(os.getenv("MARKET_CAP_MIN_USD", "100000000"))  # 100m
REQ_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "15"))
USER_AGENT = "neg-funding-tracker/0.1.15"

def _iso_from_ms(ms: str) -> str:
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return ""

def _http_get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    r = requests.get(url, params=params or {}, headers=h, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    return r.json()

def bybit_get_all_linear_instruments() -> List[dict]:
    """Fetch all linear instruments with pagination via nextPageCursor."""
    out: List[dict] = []
    cursor = None

    while True:
        params = {"category": "linear", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
            
        resp = _http_get(f"{BYBIT_REST}/v5/market/instruments-info", params=params)
        
        if "result" in resp and "list" in resp["result"]:
            out.extend(resp["result"]["list"])
            
        # Check for next page
        if resp.get("result", {}).get("nextPageCursor"):
            cursor = resp["result"]["nextPageCursor"]
        else:
            break
            
        time.sleep(0.1)  # Rate limiting
        
    return out

def bybit_get_funding_rate(symbol: str) -> Dict:
    """Get current funding rate for a symbol."""
    params = {"category": "linear", "symbol": symbol}
    resp = _http_get(f"{BYBIT_REST}/v5/market/funding/history", params=params)
    
    if "result" in resp and "list" in resp["result"] and resp["result"]["list"]:
        return resp["result"]["list"][0]
    return {}

def bybit_get_ticker(symbol: str) -> Dict:
    """Get ticker information for a symbol."""
    params = {"category": "linear", "symbol": symbol}
    resp = _http_get(f"{BYBIT_REST}/v5/market/tickers", params=params)
    
    if "result" in resp and "list" in resp["result"] and resp["result"]["list"]:
        return resp["result"]["list"][0]
    return {}

def coingecko_get_market_data(symbol_id: str) -> Dict:
    """Get market data from CoinGecko for a coin."""
    try:
        # First get the coin ID from symbol
        coins_list = _http_get(f"{COINGECKO_REST}/coins/list")
        
        coin_id = None
        for coin in coins_list:
            if coin["symbol"].lower() == symbol_id.lower():
                coin_id = coin["id"]
                break
        
        if not coin_id:
            return {}
        
        # Get market data
        params = {
            "ids": coin_id,
            "vs_currency": "usd",
            "sparkline": "false"
        }
        data = _http_get(f"{COINGECKO_REST}/coins/markets", params=params)
        
        if data:
            return data[0]
        return {}
        
    except Exception as e:
        print(f"Error getting CoinGecko data for {symbol_id}: {e}")
        return {}

def format_number(num: float) -> str:
    """Format number with commas."""
    try:
        return f"{num:,.6f}".rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return str(num)

def main():
    parser = argparse.ArgumentParser(description="Track negative funding rates on Bybit")
    parser.add_argument("--min-cap", type=float, default=MARKET_CAP_MIN_USD,
                       help=f"Minimum market cap in USD (default: {MARKET_CAP_MIN_USD})")
    parser.add_argument("--top", type=int, default=20,
                       help="Number of top negative funding rates to show")
    parser.add_argument("--skip-market-cap", action="store_true",
                       help="Skip market cap filtering (show all symbols)")
    args = parser.parse_args()

    print(f"UTC {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} | min_cap={args.min_cap:,.0f} USD | fetching...")
    
    # Get all linear instruments
    instruments = bybit_get_all_linear_instruments()
    print(f"Found {len(instruments)} linear instruments")
    
    results = []
    
    for i, instr in enumerate(instruments):
        symbol = instr.get("symbol", "")
        base_coin = instr.get("baseCoin", "")
        
        if not symbol.endswith("USDT"):
            continue
        
        print(f"Processing {i+1}/{len(instruments)}: {symbol}...")
        
        # Get funding rate
        funding_data = bybit_get_funding_rate(symbol)
        if not funding_data:
            continue
            
        funding_rate = float(funding_data.get("fundingRate", 0))
        
        # Skip positive or zero funding rates
        if funding_rate >= 0:
            continue
        
        # Get ticker data
        ticker = bybit_get_ticker(symbol)
        if not ticker:
            continue
            
        mark_price = float(ticker.get("markPrice", 0))
        turnover24h = float(ticker.get("turnover24h", 0))
        next_funding_time = funding_data.get("fundingRateTimestamp", "")
        
        # Initialize market cap
        market_cap = 0
        
        # Get market cap from CoinGecko if not skipping
        if not args.skip_market_cap:
            market_data = coingecko_get_market_data(base_coin)
            market_cap = market_data.get("market_cap", 0) or 0
            
            # Apply market cap filter (only if we have valid data)
            if market_cap and market_cap < args.min_cap:
                continue
        else:
            # If skipping market cap check, set a placeholder value
            market_cap = float('inf')
        
        results.append({
            "symbol": symbol,
            "base": base_coin,
            "fundingRate": funding_rate,
            "marketCapUSD": market_cap,
            "nextFundingTime": _iso_from_ms(next_funding_time) if next_funding_time else "",
            "markPrice": mark_price,
            "turnover24h": turnover24h
        })
        
        # Rate limiting
        time.sleep(0.1)
    
    # Sort by most negative funding rate
    results.sort(key=lambda x: x["fundingRate"])
    
    # Take top N results
    results = results[:args.top]
    
    # Print header
    print(f"\n{'symbol':<12} {'base':<8} {'fundingRate':<12} {'marketCapUSD':<20} {'nextFundingTime':<25} {'markPrice':<12} {'turnover24h':<15}")
    print("-" * 120)
    
    # Print data
    for r in results:
        market_cap_display = "N/A" if r['marketCapUSD'] == float('inf') else f"{r['marketCapUSD']:,.0f}"
        print(f"{r['symbol']:<12} {r['base']:<8} "
              f"{r['fundingRate']:<12.6f} "
              f"{market_cap_display:<20} "
              f"{r['nextFundingTime']:<25} "
              f"{r['markPrice']:<12.6f} "
              f"{r['turnover24h']:<15.6f}")

if __name__ == "__main__":
    main()

