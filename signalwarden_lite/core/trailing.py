from dataclasses import dataclass
from .types import Position, Side

@dataclass
class TrailingConfig:
    activate_R: float = 0.35         # откуда начинать шаговый трейлинг
    step_R: float = 0.25             # шаг R для подтяжек
    move_to_be_at_R: float = 0.55    # когда перевести в BE
    be_offset_R: float = 0.06        # +δR поверх BE, чтобы покрыть комиссии/проскальзывание
    chandelier_k_atr: float = 3.0    # Chandelier-ATR доп. ограничитель

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