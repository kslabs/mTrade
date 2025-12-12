"""
Тест API разрешений торговли
"""
import requests
import json

BASE_URL = "http://localhost:5050"

print("=" * 60)
print("ТЕСТ API РАЗРЕШЕНИЙ ТОРГОВЛИ")
print("=" * 60)

# 1. Получаем текущие разрешения
print("\n1. Получаем текущие разрешения:")
try:
    r = requests.get(f"{BASE_URL}/api/trade/permissions", timeout=3)
    data = r.json()
    print(f"   Статус: {r.status_code}")
    print(f"   Успех: {data.get('success')}")
    print(f"   Разрешения: {json.dumps(data.get('permissions', {}), indent=2)}")
except Exception as e:
    print(f"   ✗ Ошибка: {e}")

# 2. Устанавливаем разрешение для BTC (включаем)
print("\n2. Включаем торговлю для BTC:")
try:
    r = requests.post(
        f"{BASE_URL}/api/trade/permission",
        json={"base_currency": "BTC", "enabled": True},
        timeout=3
    )
    data = r.json()
    print(f"   Статус: {r.status_code}")
    print(f"   Успех: {data.get('success')}")
    print(f"   Сообщение: {data.get('message')}")
except Exception as e:
    print(f"   ✗ Ошибка: {e}")

# 3. Проверяем, что разрешение изменилось
print("\n3. Проверяем обновленные разрешения:")
try:
    r = requests.get(f"{BASE_URL}/api/trade/permissions", timeout=3)
    data = r.json()
    perms = data.get('permissions', {})
    print(f"   BTC: {perms.get('BTC')}")
    if perms.get('BTC') == True:
        print("   ✓ Разрешение для BTC установлено корректно")
    else:
        print("   ✗ Разрешение для BTC не изменилось")
except Exception as e:
    print(f"   ✗ Ошибка: {e}")

# 4. Отключаем торговлю для BTC
print("\n4. Отключаем торговлю для BTC:")
try:
    r = requests.post(
        f"{BASE_URL}/api/trade/permission",
        json={"base_currency": "BTC", "enabled": False},
        timeout=3
    )
    data = r.json()
    print(f"   Статус: {r.status_code}")
    print(f"   Успех: {data.get('success')}")
    print(f"   Сообщение: {data.get('message')}")
except Exception as e:
    print(f"   ✗ Ошибка: {e}")

# 5. Проверяем финальное состояние
print("\n5. Проверяем финальное состояние:")
try:
    r = requests.get(f"{BASE_URL}/api/trade/permissions", timeout=3)
    data = r.json()
    perms = data.get('permissions', {})
    print(f"   BTC: {perms.get('BTC')}")
    if perms.get('BTC') == False:
        print("   ✓ Разрешение для BTC отключено корректно")
    else:
        print("   ✗ Разрешение для BTC не изменилось")
except Exception as e:
    print(f"   ✗ Ошибка: {e}")

print("\n" + "=" * 60)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 60)
