#// This Script® code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

import requests

BYBIT_REST = os.getenv("BYBIT_REST", "https://api.bybit.com")
COINGECKO_REST = os.getenv("COINGECKO_REST", "https://api.coingecko.com/api/v3")

MARKET_CAP_MIN_USD = float(os.getenv("MARKET_CAP_MIN_USD", "100000000"))  # 100m
REQ_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "15"))
USER_AGENT = "neg-funding-tracker/0.1.20"

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

def bybit_get_funding_rates_batch(symbols: List[str]) -> Dict[str, Dict]:
    """Get funding rates for multiple symbols in batches."""
    funding_data = {}
    
    # Bybit API supports up to 10 symbols per request for funding rate
    batch_size = 10
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        
        # Get funding rates for all symbols in batch
        params = {"category": "linear", "symbol": ",".join(batch)}
        try:
            resp = _http_get(f"{BYBIT_REST}/v5/market/funding/history", params=params)
            
            if "result" in resp and "list" in resp["result"]:
                for item in resp["result"]["list"]:
                    symbol = item.get("symbol")
                    if symbol:
                        funding_data[symbol] = item
        except Exception as e:
            print(f"Error fetching funding rates for batch: {e}")
        
        time.sleep(0.2)  # Rate limiting between batches
    
    return funding_data

def bybit_get_tickers_batch(symbols: List[str]) -> Dict[str, Dict]:
    """Get ticker data for multiple symbols in batches."""
    ticker_data = {}
    
    # Bybit API supports up to 10 symbols per request for tickers
    batch_size = 10
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        
        params = {"category": "linear", "symbol": ",".join(batch)}
        try:
            resp = _http_get(f"{BYBIT_REST}/v5/market/tickers", params=params)
            
            if "result" in resp and "list" in resp["result"]:
                for item in resp["result"]["list"]:
                    symbol = item.get("symbol")
                    if symbol:
                        ticker_data[symbol] = item
        except Exception as e:
            print(f"Error fetching tickers for batch: {e}")
        
        time.sleep(0.2)  # Rate limiting between batches
    
    return ticker_data

def coingecko_get_market_data_batch(symbols: Set[str]) -> Dict[str, Dict]:
    """Get market data from CoinGecko for multiple symbols in minimal requests."""
    print(f"Fetching CoinGecko data for {len(symbols)} unique symbols...")
    
    try:
        # Get all coins list once
        coins_list = _http_get(f"{COINGECKO_REST}/coins/list")
        print(f"Retrieved {len(coins_list)} coins from CoinGecko")
        
        # Map symbols to coin IDs
        symbol_to_id = {}
        for coin in coins_list:
            symbol = coin["symbol"].lower()
            if symbol in symbols:
                symbol_to_id[symbol] = coin["id"]
        
        print(f"Found {len(symbol_to_id)} symbols in CoinGecko")
        
        # Batch by 30 coin IDs per request (CoinGecko limit)
        coin_ids = list(symbol_to_id.values())
        market_data = {}
        
        batch_size = 30  # CoinGecko's limit per request
        for i in range(0, len(coin_ids), batch_size):
            batch_ids = coin_ids[i:i + batch_size]
            
            params = {
                "ids": ",".join(batch_ids),
                "vs_currency": "usd",
                "sparkline": "false"
            }
            
            try:
                data = _http_get(f"{COINGECKO_REST}/coins/markets", params=params)
                
                for coin_data in data:
                    coin_id = coin_data.get("id")
                    # Find which symbol this coin_id corresponds to
                    for symbol, cid in symbol_to_id.items():
                        if cid == coin_id:
                            market_data[symbol] = coin_data
                            break
                
                print(f"Processed batch {i//batch_size + 1}/{(len(coin_ids)-1)//batch_size + 1}")
                
                # Rate limiting for CoinGecko (max 10-30 calls per minute)
                if i + batch_size < len(coin_ids):
                    time.sleep(6)  # Wait 6 seconds between batches
                    
            except Exception as e:
                print(f"Error fetching CoinGecko batch: {e}")
                continue
        
        return market_data
        
    except Exception as e:
        print(f"Error getting CoinGecko data: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description="Track negative funding rates on Bybit")
    parser.add_argument("--min-cap", type=float, default=MARKET_CAP_MIN_USD,
                       help=f"Minimum market cap in USD (default: {MARKET_CAP_MIN_USD})")
    parser.add_argument("--top", type=int, default=20,
                       help="Number of top negative funding rates to show")
    parser.add_argument("--skip-market-cap", action="store_true",
                       help="Skip market cap filtering (show all symbols)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show verbose output")
    args = parser.parse_args()

    print(f"UTC {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} | min_cap={args.min_cap:,.0f} USD")
    print("=" * 80)
    
    # Step 1: Get all linear instruments
    print("Fetching all linear instruments from Bybit...")
    instruments = bybit_get_all_linear_instruments()
    print(f"Found {len(instruments)} linear instruments")
    
    # Filter for USDT pairs
    usdt_instruments = [instr for instr in instruments if instr.get("symbol", "").endswith("USDT")]
    print(f"Filtered to {len(usdt_instruments)} USDT pairs")
    
    # Step 2: Get funding rates for all USDT pairs in batches
    symbols = [instr["symbol"] for instr in usdt_instruments]
    print(f"Fetching funding rates for {len(symbols)} symbols...")
    funding_data = bybit_get_funding_rates_batch(symbols)
    print(f"Retrieved funding rates for {len(funding_data)} symbols")
    
    # Step 3: Filter for negative funding rates
    negative_symbols = []
    for symbol, data in funding_data.items():
        funding_rate = float(data.get("fundingRate", 0))
        if funding_rate < 0:  # Negative funding
            negative_symbols.append(symbol)
    
    print(f"Found {len(negative_symbols)} symbols with negative funding rates")
    
    if not negative_symbols:
        print("No negative funding rates found!")
        return
    
    # Step 4: Get ticker data for negative symbols in batches
    print(f"Fetching ticker data for {len(negative_symbols)} symbols...")
    ticker_data = bybit_get_tickers_batch(negative_symbols)
    
    # Step 5: Get CoinGecko data for unique base coins
    base_coins = set()
    symbol_to_base = {}
    for symbol in negative_symbols:
        # Extract base coin (remove 'USDT')
        base_coin = symbol[:-4].upper()
        base_coins.add(base_coin.lower())  # CoinGecko uses lowercase
        symbol_to_base[symbol] = base_coin
    
    # Step 6: Get market cap data from CoinGecko (if not skipping)
    market_cap_data = {}
    if not args.skip_market_cap:
        market_cap_data = coingecko_get_market_data_batch(base_coins)
        print(f"Retrieved market cap data for {len(market_cap_data)} symbols")
    else:
        print("Skipping market cap filtering as requested")
    
    # Step 7: Process and compile results
    results = []
    
    for symbol in negative_symbols:
        base_coin = symbol_to_base[symbol]
        funding_info = funding_data.get(symbol, {})
        ticker_info = ticker_data.get(symbol, {})
        
        funding_rate = float(funding_info.get("fundingRate", 0))
        mark_price = float(ticker_info.get("markPrice", 0))
        turnover24h = float(ticker_info.get("turnover24h", 0))
        next_funding_time = funding_info.get("fundingRateTimestamp", "")
        
        # Get market cap
        market_cap = 0
        if not args.skip_market_cap:
            coin_data = market_cap_data.get(base_coin.lower(), {})
            market_cap = coin_data.get("market_cap", 0) or 0
            
            # Apply market cap filter
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
    
    # Step 8: Sort by most negative funding rate
    results.sort(key=lambda x: x["fundingRate"])
    
    # Take top N results
    results = results[:args.top]
    
    # Step 9: Display results
    print("\n" + "=" * 120)
    print(f"TOP {len(results)} NEGATIVE FUNDING RATES")
    print("=" * 120)
    
    # Print header
    print(f"{'#':<3} {'symbol':<12} {'base':<8} {'fundingRate':<12} {'marketCapUSD':<20} {'nextFundingTime':<25} {'markPrice':<12} {'turnover24h':<15}")
    print("-" * 120)
    
    # Print data
    for idx, r in enumerate(results, 1):
        if r['marketCapUSD'] == float('inf'):
            market_cap_display = "N/A"
        elif r['marketCapUSD'] == 0:
            market_cap_display = "Not Found"
        else:
            market_cap_display = f"${r['marketCapUSD']:,.0f}"
        
        funding_rate_display = f"{r['fundingRate']:.6f}"
        if r['fundingRate'] < -0.001:
            funding_rate_display = f"\033[91m{funding_rate_display}\033[0m"  # Red for very negative
        
        print(f"{idx:<3} {r['symbol']:<12} {r['base']:<8} "
              f"{funding_rate_display:<12} "
              f"{market_cap_display:<20} "
              f"{r['nextFundingTime']:<25} "
              f"{r['markPrice']:<12.6f} "
              f"{r['turnover24h']:<15.6f}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")

