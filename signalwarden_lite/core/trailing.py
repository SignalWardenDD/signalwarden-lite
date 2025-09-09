from dataclasses import dataclass
from .types import Position, Side

@dataclass
class TrailingConfig:
    # Новая система трейлинга по уровням PnL в USDT
    activate_pnl_usdt: float = 0.10      # Активация трейлинга при 0.10 USDT PnL
    
    # Уровни сохранения прибыли
    level_1_pnl: float = 0.10           # 0.10 USDT - сохранить 50%
    level_1_keep_pct: float = 0.50      # 50%
    
    level_2_pnl: float = 0.20           # 0.20 USDT - сохранить 60%
    level_2_keep_pct: float = 0.60      # 60%
    
    level_3_pnl: float = 0.30           # 0.30 USDT - сохранить 70%
    level_3_keep_pct: float = 0.70      # 70%
    
    level_4_pnl: float = 0.40           # 0.40+ USDT - сохранить 80%
    level_4_keep_pct: float = 0.80      # 80%
    
    # Старые параметры для обратной совместимости
    activate_R: float = 0.35         # откуда начинать шаговый трейлинг
    step_R: float = 0.25             # шаг R для подтяжек
    move_to_be_at_R: float = 0.55    # когда перевести в BE
    be_offset_R: float = 0.06        # +δR поверх BE, чтобы покрыть комиссии/проскальзывание
    chandelier_k_atr: float = 3.0    # Chandelier-ATR доп. ограничитель

def update_trailing_pnl_based(pos: Position, current_price: float, current_pnl_usdt: float, cfg: TrailingConfig) -> Position:
    """
    Новая система трейлинга на основе PnL в USDT
    Уровневая система сохранения прибыли: 50%/60%/70%/80%
    Никогда не ухудшает SL, только улучшает
    """
    
    # Активация трейлинга только при достижении минимального PnL
    # ИСПРАВЛЕНО: используем <= чтобы активировать при точном равенстве 0.10 USDT
    if current_pnl_usdt < cfg.activate_pnl_usdt:
        return pos
    
    # Обновляем максимальный PnL (только улучшаем)
    pos.peak_pnl_usdt = max(pos.peak_pnl_usdt, current_pnl_usdt)
    
    # КРИТИЧЕСКИ ВАЖНО: Определяем уровень сохранения прибыли по МАКСИМАЛЬНОМУ PnL
    if pos.peak_pnl_usdt >= cfg.level_4_pnl:
        keep_pct = cfg.level_4_keep_pct  # 80%
        level_name = "L4"
    elif pos.peak_pnl_usdt >= cfg.level_3_pnl:
        keep_pct = cfg.level_3_keep_pct  # 70%
        level_name = "L3"
    elif pos.peak_pnl_usdt >= cfg.level_2_pnl:
        keep_pct = cfg.level_2_keep_pct  # 60%
        level_name = "L2"
    else:
        keep_pct = cfg.level_1_keep_pct  # 50%
        level_name = "L1"
    
    # Рассчитываем целевую прибыль для сохранения
    target_profit_usdt = pos.peak_pnl_usdt * keep_pct
    
    # Добавляем отладочную информацию
    pos.trailing_debug = {
        'level': level_name,
        'keep_pct': keep_pct,
        'peak_pnl': pos.peak_pnl_usdt,
        'target_profit': target_profit_usdt,
        'current_pnl': current_pnl_usdt,
        'sl_updated': False
    }
    
    # Сохраняем старый SL для сравнения
    old_sl = pos.sl
    
    # Рассчитываем новый stop loss на основе целевой прибыли
    if pos.side == Side.LONG:
        # Для лонгов: entry + target_profit_usdt / qty
        quantity = abs(pos.qty)
        if quantity > 0:
            new_sl = pos.entry + (target_profit_usdt / quantity)
            # Никогда не ухудшаем SL для лонгов (только увеличиваем)
            # ВАЖНО: используем небольшую толерантность для числовых ошибок
            if new_sl > pos.sl + 1e-8:  # Добавляем минимальную толерантность
                pos.sl = new_sl
                pos.trailing_debug['sl_updated'] = True
            else:
                pos.trailing_debug['sl_updated'] = False
                pos.trailing_debug['reason'] = f'new_sl {new_sl:.8f} <= current_sl {pos.sl:.8f}'
                
    else:  # SHORT
        # Для шортов: entry - target_profit_usdt / qty
        quantity = abs(pos.qty)
        if quantity > 0:
            new_sl = pos.entry - (target_profit_usdt / quantity)
            # Никогда не ухудшаем SL для шортов (только уменьшаем)
            # ВАЖНО: используем небольшую толерантность для числовых ошибок
            if new_sl < pos.sl - 1e-8:  # Добавляем минимальную толерантность
                pos.sl = new_sl
                pos.trailing_debug['sl_updated'] = True
            else:
                pos.trailing_debug['sl_updated'] = False
                pos.trailing_debug['reason'] = f'new_sl {new_sl:.8f} >= current_sl {pos.sl:.8f}'
    
    # Обновляем отладочную информацию
    pos.trailing_debug.update({
        'old_sl': old_sl,
        'new_sl': pos.sl,
        'sl_updated': pos.sl != old_sl
    })
    
    return pos

def update_trailing_hybrid(pos: Position, hi: float, lo: float, atr: float, cfg: TrailingConfig) -> Position:
    """
    Гибридный трейлинг: R-step + Chandelier-ATR + ранний BE+δ
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

    return pos

# Оставляем старую функцию для совместимости
def update_trailing(pos: Position, price_high: float, price_low: float, cfg: TrailingConfig):
    """Обратная совместимость со старым API"""
    return update_trailing_hybrid(pos, price_high, price_low, 0.0, cfg)