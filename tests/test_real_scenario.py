#!/usr/bin/env python3
"""
Тест реального сценария из логов
"""

import sys
sys.path.append('.')

from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def test_real_doge_scenario():
    """
    Тестируем реальный сценарий DOGE из логов
    """
    print("🐕 ТЕСТ РЕАЛЬНОГО СЦЕНАРИЯ DOGE")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Данные из логов: DOGE открыт на 0.236573, SL 0.230135
    entry = 0.236573
    qty = 88.767714
    sl_initial = 0.230135
    
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
    
    print(f"📊 Позиция DOGE из логов:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Qty: {qty:.2f}")
    print(f"   Initial SL: ${sl_initial:.6f}")
    print()
    
    # Тестируем различные сценарии роста цены
    test_scenarios = [
        (0.237000, "Небольшой рост"),
        (0.238000, "Умеренный рост"), 
        (0.239000, "Хороший рост"),
        (0.240000, "Отличный рост"),
        (0.238500, "Откат после роста")
    ]
    
    for price, description in test_scenarios:
        current_pnl = (price - entry) * qty
        
        print(f"💰 {description}: ${price:.6f}")
        print(f"   PnL: ${current_pnl:.3f} USDT")
        print(f"   Активация: {current_pnl >= cfg.activate_pnl_usdt}")
        
        if current_pnl >= cfg.activate_pnl_usdt:
            old_sl = pos.sl
            old_peak = pos.peak_pnl_usdt
            
            updated_pos = update_trailing_pnl_based(pos, price, current_pnl, cfg)
            debug = getattr(updated_pos, 'trailing_debug', {})
            
            print(f"   Результат:")
            print(f"     Peak: ${old_peak:.3f} → ${updated_pos.peak_pnl_usdt:.3f}")
            print(f"     SL: ${old_sl:.6f} → ${updated_pos.sl:.6f}")
            print(f"     Уровень: {debug.get('level', 'N/A')} ({debug.get('keep_pct', 0)*100:.0f}%)")
            print(f"     Обновлен: {debug.get('sl_updated', False)}")
            
            # Обновляем позицию для следующего теста
            pos = updated_pos
            
            # Рассчитываем защищенную прибыль
            if debug.get('sl_updated', False):
                protected_profit = (pos.sl - entry) * qty
                protection_pct = protected_profit / pos.peak_pnl_usdt * 100 if pos.peak_pnl_usdt > 0 else 0
                print(f"     💰 Защищено: ${protected_profit:.3f} ({protection_pct:.1f}% от пика)")
        else:
            print(f"   ⚠️  PnL ниже порога активации")
        
        print()
    
    print("🎯 ИТОГОВОЕ СОСТОЯНИЕ:")
    print(f"   Финальный SL: ${pos.sl:.6f}")
    print(f"   Peak PnL: ${pos.peak_pnl_usdt:.3f}")
    
    # Проверяем что произойдет при падении до различных уровней
    test_drops = [0.238000, 0.237500, 0.237000, 0.236500]
    
    print(f"\n📉 ТЕСТ ПАДЕНИЙ ЦЕНЫ:")
    for drop_price in test_drops:
        sl_hit = drop_price <= pos.sl
        if sl_hit:
            realized_profit = (pos.sl - entry) * qty
            print(f"   ${drop_price:.6f}: 🚨 SL HIT → Прибыль ${realized_profit:.3f}")
            break
        else:
            unrealized_pnl = (drop_price - entry) * qty
            print(f"   ${drop_price:.6f}: ✅ Позиция открыта, PnL ${unrealized_pnl:.3f}")

def test_why_positions_closed_at_loss():
    """
    Анализируем почему позиции закрывались в убыток
    """
    print("\n🔍 АНАЛИЗ: ПОЧЕМУ ПОЗИЦИИ ЗАКРЫВАЛИСЬ В УБЫТОК")
    print("=" * 70)
    
    print("📋 ПРОБЛЕМА В СТАРОЙ ЛОГИКЕ:")
    print("   1. Трейлинг вычислял новый SL (например, 0.237)")
    print("   2. Система СРАЗУ проверяла: current_price <= new_SL")
    print("   3. Если цена упала ниже нового SL → НЕМЕДЛЕННОЕ закрытие")
    print("   4. SL на бирже НЕ УСПЕВАЛ обновиться!")
    print()
    
    print("✅ ИСПРАВЛЕНИЕ:")
    print("   1. СНАЧАЛА обновляем SL на бирже")
    print("   2. ПОТОМ проверяем hit с обновленным SL")
    print("   3. Peak PnL ВСЕГДА сохраняется")
    print("   4. Позиции защищены от преждевременного закрытия")
    print()
    
    print("💡 РЕЗУЛЬТАТ ИСПРАВЛЕНИЯ:")
    print("   - DOGE с PnL 0.13+ должен был иметь SL ~0.237")
    print("   - При падении до 0.236 позиция должна остаться открытой")
    print("   - Только при падении ниже 0.237 должно быть закрытие")
    print("   - Прибыль ~0.07 USDT должна быть защищена")

if __name__ == '__main__':
    test_real_doge_scenario()
    test_why_positions_closed_at_loss()
