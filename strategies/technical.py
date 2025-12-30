import pandas as pd

def calculate_ma(prices, window=20):
    """
    Calculate Moving Average
    prices: list of close prices
    window: period (default 20)
    """
    if len(prices) < window:
        return None
    
    series = pd.Series(prices)
    ma = series.rolling(window=window).mean()
    return ma.iloc[-1]

def check_trend(current_price, ma_value):
    """
    Returns True if Bull Market (Price > MA)
    """
    if ma_value is None:
        return False
    return current_price > ma_value
