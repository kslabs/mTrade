"""
Конвертация currencies.json обратно в простой формат (массив)
"""
import json

print("Конвертация currencies.json в старый формат...")

# Читаем текущий файл
with open('currencies.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Извлекаем массив валют
if isinstance(data, dict) and 'currencies' in data:
    currencies = data['currencies']
    # Упрощаем структуру - оставляем только code и symbol
    simple_currencies = []
    for c in currencies:
        simple_currencies.append({
            "code": c.get("code", ""),
            "symbol": c.get("symbol", "")
        })
    
    # Сохраняем в старом формате
    with open('currencies.json', 'w', encoding='utf-8') as f:
        json.dump(simple_currencies, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Готово! Конвертировано {len(simple_currencies)} валют")
    print("   Формат: простой массив [code, symbol]")
else:
    print("❌ Файл уже в старом формате или неверная структура")
