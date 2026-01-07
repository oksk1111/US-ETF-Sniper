import time
import datetime
import schedule
import sys
from modules.kis_api import KisOverseas
from modules.gemini_analyst import GeminiAnalyst
from modules.logger import logger
from strategies.technical import calculate_ma, check_trend
from strategies.volatility_breakout import calculate_target_price

# Configuration
# "Universe" of Hot ETFs/Stocks to monitor
# The Sniper will watch ALL of these and only attack the ones triggering the strategy.
TARGET_TICKERS = [
    # --- AI & Semiconductors (The Hottest) ---
    "NVDL",  # GraniteShares 2x Long NVDA (AI Core)
    "SOXL",  # Direxion Daily Semiconductor Bull 3X (Chips)
    
    # --- Big Tech & Growth ---
    "TQQQ",  # ProShares UltraPro QQQ (Nasdaq 100 3x)
    "TECL",  # Direxion Daily Technology Bull 3X
    "FNGU",  # MicroSectors FANG+ Index 3X (Big Tech Leaders)
    
    # --- Crypto / Blockchain ---
    "BITX",  # 2x Bitcoin Strategy ETF
    "CONL",  # 2x Coinbase (Crypto Proxy)
    
    # --- High Volatility / Momentum ---
    "TSLA",  # Tesla (King of Volatility)
]

QTY = 1 # Quantity per trade (Adjust based on portfolio size!)
K_VALUE = 0.5

def get_us_market_time():
    # Simple check for US Market Time (approximate)
    # Returns True if within 23:30 ~ 06:00 (Standard Time)
    # Need to handle DST properly in production, but for now simple check
    now = datetime.datetime.now()
    # Convert to simple time integer HHMM
    t = int(now.strftime("%H%M"))
    
    # Market Hours: 2330 ~ 2400 OR 0000 ~ 0600
    if 2330 <= t <= 2400 or 0 <= t < 600:
        return True
    return False

def job():
    logger.info(f"Starting Trading Session for {TARGET_TICKERS}")
    
    kis = KisOverseas()
    ai = GeminiAnalyst()
    
    # Dictionary to store monitoring targets
    # Structure: {'TQQQ': {'target': 105.5, 'status': 'monitoring'}, ...}
    monitoring_targets = {}

    # 1. Initialize Targets for each ticker
    for ticker in TARGET_TICKERS:
        logger.info(f"Analyzing {ticker}...")
        
        # A. Trend Check (20MA)
        ohlc = kis.get_daily_ohlc(ticker)
        if not ohlc:
            logger.error(f"[{ticker}] Failed to get OHLC. Skipping.")
            continue

        closes = [float(x['clos']) for x in ohlc]
        closes.reverse() 
        
        ma20 = calculate_ma(closes, 20)
        current_price = kis.get_current_price(ticker)
        
        if not current_price:
             logger.error(f"[{ticker}] Failed to get Current Price. Skipping.")
             continue

        logger.info(f"[{ticker}] Current: {current_price}, MA20: {ma20}")
        
        if not check_trend(current_price, ma20):
            logger.info(f"[{ticker}] Bear Market (Price < 20MA). Skipping.")
            continue

        # B. Calculate Target Price
        quote = kis.get_quote(ticker)
        if not quote:
            logger.error(f"[{ticker}] Failed to get Quote.")
            continue
            
        try:
            today_open = float(quote.get('open', 0))
        except (ValueError, TypeError):
            today_open = 0
            
        if today_open == 0:
            logger.warning(f"[{ticker}] Market not fully open (Open=0). Using Current as Open.")
            today_open = current_price 
            
        target_price = calculate_target_price(today_open, ohlc, K_VALUE)
        logger.info(f"[{ticker}] Bull Market! Target Price: {target_price} (Open: {today_open})")
        
        monitoring_targets[ticker] = {
            'target': target_price,
            'status': 'monitoring',  # monitoring, bought
            'buys': 0
        }

    if not monitoring_targets:
        logger.info("No targets found for today (All Bear Market or Errors). Sleeping.")
        return

    logger.info(f"Watch List: {list(monitoring_targets.keys())}")
    
    # 2. Watch Loop
    while get_us_market_time():
        for ticker, data in monitoring_targets.items():
            # If already bought, we might want to check for Stop Loss (Optional Improvement)
            if data['status'] == 'bought':
                continue
                
            current_price = kis.get_current_price(ticker)
            target_price = data['target']
            
            # Simple Breakout Check
            if current_price and current_price >= target_price:
                logger.info(f"[{ticker}] Breakout Detected! ({current_price} >= {target_price})")
                
                # 3. AI Filter
                logger.info("Checking AI Sentiment...")
                news = ai.fetch_news()
                sentiment = ai.check_market_sentiment(news)
                
                logger.info(f"AI Result: {sentiment}")
                
                if sentiment.get('can_buy', False):
                    logger.info(f"[{ticker}] AI Approved. Buying...")
                    res = kis.buy_market_order(ticker, QTY)
                    if res and res.get('rt_cd') == '0':
                        data['status'] = 'bought'
                        data['buys'] += 1
                        logger.info(f"[{ticker}] Buy Success!")
                    else:
                        logger.error(f"[{ticker}] Buy Failed: {res}")
                else:
                    logger.info(f"[{ticker}] AI Rejected buying due to risk.")
                    # Add cooldown to prevent spamming AI checks for the same ticker
                    time.sleep(10) 

        time.sleep(0.1) # Optimized Polling
        
    # 3. Market Close Sell-off
    logger.info("Market Close. Selling All Holdings.")
    for ticker, data in monitoring_targets.items():
        if data['status'] == 'bought':
            logger.info(f"[{ticker}] Selling Market Order...")
            kis.sell_market_order(ticker, QTY)

if __name__ == "__main__":
    logger.info("=== US ETF Sniper Bot Started ===")
    logger.info(f"Targets: {TARGET_TICKERS}")
    logger.info("Waiting for schedule (23:30 KST)...")
    
    # Schedule
    schedule.every().day.at("23:30").do(job)
    
    # Heartbeat (Every 1 minute) to keep dashboard alive
    def heartbeat():
        logger.info("Heartbeat: Bot is alive... Waiting for 23:30 KST")
        
    schedule.every(1).minutes.do(heartbeat)
    
    # Initial status log
    try:
        startup_kis = KisOverseas()
        for t in TARGET_TICKERS:
            curr = startup_kis.get_current_price(t)
            if curr:
                logger.info(f"[{t}] Startup Check - Current Price: {curr}")
    except Exception as e:
        logger.error(f"Startup Check Failed: {e}")

    # For testing, run immediately if argument provided
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("DEBUG: Running in TEST mode")
        job()
        print("DEBUG: Test job finished")
        sys.exit(0) # Exit after test
    
    while True:
        schedule.run_pending()
        time.sleep(60)
