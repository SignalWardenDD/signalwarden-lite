import pandas as pd
import numpy as np

def compute_market_bias(df_btc: pd.DataFrame, ema_fast: int = 50, ema_slow: int = 200) -> pd.DataFrame:
    """
    Вычисляет рыночное смещение на основе BTC
    Возвращает DataFrame с колонками mkt_long_ok и mkt_short_ok
    """
    out = df_btc.copy().sort_values('timestamp')
    
    # EMA расчеты
    out['ema_fast'] = out['close'].ewm(span=ema_fast, adjust=False).mean()
    out['ema_slow'] = out['close'].ewm(span=ema_slow, adjust=False).mean()
    
    # Наклон медленной EMA (сравнение с 3 барами назад)
    out['ema_slow_slope'] = out['ema_slow'] - out['ema_slow'].shift(3)
    
    # Условия для лонгов и шортов
    out['mkt_long_ok'] = (out['ema_fast'] > out['ema_slow']) & (out['ema_slow_slope'] > 0)
    out['mkt_short_ok'] = (out['ema_fast'] < out['ema_slow']) & (out['ema_slow_slope'] < 0)
    
    return out[['timestamp', 'mkt_long_ok', 'mkt_short_ok']]

def apply_market_filter(df: pd.DataFrame, market_gate: pd.DataFrame) -> pd.DataFrame:
    """
    Применяет рыночный фильтр к сигналам
    """
    if market_gate is None or market_gate.empty:
        return df
    
    # Объединяем по timestamp
    df_filtered = df.merge(market_gate, on='timestamp', how='left')
    
    # Заполняем пропуски (если есть)
    df_filtered['mkt_long_ok'] = df_filtered['mkt_long_ok'].fillna(True)
    df_filtered['mkt_short_ok'] = df_filtered['mkt_short_ok'].fillna(True)
    
    # Применяем фильтр к сигналам
    if 'allow_long' in df_filtered.columns:
        df_filtered['allow_long'] = df_filtered['allow_long'] & df_filtered['mkt_long_ok']
    
    if 'allow_short' in df_filtered.columns:
        df_filtered['allow_short'] = df_filtered['allow_short'] & df_filtered['mkt_short_ok']
    
    return df_filtered
