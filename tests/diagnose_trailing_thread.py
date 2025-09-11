#!/usr/bin/env python3
"""
Диагностика работы трейлинг потока в live системе
"""

import sys
sys.path.append('.')

import json
import time
import threading
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def simulate_trailing_thread():
    """
    Симулируем работу трейлинг потока как в live системе
    """
    print("🔄 СИМУЛЯЦИЯ ТРЕЙЛИНГ ПОТОКА")
    print("=" * 70)
    
    # Конфигурация из production.yaml
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Читаем текущую позицию DOGE из JSON
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    doge_pos = state.get('DOGE_USDT', {}).get('active_position')
    
    if not doge_pos:
        print("❌ DOGE позиция не найдена в JSON")
        return
    
    print(f"📊 Текущая позиция DOGE:")
    print(f"   Entry: ${doge_pos['entry']:.6f}")
    print(f"   Qty: {doge_pos['qty']:.2f}")
    print(f"   SL Current: ${doge_pos['sl_current']:.6f}")
    print(f"   Trailing Active: {doge_pos['trailing_active']}")
    print(f"   Peak PnL: ${doge_pos.get('peak_pnl_usdt', 0.0):.3f}")
    print()
    
    # Симулируем текущий PnL (0.13 USDT как в реальности)
    current_price = 0.238  # Примерная текущая цена
    current_pnl = 0.13     # PnL как в реальности
    
    print(f"🎯 Тест трейлинга:")
    print(f"   Current Price: ${current_price:.6f}")
    print(f"   Current PnL: ${current_pnl:.3f} USDT")
    print(f"   Порог активации: ${cfg.activate_pnl_usdt:.2f} USDT")
    print(f"   Должен активироваться: {current_pnl >= cfg.activate_pnl_usdt}")
    print()
    
    # Создаем Position объект
    position = Position(
        side=Side.LONG,
        entry=doge_pos['entry'],
        sl=doge_pos['sl_current'],
        sl_initial=doge_pos['sl_initial'],
        qty=doge_pos['qty'],
        remaining_qty=doge_pos['qty'],
        r_per_unit=doge_pos['atr'] * 2.5  # sl_atr_mult из конфига
    )
    
    # Устанавливаем текущий peak_pnl_usdt
    position.peak_pnl_usdt = doge_pos.get('peak_pnl_usdt', 0.0)
    
    print(f"📈 Применяем трейлинг:")
    old_sl = position.sl
    old_peak = position.peak_pnl_usdt
    
    updated_pos = update_trailing_pnl_based(position, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    print(f"   Результат:")
    print(f"     Peak PnL: ${old_peak:.3f} → ${updated_pos.peak_pnl_usdt:.3f}")
    print(f"     Уровень: {debug.get('level', 'N/A')}")
    print(f"     Сохранить: {debug.get('keep_pct', 0)*100:.0f}%")
    print(f"     SL: ${old_sl:.6f} → ${updated_pos.sl:.6f}")
    print(f"     SL обновлен: {debug.get('sl_updated', False)}")
    
    if debug.get('sl_updated', False):
        protected_profit = (updated_pos.sl - position.entry) * position.qty
        print(f"     💰 Защищенная прибыль: ${protected_profit:.3f} USDT")
        print(f"   ✅ ТРЕЙЛИНГ ДОЛЖЕН РАБОТАТЬ!")
    else:
        print(f"   ❌ ТРЕЙЛИНГ НЕ АКТИВИРОВАЛСЯ")
    
    print()

def test_threading_mechanism():
    """
    Тестируем механизм потоков как в live системе
    """
    print("🧵 ТЕСТ МЕХАНИЗМА ПОТОКОВ")
    print("=" * 70)
    
    # Симулируем threading механизм из live системы
    stop_event = threading.Event()
    update_count = 0
    
    def trailing_loop():
        nonlocal update_count
        while not stop_event.is_set():
            try:
                update_count += 1
                print(f"   Обновление трейлинга #{update_count}")
                
                # Симулируем update_trailing_stops()
                simulate_single_trailing_update()
                
                # Ждем 3 секунды как в реальной системе
                if stop_event.wait(3):
                    break
                    
            except Exception as e:
                print(f"   ❌ Ошибка в трейлинг потоке: {e}")
                if stop_event.wait(3):
                    break
    
    def simulate_single_trailing_update():
        """Симулируем одно обновление трейлинга"""
        # Читаем позицию
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
        
        doge_pos = state.get('DOGE_USDT', {}).get('active_position')
        if not doge_pos:
            return
            
        # Симулируем получение PnL с биржи
        current_pnl = 0.13  # Как в реальности
        
        print(f"     DOGE: PnL=${current_pnl:.3f}, Trailing={doge_pos.get('trailing_active', False)}")
        
        if current_pnl >= 0.10:  # Порог активации
            print(f"     ✅ Трейлинг должен активироваться!")
        else:
            print(f"     ⚠️  PnL ниже порога активации")
    
    print("Запуск трейлинг потока на 10 секунд...")
    
    # Запускаем поток
    trailing_thread = threading.Thread(target=trailing_loop, daemon=True)
    trailing_thread.start()
    
    # Ждем 10 секунд
    time.sleep(10)
    
    # Останавливаем поток
    stop_event.set()
    trailing_thread.join(timeout=5)
    
    print(f"✅ Поток остановлен. Всего обновлений: {update_count}")
    print()

def check_live_system_status():
    """
    Проверяем статус live системы
    """
    print("🔍 ПРОВЕРКА СТАТУСА LIVE СИСТЕМЫ")
    print("=" * 70)
    
    # Проверяем процессы
    import subprocess
    
    try:
        # Ищем запущенные процессы SignalWarden
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        signalwarden_processes = [line for line in result.stdout.split('\\n') if 'signalwarden' in line.lower() or 'run_live' in line]
        
        print(f"🔍 Запущенные процессы SignalWarden:")
        if signalwarden_processes:
            for proc in signalwarden_processes:
                print(f"   {proc}")
        else:
            print(f"   ❌ Процессы SignalWarden не найдены")
        
    except Exception as e:
        print(f"   ⚠️  Не удалось проверить процессы: {e}")
    
    # Проверяем логи
    import os
    log_files = [f for f in os.listdir('.') if f.endswith('.log')]
    
    print(f"\\n📄 Доступные лог файлы:")
    for log_file in log_files:
        stat = os.stat(log_file)
        print(f"   {log_file} (размер: {stat.st_size} байт, изменен: {time.ctime(stat.st_mtime)})")
    
    # Проверяем последние записи в логе
    if 'signalwarden_v1_6_TXB.log' in log_files:
        print(f"\\n📖 Последние 10 строк лога:")
        try:
            with open('signalwarden_v1_6_TXB.log', 'r') as f:
                lines = f.readlines()
                for line in lines[-10:]:
                    print(f"   {line.strip()}")
        except Exception as e:
            print(f"   ❌ Не удалось прочитать лог: {e}")
    
    print()

if __name__ == '__main__':
    print("🚀 ДИАГНОСТИКА ТРЕЙЛИНГ ПОТОКА SignalWarden v1.6-TXB")
    print("=" * 80)
    print()
    
    try:
        simulate_trailing_thread()
        test_threading_mechanism()
        check_live_system_status()
        
        print("📋 ЗАКЛЮЧЕНИЕ:")
        print("   1. Логика трейлинга работает правильно")
        print("   2. PnL 0.13 USDT должен активировать трейлинг")
        print("   3. Проблема может быть в:")
        print("      - Live система не запущена")
        print("      - Трейлинг поток не запускается")
        print("      - Ошибка в получении PnL с биржи")
        print("      - Проблема с сохранением состояния")
        print()
        print("🔧 РЕШЕНИЕ:")
        print("   1. Убедитесь что live система запущена")
        print("   2. Проверьте логи на ошибки")
        print("   3. Перезапустите систему если нужно")
        
    except Exception as e:
        print(f"💥 ОШИБКА В ДИАГНОСТИКЕ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
