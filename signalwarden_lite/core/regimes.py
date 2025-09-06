from dataclasses import dataclass
import pandas as pd

@dataclass
class RegimeThresholds:
    ultra_calm: float = 0.8
    calm: float = 1.2
    high: float = 2.5

def classify_regime(natr_val: float, th: RegimeThresholds) -> str:
    """Classify market regime based on NATR value"""
    if pd.isna(natr_val):
        return 'normal'  # Default fallback
        
    if natr_val < th.ultra_calm:
        return 'ultra_calm'
    elif natr_val < th.calm:
        return 'calm'
    elif natr_val < th.high:
        return 'normal'
    else:
        return 'high'

def add_regime(df: pd.DataFrame, th: RegimeThresholds) -> pd.DataFrame:
    """Add regime classification to dataframe"""
    out = df.copy()
    
    # Fill NaN values with forward fill, then apply regime classification
    natr_filled = out['natr'].ffill().bfill()
    out['regime'] = natr_filled.apply(lambda v: classify_regime(v, th))
    
    return out
