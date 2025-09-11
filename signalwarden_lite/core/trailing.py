from dataclasses import dataclass
from .types import Position, Side

@dataclass
class TrailingConfig:
    # ОРИГИНАЛЬНАЯ гибридная trailing система (из прибыльного коммита)
    activate_R: float = 0.35         # откуда начинать шаговый трейлинг
    step_R: float = 0.25             # шаг R для подтяжек
    move_to_be_at_R: float = 0.55    # когда перевести в BE
    be_offset_R: float = 0.06        # +δR поверх BE, чтобы покрыть комиссии/проскальзывание
    chandelier_k_atr: float = 3.0    # Chandelier-ATR доп. ограничитель
    
    # PnL-based уровни сохранения прибыли (ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА)
    level_1_pnl: float = 0.06           # $0.06 - сохранить 50%
    level_1_keep_pct: float = 0.50      # 50%
    level_2_pnl: float = 0.15           # $0.15 - сохранить 60%
    level_2_keep_pct: float = 0.60      # 60%
    level_3_pnl: float = 0.25           # $0.25 - сохранить 70%
    level_3_keep_pct: float = 0.70      # 70%
    level_4_pnl: float = 0.35           # $0.35+ - сохранить 80%
    level_4_keep_pct: float = 0.80      # 80%

def update_trailing_hybrid(pos: Position, hi: float, lo: float, atr: float, cfg: TrailingConfig) -> Position:
    """
    ГИБРИДНАЯ система трейлинга (из прибыльного коммита):
    R-step + Chandelier-ATR + ранний BE+δ + PnL-based уровни
    Никогда не ухудшает SL, только улучшает
    """
    
    def _apply_be(p: Position):
        """Применить Break-Even с небольшим отступом для покрытия комиссий"""
        if p.be_applied: 
            return
        if p.side == Side.LONG:
            be_price = p.entry + cfg.be_offset_R * p.r_per_unit
            p.sl = max(p.sl, be_price)
        else:
            be_price = p.entry - cfg.be_offset_R * p.r_per_unit
            p.sl = min(p.sl, be_price)
        p.be_applied = True

    # Расчет для LONG позиций
    if pos.side == Side.LONG:
        r_unit = pos.entry - pos.sl_initial
        if r_unit <= 0: 
            return pos
        
        # Текущее движение в нашу пользу
        move = hi - pos.entry
        pos.peak_R = max(pos.peak_R, move / r_unit)

        # 1) Перевод в BE+δ при достижении порога
        if (not pos.be_applied) and pos.peak_R >= cfg.move_to_be_at_R:
            _apply_be(pos)

        # 2) R-step трейлинг
        if pos.peak_R >= cfg.activate_R:
            new_sl_r = pos.peak_R - cfg.step_R
            step_sl = pos.entry + new_sl_r * r_unit
            if step_sl > pos.sl:
                pos.sl = step_sl

        # 3) Chandelier-ATR ограничитель
        chandelier_sl = hi - cfg.chandelier_k_atr * atr
        if chandelier_sl > pos.sl:
            pos.sl = chandelier_sl

        # 4) PnL-based уровни (ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА)
        current_pnl_usdt = (hi - pos.entry) * pos.qty
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
            
            if keep_pct > 0:
                # ЗАЩИТА МИНИМАЛЬНОЙ ПРИБЫЛИ $0.03
                min_profit_usdt = 0.03  # Минимальная прибыль $0.03
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: ВСЕ уровни используют МАКСИМАЛЬНЫЙ PnL!
                # Это означает, что SL всегда растет и никогда не падает внутри уровня
                target_profit = pos.peak_pnl_usdt * keep_pct
                
                # ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА: target_profit не может быть меньше $0.03
                target_profit = max(target_profit, min_profit_usdt)
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: SL должен быть на уровне entry + сохраненная прибыль на единицу
                # Для LONG: (SL - entry) * qty = target_profit, поэтому SL = entry + (target_profit / qty)
                pnl_sl = pos.entry + (target_profit / pos.qty)
                
                # ЗАЩИТА: Минимальный SL для LONG
                min_sl = pos.entry + (min_profit_usdt / pos.qty)
                protected_sl = max(pnl_sl, min_sl)
                
                if protected_sl > pos.sl:
                    pos.sl = protected_sl
                    
                # Добавляем отладочную информацию
                pos.trailing_debug = {
                    'level': level_name,
                    'keep_pct': keep_pct,
                    'peak_pnl': pos.peak_pnl_usdt,
                    'target_profit': target_profit,
                    'current_pnl': current_pnl_usdt,
                    'sl_updated': pnl_sl > pos.sl
                }


    # Расчет для SHORT позиций
    else:  # SHORT
        r_unit = pos.sl_initial - pos.entry
        if r_unit <= 0: 
            return pos
        
        # Текущее движение в нашу пользу
        move = pos.entry - lo
        pos.peak_R = max(pos.peak_R, move / r_unit)

        # 1) Перевод в BE+δ при достижении порога
        if (not pos.be_applied) and pos.peak_R >= cfg.move_to_be_at_R:
            _apply_be(pos)

        # 2) R-step трейлинг
        if pos.peak_R >= cfg.activate_R:
            new_sl_r = pos.peak_R - cfg.step_R
            step_sl = pos.entry - new_sl_r * r_unit
            if step_sl < pos.sl:
                pos.sl = step_sl

        # 3) Chandelier-ATR ограничитель
        chandelier_sl = lo + cfg.chandelier_k_atr * atr
        if chandelier_sl < pos.sl:
            pos.sl = chandelier_sl

        # 4) PnL-based уровни (ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА)
        current_pnl_usdt = (pos.entry - lo) * pos.qty
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
            
            if keep_pct > 0:
                # ЗАЩИТА МИНИМАЛЬНОЙ ПРИБЫЛИ $0.03
                min_profit_usdt = 0.03  # Минимальная прибыль $0.03
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: ВСЕ уровни используют МАКСИМАЛЬНЫЙ PnL!
                # Это означает, что SL всегда растет и никогда не падает внутри уровня
                target_profit = pos.peak_pnl_usdt * keep_pct
                
                # ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА: target_profit не может быть меньше $0.03
                target_profit = max(target_profit, min_profit_usdt)
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: SL должен быть на уровне entry - сохраненная прибыль на единицу
                # Для SHORT: (entry - SL) * qty = target_profit, поэтому SL = entry - (target_profit / qty)
                pnl_sl = pos.entry - (target_profit / pos.qty)
                
                # ЗАЩИТА: Минимальный SL для SHORT
                min_sl = pos.entry - (min_profit_usdt / pos.qty)
                protected_sl = min(pnl_sl, min_sl)
                
                if protected_sl < pos.sl:
                    pos.sl = protected_sl
                    
                # Добавляем отладочную информацию
                pos.trailing_debug = {
                    'level': level_name,
                    'keep_pct': keep_pct,
                    'peak_pnl': pos.peak_pnl_usdt,
                    'target_profit': target_profit,
                    'current_pnl': current_pnl_usdt,
                    'sl_updated': pnl_sl < pos.sl
                }


    return pos

# Оставляем старую функцию для совместимости
def update_trailing(pos: Position, price_high: float, price_low: float, cfg: TrailingConfig):
    """Обратная совместимость со старым API"""
    return update_trailing_hybrid(pos, price_high, price_low, 0.0, cfg)