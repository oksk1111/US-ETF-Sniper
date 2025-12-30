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
TARGET_TICKER = "TQQQ" # or SOXL
QTY = 1 # Test Quantity
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
    logger.info(f"Starting Trading Session")
    
    kis = KisOverseas()
    ai = GeminiAnalyst()
    
    # 1. Trend Check (20MA)
    logger.info("Checking Trend...")
    ohlc = kis.get_daily_ohlc(TARGET_TICKER)
    if not ohlc:
        logger.error("Failed to get OHLC. Aborting.")
        return

    # Parse Close prices for MA
    closes = [float(x['clos']) for x in ohlc] # Newest first
    closes.reverse() # Oldest first for rolling calculation
    
    ma20 = calculate_ma(closes, 20)
    current_price = kis.get_current_price(TARGET_TICKER)
    
    logger.info(f"Current: {current_price}, MA20: {ma20}")
    
    if not check_trend(current_price, ma20):
        logger.info("Bear Market (Price < 20MA). No Trade Today.")
        return

    logger.info("Bull Market! Preparing to trade.")
    
    # 2. Calculate Target Price
    # Need Today's Open. If market just started, get from Quote.
    quote = kis.get_quote(TARGET_TICKER)
    if not quote:
        logger.error("Failed to get Quote.")
        return
        
    today_open = float(quote['open'])
    if today_open == 0:
        logger.warning("Market not fully open yet (Open=0). Waiting...")
        # In real loop, retry. Here we assume open.
        today_open = current_price # Fallback for testing
        
    target_price = calculate_target_price(today_open, ohlc, K_VALUE)
    logger.info(f"Target Price: {target_price} (Open: {today_open})")
    
    # 3. Watch Loop
    bought = False
    buy_price = 0
    
    while get_us_market_time():
        current_price = kis.get_current_price(TARGET_TICKER)
        # logger.debug(f"Cur: {current_price} / Tgt: {target_price}") # Too noisy
        
        if not bought and current_price >= target_price:
            logger.info("Breakout Detected!")
            
            # 4. AI Filter
            logger.info("Checking AI Sentiment...")
            news = ai.fetch_news()
            sentiment = ai.check_market_sentiment(news)
            
            logger.info(f"AI Result: {sentiment}")
            
            if sentiment.get('can_buy', False):
                logger.info("AI Approved. Buying...")
                res = kis.buy_market_order(TARGET_TICKER, QTY)
                if res and res.get('rt_cd') == '0':
                    logger.info(f"Buy Order Success! {res.get('msg1')}")
                    bought = True
                    buy_price = current_price # Approximate
                else:
                    logger.error(f"Buy Failed: {res}")
            else:
                logger.info(f"AI Rejected: {sentiment.get('reason')}")
                break # Stop for the day if AI rejects? Or wait? Strategy says "Cancel Order" -> No trade.
        
        if bought:
            # 5. Monitoring (Stop Loss / Trailing Stop)
            # Simple Stop Loss -3%
            loss_pct = (current_price - buy_price) / buy_price * 100
            if loss_pct <= -3.0:
                logger.warning(f"Stop Loss Triggered! ({loss_pct:.2f}%)")
                kis.sell_market_order(TARGET_TICKER, QTY)
                break
            
            # Trailing Stop logic could be added here
            
        time.sleep(1)
        
    # 6. Market Close Sell-off
    if bought:
        logger.info("Market Close. Selling All.")
        kis.sell_market_order(TARGET_TICKER, QTY)

if __name__ == "__main__":
    logger.info("=== US ETF Sniper Bot Started ===")
    logger.info("Waiting for schedule (23:30 KST)...")
    
    # Schedule
    schedule.every().day.at("23:30").do(job)
    
    # For testing, run immediately if argument provided
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        job()
    
    while True:
        schedule.run_pending()
        time.sleep(60)
