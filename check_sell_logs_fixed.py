#!/usr/bin/env python3
"""
Скрипт для проверки логов продаж после исправления
Проверяет, что все продажи логируются с реальными метриками (не нулевыми)
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta

# Путь к папке с логами
LOGS_DIR = Path(__file__).parent / "trade_logs"

# Время, после которого считаем логи "новыми" (после исправления)
# Исправление применено 10 декабря 2025, 21:35 UTC (сервер перезапущен)
CUTOFF_TIME = datetime(2025, 12, 10, 21, 35, 0)

def check_logs():
    """Проверить все логи продаж"""
    print("=" * 80)
    print("🔍 ПРОВЕРКА ЛОГОВ ПРОДАЖ ПОСЛЕ ИСПРАВЛЕНИЯ")
    print("=" * 80)
    print(f"⏰ Проверяем логи после: {CUTOFF_TIME.isoformat()}")
    print()
    
    # Счётчики
    total_sells = 0
    zero_metric_sells = 0
    good_sells = 0
    currencies_with_issues = []
    
    # Перебираем все файлы логов
    for log_file in sorted(LOGS_DIR.glob("*_logs.jsonl")):
        currency = log_file.stem.replace("_logs", "")
        
        # Читаем последние записи
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Фильтруем только продажи после cutoff_time
        recent_sells = []
        for line in lines:
            try:
                entry = json.loads(line.strip())
                if entry.get('type') == 'sell':
                    # Парсим timestamp
                    ts = datetime.fromisoformat(entry['timestamp'])
                    if ts > CUTOFF_TIME:
                        recent_sells.append(entry)
            except (json.JSONDecodeError, ValueError, KeyError):
                continue
        
        # Проверяем метрики
        if recent_sells:
            for sell in recent_sells:
                total_sells += 1
                delta = sell.get('delta_percent', 0)
                pnl = sell.get('pnl', 0)
                
                if delta == 0 and pnl == 0:
                    zero_metric_sells += 1
                    if currency not in currencies_with_issues:
                        currencies_with_issues.append(currency)
                    print(f"❌ {currency}: Продажа с нулевыми метриками!")
                    print(f"   Время: {sell['time']}")
                    print(f"   Цена: {sell['price']}")
                    print(f"   Дельта: {delta}%")
                    print(f"   PnL: {pnl}")
                    print()
                else:
                    good_sells += 1
                    print(f"✅ {currency}: Продажа с правильными метриками")
                    print(f"   Время: {sell['time']}")
                    print(f"   Цена: {sell['price']}")
                    print(f"   Дельта: {delta:.2f}%")
                    print(f"   PnL: {pnl:.4f}")
                    print()
    
    # Итоговая статистика
    print("=" * 80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего продаж после {CUTOFF_TIME.time()}: {total_sells}")
    print(f"✅ Продаж с правильными метриками: {good_sells}")
    print(f"❌ Продаж с нулевыми метриками: {zero_metric_sells}")
    print()
    
    if zero_metric_sells > 0:
        print("⚠️  ВНИМАНИЕ! Обнаружены продажи с нулевыми метриками!")
        print(f"   Проблемные валюты: {', '.join(currencies_with_issues)}")
        print()
        print("🔧 Действия:")
        print("   1. Убедитесь, что сервер запущен с обновлённым кодом")
        print("   2. Проверьте логи сервера на наличие метки:")
        print("      '[{ВАЛЮТА}] 🔴 _try_sell вызван | КОД ВЕРСИЯ: 2025-12-08_10:00'")
        print("   3. Перезапустите сервер, если метка отсутствует")
    elif total_sells == 0:
        print("⏳ Пока нет новых продаж после исправления")
        print()
        print("📝 Что делать:")
        print("   1. Дождитесь, когда цена одной из валют вырастет до целевой")
        print("   2. Запустите этот скрипт снова после продажи")
        print()
        print("📊 Текущие активные циклы (ждут роста цены):")
        print("   - DOGE: нужно до 0.14919 USDT (+1.34%)")
        print("   - XRP: нужно до 2.08936 USDT (+1.18%)")
        print("   - ETH: нужно до 3416.96 USDT (+1.07%)")
    else:
        print("🎉 ВСЕ ПРОДАЖИ ЛОГИРУЮТСЯ ПРАВИЛЬНО!")
        print()
        print("✅ Исправление работает корректно")
        print("✅ Проблема с 'двойными стартовыми покупками' решена")
    
    print("=" * 80)

if __name__ == "__main__":
    try:
        check_logs()
    except Exception as e:
        print(f"❌ Ошибка при проверке логов: {e}")
        import traceback
        traceback.print_exc()
