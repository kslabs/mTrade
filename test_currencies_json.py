import json
import sys

try:
    with open('currencies.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict) and 'currencies' in data:
        print(f"✅ JSON валиден: {len(data['currencies'])} валют")
        print(f"   Формат: новый (объект)")
        print(f"   Размер: {sys.getsizeof(data) / 1024:.2f} KB в памяти")
    elif isinstance(data, list):
        print(f"✅ JSON валиден: {len(data)} валют")
        print(f"   Формат: старый (массив)")
    else:
        print("❌ Неизвестный формат данных")
        sys.exit(1)
    
except json.JSONDecodeError as e:
    print(f"❌ Ошибка парсинга JSON: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка: {e}")
    sys.exit(1)
