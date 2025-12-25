# Funding Tracker

What this script does:
This is a Python script that tracks negative funding rates on Bybit exchange for perpetual futures contracts. It:

- Fetches all linear (perpetual) trading pairs from Bybit

- Gets current funding rates and other market data

- Filters for assets with market cap > $100M

- Sorts by most negative funding rates

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

## Notable negative rates in your output:

    OG USDT : -0.002507 % (quite negative)

    PIPPIN USDT : -0.001290 %

    BEAT USDT : -0.000807 %

    IP USDT : -0.000017 %



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


# To use this script:

- Solution 1: Run Python Directly (Easiest)
Simply run the script with Python directly:

powershell

    python bybit_negative_funding_tracker.py
Or if that doesn't work:

powershell

    python3 bybit_negative_funding_tracker.py
Or:

powershell

    py bybit_negative_funding_tracker.py


- Solution 2: Run a Batch File called run_funding_tracker.bat in the same folder:

batch
  
    @echo off
    python bybit_negative_funding_tracker.py %*
    pause
Then double-click the .bat file to run.

