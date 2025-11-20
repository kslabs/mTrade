"""
Скрипт для восстановления currencies.json до рабочего состояния
Оставляет только первые 20 валют из синхронизации
"""

import json
import os
import shutil
from datetime import datetime

CURRENCIES_FILE = "currencies.json"
BACKUP_FILE = f"currencies.json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def restore_currencies():
    """Восстановить currencies.json до рабочего состояния"""
    
    if not os.path.exists(CURRENCIES_FILE):
        print("❌ Файл currencies.json не найден")
        return False
    
    # Создаём бэкап
    print(f"📦 Создаю бэкап: {BACKUP_FILE}")
    shutil.copy(CURRENCIES_FILE, BACKUP_FILE)
    
    # Читаем текущие данные
    print("📖 Читаю текущие данные...")
    with open(CURRENCIES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Определяем формат
    if isinstance(data, dict) and 'currencies' in data:
        print(f"✅ Обнаружен новый формат: {len(data['currencies'])} валют")
        currencies = data['currencies']
        metadata = {k: v for k, v in data.items() if k != 'currencies'}
    else:
        print(f"✅ Обнаружен старый формат: {len(data)} валют")
        currencies = data
        metadata = {}
    
    # Выбираем только первые 20 популярных валют
    popular_codes = [
        'WLD', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC',
        'DOGE', 'LTC', 'LINK', 'UNI', 'ATOM', 'TON', 'TRX', 'NEAR', 'APT', 'SUI'
    ]
    
    # Фильтруем валюты
    filtered_currencies = []
    for code in popular_codes:
        for currency in currencies:
            if isinstance(currency, dict):
                if currency.get('code', '').upper() == code:
                    filtered_currencies.append(currency)
                    break
            elif isinstance(currency, str):
                if currency.upper() == code:
                    filtered_currencies.append({"code": code, "symbol": code[0]})
                    break
    
    print(f"🔍 Отфильтровано: {len(filtered_currencies)} валют")
    
    # Сохраняем в новом формате
    save_data = {
        "currencies": filtered_currencies,
        **metadata
    }
    
    print("💾 Сохраняю восстановленные данные...")
    with open(CURRENCIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    # Проверяем размер
    file_size_kb = os.path.getsize(CURRENCIES_FILE) / 1024
    backup_size_kb = os.path.getsize(BACKUP_FILE) / 1024
    
    print()
    print("=" * 60)
    print("✅ ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print(f"📊 Валют в файле: {len(filtered_currencies)}")
    print(f"📦 Размер файла: {file_size_kb:.2f} KB (было: {backup_size_kb:.2f} KB)")
    print(f"💾 Бэкап сохранён: {BACKUP_FILE}")
    print()
    print("Валюты в списке:")
    for i, curr in enumerate(filtered_currencies[:10], 1):
        code = curr.get('code', '?')
        symbol = curr.get('symbol', '?')
        name = curr.get('name', code)
        print(f"  {i}. {symbol} {code:8} - {name}")
    
    if len(filtered_currencies) > 10:
        print(f"  ... и ещё {len(filtered_currencies) - 10} валют")
    
    print()
    print("🔄 Теперь можно перезапустить сервер mTrade")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 ВОССТАНОВЛЕНИЕ currencies.json")
    print("=" * 60)
    print()
    
    restore_currencies()
