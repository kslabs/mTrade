"""
Тест импорта всех модулей mTrade
"""
import sys
print(f"Python версия: {sys.version}")
print()

modules = [
    'flask',
    'flask_cors',
    'config',
    'gate_api_client',
    'currency_sync',
    'trade_logger',
]

print("Проверка импортов:")
for module in modules:
    try:
        __import__(module)
        print(f"  ✅ {module}")
    except Exception as e:
        print(f"  ❌ {module}: {e}")

print()
print("Проверка Config.load_currencies():")
try:
    from config import Config
    currencies = Config.load_currencies()
    print(f"  ✅ Загружено {len(currencies)} валют")
    if currencies:
        print(f"  Первая валюта: {currencies[0]}")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
