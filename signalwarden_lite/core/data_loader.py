import os
import re
import pandas as pd
from typing import Optional

def _find_file(data_dir: str, symbol: str, tf: str = '1h') -> Optional[str]:
    """Find pickle file for symbol and timeframe"""
    # First try exact match
    preferred = f"{symbol}_{tf}.pkl"
    for fn in os.listdir(data_dir):
        if fn == preferred:
            return os.path.join(data_dir, fn)
    
    # Then try pattern match
    pattern = re.compile(re.escape(symbol))
    for fn in os.listdir(data_dir):
        if pattern.search(fn) and tf in fn and fn.endswith('.pkl'):
            return os.path.join(data_dir, fn)
    
    return None

def load_candles_pkl(data_dir: str, symbol: str, tf: str = '1h') -> pd.DataFrame:
    """Load candles from pickle file"""
    fp = _find_file(data_dir, symbol, tf)
    if not fp or not os.path.exists(fp):
        raise FileNotFoundError(f"No pickle for {symbol} {tf} in {data_dir}")
    
    df = pd.read_pickle(fp)
    
    # Normalize column names
    cols = [c.lower() for c in df.columns]
    df.columns = cols
    
    # Handle timestamp column
    if df.index.name == 'timestamp':
        # Timestamp is already in index, convert to column
        df = df.reset_index()
        # Convert pandas timestamp to unix timestamp in seconds
        df['timestamp'] = pd.to_datetime(df['timestamp']).astype('int64') // 10**9
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce').astype('int64') // 10**6
    elif 'open_time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce').astype('int64') // 10**6
    else:
        # If no timestamp, create from index assuming it's datetime
        df = df.reset_index()
        df['timestamp'] = pd.to_datetime(df['timestamp']).astype('int64') // 10**9
    
    # Ensure required columns exist
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f'Missing {col} column in {symbol} data')
    
    # Return clean dataframe
    result_df = df[['timestamp'] + required_cols].sort_values('timestamp').reset_index(drop=True)
    return result_df
