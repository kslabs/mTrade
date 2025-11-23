"""
Тестовый скрипт для проверки работы кнопки "Сброс цикла"
"""
import requests
import json
import time

API_URL = "http://localhost:5000"

def test_reset_cycle():
    """Тестирует сброс цикла через API"""
    print("=" * 60)
    print("ТЕСТ: Сброс цикла DOGE через API")
    print("=" * 60)
    
    # 1. Проверяем текущее состояние цикла
    print("\n1. Проверка текущего состояния цикла...")
    response = requests.get(f"{API_URL}/api/trade/indicators?base=DOGE&quote=USDT")
    if response.ok:
        data = response.json()
        if data.get('autotrade_levels'):
            levels = data['autotrade_levels']
            print(f"   Активный цикл: {levels.get('active_cycle')}")
            print(f"   Шаг: {levels.get('active_step')}")
            invested = levels.get('invested_usd') or 0
            volume = levels.get('base_volume') or 0
            print(f"   Инвестировано: {invested:.4f} USDT")
            print(f"   Объём: {volume:.8f} DOGE")
        else:
            print("   ⚠️ Нет данных об автотрейдинге")
    else:
        print(f"   ❌ Ошибка получения состояния: {response.status_code}")
    
    # 2. Выполняем сброс цикла
    print("\n2. Выполнение сброса цикла...")
    response = requests.post(
        f"{API_URL}/api/autotrader/reset_cycle",
        json={"base_currency": "DOGE"},
        headers={"Content-Type": "application/json"}
    )
    
    if response.ok:
        data = response.json()
        if data.get('success'):
            print(f"   ✅ Сброс выполнен успешно!")
            print(f"   Сообщение: {data.get('message')}")
            if data.get('old_state'):
                old = data['old_state']
                print(f"   Старое состояние: активен={old.get('active')}, "
                      f"шаг={old.get('step')}, инвест={old.get('invested', 0):.4f}")
        else:
            print(f"   ❌ Ошибка: {data.get('error')}")
    else:
        print(f"   ❌ HTTP ошибка: {response.status_code}")
        print(f"   {response.text}")
    
    # 3. Ждём немного и проверяем обновлённое состояние
    print("\n3. Ожидание обновления состояния (5 сек)...")
    time.sleep(5)
    
    print("\n4. Проверка нового состояния цикла...")
    response = requests.get(f"{API_URL}/api/trade/indicators?base=DOGE&quote=USDT")
    if response.ok:
        data = response.json()
        if data.get('autotrade_levels'):
            levels = data['autotrade_levels']
            print(f"   Активный цикл: {levels.get('active_cycle')}")
            print(f"   Шаг: {levels.get('active_step')}")
            invested = levels.get('invested_usd') or 0
            volume = levels.get('base_volume') or 0
            print(f"   Инвестировано: {invested:.4f} USDT")
            print(f"   Объём: {volume:.8f} DOGE")
            
            if levels.get('active_cycle'):
                print("\n   ✅ НОВЫЙ ЦИКЛ НАЧАТ АВТОМАТИЧЕСКИ!")
            else:
                print("\n   ⚠️ Цикл ещё не начат (может быть недостаточно средств)")
        else:
            print("   ⚠️ Нет данных об автотрейдинге")
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)

if __name__ == "__main__":
    test_reset_cycle()
