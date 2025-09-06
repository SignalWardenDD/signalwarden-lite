from dataclasses import dataclass
from typing import List
from .types import PartialTake, Side, OrderPlan

@dataclass
class RiskConfig:
    mode: str = 'fixed_notional'
    notional_usdt: float = 15.0
    sl_atr_mult: float = 1.5
    cutloss_early_enabled: bool = True
    cutloss_early_bars: int = 2
    cutloss_early_threshold_R: float = -0.7

def build_partials(cfg_list: List[dict]) -> List[PartialTake]:
    """Build partial take profit list from config"""
    return [PartialTake(take_R=item['take_R'], size_pct=item['size_pct']) for item in cfg_list]

def make_order_plan(side: Side, entry: float, atr: float, partials: List[PartialTake], risk: RiskConfig) -> OrderPlan:
    """Create order plan with stop loss and partial takes"""
    if side == Side.LONG:
        sl = entry - risk.sl_atr_mult * atr
    else:
        sl = entry + risk.sl_atr_mult * atr
    
    return OrderPlan(
        side=side,
        entry=entry,
        sl=sl,
        partials=partials,
        ttl_seconds=8,
        maker_first=True
    )
