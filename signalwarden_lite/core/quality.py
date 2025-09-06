from dataclasses import dataclass

@dataclass
class QualityConfig:
    max_positions_per_symbol: int = 1
    max_trades_per_symbol_per_day: int = 3
    stop_if_two_losses_per_day: bool = True

class QualityController:
    """Controls trading quality and limits"""
    
    def __init__(self, cfg: QualityConfig):
        self.cfg = cfg
        self.day_losses = {}  # symbol -> loss count
        self.day_trades = {}  # symbol -> trade count
    
    def can_trade(self, symbol: str, open_positions: int, trades_today: int) -> bool:
        """Check if we can open new position for symbol"""
        # Check position limit
        if open_positions >= self.cfg.max_positions_per_symbol:
            return False
        
        # Check daily trade limit
        if trades_today >= self.cfg.max_trades_per_symbol_per_day:
            return False
        
        # Check loss limit
        if self.cfg.stop_if_two_losses_per_day:
            losses_today = self.day_losses.get(symbol, 0)
            if losses_today >= 2:
                return False
        
        return True
    
    def note_loss(self, symbol: str):
        """Record a loss for symbol"""
        self.day_losses[symbol] = self.day_losses.get(symbol, 0) + 1
    
    def note_trade(self, symbol: str):
        """Record a trade for symbol"""
        self.day_trades[symbol] = self.day_trades.get(symbol, 0) + 1
    
    def reset_daily_counters(self):
        """Reset daily counters (call at UTC midnight)"""
        self.day_losses.clear()
        self.day_trades.clear()
