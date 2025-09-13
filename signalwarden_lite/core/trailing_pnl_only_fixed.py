from dataclasses import dataclass
from .types import Position, Side
import logging

logger = logging.getLogger(__name__)

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

        }
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Обновляем peak_pnl_usdt только при росте
        if current_pnl_usdt > 0:
            pos.peak_pnl_usdt = max(pos.peak_pnl_usdt, current_pnl_usdt)
        
        # ТРЕЙЛИНГ РАБОТАЕТ НА ОСНОВЕ PEAK PnL, даже если текущий PnL упал!
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
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Минимальная прибыль $0.03 (как в успешных бэктестах)
            min_profit_usdt = 0.03  # Минимальная прибыль $0.03
            
            min_sl = pos.entry + (min_profit_usdt / pos.qty)  # Минимальный SL (гарантируем $0.03)
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: ВСЕ уровни используют МАКСИМАЛЬНЫЙ PnL!
            target_profit_raw = pos.peak_pnl_usdt * keep_pct
            
            # Обеспечиваем минимальную прибыль $0.03
            target_profit = max(target_profit_raw, min_profit_usdt)
            
            # Рассчитываем новый SL на основе целевой прибыли
            new_sl = pos.entry + (target_profit / pos.qty)
            
            # Применяем минимальную защиту $0.03
            protected_sl = max(new_sl, min_sl)
            protection_applied = protected_sl > new_sl
            
            # КРИТИЧЕСКОЕ ПРАВИЛО: SL может ТОЛЬКО УЛУЧШАТЬСЯ (для лонгов - расти)
            if protected_sl > pos.sl:
                pos.sl = protected_sl
                pos.trailing_debug['sl_updated'] = True
                pos.trailing_debug['protection_applied'] = protection_applied
                pos.trailing_debug['protected_sl'] = protected_sl
                pos.trailing_debug['pnl_sl'] = new_sl
                logger.debug(f"📊 PnL-трейлинг: SL обновлен до ${protected_sl:.6f} (уровень {level_name}, цель: ${target_profit:.4f})")
            else:
                pos.trailing_debug['sl_updated'] = False
                logger.debug(f"📊 PnL-трейлинг: SL ${protected_sl:.6f} не лучше текущего ${pos.sl:.6f} (уровень {level_name})")
        else:
            pos.trailing_debug['sl_updated'] = False
            logger.debug(f"📊 PnL-трейлинг: неактивен, Peak PnL ${pos.peak_pnl_usdt:.4f} < ${cfg.level_1_pnl}")
    
    elif pos.side == Side.SHORT:
        # Текущий PnL для SHORT
        current_pnl_usdt = (pos.entry - lo) * pos.qty
        
        # Инициализируем отладочную информацию
        pos.trailing_debug = {
            'level': 'INACTIVE',
            'keep_pct': 0,
            'peak_pnl': pos.peak_pnl_usdt,
            'target_profit': 0,
            'current_pnl': current_pnl_usdt
        }
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Обновляем peak_pnl_usdt только при росте
        if current_pnl_usdt > 0:
            pos.peak_pnl_usdt = max(pos.peak_pnl_usdt, current_pnl_usdt)
        
        # ТРЕЙЛИНГ РАБОТАЕТ НА ОСНОВЕ PEAK PnL, даже если текущий PnL упал!
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
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Минимальная прибыль $0.03
            min_profit_usdt = 0.03
            
            max_sl = pos.entry - (min_profit_usdt / pos.qty)  # Максимальный SL (гарантируем $0.03)
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: ВСЕ уровни используют МАКСИМАЛЬНЫЙ PnL!
            target_profit_raw = pos.peak_pnl_usdt * keep_pct
            
            # Обеспечиваем минимальную прибыль $0.03
            target_profit = max(target_profit_raw, min_profit_usdt)
            
            # Рассчитываем новый SL на основе целевой прибыли
            new_sl = pos.entry - (target_profit / pos.qty)
            
            # Применяем минимальную защиту $0.03
            protected_sl = min(new_sl, max_sl)
            protection_applied = protected_sl < new_sl
            
            # КРИТИЧЕСКОЕ ПРАВИЛО: SL может ТОЛЬКО УЛУЧШАТЬСЯ (для шортов - падать)
            if protected_sl < pos.sl:
                pos.sl = protected_sl
                pos.trailing_debug['sl_updated'] = True
                pos.trailing_debug['protection_applied'] = protection_applied
                pos.trailing_debug['protected_sl'] = protected_sl
                pos.trailing_debug['pnl_sl'] = new_sl
                logger.debug(f"📊 PnL-трейлинг SHORT: SL обновлен до ${protected_sl:.6f} (уровень {level_name}, цель: ${target_profit:.4f})")
            else:
                pos.trailing_debug['sl_updated'] = False
                logger.debug(f"📊 PnL-трейлинг SHORT: SL ${protected_sl:.6f} не лучше текущего ${pos.sl:.6f} (уровень {level_name})")
        else:
            pos.trailing_debug['sl_updated'] = False
            logger.debug(f"📊 PnL-трейлинг SHORT: неактивен, Peak PnL ${pos.peak_pnl_usdt:.4f} < ${cfg.level_1_pnl}")
    
    return pos
