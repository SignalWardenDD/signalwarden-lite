#!/usr/bin/env python3
"""
Проверка правильности логики трейлинга
"""

def test_long_trailing_logic():
    print("🔍 ТЕСТ ЛОГИКИ ТРЕЙЛИНГА ДЛЯ LONG ПОЗИЦИИ")
    print("=" * 50)
    
    # Пример LONG позиции
    entry = 100.0
    qty = 1.0
    peak_pnl_usdt = 6.0  # $6 прибыли
    keep_pct = 0.5  # Сохранить 50%
    min_profit_usdt = 0.03
    
    # Рассчитываем target_profit
    target_profit = max(peak_pnl_usdt * keep_pct, min_profit_usdt)
    print(f"📊 Entry: ${entry}")
    print(f"📊 Peak PnL: ${peak_pnl_usdt}")
    print(f"📊 Keep: {keep_pct*100}%")
    print(f"📊 Target profit to preserve: ${target_profit}")
    
    # Рассчитываем SL по ИСПРАВЛЕННОЙ формуле
    pnl_sl = entry - (target_profit / qty)
    min_sl = entry - (min_profit_usdt / qty)
    protected_sl = max(pnl_sl, min_sl)
    
    print(f"📊 Calculated SL: ${pnl_sl}")
    print(f"📊 Min SL: ${min_sl}")
    print(f"📊 Protected SL: ${protected_sl}")
    
    # Проверяем логику
    if protected_sl < entry:
        print("✅ ПРАВИЛЬНО: SL ниже entry для LONG")
        
        # Проверяем сколько мы потеряем если SL сработает
        loss_if_sl_hit = (entry - protected_sl) * qty
        remaining_profit = peak_pnl_usdt - loss_if_sl_hit
        print(f"📊 Если SL сработает:")
        print(f"   - Потеряем: ${loss_if_sl_hit:.2f}")
        print(f"   - Сохраним прибыль: ${remaining_profit:.2f}")
        
        if remaining_profit >= min_profit_usdt * 0.95:  # Небольшая погрешность
            print("✅ ПРАВИЛЬНО: Сохраняем нужную прибыль")
        else:
            print("❌ ОШИБКА: Не сохраняем нужную прибыль")
    else:
        print("❌ ОШИБКА: SL выше или равен entry для LONG")
    
    print()

def test_short_trailing_logic():
    print("🔍 ТЕСТ ЛОГИКИ ТРЕЙЛИНГА ДЛЯ SHORT ПОЗИЦИИ")
    print("=" * 50)
    
    # Пример SHORT позиции
    entry = 100.0
    qty = 1.0
    peak_pnl_usdt = 6.0  # $6 прибыли
    keep_pct = 0.5  # Сохранить 50%
    min_profit_usdt = 0.03
    
    # Рассчитываем target_profit
    target_profit = max(peak_pnl_usdt * keep_pct, min_profit_usdt)
    print(f"📊 Entry: ${entry}")
    print(f"📊 Peak PnL: ${peak_pnl_usdt}")
    print(f"📊 Keep: {keep_pct*100}%")
    print(f"📊 Target profit to preserve: ${target_profit}")
    
    # Рассчитываем SL по ИСПРАВЛЕННОЙ формуле
    pnl_sl = entry + (target_profit / qty)
    min_sl = entry + (min_profit_usdt / qty)
    protected_sl = min(pnl_sl, min_sl)
    
    print(f"📊 Calculated SL: ${pnl_sl}")
    print(f"📊 Min SL: ${min_sl}")
    print(f"📊 Protected SL: ${protected_sl}")
    
    # Проверяем логику
    if protected_sl > entry:
        print("✅ ПРАВИЛЬНО: SL выше entry для SHORT")
        
        # Проверяем сколько мы потеряем если SL сработает
        loss_if_sl_hit = (protected_sl - entry) * qty
        remaining_profit = peak_pnl_usdt - loss_if_sl_hit
        print(f"📊 Если SL сработает:")
        print(f"   - Потеряем: ${loss_if_sl_hit:.2f}")
        print(f"   - Сохраним прибыль: ${remaining_profit:.2f}")
        
        if remaining_profit >= min_profit_usdt * 0.95:  # Небольшая погрешность
            print("✅ ПРАВИЛЬНО: Сохраняем нужную прибыль")
        else:
            print("❌ ОШИБКА: Не сохраняем нужную прибыль")
    else:
        print("❌ ОШИБКА: SL ниже или равен entry для SHORT")
    
    print()

def test_ltc_example():
    print("🔍 ТЕСТ НА ПРИМЕРЕ LTC ИЗ ЛОГОВ")
    print("=" * 50)
    
    # Данные из логов
    entry = 115.720000
    qty = 0.181
    peak_pnl_usdt = 0.0634  # Из логов
    keep_pct = 0.5  # L1 = 50%
    min_profit_usdt = 0.03
    
    print(f"📊 LTC Entry: ${entry}")
    print(f"📊 LTC Peak PnL: ${peak_pnl_usdt}")
    print(f"📊 LTC Qty: {qty}")
    
    # Рассчитываем по ИСПРАВЛЕННОЙ формуле
    target_profit = max(peak_pnl_usdt * keep_pct, min_profit_usdt)
    pnl_sl = entry - (target_profit / qty)  # ИСПРАВЛЕННАЯ формула
    min_sl = entry - (min_profit_usdt / qty)
    protected_sl = max(pnl_sl, min_sl)
    
    print(f"📊 Target profit: ${target_profit:.4f}")
    print(f"📊 Calculated SL: ${pnl_sl:.6f}")
    print(f"📊 Protected SL: ${protected_sl:.6f}")
    
    # Сравниваем с логами
    log_sl = 115.895000  # Из логов
    print(f"📊 SL из логов: ${log_sl:.6f}")
    
    if protected_sl < entry:
        print("✅ ИСПРАВЛЕННАЯ формула: SL ниже entry")
    else:
        print("❌ ИСПРАВЛЕННАЯ формула: SL выше entry")
        
    if log_sl > entry:
        print("❌ ЛОГИ: SL выше entry (неправильно)")
    else:
        print("✅ ЛОГИ: SL ниже entry")

if __name__ == "__main__":
    test_long_trailing_logic()
    test_short_trailing_logic()
    test_ltc_example()
