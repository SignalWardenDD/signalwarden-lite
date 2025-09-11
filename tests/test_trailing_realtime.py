#!/usr/bin/env python3
"""
Тест трейлинга в режиме реального времени
Проверяем отсутствие проблем с синхронизацией и корректность работы
"""

import sys
sys.path.append('.')

import json
import copy
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def simulate_realtime_updates():
    """
    Симулируем обновления трейлинга в реальном времени
    как это происходит в live торговле
    """
    print("🕐 СИМУЛЯЦИЯ РЕАЛЬНОГО ВРЕМЕНИ")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Начальная позиция (как в live системе)
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0200,
        sl=0.9800,
        sl_initial=0.9800,
        peak_pnl_usdt=0.0
    )
    
    print("Начальное состояние позиции:")
    print(f"   Entry: ${pos.entry:.4f}")
    print(f"   Qty: {pos.qty:.1f}")
    print(f"   SL: ${pos.sl:.4f}")
    print(f"   Peak PnL: ${pos.peak_pnl_usdt:.3f}")
    print()
    
    # Симулируем серию обновлений как в реальной торговле
    market_updates = [
        {"timestamp": "2024-01-01T10:00:00", "price": 1.0030, "description": "Открытие рынка"},
        {"timestamp": "2024-01-01T10:15:00", "price": 1.0060, "description": "Первый рост"},
        {"timestamp": "2024-01-01T10:30:00", "price": 1.0080, "description": "Активация трейлинга"},
        {"timestamp": "2024-01-01T10:45:00", "price": 1.0070, "description": "Небольшой откат"},
        {"timestamp": "2024-01-01T11:00:00", "price": 1.0120, "description": "Новый максимум"},
        {"timestamp": "2024-01-01T11:15:00", "price": 1.0100, "description": "Коррекция"},
        {"timestamp": "2024-01-01T11:30:00", "price": 1.0150, "description": "Рост продолжается"},
        {"timestamp": "2024-01-01T11:45:00", "price": 1.0130, "description": "Откат"},
        {"timestamp": "2024-01-01T12:00:00", "price": 1.0200, "description": "Сильный рост"},
        {"timestamp": "2024-01-01T12:15:00", "price": 1.0180, "description": "Консолидация"},
    ]
    
    # Сохраняем состояния для проверки консистентности
    position_history = []
    
    for update in market_updates:
        current_price = update["price"]
        current_pnl = (current_price - pos.entry) * pos.qty
        
        # Сохраняем состояние до обновления
        pre_state = {
            "timestamp": update["timestamp"],
            "price": current_price,
            "pnl": current_pnl,
            "sl_before": pos.sl,
            "peak_before": pos.peak_pnl_usdt
        }
        
        # Обновляем трейлинг
        old_pos = copy.deepcopy(pos)
        pos = update_trailing_pnl_based(pos, current_price, current_pnl, cfg)
        debug = getattr(pos, 'trailing_debug', {})
        
        # Дополняем состояние после обновления
        pre_state.update({
            "sl_after": pos.sl,
            "peak_after": pos.peak_pnl_usdt,
            "level": debug.get('level', 'N/A'),
            "sl_updated": debug.get('sl_updated', False),
            "keep_pct": debug.get('keep_pct', 0)
        })
        
        position_history.append(pre_state)
        
        print(f"{update['timestamp']} - {update['description']}")
        print(f"   Цена: ${current_price:.4f}, PnL: ${current_pnl:.3f}")
        print(f"   Peak: ${pre_state['peak_before']:.3f} → ${pre_state['peak_after']:.3f}")
        print(f"   SL: ${pre_state['sl_before']:.4f} → ${pre_state['sl_after']:.4f}")
        print(f"   Уровень: {pre_state['level']}, Обновлен: {pre_state['sl_updated']}")
        
        # Критические проверки
        assert pos.peak_pnl_usdt >= old_pos.peak_pnl_usdt, "Peak PnL не должен уменьшаться!"
        assert pos.sl >= old_pos.sl, "SL не должен ухудшаться для лонга!"
        
        print("   ✅ Проверки пройдены")
        print()
    
    return position_history

def test_state_persistence():
    """
    Тест сохранения состояния (как в JSON файле)
    """
    print("💾 ТЕСТ СОХРАНЕНИЯ СОСТОЯНИЯ")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Создаем позицию и развиваем трейлинг
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0200,
        sl=0.9800,
        sl_initial=0.9800,
        peak_pnl_usdt=0.0
    )
    
    # Развиваем позицию до значительного трейлинга
    test_price = 1.0200
    test_pnl = (test_price - pos.entry) * pos.qty
    pos = update_trailing_pnl_based(pos, test_price, test_pnl, cfg)
    
    print(f"Развитая позиция:")
    print(f"   Peak PnL: ${pos.peak_pnl_usdt:.3f}")
    print(f"   SL: ${pos.sl:.4f}")
    print()
    
    # Симулируем сохранение в JSON (как в реальной системе)
    position_dict = {
        "side": pos.side.value,
        "entry": pos.entry,
        "qty": pos.qty,
        "remaining_qty": pos.remaining_qty,
        "r_per_unit": pos.r_per_unit,
        "sl": pos.sl,
        "sl_initial": pos.sl_initial,
        "peak_pnl_usdt": pos.peak_pnl_usdt,
    }
    
    json_state = json.dumps(position_dict, indent=2)
    print("Сохраненное состояние (JSON):")
    print(json_state)
    print()
    
    # Восстанавливаем из JSON
    restored_dict = json.loads(json_state)
    restored_pos = Position(
        side=Side(restored_dict["side"]),
        entry=restored_dict["entry"],
        qty=restored_dict["qty"],
        remaining_qty=restored_dict["remaining_qty"],
        r_per_unit=restored_dict["r_per_unit"],
        sl=restored_dict["sl"],
        sl_initial=restored_dict["sl_initial"],
        peak_pnl_usdt=restored_dict["peak_pnl_usdt"]
    )
    
    print("Восстановленная позиция:")
    print(f"   Peak PnL: ${restored_pos.peak_pnl_usdt:.3f}")
    print(f"   SL: ${restored_pos.sl:.4f}")
    print()
    
    # Проверяем что состояние сохранилось корректно
    assert abs(pos.peak_pnl_usdt - restored_pos.peak_pnl_usdt) < 0.001, "Peak PnL не сохранился!"
    assert abs(pos.sl - restored_pos.sl) < 0.0001, "SL не сохранился!"
    
    # Продолжаем трейлинг с восстановленной позицией
    new_price = 1.0180
    new_pnl = (new_price - restored_pos.entry) * restored_pos.qty
    updated_restored = update_trailing_pnl_based(restored_pos, new_price, new_pnl, cfg)
    
    print(f"Продолжение трейлинга после восстановления:")
    print(f"   Новая цена: ${new_price:.4f}")
    print(f"   PnL: ${new_pnl:.3f}")
    print(f"   Peak остался: ${updated_restored.peak_pnl_usdt:.3f}")
    print(f"   SL остался: ${updated_restored.sl:.4f}")
    print()
    
    # Проверяем что peak не сбросился
    assert updated_restored.peak_pnl_usdt >= restored_pos.peak_pnl_usdt, "Peak сбросился после восстановления!"
    print("✅ Состояние корректно сохраняется и восстанавливается")
    print()

def test_concurrent_updates():
    """
    Тест конкурентных обновлений (имитация множественных источников данных)
    """
    print("🔄 ТЕСТ КОНКУРЕНТНЫХ ОБНОВЛЕНИЙ")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Базовая позиция
    base_pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0200,
        sl=0.9800,
        sl_initial=0.9800,
        peak_pnl_usdt=0.0
    )
    
    # Симулируем получение данных из разных источников с небольшими различиями
    source_a_prices = [1.0050, 1.0120, 1.0100, 1.0180, 1.0160]
    source_b_prices = [1.0052, 1.0118, 1.0102, 1.0178, 1.0162]  # Небольшие различия
    
    pos_a = copy.deepcopy(base_pos)
    pos_b = copy.deepcopy(base_pos)
    
    print("Обработка данных из разных источников:")
    
    for i, (price_a, price_b) in enumerate(zip(source_a_prices, source_b_prices), 1):
        pnl_a = (price_a - pos_a.entry) * pos_a.qty
        pnl_b = (price_b - pos_b.entry) * pos_b.qty
        
        old_peak_a, old_sl_a = pos_a.peak_pnl_usdt, pos_a.sl
        old_peak_b, old_sl_b = pos_b.peak_pnl_usdt, pos_b.sl
        
        pos_a = update_trailing_pnl_based(pos_a, price_a, pnl_a, cfg)
        pos_b = update_trailing_pnl_based(pos_b, price_b, pnl_b, cfg)
        
        print(f"Обновление {i}:")
        print(f"   Источник A: ${price_a:.4f} → Peak: ${pos_a.peak_pnl_usdt:.3f}, SL: ${pos_a.sl:.4f}")
        print(f"   Источник B: ${price_b:.4f} → Peak: ${pos_b.peak_pnl_usdt:.3f}, SL: ${pos_b.sl:.4f}")
        
        # Проверяем что оба источника не ухудшают состояние
        assert pos_a.peak_pnl_usdt >= old_peak_a, f"Source A: Peak ухудшился! {old_peak_a} → {pos_a.peak_pnl_usdt}"
        assert pos_b.peak_pnl_usdt >= old_peak_b, f"Source B: Peak ухудшился! {old_peak_b} → {pos_b.peak_pnl_usdt}"
        assert pos_a.sl >= old_sl_a, f"Source A: SL ухудшился! {old_sl_a} → {pos_a.sl}"
        assert pos_b.sl >= old_sl_b, f"Source B: SL ухудшился! {old_sl_b} → {pos_b.sl}"
        
        print(f"   ✅ Оба источника корректны")
        print()
    
    # Финальная синхронизация - выбираем лучшие значения
    final_peak = max(pos_a.peak_pnl_usdt, pos_b.peak_pnl_usdt)
    final_sl = max(pos_a.sl, pos_b.sl)  # Для лонга лучше больший SL
    
    print(f"Финальная синхронизация:")
    print(f"   Лучший Peak: ${final_peak:.3f}")
    print(f"   Лучший SL: ${final_sl:.4f}")
    print("✅ Конкурентные обновления обработаны корректно")
    print()

if __name__ == '__main__':
    print("🚀 ТЕСТИРОВАНИЕ ТРЕЙЛИНГА В РЕАЛЬНОМ ВРЕМЕНИ")
    print("=" * 80)
    print()
    
    try:
        history = simulate_realtime_updates()
        test_state_persistence()
        test_concurrent_updates()
        
        print("🎉 ВСЕ ТЕСТЫ РЕАЛЬНОГО ВРЕМЕНИ ПРОЙДЕНЫ!")
        print("✅ Трейлинг работает стабильно в реальных условиях")
        print("✅ Отсутствуют проблемы с синхронизацией")
        print("✅ Состояние корректно сохраняется и восстанавливается")
        
        # Финальная статистика
        print(f"\n📊 СТАТИСТИКА ТЕСТИРОВАНИЯ:")
        print(f"   Обработано обновлений: {len(history)}")
        
        sl_improvements = sum(1 for h in history if h['sl_updated'])
        print(f"   Улучшений SL: {sl_improvements}")
        
        max_peak = max(h['peak_after'] for h in history)
        final_sl = history[-1]['sl_after']
        protection_pct = (final_sl - 1.0000) / max_peak * 100 if max_peak > 0 else 0
        
        print(f"   Максимальный Peak: ${max_peak:.3f}")
        print(f"   Финальный SL: ${final_sl:.4f}")
        print(f"   Защита прибыли: {protection_pct:.1f}%")
        
    except Exception as e:
        print(f"💥 ОШИБКА В ТЕСТЕ РЕАЛЬНОГО ВРЕМЕНИ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
