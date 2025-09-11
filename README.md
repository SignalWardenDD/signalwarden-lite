# 🚀 SignalWarden Lite v1.6-TXB

**Автоматическая торговая система для криптовалютных фьючерсов на Binance USDT-M**

## 📋 Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка API ключей
Создайте файл `.env` с вашими API ключами Binance:
```bash
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET=your_secret_here
```

### 3. Запуск системы
```bash
# Paper trading (тестирование)
python start_live_trading.py

# Live trading (реальные деньги)
python start_live_trading.py --live
```

## 📁 Структура проекта

```
├── SIGNALWARDEN_COMPLETE_DOCUMENTATION.md  # Полная документация
├── requirements.txt                        # Зависимости Python
├── start_live_trading.py                   # Запуск системы
├── .env                                    # API ключи (создать)
├── signalwarden_lite/                      # Основная система
├── data/                                   # Исторические данные
├── tests/                                  # Тесты и проверки
├── documentation/                          # Документация
└── backups/                                # Резервные копии
```

## 🎯 Основные возможности

- **Multi-Timeframe стратегия** (1h + 15m)
- **Адаптивные шорты** с BTC market filter
- **Profit-first трейлинг** с защитой прибыли
- **7 торговых пар** (ADA, LTC, DOGE, ENA, HBAR, WIF, PNUT)
- **Автоматическое управление рисками**

## 📊 Результаты

- **$5,841.2 прибыли** на 11,390 сделках (2022-2024)
- **84.9% Win Rate** с **2.07 Profit Factor**
- **10.4 сделок/день**

## 📖 Документация

Полная документация доступна в файле `SIGNALWARDEN_COMPLETE_DOCUMENTATION.md`

## ⚠️ Предупреждение

**LIVE TRADING РЕЖИМ ИСПОЛЬЗУЕТ РЕАЛЬНЫЕ ДЕНЬГИ!**

Убедитесь, что вы понимаете риски перед запуском live торговли.

## 🔧 Поддержка

Все вопросы по системе решаются через анализ логов и конфигурации.
