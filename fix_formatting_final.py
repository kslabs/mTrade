"""
Скрипт для удаления двойных переносов строк в gate_api_client.py
Сохраняет только одну пустую строку между методами/блоками
"""

# Читаем файл
with open('gate_api_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

print(f"Исходный размер: {len(content)} символов")
print(f"Исходное количество строк: {content.count(chr(10)) + 1}")

# Заменяем все множественные переносы строк на двойной перенос (максимум)
while '\n\n\n' in content:
    content = content.replace('\n\n\n', '\n\n')

print(f"После удаления тройных переносов: {content.count(chr(10)) + 1} строк")

# Сохраняем
with open('gate_api_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ Файл исправлен!")
print(f"Новый размер: {len(content)} символов")
print(f"Новое количество строк: {content.count(chr(10)) + 1}")

# Проверяем синтаксис
import py_compile
try:
    py_compile.compile('gate_api_client.py', doraise=True)
    print("✅ Синтаксис корректен!")
except SyntaxError as e:
    print(f"❌ Синтаксическая ошибка: {e}")
    exit(1)

# Проверяем импорт и наличие метода
import sys
if 'gate_api_client' in sys.modules:
    del sys.modules['gate_api_client']
    
from gate_api_client import GateAPIClient
has_orderbook = hasattr(GateAPIClient, 'get_spot_orderbook')
print(f"{'✅' if has_orderbook else '❌'} Метод get_spot_orderbook: {has_orderbook}")

if has_orderbook:
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
else:
    print("\n⚠️ Метод get_spot_orderbook отсутствует!")
