from dataclasses import dataclass
import pandas as pd
import numpy as np

@dataclass
class SignalParams:
    # динамические lookback по режимам
    lookback_calm: int = 26
    lookback_normal: int = 18
    lookback_high: int = 10

    atr_cushion_calm: float = 0.30
    atr_cushion_normal: float = 0.12
    atr_cushion_high: float = 0.08

    ltf_thinbar_k: float = 0.25

    # сетапы
    setup_breakout: bool = True
    setup_micro_breakout: bool = True
    setup_trend_cont: bool = True
    setup_squeeze: bool = True
    
    # параметры micro-breakout
    micro_lb_normal: int = 10
    micro_lb_high: int = 6
    micro_cushion_normal: float = 0.08
    micro_cushion_high: float = 0.05
    
    # параметры trend-continuation
    tc_min_body_k_range: float = 0.65
    tc_confirm_close_k_body: float = 0.30
    
    # параметры squeeze-breakout
    bb_period: int = 20
    bb_k: float = 2.0
    width_k_perc: float = 6.0

def _atr_cushion(regime: str, p: SignalParams) -> float:
    """Get ATR cushion based on regime"""
    if regime == 'high':
        return p.atr_cushion_high
    elif regime == 'normal':
        return p.atr_cushion_normal
    else:  # calm or ultra_calm
        return p.atr_cushion_calm

def _bollinger_bands(close: pd.Series, period: int, k: float):
    """Calculate Bollinger Bands"""
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + k * std
    lower = sma - k * std
    return upper, sma, lower

def generate_signals(df: pd.DataFrame, p: SignalParams, market_gate: pd.DataFrame = None) -> pd.DataFrame:
    """Generate trading signals based on four setups"""
    out = df.copy()

    # тренд (EMA 50/200 уже добавлены в features.add_indicators)
    out['trend_long'] = out['ema_fast'] > out['ema_slow']
    out['trend_short'] = out['ema_fast'] < out['ema_slow']

    # динамические swing-уровни
    lb_high_h = out['high'].shift(1).rolling(p.lookback_high, min_periods=1).max()
    lb_high_l = out['low'].shift(1).rolling(p.lookback_high, min_periods=1).min()
    lb_norm_h = out['high'].shift(1).rolling(p.lookback_normal, min_periods=1).max()
    lb_norm_l = out['low'].shift(1).rolling(p.lookback_normal, min_periods=1).min()
    lb_calm_h = out['high'].shift(1).rolling(p.lookback_calm, min_periods=1).max()
    lb_calm_l = out['low'].shift(1).rolling(p.lookback_calm, min_periods=1).min()

    swing_high = lb_calm_h.where(out['regime'].isin(['ultra_calm','calm']), lb_norm_h)
    swing_high = swing_high.where(out['regime']!='high', lb_high_h)
    swing_low = lb_calm_l.where(out['regime'].isin(['ultra_calm','calm']), lb_norm_l)
    swing_low = swing_low.where(out['regime']!='high', lb_high_l)

    out['swing_high'] = swing_high
    out['swing_low'] = swing_low

    # ATR-подушка
    atr_cush = out['regime'].apply(lambda r: _atr_cushion(r, p))
    
    # фильтр «тонкой» свечи
    hourly_range = (out['high'] - out['low']).abs()
    thin_cutoff = p.ltf_thinbar_k * out['atr']
    out['thin_bar'] = hourly_range < thin_cutoff

    # --- A) Breakout (основной) ---
    out['long_entry_breakout'] = swing_high + atr_cush * out['atr']
    out['short_entry_breakout'] = swing_low - atr_cush * out['atr']
    
    if p.setup_breakout:
        out['sig_long_breakout'] = (
            out['trend_long'] & 
            (out['regime'] != 'ultra_calm') & 
            (out['high'] >= out['long_entry_breakout']) & 
            (~out['thin_bar'])
        )
        out['sig_short_breakout'] = (
            out['trend_short'] & 
            (out['regime'] != 'ultra_calm') & 
            (out['low'] <= out['short_entry_breakout']) & 
            (~out['thin_bar'])
        )
    else:
        out['sig_long_breakout'] = False
        out['sig_short_breakout'] = False

    # --- B) Micro-breakout (короткие lookback) ---
    micro_lb_h = out['high'].shift(1).rolling(p.micro_lb_normal, min_periods=1).max()
    micro_lb_l = out['low'].shift(1).rolling(p.micro_lb_normal, min_periods=1).min()
    micro_lb_h = micro_lb_h.where(out['regime']!='high', 
                                  out['high'].shift(1).rolling(p.micro_lb_high, min_periods=1).max())
    micro_lb_l = micro_lb_l.where(out['regime']!='high', 
                                  out['low'].shift(1).rolling(p.micro_lb_high, min_periods=1).min())
    
    micro_cushion = out['regime'].apply(lambda r: p.micro_cushion_high if r == 'high' else p.micro_cushion_normal)
    out['long_entry_micro'] = micro_lb_h + micro_cushion * out['atr']
    out['short_entry_micro'] = micro_lb_l - micro_cushion * out['atr']
    
    if p.setup_micro_breakout:
        out['sig_long_micro'] = (
            out['trend_long'] & 
            (out['regime'] != 'ultra_calm') & 
            (out['high'] >= out['long_entry_micro']) & 
            (~out['thin_bar'])
        )
        out['sig_short_micro'] = (
            out['trend_short'] & 
            (out['regime'] != 'ultra_calm') & 
            (out['low'] <= out['short_entry_micro']) & 
            (~out['thin_bar'])
        )
    else:
        out['sig_long_micro'] = False
        out['sig_short_micro'] = False

    # --- C) Trend-continuation ---
    body_size = abs(out['close'] - out['open'])
    bar_range = out['high'] - out['low']
    body_ratio = body_size / bar_range.replace(0, np.nan)
    
    # Сильное тело свечи
    strong_body = body_ratio >= p.tc_min_body_k_range
    # Закрытие в направлении тренда
    trend_close_long = (out['close'] > out['open']) & (out['close'] >= out['open'] + p.tc_confirm_close_k_body * body_size)
    trend_close_short = (out['close'] < out['open']) & (out['close'] <= out['open'] - p.tc_confirm_close_k_body * body_size)
    
    out['long_entry_trend'] = out['high'] + atr_cush * out['atr']
    out['short_entry_trend'] = out['low'] - atr_cush * out['atr']
    
    if p.setup_trend_cont:
        out['sig_long_trend'] = (
            out['trend_long'] & 
            strong_body & 
            trend_close_long & 
            (out['regime'] != 'ultra_calm') & 
            (~out['thin_bar'])
        )
        out['sig_short_trend'] = (
            out['trend_short'] & 
            strong_body & 
            trend_close_short & 
            (out['regime'] != 'ultra_calm') & 
            (~out['thin_bar'])
        )
    else:
        out['sig_long_trend'] = False
        out['sig_short_trend'] = False

    # --- D) Squeeze-breakout (Bollinger Bands сжатие) ---
    bb_upper, bb_middle, bb_lower = _bollinger_bands(out['close'], p.bb_period, p.bb_k)
    bb_width = (bb_upper - bb_lower) / bb_middle * 100
    bb_squeeze = bb_width <= p.width_k_perc
    
    out['long_entry_squeeze'] = bb_upper + atr_cush * out['atr']
    out['short_entry_squeeze'] = bb_lower - atr_cush * out['atr']
    
    if p.setup_squeeze:
        out['sig_long_squeeze'] = (
            out['trend_long'] & 
            bb_squeeze & 
            (out['high'] >= out['long_entry_squeeze']) & 
            (out['regime'] != 'ultra_calm') & 
            (~out['thin_bar'])
        )
        out['sig_short_squeeze'] = (
            out['trend_short'] & 
            bb_squeeze & 
            (out['low'] <= out['short_entry_squeeze']) & 
            (out['regime'] != 'ultra_calm') & 
            (~out['thin_bar'])
        )
    else:
        out['sig_long_squeeze'] = False
        out['sig_short_squeeze'] = False

    # итог: разрешённые сигналы = ИЛИ всех сетапов
    out['allow_long'] = out[['sig_long_breakout', 'sig_long_micro', 'sig_long_trend', 'sig_long_squeeze']].any(axis=1)
    out['allow_short'] = out[['sig_short_breakout', 'sig_short_micro', 'sig_short_trend', 'sig_short_squeeze']].any(axis=1)

    # выбираем цену входа и причину (приоритет: breakout > micro > trend > squeeze)
    def _choose_long(r):
        if r['sig_long_breakout']: return r['long_entry_breakout'], 'breakout'
        if r['sig_long_micro']: return r['long_entry_micro'], 'micro_breakout'
        if r['sig_long_trend']: return r['long_entry_trend'], 'trend_continuation'
        if r['sig_long_squeeze']: return r['long_entry_squeeze'], 'squeeze_breakout'
        return np.nan, ''

    def _choose_short(r):
        if r['sig_short_breakout']: return r['short_entry_breakout'], 'breakout'
        if r['sig_short_micro']: return r['short_entry_micro'], 'micro_breakout'
        if r['sig_short_trend']: return r['short_entry_trend'], 'trend_continuation'
        if r['sig_short_squeeze']: return r['short_entry_squeeze'], 'squeeze_breakout'
        return np.nan, ''

    chosen_long = out.apply(_choose_long, axis=1, result_type='expand')
    chosen_short = out.apply(_choose_short, axis=1, result_type='expand')
    out['long_entry_final'], out['long_reason'] = chosen_long[0], chosen_long[1]
    out['short_entry_final'], out['short_reason'] = chosen_short[0], chosen_short[1]
    
    # Применяем рыночный фильтр если есть
    if market_gate is not None and not market_gate.empty:
        from .market import apply_market_filter
        out = apply_market_filter(out, market_gate)
    
    return out