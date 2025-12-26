# Funding Tracker

What this script does:
This is a Python script that tracks funding rates on Bybit exchange for perpetual futures contracts. It:

- Fetches all linear (perpetual) trading pairs from Bybit

- Gets current funding rates and other market data

- Filters for assets with market cap > $100M

- Sorts by most negative and positive funding rates

- Displays results in a formatted table



 ## Key components in the output:
 Negative Funding Rates:

- Funding rate is a periodic payment between long and short traders

- Negative means shorts pay longs (bearish sentiment)

- More negative = stronger bearish pressure



## Columns shown:

- symbol: Trading pair (e.g., BTCUSDT, ETHUSDT)

- fundingRate: Current funding rate as percentage

- marketCapUSD: Market capitalization

- indexPrice: Current index price

- turnover24h: 24-hour trading volume

- nextFundingTime: When next funding payment occurs


![Image of Minecraft comes alive](https://github.com/Yuki-Ryu/funding_tracker/blob/main/Example.png)

## Notable negative and positive rates in your output:

    SYMBOL      NAME            FUNDING
    
    AIOZUSDT    AIOZ Network    0.000100  % (quite positive)
    ARUSDT      Arweave         0.000100  %
    
    
    OGUSDT      OG              -0.010000 % (quite negative)
    2ZUSDT      DoubleZero      -0.002540 %




## Trading implications:
 
- Negative funding suggests more traders are shorting

- Can indicate potential buying opportunities if you believe sentiment is too bearish

- Traders can earn funding payments by being long in negative funding environments

- High negative funding + high volume = strong bearish conviction



## Script features:
 
- Uses Bybit API for funding data

- Uses CoinGecko for market cap filtering

- Paginates through all instruments

- Includes error handling and timeout settings


> [!NOTE]
> # What has changed:

## Resolved the 429 Error:

- The script no longer calls CoinGecko in a loop for every coin.

- It uses the /coins/markets endpoint with the ids parameter, which allows querying up to 250 coins in a single request.

## Dual Funding Monitoring:

- The script now sorts and displays two separate tables: Highest Positive Funding (Longs pay Shorts) and Most Negative Funding (Shorts pay Longs).

## Performance Optimization:

- It fetches all Bybit tickers in one call (/v5/market/tickers) instead of querying individual funding histories, making the script run significantly faster.

## Resilience:

- Added a retry mechanism: if you do hit a rate limit, the script will wait and try again automatically rather than crashing.


> [!IMPORTANT]
> #To use this script:

- Solution 1: Run Python Directly (Easiest)
Simply run the script with Python directly:

powershell

    python bybit_multi_funding_tracker.py
Or if that doesn't work:

powershell

    python3 bybit_multi_funding_tracker.py
Or:

powershell

    py bybit_multi_funding_tracker.py


- Solution 2: Run a Batch File called run_funding_tracker.bat in the same folder:

batch
  
    @echo off
    python bybit_multi_funding_tracker.py --top 20 --min-cap 100000000 %*
    pause
Then double-click the .bat file to run.

