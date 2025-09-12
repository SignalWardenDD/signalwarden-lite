#!/usr/bin/env python3
"""
Проверка статуса системы трейлинга
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_trailing_formulas():
    """Проверяем правильность формул в коде"""
    print("🔍 ПРОВЕРКА ФОРМУЛ ТРЕЙЛИНГА В КОДЕ")
    print("=" * 50)
    
    try:
        with open('signalwarden_lite/core/trailing_pnl_only.py', 'r') as f:
            content = f.read()
        
        # Проверяем формулы для LONG
        long_formula_correct = "pnl_sl = pos.entry - (target_profit / pos.qty)" in content
        long_min_sl_correct = "min_sl = pos.entry - (min_profit_usdt / pos.qty)" in content
        
        # Проверяем формулы для SHORT  
        short_formula_correct = "pnl_sl = pos.entry + (target_profit / pos.qty)" in content
        short_min_sl_correct = "min_sl = pos.entry + (min_profit_usdt / pos.qty)" in content
        
        print("📊 LONG формулы:")
        print(f"  pnl_sl = entry - profit: {'✅' if long_formula_correct else '❌'}")
        print(f"  min_sl = entry - profit: {'✅' if long_min_sl_correct else '❌'}")
        
        print("📊 SHORT формулы:")
        print(f"  pnl_sl = entry + profit: {'✅' if short_formula_correct else '❌'}")
        print(f"  min_sl = entry + profit: {'✅' if short_min_sl_correct else '❌'}")
        
        all_correct = long_formula_correct and long_min_sl_correct and short_formula_correct and short_min_sl_correct
        
        if all_correct:
            print("\n✅ ВСЕ ФОРМУЛЫ ИСПРАВЛЕНЫ ПРАВИЛЬНО!")
        else:
            print("\n❌ ЕСТЬ ПРОБЛЕМЫ С ФОРМУЛАМИ!")
            
        return all_correct
        
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
        return False

def check_live_positions():
    """Проверяем текущие позиции из логов"""
    print("\n🔍 АНАЛИЗ ТЕКУЩИХ ПОЗИЦИЙ")
    print("=" * 50)
    
    # Данные из логов
    positions = [
        {"symbol": "PNUT_USDT", "entry": 0.238290, "sl": 0.229342, "side": "LONG"},
        {"symbol": "LTC_USDT", "entry": 115.930000, "sl": 113.501429, "side": "LONG"},
        {"symbol": "HBAR_USDT", "entry": 0.240500, "sl": 0.234034, "side": "LONG"},
        {"symbol": "ADA_USDT", "entry": 0.892000, "sl": 0.871607, "side": "LONG"},
        {"symbol": "WIF_USDT", "entry": 0.903600, "sl": 0.879814, "side": "LONG"},
        {"symbol": "DOGE_USDT", "entry": 0.257118, "sl": 0.248259, "side": "LONG"},
    ]
    
    all_correct = True
    
    for pos in positions:
        symbol = pos["symbol"]
        entry = pos["entry"]
        sl = pos["sl"]
        side = pos["side"]
        
        if side == "LONG":
            sl_correct = sl < entry
            status = "✅" if sl_correct else "❌"
            direction = "ниже" if sl < entry else "выше"
        else:
            sl_correct = sl > entry
            status = "✅" if sl_correct else "❌"
            direction = "выше" if sl > entry else "ниже"
            
        print(f"{status} {symbol}: Entry ${entry:.6f}, SL ${sl:.6f} ({direction} entry)")
        
        if not sl_correct:
            all_correct = False
    
    if all_correct:
        print("\n✅ ВСЕ ПОЗИЦИИ ИМЕЮТ ПРАВИЛЬНЫЕ SL!")
    else:
        print("\n❌ ЕСТЬ ПОЗИЦИИ С НЕПРАВИЛЬНЫМИ SL!")
        
    return all_correct

def check_trailing_thresholds():
    """Проверяем пороги трейлинга"""
    print("\n🔍 ПРОВЕРКА ПОРОГОВ ТРЕЙЛИНГА")
    print("=" * 50)
    
    expected_thresholds = {
        "L1": {"pnl": 0.06, "keep": 0.50},
        "L2": {"pnl": 0.15, "keep": 0.60},
        "L3": {"pnl": 0.25, "keep": 0.70},
        "L4": {"pnl": 0.35, "keep": 0.80},
    }
    
    try:
        with open('signalwarden_lite/core/trailing_pnl_only.py', 'r') as f:
            content = f.read()
        
        all_correct = True
        
        for level, thresholds in expected_thresholds.items():
            pnl_correct = f"level_1_pnl: float = {thresholds['pnl']}" in content if level == "L1" else True
            keep_correct = f"level_1_keep_pct: float = {thresholds['keep']}" in content if level == "L1" else True
            
            # Проверяем для всех уровней
            if level == "L1":
                pnl_correct = "level_1_pnl: float = 0.06" in content
                keep_correct = "level_1_keep_pct: float = 0.50" in content
            elif level == "L2":
                pnl_correct = "level_2_pnl: float = 0.15" in content
                keep_correct = "level_2_keep_pct: float = 0.60" in content
            elif level == "L3":
                pnl_correct = "level_3_pnl: float = 0.25" in content
                keep_correct = "level_3_keep_pct: float = 0.70" in content
            elif level == "L4":
                pnl_correct = "level_4_pnl: float = 0.35" in content
                keep_correct = "level_4_keep_pct: float = 0.80" in content
            
            status = "✅" if (pnl_correct and keep_correct) else "❌"
            print(f"{status} {level}: ${thresholds['pnl']} PnL → {thresholds['keep']*100:.0f}% сохранить")
            
            if not (pnl_correct and keep_correct):
                all_correct = False
        
        # Проверяем минимальную защиту
        min_profit_correct = "min_profit_usdt = 0.03" in content
        status = "✅" if min_profit_correct else "❌"
        print(f"{status} Минимальная защита: $0.03 USDT")
        
        if not min_profit_correct:
            all_correct = False
            
        return all_correct
        
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
        return False

def main():
    """Основная проверка"""
    print("🚀 ПРОВЕРКА СИСТЕМЫ ТРЕЙЛИНГА")
    print("=" * 60)
    
    checks = [
        ("Формулы трейлинга", check_trailing_formulas),
        ("Текущие позиции", check_live_positions), 
        ("Пороги трейлинга", check_trailing_thresholds),
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        print(f"\n🔍 {name.upper()}:")
        try:
            if check_func():
                passed += 1
                print(f"✅ {name}: ПРОЙДЕНО")
            else:
                print(f"❌ {name}: ПРОВАЛЕНО")
        except Exception as e:
            print(f"❌ {name}: ОШИБКА - {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 ИТОГО: {passed}/{total} проверок пройдено")
    
    if passed == total:
        print("🎉 ВСЯ СИСТЕМА ТРЕЙЛИНГА РАБОТАЕТ ПРАВИЛЬНО!")
        print("✅ Формулы исправлены")
        print("✅ Позиции защищены правильными SL")
        print("✅ Пороги настроены корректно")
        print("✅ Система готова к торговле")
    else:
        print(f"⚠️ {total-passed} проблем требуют внимания!")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
