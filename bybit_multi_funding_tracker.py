#// This Script® code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

# Constants
BYBIT_REST = os.getenv("BYBIT_REST", "https://api.bybit.com")
COINGECKO_REST = os.getenv("COINGECKO_REST", "https://api.coingecko.com/api/v3")

MARKET_CAP_MIN_USD = float(os.getenv("MARKET_CAP_MIN_USD", "100000000"))
REQ_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "15"))
USER_AGENT = "funding-tracker-pro/1.0.0"

def _http_get(url: str, params: Optional[dict] = None) -> dict:
    """Helper for HTTP GET with automatic retry for 429 errors."""
    for attempt in range(3):
        try:
            r = requests.get(url, params=params or {}, headers={"User-Agent": USER_AGENT}, timeout=REQ_TIMEOUT)
            if r.status_code == 429:
                wait = (attempt + 1) * 30 # Wait 30s, then 60s
                print(f"Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2: raise e
            time.sleep(2)
    return {}

def get_coingecko_data(symbols: List[str]) -> Dict[str, dict]:
    """Fetches market names and caps for multiple symbols using batching."""
    print(f"Syncing names and market caps from CoinGecko...")
    
    # 1. Map lowercase symbol to CoinGecko ID
    all_coins = _http_get(f"{COINGECKO_REST}/coins/list")
    symbol_to_id = {c['symbol'].lower(): c['id'] for c in all_coins}
    
    target_ids = list(set(symbol_to_id.get(s.lower()) for s in symbols if symbol_to_id.get(s.lower())))
    
    coin_data_map = {}
    # 2. Batch query (up to 250 IDs per request) CoinGecko allows batching up to 250 IDs per request
    for i in range(0, len(target_ids), 250):
        batch = target_ids[i:i+250]
        params = {
            "vs_currency": "usd",
            "ids": ",".join(batch),
            "per_page": 250,
            "page": 1
        }
        data = _http_get(f"{COINGECKO_REST}/coins/markets", params=params)
        for coin in data:
            coin_data_map[coin['symbol'].upper()] = {
                "name": coin.get('name', 'N/A'),
                "mcap": coin.get('market_cap') or 0
            }
        time.sleep(1.5) # Small delay between batches
        
    return coin_data_map

def bybit_get_tickers() -> List[dict]:
    """Fetch all tickers at once to reduce individual API calls."""
    resp = _http_get(f"{BYBIT_REST}/v5/market/tickers", params={"category": "linear"})
    return resp.get("result", {}).get("list", [])

def display_table(title: str, data: List[dict]):
    """Helper to print a formatted table with mark price and base name."""
    print(f"\n--- {title} ---")
    header = f"{'SYMBOL':<12} {'NAME':<15} {'MARK PRICE':<12} {'FUNDING':<12} {'MARKET CAP':<18} {'TURNOVER':<12}"
    print(header)
    print("-" * len(header))
    for r in data:
        print(f"{r['symbol']:<12} {r['name']:<15.15} {r['markPrice']:<12.4f} "
              f"{r['fundingRate']:<12.6f} {r['marketCapUSD']:<18,.0f} {r['turnover24h']:<12,.0f}")

def main():
    parser = argparse.ArgumentParser(description="Bybit Multi-Direction Funding Tracker")
    parser.add_argument("--min-cap", type=float, default=MARKET_CAP_MIN_USD)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    # 1. Get all ticker data (Includes Funding Rate & Prices in one go)
    tickers = bybit_get_tickers()
    usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
    
    # 2. Get CoinGecko Metadata (Names & Market Caps)
    base_symbols = [t['symbol'].replace('USDT', '') for t in usdt_pairs]
    cg_metadata = get_coingecko_data(base_symbols)
    
    processed_list = []
    for t in usdt_pairs:
        symbol = t['symbol']
        base = symbol.replace('USDT', '')
        meta = cg_metadata.get(base, {"name": "N/A", "mcap": 0})
        
        # Filter by market cap
        if meta['mcap'] < args.min_cap:
            continue
            
        processed_list.append({
            "symbol": symbol,
            "name": meta['name'],
            "markPrice": float(t.get('markPrice', 0)), # Fetched from Bybit ticker
            "fundingRate": float(t.get('fundingRate', 0)),
            "marketCapUSD": meta['mcap'],
            "turnover24h": float(t.get('turnover24h', 0))
        })

    # 3. Sort Results
    # Top Positive (Highest first)
    pos_funding = sorted(processed_list, key=lambda x: x["fundingRate"], reverse=True)
    # Top Negative (Most negative first)
    neg_funding = sorted(processed_list, key=lambda x: x["fundingRate"])

    # 4. Output Tables
    display_table("HIGHEST POSITIVE FUNDING", pos_funding[:args.top])
    display_table("MOST NEGATIVE FUNDING", neg_funding[:args.top])

if __name__ == "__main__":
    main()

