#!/usr/bin/env python3
"""
Backtest with PnL-based trailing system (matching production exactly)
"""

import os
import sys
import yaml
import pandas as pd
from datetime import datetime

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.backtest.engine_pnl import run_backtest_pnl_based, FeesCfg
from signalwarden_lite.core.trailing import TrailingConfig
from signalwarden_lite.core.types import Side
from signalwarden_lite.live.run_live_v1_6_TXB import SignalWardenLive

def load_config():
    """Load PnL-based backtest configuration"""
    with open('signalwarden_lite/config/config_backtest_pnl.yaml', 'r') as f:
        return yaml.safe_load(f)

def run_pnl_backtest():
    """Run backtest with PnL-based trailing system"""
    
    print("🚀 ЗАПУСК БЭКТЕСТА С PnL-based СИСТЕМОЙ ТРЕЙЛИНГА")
    print("=" * 80)
    print("📋 СИСТЕМА ТОЧНО СООТВЕТСТВУЕТ PRODUCTION!")
    print()
    
    # Загружаем конфигурацию
    config = load_config()
    
    print("📊 ПАРАМЕТРЫ БЭКТЕСТА:")
    print("-" * 60)
    print(f"💰 Position Size: {config['trading']['notional_usdt']} USDT")
    print(f"🛡️ SL ATR Multiplier: {config['trading']['sl_atr_mult']}")
    print(f"📈 Leverage: {config['trading']['leverage']}")
    print(f"📅 Period: {config['data']['start_date']} - {config['data']['end_date']}")
    print(f"⏰ Timeframe: {config['data']['timeframe']}")
    print()
    
    print("🔧 PnL-based ТРЕЙЛИНГ (как в production):")
    print("-" * 60)
    trailing_config = config['trailing']
    print(f"🎯 Activation: {trailing_config['activate_pnl_usdt']} USDT")
    print(f"📊 Level 1: {trailing_config['level_1_pnl']} USDT → {trailing_config['level_1_keep_pct']*100:.0f}%")
    print(f"📊 Level 2: {trailing_config['level_2_pnl']} USDT → {trailing_config['level_2_keep_pct']*100:.0f}%")
    print(f"📊 Level 3: {trailing_config['level_3_pnl']} USDT → {trailing_config['level_3_keep_pct']*100:.0f}%")
    print(f"📊 Level 4: {trailing_config['level_4_pnl']} USDT → {trailing_config['level_4_keep_pct']*100:.0f}%")
    print()
    
    # Создаем объекты конфигурации
    trailing = TrailingConfig(
        activate_pnl_usdt=trailing_config['activate_pnl_usdt'],
        level_1_pnl=trailing_config['level_1_pnl'],
        level_1_keep_pct=trailing_config['level_1_keep_pct'],
        level_2_pnl=trailing_config['level_2_pnl'],
        level_2_keep_pct=trailing_config['level_2_keep_pct'],
        level_3_pnl=trailing_config['level_3_pnl'],
        level_3_keep_pct=trailing_config['level_3_keep_pct'],
        level_4_pnl=trailing_config['level_4_pnl'],
        level_4_keep_pct=trailing_config['level_4_keep_pct']
    )
    
    fees = FeesCfg(
        maker_bps=config['fees']['maker_bps'],
        taker_bps=config['fees']['taker_bps'],
        entry_liquidity=config['fees']['entry_liquidity']
    )
    
    # Инициализируем систему для генерации сигналов
    print("🔧 ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ...")
    system = SignalWardenLive('signalwarden_lite/config/config_production.yaml', paper_mode=True)
    
    # Загружаем данные и генерируем сигналы
    print("📊 ЗАГРУЗКА ДАННЫХ И ГЕНЕРАЦИЯ СИГНАЛОВ...")
    data_dict = {}
    signals_dict = {}
    
    for symbol in config['symbols']:
        print(f"  📈 {symbol}...")
        
        # Загружаем данные (используем метод из системы)
        try:
            df = system.exchange.fetch_ohlcv(
                symbol, 
                timeframe=config['data']['timeframe'],
                since=system.exchange.parse8601(f"{config['data']['start_date']}T00:00:00Z"),
                limit=1000
            )
            
            if len(df) < 100:
                print(f"    ⚠️ Недостаточно данных для {symbol}")
                continue
                
            # Конвертируем в DataFrame
            df = pd.DataFrame(df, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Генерируем сигналы
            signals = system.generate_signals_for_symbol(symbol, df)
            
            if signals is not None and len(signals) > 0:
                data_dict[symbol] = df
                signals_dict[symbol] = signals
                print(f"    ✅ {len(df)} свечей, {len(signals)} сигналов")
            else:
                print(f"    ⚠️ Нет сигналов для {symbol}")
                
        except Exception as e:
            print(f"    ❌ Ошибка для {symbol}: {e}")
            continue
    
    if not data_dict:
        print("❌ Нет данных для бэктеста!")
        return
    
    print(f"\n📊 ГОТОВО К БЭКТЕСТУ: {len(data_dict)} символов")
    print()
    
    # Запускаем бэктест
    print("🚀 ЗАПУСК БЭКТЕСТА...")
    print("-" * 60)
    
    trades = run_backtest_pnl_based(
        data_dict,
        signals_dict,
        config['trading']['notional_usdt'],
        config['trading']['sl_atr_mult'],
        trailing,
        fees
    )
    
    if not trades:
        print("❌ Нет сделок в бэктесте!")
        return
    
    # Анализируем результаты
    print("\n📊 РЕЗУЛЬТАТЫ БЭКТЕСТА:")
    print("=" * 80)
    
    df_trades = pd.DataFrame([{
        'symbol': t.symbol,
        'timestamp': t.timestamp,
        'side': t.side,
        'entry': t.entry,
        'exit': t.exit,
        'qty': t.qty,
        'pnl_usdt': t.pnl_usdt,
        'entry_fees_usdt': t.entry_fees_usdt,
        'exit_fees_usdt': t.exit_fees_usdt,
        'bars_held': t.bars_held,
        'sl_initial': t.sl_initial,
        'sl_final': t.sl_final,
        'peak_pnl_usdt': t.peak_pnl_usdt
    } for t in trades])
    
    # Общая статистика
    total_trades = len(df_trades)
    total_pnl = df_trades['pnl_usdt'].sum()
    total_fees = (df_trades['entry_fees_usdt'] + df_trades['exit_fees_usdt']).sum()
    winning_trades = len(df_trades[df_trades['pnl_usdt'] > 0])
    losing_trades = len(df_trades[df_trades['pnl_usdt'] < 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    avg_win = df_trades[df_trades['pnl_usdt'] > 0]['pnl_usdt'].mean() if winning_trades > 0 else 0
    avg_loss = df_trades[df_trades['pnl_usdt'] < 0]['pnl_usdt'].mean() if losing_trades > 0 else 0
    profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else float('inf')
    
    print(f"📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"   💰 Total PnL: ${total_pnl:.2f}")
    print(f"   📈 Total Trades: {total_trades}")
    print(f"   ✅ Win Rate: {win_rate:.1f}%")
    print(f"   📊 Profit Factor: {profit_factor:.2f}")
    print(f"   💸 Total Fees: ${total_fees:.2f}")
    print(f"   📊 Net PnL: ${total_pnl - total_fees:.2f}")
    print()
    
    # Статистика по символам
    print(f"📊 СТАТИСТИКА ПО СИМВОЛАМ:")
    symbol_stats = df_trades.groupby('symbol').agg({
        'pnl_usdt': ['count', 'sum', 'mean'],
        'entry_fees_usdt': 'sum',
        'exit_fees_usdt': 'sum'
    }).round(2)
    
    for symbol in symbol_stats.index:
        trades_count = symbol_stats.loc[symbol, ('pnl_usdt', 'count')]
        pnl_sum = symbol_stats.loc[symbol, ('pnl_usdt', 'sum')]
        pnl_avg = symbol_stats.loc[symbol, ('pnl_usdt', 'mean')]
        fees_sum = symbol_stats.loc[symbol, ('entry_fees_usdt', 'sum')] + symbol_stats.loc[symbol, ('exit_fees_usdt', 'sum')]
        
        print(f"   📈 {symbol}: {trades_count} trades, PnL: ${pnl_sum:.2f}, Avg: ${pnl_avg:.2f}, Fees: ${fees_sum:.2f}")
    
    print()
    
    # Статистика по типам сделок
    long_trades = df_trades[df_trades['side'] == 'LONG']
    short_trades = df_trades[df_trades['side'] == 'SHORT']
    
    print(f"📊 СТАТИСТИКА ПО ТИПАМ СДЕЛОК:")
    print(f"   📈 Long trades: {len(long_trades)} ({len(long_trades)/total_trades*100:.1f}%)")
    if len(long_trades) > 0:
        print(f"      💰 Long PnL: ${long_trades['pnl_usdt'].sum():.2f}")
    
    print(f"   📉 Short trades: {len(short_trades)} ({len(short_trades)/total_trades*100:.1f}%)")
    if len(short_trades) > 0:
        print(f"      💰 Short PnL: ${short_trades['pnl_usdt'].sum():.2f}")
    
    print()
    
    # Анализ трейлинга
    print(f"📊 АНАЛИЗ ТРЕЙЛИНГА:")
    trailing_trades = df_trades[df_trades['peak_pnl_usdt'] > 0]
    print(f"   🎯 Trades with trailing: {len(trailing_trades)} ({len(trailing_trades)/total_trades*100:.1f}%)")
    
    if len(trailing_trades) > 0:
        avg_peak_pnl = trailing_trades['peak_pnl_usdt'].mean()
        avg_final_pnl = trailing_trades['pnl_usdt'].mean()
        trailing_effectiveness = (avg_final_pnl / avg_peak_pnl) * 100 if avg_peak_pnl > 0 else 0
        
        print(f"   📊 Avg Peak PnL: ${avg_peak_pnl:.2f}")
        print(f"   📊 Avg Final PnL: ${avg_final_pnl:.2f}")
        print(f"   📊 Trailing Effectiveness: {trailing_effectiveness:.1f}%")
    
    print()
    print("🎯 ЗАКЛЮЧЕНИЕ:")
    print("-" * 60)
    
    if total_pnl > 0:
        print("✅ PnL-based БЭКТЕСТ ПРИБЫЛЬНЫЙ!")
        print(f"✅ Total PnL: ${total_pnl:.2f}")
        print(f"✅ Win Rate: {win_rate:.1f}%")
    else:
        print("❌ PnL-based БЭКТЕСТ УБЫТОЧНЫЙ!")
        print(f"❌ Total PnL: ${total_pnl:.2f}")
        print(f"❌ Win Rate: {win_rate:.1f}%")
    
    print()
    print("📋 СРАВНЕНИЕ С R-based БЭКТЕСТОМ:")
    print("-" * 60)
    print("📊 R-based (старый): $5,750.8 PnL, 84.6% Win Rate")
    print(f"📊 PnL-based (новый): ${total_pnl:.2f} PnL, {win_rate:.1f}% Win Rate")
    
    if total_pnl > 5750.8:
        print("✅ PnL-based СИСТЕМА ЛУЧШЕ!")
    elif total_pnl < 5750.8:
        print("❌ PnL-based СИСТЕМА ХУЖЕ!")
    else:
        print("➡️ СИСТЕМЫ ОДИНАКОВЫ!")
    
    # Сохраняем результаты
    results_file = f"backtest_results_pnl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df_trades.to_csv(results_file, index=False)
    print(f"\n💾 Результаты сохранены в: {results_file}")

if __name__ == "__main__":
    run_pnl_backtest()
