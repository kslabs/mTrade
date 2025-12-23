"""
Тест API старта (возобновления) цикла
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"
CURRENCY = "ETH"

def test_resume_cycle():
    print("=" * 80)
    print("ТЕСТ API СТАРТА (ВОЗОБНОВЛЕНИЯ) ЦИКЛА")
    print("=" * 80)
    print()
    
    # 1. Проверяем текущее состояние
    print("[1] Текущее состояние ETH:")
    try:
        r = requests.get(f"{BASE_URL}/api/autotrader/stats?base_currency={CURRENCY}")
        data = r.json()
        stats = data.get('stats', {})
        active = stats.get('active')
        manual_pause = stats.get('manual_pause', 'N/A')
        
        print(f"    Active: {active}")
        print(f"    State: {stats.get('state')}")
        print(f"    Manual Pause: {manual_pause}")
        
        if active:
            print("    ⚠️ Цикл уже активен! Сначала сбросьте цикл.")
            return
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
        return
    
    print()
    
    # 2. Попытка старта цикла
    print("[2] Отправка запроса на старт цикла:")
    try:
        r = requests.post(
            f"{BASE_URL}/api/autotrader/resume_cycle",
            json={"base_currency": CURRENCY},
            timeout=10
        )
        
        print(f"    HTTP Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            print(f"    Success: {data.get('success')}")
            
            if data.get('success'):
                print(f"    ✅ {data.get('message', '').split('.')[0]}")
            else:
                print(f"    ❌ Error: {data.get('error')}")
        else:
            print(f"    ❌ HTTP Error")
            try:
                error_data = r.json()
                print(f"    Error: {error_data.get('error')}")
            except:
                print(f"    Response: {r.text[:200]}")
    except Exception as e:
        print(f"    ❌ Исключение: {e}")
    
    print()
    time.sleep(0.5)
    
    # 3. Проверка состояния после старта
    print("[3] Состояние после старта:")
    try:
        r = requests.get(f"{BASE_URL}/api/autotrader/stats?base_currency={CURRENCY}")
        data = r.json()
        stats = data.get('stats', {})
        
        print(f"    Active: {stats.get('active')}")
        print(f"    State: {stats.get('state')}")
        
        # Проверяем файл состояния
        import json as json_lib
        with open('autotrader_cycles_state.json', 'r', encoding='utf-8') as f:
            file_data = json_lib.load(f)
        
        eth = file_data.get('ETH', {})
        print(f"    Manual Pause (файл): {eth.get('manual_pause')}")
        
        if not eth.get('manual_pause'):
            print("    ✅ Флаг manual_pause снят, автостарт разрешён")
        else:
            print("    ❌ Флаг manual_pause всё ещё установлен")
            
    except Exception as e:
        print(f"    ❌ Ошибка: {e}")
    
    print()
    print("=" * 80)
    print("ПРИМЕЧАНИЕ:")
    print("Цикл не активируется сразу после нажатия кнопки 'Старт цикла'.")
    print("Автотрейдер начнёт новый цикл автоматически, когда выполнятся")
    print("условия для стартовой покупки (достаточный баланс, цена и т.д.).")
    print("=" * 80)

if __name__ == "__main__":
    test_resume_cycle()
