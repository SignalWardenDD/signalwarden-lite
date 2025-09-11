import pandas as pd
import numpy as np

def compute_market_bias(df_btc: pd.DataFrame, ema_fast: int = 50, ema_slow: int = 200) -> pd.DataFrame:
    """
    Вычисляет рыночное смещение на основе BTC
    Возвращает DataFrame с колонками mkt_long_ok и mkt_short_ok
    
    ИСПРАВЛЕНО: Более чувствительная логика определения тренда
    """
    out = df_btc.copy().sort_values('timestamp')
    
    # EMA расчеты
    out['ema_fast'] = out['close'].ewm(span=ema_fast, adjust=False).mean()
    out['ema_slow'] = out['close'].ewm(span=ema_slow, adjust=False).mean()
    
    # Наклон медленной EMA (сравнение с 3 барами назад)
    out['ema_slow_slope'] = out['ema_slow'] - out['ema_slow'].shift(3)
    
    # Наклон быстрой EMA (сравнение с 2 барами назад) - для более быстрого реагирования
    out['ema_fast_slope'] = out['ema_fast'] - out['ema_fast'].shift(2)
    
    # ИСПРАВЛЕННАЯ ЛОГИКА: Более чувствительное определение тренда
    
    # Бычий тренд: EMA50 > EMA200 И (EMA200 растет ИЛИ EMA50 растет)
    out['mkt_long_ok'] = (out['ema_fast'] > out['ema_slow']) & (
        (out['ema_slow_slope'] > 0) | (out['ema_fast_slope'] > 0)
    )
    
    # Медвежий тренд: EMA50 < EMA200 И (EMA200 падает ИЛИ EMA50 падает)
    out['mkt_short_ok'] = (out['ema_fast'] < out['ema_slow']) & (
        (out['ema_slow_slope'] < 0) | (out['ema_fast_slope'] < 0)
    )
    
    # Дополнительная логика: если EMA50 пересекла EMA200, сразу переключаемся
    # (даже если наклоны еще не изменились)
    ema_cross_down = (out['ema_fast'] < out['ema_slow']) & (out['ema_fast'].shift(1) >= out['ema_slow'].shift(1))
    ema_cross_up = (out['ema_fast'] > out['ema_slow']) & (out['ema_fast'].shift(1) <= out['ema_slow'].shift(1))
    
    # При пересечении вниз - разрешаем шорты, запрещаем лонги
    out.loc[ema_cross_down, 'mkt_short_ok'] = True
    out.loc[ema_cross_down, 'mkt_long_ok'] = False
    
    # При пересечении вверх - разрешаем лонги, запрещаем шорты  
    out.loc[ema_cross_up, 'mkt_long_ok'] = True
    out.loc[ema_cross_up, 'mkt_short_ok'] = False
    
    # Return with timestamp as column if it exists, otherwise reset index to create timestamp column
    if 'timestamp' in out.columns:
        return out[['timestamp', 'mkt_long_ok', 'mkt_short_ok']]
    else:
        # Reset index to create timestamp column
        out_reset = out.reset_index()
        # Rename index column to timestamp if it's not named correctly
        if out_reset.columns[0] != 'timestamp':
            out_reset = out_reset.rename(columns={out_reset.columns[0]: 'timestamp'})
        return out_reset[['timestamp', 'mkt_long_ok', 'mkt_short_ok']]

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
