"""
Тестовый скрипт для проверки синхронизации валют с Gate.io
Запускает синхронизацию и отображает результаты
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from currency_sync import sync_currencies, CurrencySync


def main():
    print("=" * 60)
    print("🔄 ТЕСТ СИНХРОНИЗАЦИИ ВАЛЮТ С GATE.IO")
    print("=" * 60)
    print()
    
    # Показываем текущую информацию
    sync = CurrencySync()
    info = sync.get_sync_info()
    
    print("📊 Текущее состояние:")
    print(f"   Последнее обновление: {info['last_update'] or 'Не выполнялось'}")
    print(f"   Режим сети: {info['network_mode']}")
    print(f"   Всего валют: {info['total_currencies']}")
    print(f"   Изменённых символов: {info['custom_symbols']}")
    print()
    
    # Запускаем синхронизацию
    print("🚀 Запуск синхронизации...")
    print("   (публичный API, не требует ключей)")
    print()
    
    result = sync_currencies()
    
    print()
    print("=" * 60)
    print("📋 РЕЗУЛЬТАТЫ СИНХРОНИЗАЦИИ")
    print("=" * 60)
    
    if result["success"]:
        print("✅ Статус: УСПЕШНО")
        print()
        print(f"   📥 Добавлено новых валют: {result['added']}")
        print(f"   🔄 Обновлено валют: {result['updated']}")
        print(f"   📊 Всего валют в базе: {result['total']}")
        print(f"   ⏰ Время синхронизации: {result['timestamp']}")
        print()
        
        # Показываем примеры валют
        print("📝 Примеры валют:")
        currencies = sync.get_all_currencies()
        
        # Топ-10 популярных
        popular = ['BTC', 'ETH', 'USDT', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'DOT', 'MATIC']
        for code in popular:
            currency = sync.get_currency(code)
            if currency:
                name = currency.get('name', currency['code'])
                print(f"   {currency['symbol']} {currency['code']:8} - {name}")
        
        print()
        print(f"💾 Данные сохранены в: currencies.json")
        
    else:
        print("❌ Статус: ОШИБКА")
        print()
        print(f"   Ошибка: {result.get('error', 'Неизвестная ошибка')}")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
