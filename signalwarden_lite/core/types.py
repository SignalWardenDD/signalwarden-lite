from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class PartialTake:
    take_R: float
    size_pct: float

@dataclass
class OrderPlan:
    side: Side
    entry: float
    sl: float
    partials: List[PartialTake]
    ttl_seconds: int = 8
    maker_first: bool = True

@dataclass
class Position:
    side: Side
    entry: float
    sl: float
    qty: float
    remaining_qty: float
    r_per_unit: float          # (entry - sl) для LONG; (sl - entry) для SHORT
    is_open: bool = True
    peak_R: float = 0.0
    realized_pnl: float = 0.0
    peak_pnl_usdt: float = 0.0  # Track maximum PnL for trailing
    bars_open: int = 0
    entry_reason: str = "breakout"
    sl_initial: float = 0.0    # исходный SL (для логики TRAIL vs SL_INIT)
    be_applied: bool = False   # выставлен ли BE(+δ)
    partials_done: Dict[float, bool] = field(default_factory=dict)

@dataclass
class TradeLog:
    symbol: str
    open_ts: int
    close_ts: Optional[int]
    side: Side
    entry: float
    exit: float
    pnl_abs: float
    pnl_R: float
    reason: str               # SL_INIT | TRAIL | BE | TPx
    entry_reason: str = "breakout"
    fees: float = 0.0