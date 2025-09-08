#!/usr/bin/env python3
"""
Диагностика проблемы трейлинга - почему позиции закрываются в маленький убыток
"""

import sys
sys.path.append('.')

from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def analyze_pnut_case():
    """
    Анализируем случай PNUT из логов
    """
    print("🔍 АНАЛИЗ СЛУЧАЯ PNUT ИЗ ЛОГОВ")
    print("=" * 70)
    
    # Конфигурация из config_production.yaml
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # PNUT из логов:
    # Entry: 0.233207, SL initial: 0.223694, Qty: 90.048909
    # Трейлинг активировался при PnL: 0.10 USDT (L1: 50%)
    # Последний трейлинг SL: 0.235182, PnL: 0.30 USDT (L2: 60%)
    # Закрылся по SL: 0.235160 - НО ЭТО МЕНЬШЕ ПОСЛЕДНЕГО ТРЕЙЛИНГ SL!
    
    entry = 0.233207
    qty = 90.048909
    sl_initial = 0.223694
    last_trailing_sl = 0.235182
    actual_close_price = 0.235160  # Из логов "SL hit at 0.235160"
    
    print(f"📊 Данные PNUT из логов:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Qty: {qty:.2f}")
    print(f"   Initial SL: ${sl_initial:.6f}")
    print(f"   Последний трейлинг SL: ${last_trailing_sl:.6f}")
    print(f"   Фактическая цена закрытия: ${actual_close_price:.6f}")
    print()
    
    # Рассчитываем что должно было быть
    actual_pnl = (actual_close_price - entry) * qty
    print(f"💰 Фактический результат:")
    print(f"   PnL: ${actual_pnl:.3f} USDT")
    print()
    
    # Что должно было быть при правильном трейлинге
    if last_trailing_sl > sl_initial:
        expected_pnl = (last_trailing_sl - entry) * qty
        print(f"✅ Ожидаемый результат при правильном трейлинге:")
        print(f"   SL должен был быть: ${last_trailing_sl:.6f}")
        print(f"   PnL должен был быть: ${expected_pnl:.3f} USDT")
        print()
        
        # Анализируем проблему
        if actual_close_price < last_trailing_sl:
            print("🚨 ПРОБЛЕМА НАЙДЕНА:")
            print(f"   Позиция закрылась по цене ${actual_close_price:.6f}")
            print(f"   НО последний трейлинг SL был ${last_trailing_sl:.6f}")
            print(f"   Разница: {last_trailing_sl - actual_close_price:.6f}")
            print()
            print("🔍 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
            print("   1. Старый SL ордер не был отменен вовремя")
            print("   2. Новый SL ордер не был создан/активирован")
            print("   3. Race condition между обновлением SL и проверкой hit")
            print("   4. Биржа исполнила старый SL ордер")
    
    print()
    
    # Тестируем минимальную логику трейлинга
    print("🧪 ТЕСТ МИНИМАЛЬНОГО ТРЕЙЛИНГА:")
    
    # Создаем позицию с минимальным PnL для активации
    pos = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=entry - sl_initial,
        sl=sl_initial,
        sl_initial=sl_initial,
        peak_pnl_usdt=0.0
    )
    
    # PnL ровно на пороге активации
    threshold_price = entry + (cfg.activate_pnl_usdt / qty)
    threshold_pnl = cfg.activate_pnl_usdt
    
    print(f"   Цена активации трейлинга: ${threshold_price:.6f}")
    print(f"   PnL активации: ${threshold_pnl:.3f} USDT")
    
    updated_pos = update_trailing_pnl_based(pos, threshold_price, threshold_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    if updated_pos.sl > pos.sl:
        min_profit = (updated_pos.sl - entry) * qty
        print(f"   Новый SL: ${updated_pos.sl:.6f}")
        print(f"   Минимальная защищенная прибыль: ${min_profit:.3f} USDT")
        print(f"   Уровень: {debug.get('level')} ({debug.get('keep_pct', 0)*100:.0f}%)")
        
        if min_profit < 0.05:
            print(f"   🚨 ОШИБКА: Минимальная прибыль {min_profit:.3f} < 0.05 USDT!")
        else:
            print(f"   ✅ Минимальная прибыль корректна")
    else:
        print(f"   ❌ SL не обновился!")

def analyze_wif_case():
    """
    Анализируем случай WIF - убыток -0.04 USDT
    """
    print("\n🔍 АНАЛИЗ СЛУЧАЯ WIF - УБЫТОК")
    print("=" * 70)
    
    # WIF из Binance истории: -0.04 USDT
    # Это НЕВОЗМОЖНО при правильном трейлинге!
    
    print("📊 WIF закрылся в убыток -0.04 USDT")
    print("🚨 ЭТО КРИТИЧЕСКАЯ ОШИБКА!")
    print()
    print("При правильном трейлинге:")
    print("   - Активация при PnL ≥ 0.10 USDT")
    print("   - Сохранение минимум 50% прибыли = 0.05 USDT")
    print("   - УБЫТКИ НЕВОЗМОЖНЫ после активации трейлинга!")
    print()
    print("🔍 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
    print("   1. Трейлинг вообще не активировался")
    print("   2. Позиция закрылась по ИЗНАЧАЛЬНОМУ SL")
    print("   3. Ошибка в логике проверки SL hit")
    print("   4. Проблема с синхронизацией ордеров на бирже")

def main():
    print("🚨 ДИАГНОСТИКА ПРОБЛЕМЫ ТРЕЙЛИНГА")
    print("=" * 70)
    print("Анализируем почему позиции закрываются с маленькими убытками")
    print("вместо защищенной прибыли от трейлинга")
    print()
    
    analyze_pnut_case()
    analyze_wif_case()
    
    print("\n💡 РЕКОМЕНДАЦИИ ДЛЯ ИСПРАВЛЕНИЯ:")
    print("=" * 70)
    print("1. Исправить race condition в update_sliding_stop_loss")
    print("2. Добавить проверку что новый SL действительно активен")
    print("3. Логировать все изменения SL ордеров с временными метками")
    print("4. Добавить защиту от закрытия по старым SL ордерам")
    print("5. Проверить что _fast_trailing_loop работает корректно")

if __name__ == '__main__':
    main()
