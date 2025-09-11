#!/usr/bin/env python3
"""
Бэктест SignalWarden v1.6-TXB с production настройками на 2 года
Точная копия текущей live системы
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import yaml
from datetime import datetime, timedelta
from signalwarden_lite.backtest.engine import BacktestEngine

def main():
    print("🚀 БЭКТЕСТ SignalWarden v1.6-TXB Production (2 года)")
    print("=" * 70)
    
    # Загружаем конфиг
    config_path = "signalwarden_lite/config/config_backtest_2year.yaml"
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Настройки периода - 2 года
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # 2 года
    
    print(f"📅 Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
    print(f"📊 Символы: {config['symbols']}")
    print(f"💰 Размер позиции: {config['risk']['margin_usdt']} USDT нотационал")
    print(f"⚡ Плечо: {config['risk']['leverage']}x")
    print(f"🛡️ Stop Loss: {config['risk']['sl_atr_mult']}x ATR")
    print(f"🔄 Трейлинг: {config['trailing']['activate_R']*100}% R активация")
    print()
    
    # Создаем движок бэктеста
    engine = BacktestEngine(config_path)
    
    # Запускаем бэктест
    print("🔄 Запуск бэктеста...")
    results = engine.run(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        symbols=config['symbols']
    )
    
    # Выводим результаты
    if results is not None:
        print("\n" + "="*70)
        print("📈 РЕЗУЛЬТАТЫ БЭКТЕСТА")
        print("="*70)
        
        # Основные метрики
        total_return = results['total_return']
        win_rate = results['win_rate'] 
        sharpe = results['sharpe_ratio']
        max_dd = results['max_drawdown']
        total_trades = results['total_trades']
        
        print(f"💰 Общая доходность: {total_return:+.2f}%")
        print(f"📊 Win Rate: {win_rate:.1f}%")
        print(f"⚡ Sharpe Ratio: {sharpe:.2f}")
        print(f"📉 Max Drawdown: {max_dd:.2f}%")
        print(f"🔄 Всего сделок: {total_trades}")
        
        if 'profit_factor' in results:
            print(f"💎 Profit Factor: {results['profit_factor']:.2f}")
        
        # Годовая доходность
        years = 2
        annual_return = ((1 + total_return/100) ** (1/years) - 1) * 100
        print(f"📅 Годовая доходность: {annual_return:+.2f}%")
        
        # Сохраняем детальные результаты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"backtest_production_2year_{timestamp}.csv"
        
        if 'trades' in results and len(results['trades']) > 0:
            trades_df = pd.DataFrame(results['trades'])
            trades_df.to_csv(report_file, index=False)
            print(f"💾 Детали сохранены: {report_file}")
        
        print("\n" + "="*70)
        print("✅ БЭКТЕСТ ЗАВЕРШЕН")
        print("="*70)
        
    else:
        print("❌ Ошибка выполнения бэктеста")

if __name__ == "__main__":
    main()
