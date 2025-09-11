from dataclasses import dataclass
from .types import Position, Side

@dataclass
class TrailingConfigPnLOnly:
    # Только PnL-based уровни сохранения прибыли
    # АКТИВАЦИЯ: $0.06 -> сохранить $0.03 (50%)
    level_1_pnl: float = 0.06           # $0.06 - сохранить 50% = $0.03
    level_1_keep_pct: float = 0.50      # 50%
    level_2_pnl: float = 0.15           # $0.15 - сохранить 60% = $0.09
    level_2_keep_pct: float = 0.60      # 60%
    level_3_pnl: float = 0.25           # $0.25 - сохранить 70% = $0.175
    level_3_keep_pct: float = 0.70      # 70%
    level_4_pnl: float = 0.35           # $0.35+ - сохранить 80% = $0.28
    level_4_keep_pct: float = 0.80      # 80%

def update_trailing_pnl_only(pos: Position, hi: float, lo: float, atr: float, cfg: TrailingConfigPnLOnly) -> Position:
    """
    ТОЛЬКО PnL-based система трейлинга:
    Только PnL-based уровни сохранения прибыли
    Никогда не ухудшает SL, только улучшает
    """
    
    # Расчет для LONG позиций
    if pos.side == Side.LONG:
        # Текущий PnL
        current_pnl_usdt = (hi - pos.entry) * pos.qty
        
        # Инициализируем отладочную информацию
        pos.trailing_debug = {
            'level': 'INACTIVE',
            'keep_pct': 0,
            'peak_pnl': pos.peak_pnl_usdt,
            'target_profit': 0,
            'current_pnl': current_pnl_usdt,
            'sl_updated': False
        }
        
        # Трейлинг активируется только при положительном PnL
        if current_pnl_usdt > 0:
            pos.peak_pnl_usdt = max(pos.peak_pnl_usdt, current_pnl_usdt)
            
            # Определяем уровень сохранения прибыли по МАКСИМАЛЬНОМУ PnL
            if pos.peak_pnl_usdt >= cfg.level_4_pnl:
                keep_pct = cfg.level_4_keep_pct  # 80%
                level_name = "L4"
            elif pos.peak_pnl_usdt >= cfg.level_3_pnl:
                keep_pct = cfg.level_3_keep_pct  # 70%
                level_name = "L3"
            elif pos.peak_pnl_usdt >= cfg.level_2_pnl:
                keep_pct = cfg.level_2_keep_pct  # 60%
                level_name = "L2"
            elif pos.peak_pnl_usdt >= cfg.level_1_pnl:
                keep_pct = cfg.level_1_keep_pct  # 50%
                level_name = "L1"
            else:
                keep_pct = 0  # Не достигли минимального уровня
                level_name = "INACTIVE"
                
            # Обновляем отладочную информацию
            pos.trailing_debug.update({
                'level': level_name,
                'keep_pct': keep_pct,
                'peak_pnl': pos.peak_pnl_usdt,
                'target_profit': pos.peak_pnl_usdt * keep_pct if keep_pct > 0 else 0
            })
            
            if keep_pct > 0:
                # СТРОГАЯ ЗАЩИТА: Минимальная прибыль $0.03 (как требуется)
                min_profit_usdt = 0.03  # Минимальная прибыль $0.03
                min_sl = pos.entry + (min_profit_usdt / pos.qty)  # Минимальный SL для LONG
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: ВСЕ уровни используют МАКСИМАЛЬНЫЙ PnL!
                # Это означает, что SL всегда растет и никогда не падает внутри уровня
                target_profit = pos.peak_pnl_usdt * keep_pct
                
                # КРИТИЧЕСКАЯ ЗАЩИТА: target_profit не может быть меньше $0.03
                target_profit = max(target_profit, min_profit_usdt)
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: SL должен быть на уровне entry + сохраненная прибыль на единицу
                # Для LONG: (SL - entry) * qty = target_profit, поэтому SL = entry + (target_profit / qty)
                pnl_sl = pos.entry + (target_profit / pos.qty)
                
                # ЗАЩИТА: Используем максимальный из рассчитанного SL и минимального защитного SL
                protected_sl = max(pnl_sl, min_sl)
                
                old_sl = pos.sl  # Сохраняем старый SL
                sl_updated = False
                if protected_sl > pos.sl:
                    pos.sl = protected_sl
                    sl_updated = True
                    
                # Обновляем отладочную информацию
                pos.trailing_debug.update({
                    'target_profit': target_profit,
                    'min_sl': min_sl,
                    'pnl_sl': pnl_sl,
                    'protected_sl': protected_sl,
                    'protection_applied': protected_sl > pnl_sl,
                    'sl_updated': sl_updated
                })

    # Расчет для SHORT позиций
    else:  # SHORT
        # Текущий PnL
        current_pnl_usdt = (pos.entry - lo) * pos.qty
        
        # Инициализируем отладочную информацию
        pos.trailing_debug = {
            'level': 'INACTIVE',
            'keep_pct': 0,
            'peak_pnl': pos.peak_pnl_usdt,
            'target_profit': 0,
            'current_pnl': current_pnl_usdt,
            'sl_updated': False
        }
        
        # Трейлинг активируется только при положительном PnL
        if current_pnl_usdt > 0:
            pos.peak_pnl_usdt = max(pos.peak_pnl_usdt, current_pnl_usdt)
            
            # Определяем уровень сохранения прибыли по МАКСИМАЛЬНОМУ PnL
            if pos.peak_pnl_usdt >= cfg.level_4_pnl:
                keep_pct = cfg.level_4_keep_pct  # 80%
                level_name = "L4"
            elif pos.peak_pnl_usdt >= cfg.level_3_pnl:
                keep_pct = cfg.level_3_keep_pct  # 70%
                level_name = "L3"
            elif pos.peak_pnl_usdt >= cfg.level_2_pnl:
                keep_pct = cfg.level_2_keep_pct  # 60%
                level_name = "L2"
            elif pos.peak_pnl_usdt >= cfg.level_1_pnl:
                keep_pct = cfg.level_1_keep_pct  # 50%
                level_name = "L1"
            else:
                keep_pct = 0  # Не достигли минимального уровня
                level_name = "INACTIVE"
                
            # Обновляем отладочную информацию
            pos.trailing_debug.update({
                'level': level_name,
                'keep_pct': keep_pct,
                'peak_pnl': pos.peak_pnl_usdt,
                'target_profit': pos.peak_pnl_usdt * keep_pct if keep_pct > 0 else 0
            })
            
            if keep_pct > 0:
                # СТРОГАЯ ЗАЩИТА: Минимальная прибыль $0.03 (как требуется)
                min_profit_usdt = 0.03  # Минимальная прибыль $0.03
                min_sl = pos.entry - (min_profit_usdt / pos.qty)  # Минимальный SL для SHORT
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: ВСЕ уровни используют МАКСИМАЛЬНЫЙ PnL!
                # Это означает, что SL всегда растет и никогда не падает внутри уровня
                target_profit = pos.peak_pnl_usdt * keep_pct
                
                # КРИТИЧЕСКАЯ ЗАЩИТА: target_profit не может быть меньше $0.03
                target_profit = max(target_profit, min_profit_usdt)
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: SL должен быть на уровне entry - сохраненная прибыль на единицу
                pnl_sl = pos.entry - (target_profit / pos.qty)
                
                # ЗАЩИТА: Используем минимальный из рассчитанного SL и максимального защитного SL
                protected_sl = min(pnl_sl, min_sl)
                
                old_sl = pos.sl  # Сохраняем старый SL
                sl_updated = False
                if protected_sl < pos.sl:
                    pos.sl = protected_sl
                    sl_updated = True
                    
                # Обновляем отладочную информацию
                pos.trailing_debug.update({
                    'target_profit': target_profit,
                    'min_sl': min_sl,
                    'pnl_sl': pnl_sl,
                    'protected_sl': protected_sl,
                    'protection_applied': protected_sl < pnl_sl,
                    'sl_updated': sl_updated
                })

    return pos
