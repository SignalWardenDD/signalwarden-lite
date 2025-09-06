import numpy as np
import pandas as pd

def ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()

def true_range(df: pd.DataFrame) -> pd.Series:
    """Calculate True Range"""
    prev_close = df['close'].shift(1)
    tr = (df['high'] - df['low']).abs()
    tr = np.maximum(tr, (df['high'] - prev_close).abs())
    tr = np.maximum(tr, (df['low'] - prev_close).abs())
    return tr

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    return true_range(df).rolling(period, min_periods=1).mean()

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator"""
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_indicators(df: pd.DataFrame, ema_fast: int = 50, ema_slow: int = 200, atr_p: int = 14, rsi_p: int = 14) -> pd.DataFrame:
    """Add technical indicators to dataframe"""
    out = df.copy()
    
    # EMAs for trend detection
    out['ema_fast'] = ema(out['close'], ema_fast)
    out['ema_slow'] = ema(out['close'], ema_slow)
    
    # ATR and normalized ATR
    out['atr'] = atr(out, atr_p)
    out['natr'] = 100.0 * (out['atr'] / out['close'])
    
    # RSI for momentum
    out['rsi'] = rsi(out['close'], rsi_p)
    
    return out

def swing_levels(df: pd.DataFrame, lookback: int = 20):
    """Calculate swing high and low levels"""
    # Use shifted data to avoid look-ahead bias
    highs = df['high'].shift(1).rolling(lookback, min_periods=1).max()
    lows = df['low'].shift(1).rolling(lookback, min_periods=1).min()
    return highs, lows
