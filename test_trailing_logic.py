#!/usr/bin/env python3
"""
Тест логики трейлинга SignalWarden v1.6-TXB
Проверяем правильность работы PnL-based trailing системы
"""

import sys
sys.path.append('.')

from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def test_long_trailing():
    """Тест трейлинга для длинной позиции"""
    print("🔍 ТЕСТ ТРЕЙЛИНГА ДЛЯ ДЛИННОЙ ПОЗИЦИИ")
    print("=" * 60)
    
    # Создаем конфигурацию трейлинга
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,  # 50%
        level_2_pnl=0.20, level_2_keep_pct=0.60,  # 60%
        level_3_pnl=0.30, level_3_keep_pct=0.70,  # 70%
        level_4_pnl=0.40, level_4_keep_pct=0.80   # 80%
    )
    
    # Создаем позицию: ADA LONG @ $0.8347, qty=25.1, SL @ $0.8150
    pos = Position(
        side=Side.LONG,
        entry=0.8347,
        qty=25.1,  # $21 notional / $0.8347 = 25.1 ADA
        remaining_qty=25.1,
        r_per_unit=0.8347 - 0.8150,  # 0.0197
        sl=0.8150,  # Initial SL
        sl_initial=0.8150,
        peak_pnl_usdt=0.0
    )
    
    print(f"📊 Начальная позиция:")
    print(f"   Entry: ${pos.entry:.4f}")
    print(f"   Qty: {pos.qty:.1f} ADA")
    print(f"   Initial SL: ${pos.sl:.4f}")
    print()
    
    # Сценарий 1: Цена поднимается до $0.8400 (PnL = +$0.133)
    current_price = 0.8400
    current_pnl = (current_price - pos.entry) * pos.qty
    print(f"📈 Сценарий 1: Цена ${current_price:.4f}")
    print(f"   Current PnL: ${current_pnl:.3f} USDT")
    
    updated_pos = update_trailing_pnl_based(pos, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    print(f"   Трейлинг активен: {current_pnl >= cfg.activate_pnl_usdt}")
    print(f"   Уровень: {debug.get('level', 'N/A')}")
    print(f"   Сохранить: {debug.get('keep_pct', 0)*100:.0f}% от пика")
    print(f"   Peak PnL: ${debug.get('peak_pnl', 0):.3f}")
    print(f"   Target Profit: ${debug.get('target_profit', 0):.3f}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print(f"   Новый SL: ${updated_pos.sl:.4f}")
    print()
    
    # Сценарий 2: Цена поднимается до $0.8500 (PnL = +$0.384)
    current_price = 0.8500
    current_pnl = (current_price - pos.entry) * pos.qty
    print(f"📈 Сценарий 2: Цена ${current_price:.4f}")
    print(f"   Current PnL: ${current_pnl:.3f} USDT")
    
    updated_pos = update_trailing_pnl_based(updated_pos, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    print(f"   Уровень: {debug.get('level', 'N/A')}")
    print(f"   Сохранить: {debug.get('keep_pct', 0)*100:.0f}% от пика")
    print(f"   Peak PnL: ${debug.get('peak_pnl', 0):.3f}")
    print(f"   Target Profit: ${debug.get('target_profit', 0):.3f}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print(f"   Новый SL: ${updated_pos.sl:.4f}")
    print()
    
    # Сценарий 3: Цена немного падает до $0.8450 (должен сохранить прибыль)
    current_price = 0.8450
    current_pnl = (current_price - pos.entry) * pos.qty
    print(f"📉 Сценарий 3: Цена падает до ${current_price:.4f}")
    print(f"   Current PnL: ${current_pnl:.3f} USDT")
    
    updated_pos = update_trailing_pnl_based(updated_pos, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    print(f"   Уровень: {debug.get('level', 'N/A')} (по максимальному PnL)")
    print(f"   Сохранить: {debug.get('keep_pct', 0)*100:.0f}% от пика")
    print(f"   Peak PnL: ${debug.get('peak_pnl', 0):.3f} (не изменился)")
    print(f"   Target Profit: ${debug.get('target_profit', 0):.3f}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print(f"   SL остался: ${updated_pos.sl:.4f}")
    print()
    
    # Проверим расчет прибыли при закрытии по SL
    sl_pnl = (updated_pos.sl - pos.entry) * pos.qty
    print(f"💰 РЕЗУЛЬТАТ:")
    print(f"   Если закроется по SL ${updated_pos.sl:.4f}")
    print(f"   Прибыль: ${sl_pnl:.3f} USDT")
    print(f"   Сохранено: {sl_pnl/debug.get('peak_pnl', 1)*100:.1f}% от пика")
    print()

def test_short_trailing():
    """Тест трейлинга для короткой позиции"""
    print("🔍 ТЕСТ ТРЕЙЛИНГА ДЛЯ КОРОТКОЙ ПОЗИЦИИ")
    print("=" * 60)
    
    # Создаем конфигурацию трейлинга
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,  # 50%
        level_2_pnl=0.20, level_2_keep_pct=0.60,  # 60%
        level_3_pnl=0.30, level_3_keep_pct=0.70,  # 70%
        level_4_pnl=0.40, level_4_keep_pct=0.80   # 80%
    )
    
    # Создаем позицию: DOGE SHORT @ $0.2320, qty=-90.5, SL @ $0.2380
    pos = Position(
        side=Side.SHORT,
        entry=0.2320,
        qty=-90.5,  # $21 notional / $0.2320 = 90.5 DOGE (отрицательное для шорта)
        remaining_qty=-90.5,
        r_per_unit=0.2380 - 0.2320,  # 0.0060
        sl=0.2380,  # Initial SL
        sl_initial=0.2380,
        peak_pnl_usdt=0.0
    )
    
    print(f"📊 Начальная позиция:")
    print(f"   Entry: ${pos.entry:.4f}")
    print(f"   Qty: {pos.qty:.1f} DOGE")
    print(f"   Initial SL: ${pos.sl:.4f}")
    print()
    
    # Сценарий 1: Цена падает до $0.2300 (PnL = +$0.181)
    current_price = 0.2300
    current_pnl = (pos.entry - current_price) * abs(pos.qty)  # Для шорта
    print(f"📉 Сценарий 1: Цена ${current_price:.4f}")
    print(f"   Current PnL: ${current_pnl:.3f} USDT")
    
    updated_pos = update_trailing_pnl_based(pos, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    print(f"   Трейлинг активен: {current_pnl >= cfg.activate_pnl_usdt}")
    print(f"   Уровень: {debug.get('level', 'N/A')}")
    print(f"   Сохранить: {debug.get('keep_pct', 0)*100:.0f}% от пика")
    print(f"   Peak PnL: ${debug.get('peak_pnl', 0):.3f}")
    print(f"   Target Profit: ${debug.get('target_profit', 0):.3f}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print(f"   Новый SL: ${updated_pos.sl:.4f}")
    print()
    
    # Проверим расчет прибыли при закрытии по SL
    sl_pnl = (pos.entry - updated_pos.sl) * abs(pos.qty)
    print(f"💰 РЕЗУЛЬТАТ:")
    print(f"   Если закроется по SL ${updated_pos.sl:.4f}")
    print(f"   Прибыль: ${sl_pnl:.3f} USDT")
    print(f"   Сохранено: {sl_pnl/debug.get('peak_pnl', 1)*100:.1f}% от пика")
    print()

def test_edge_cases():
    """Тест граничных случаев"""
    print("🔍 ТЕСТ ГРАНИЧНЫХ СЛУЧАЕВ")
    print("=" * 60)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=1.0000 - 0.9500,  # 0.0500
        sl=0.9500,
        sl_initial=0.9500,
        peak_pnl_usdt=0.0
    )
    
    print("Тест 1: PnL ниже порога активации")
    current_pnl = 0.05  # Ниже 0.10
    updated_pos = update_trailing_pnl_based(pos, 1.0025, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    print(f"   PnL: ${current_pnl:.3f} < ${cfg.activate_pnl_usdt:.2f}")
    print(f"   SL изменился: {updated_pos.sl != pos.sl}")
    print(f"   SL: ${updated_pos.sl:.4f} (должен остаться ${pos.sl:.4f})")
    print()
    
    print("Тест 2: Попытка ухудшить SL")
    pos.sl = 1.0100  # Установим хороший SL
    pos.peak_pnl_usdt = 0.30  # Установим хороший пик
    current_pnl = 0.15  # Текущий PnL ниже пика
    updated_pos = update_trailing_pnl_based(pos, 1.0075, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    print(f"   Старый SL: ${pos.sl:.4f}")
    print(f"   Попытка установить: ${debug.get('target_profit', 0)/pos.qty + pos.entry:.4f}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print(f"   Финальный SL: ${updated_pos.sl:.4f} (не должен ухудшиться)")
    print()

if __name__ == '__main__':
    print("🚀 ТЕСТИРОВАНИЕ ЛОГИКИ ТРЕЙЛИНГА SignalWarden v1.6-TXB")
    print("=" * 70)
    print()
    
    test_long_trailing()
    test_short_trailing()
    test_edge_cases()
    
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
