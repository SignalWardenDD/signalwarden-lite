#!/usr/bin/env python3
"""
Анализ закрытия ADA позиции
"""

def analyze_ada_close():
    print("🔍 АНАЛИЗ ЗАКРЫТИЯ ПОЗИЦИИ ADA")
    print("=" * 50)
    
    # Данные из скриншота и логов
    entry_price = 0.89150  # Цена входа
    exit_price = 0.89190   # Цена закрытия (средняя)
    qty = 23.0            # Количество из логов
    roi_percent = 0.22    # ROI из скриншота
    final_pnl = 0.00      # Финальный PnL из скриншота
    
    print(f"📊 Данные позиции:")
    print(f"   Entry: ${entry_price}")
    print(f"   Exit:  ${exit_price}")
    print(f"   Qty:   {qty} ADA")
    print(f"   ROI:   +{roi_percent}%")
    print(f"   Final PnL: ${final_pnl}")
    
    # Расчет PnL до комиссий
    pnl_before_fees = (exit_price - entry_price) * qty
    print(f"\n📈 PnL до комиссий: ${pnl_before_fees:.6f}")
    
    # Расчет комиссий по разным сценариям
    position_value = entry_price * qty
    
    print(f"\n💰 Анализ комиссий:")
    print(f"   Стоимость позиции: ${position_value:.2f}")
    
    # Сценарий 1: Обе операции taker (0.05%)
    taker_fee = 0.0005
    commission_taker_both = position_value * taker_fee * 2
    pnl_taker_both = pnl_before_fees - commission_taker_both
    print(f"   1. Обе taker (0.05%): Комиссия ${commission_taker_both:.6f}, PnL ${pnl_taker_both:.6f}")
    
    # Сценарий 2: Entry maker, exit taker
    maker_fee = 0.0002
    commission_mixed = (position_value * maker_fee) + (position_value * taker_fee)
    pnl_mixed = pnl_before_fees - commission_mixed
    print(f"   2. Maker+Taker: Комиссия ${commission_mixed:.6f}, PnL ${pnl_mixed:.6f}")
    
    # Сценарий 3: Обе maker (0.02%)
    commission_maker_both = position_value * maker_fee * 2
    pnl_maker_both = pnl_before_fees - commission_maker_both
    print(f"   3. Обе maker (0.02%): Комиссия ${commission_maker_both:.6f}, PnL ${pnl_maker_both:.6f}")
    
    # Проверяем какой сценарий дает PnL близкий к 0.00
    print(f"\n🎯 Анализ результатов:")
    scenarios = [
        ("Обе taker", pnl_taker_both),
        ("Maker+Taker", pnl_mixed), 
        ("Обе maker", pnl_maker_both)
    ]
    
    for name, pnl in scenarios:
        diff = abs(pnl - final_pnl)
        if diff < 0.005:  # Менее 0.5 цента разницы
            print(f"   ✅ {name}: ${pnl:.6f} (разница ${diff:.6f}) - СОВПАДАЕТ!")
        else:
            print(f"   ❌ {name}: ${pnl:.6f} (разница ${diff:.6f})")
    
    # Проверяем соответствие ROI
    print(f"\n📊 Проверка ROI:")
    expected_roi = (pnl_before_fees / position_value) * 100
    print(f"   Ожидаемый ROI (до комиссий): {expected_roi:.2f}%")
    print(f"   Фактический ROI: {roi_percent}%")
    
    if abs(expected_roi - roi_percent) < 0.05:
        print(f"   ✅ ROI совпадает - Binance показывает ROI до комиссий")
    else:
        print(f"   ❌ ROI не совпадает")

def check_minimum_profit_protection():
    print(f"\n🛡️ ПРОВЕРКА МИНИМАЛЬНОЙ ЗАЩИТЫ ПРИБЫЛИ")
    print("=" * 50)
    
    # Данные ADA
    entry_price = 0.89150
    qty = 23.0
    min_profit_usdt = 0.03  # Минимальная защита
    
    # Рассчитываем минимальный SL для защиты $0.03
    min_sl = entry_price + (min_profit_usdt / qty)
    print(f"📊 Для защиты $0.03 прибыли:")
    print(f"   Entry: ${entry_price}")
    print(f"   Минимальный SL: ${min_sl:.6f}")
    print(f"   Цена закрытия: $0.89190")
    
    if 0.89190 >= min_sl:
        actual_profit_protected = (0.89190 - entry_price) * qty
        print(f"   ✅ Цена закрытия выше минимального SL")
        print(f"   ✅ Защищено ${actual_profit_protected:.6f} прибыли до комиссий")
        
        # Но комиссии съели всю прибыль!
        position_value = entry_price * qty
        estimated_commission = position_value * 0.00035 * 2  # Средняя комиссия
        net_profit = actual_profit_protected - estimated_commission
        print(f"   ⚠️ После комиссий ~${estimated_commission:.6f}: ${net_profit:.6f}")
        
        if net_profit <= 0.01:
            print(f"   🚨 ПРОБЛЕМА: Комиссии съели всю прибыль!")
            return False
    else:
        print(f"   ❌ Цена закрытия ниже минимального SL")
        return False
    
    return True

def suggest_improvements():
    print(f"\n💡 ПРЕДЛОЖЕНИЯ ПО УЛУЧШЕНИЮ")
    print("=" * 50)
    
    print("1. 🛡️ УВЕЛИЧИТЬ МИНИМАЛЬНУЮ ЗАЩИТУ:")
    print("   - Текущая: $0.03")
    print("   - Предлагаемая: $0.06-0.08 (учитывая комиссии)")
    
    print("\n2. 📊 УЧЕТ КОМИССИЙ В ТРЕЙЛИНГЕ:")
    print("   - Добавить комиссии к target_profit")
    print("   - Формула: target_profit = max(pnl * keep_pct, min_profit + estimated_fees)")
    
    print("\n3. ⚠️ ПРЕДУПРЕЖДЕНИЯ О МАЛОЙ ПРИБЫЛИ:")
    print("   - Предупреждать если ожидаемая прибыль < комиссий")
    print("   - Не активировать трейлинг для очень малых прибылей")
    
    print("\n4. 🎯 УЛУЧШЕННАЯ ЛОГИКА ЗАКРЫТИЯ:")
    print("   - Проверять что чистая прибыль > минимума перед закрытием")
    print("   - Использовать реальные комиссии из ордеров")

if __name__ == "__main__":
    analyze_ada_close()
    protection_ok = check_minimum_profit_protection()
    suggest_improvements()
    
    print(f"\n" + "=" * 50)
    if not protection_ok:
        print("🚨 ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ МИНИМАЛЬНОЙ ЗАЩИТЫ!")
    else:
        print("✅ Система работает, но можно улучшить")
