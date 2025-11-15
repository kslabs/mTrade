"""
Минимальный тест запуска Flask сервера
"""
import sys
import time

print("1. Импорт модулей...")
try:
    from flask import Flask
    from config import Config
    print("  ✅ Flask и Config импортированы")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
    sys.exit(1)

print("2. Загрузка валют...")
try:
    currencies = Config.load_currencies()
    print(f"  ✅ Загружено {len(currencies)} валют")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
    sys.exit(1)

print("3. Создание Flask приложения...")
try:
    app = Flask(__name__)
    print("  ✅ Flask app создано")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
    sys.exit(1)

print("4. Добавление простого роута...")
try:
    @app.route('/')
    def index():
        return "OK"
    print("  ✅ Роут добавлен")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
    sys.exit(1)

print()
print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
print("Сервер должен запускаться нормально")
print()
