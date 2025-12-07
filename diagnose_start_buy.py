"""
Диагностика проблемы со стартовой покупкой
"""
import requests
import json

BASE_URL = "http://localhost:5000"
CURRENCY = "ETH"

def check_current_state():
    """Проверить текущее состояние цикла"""
    print("=" * 70)
    print("ДИАГНОСТИКА СТАРТОВОЙ ПОКУПКИ")
    print("=" * 70)
    
    # 1. Проверяем состояние цикла через API
    print(f"\n1. Состояние цикла {CURRENCY}:")
    try:
        response = requests.get(f"{BASE_URL}/api/autotrader/cycle/{CURRENCY}")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                cycle = data.get("cycle", {})
                print(f"   State: {cycle.get('state')}")
                print(f"   Active: {cycle.get('active')}")
                print(f"   Cycle ID: {cycle.get('cycle_id')}")
                print(f"   Total Cycles: {cycle.get('total_cycles_count')}")
                print(f"   Active Step: {cycle.get('active_step')}")
                print(f"   Base Volume: {cycle.get('base_volume')}")
                print(f"   Start Price: {cycle.get('start_price')}")
                print(f"   Invested USD: {cycle.get('total_invested_usd')}")
            else:
                print(f"   ❌ Error: {data.get('error')}")
        else:
            print(f"   ❌ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # 2. Проверяем stats
    print(f"\n2. Stats для {CURRENCY}:")
    try:
        response = requests.get(f"{BASE_URL}/api/autotrader/stats", params={"base_currency": CURRENCY})
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                stats = data.get("stats", {})
                print(f"   Enabled: {stats.get('enabled')}")
                print(f"   Active: {stats.get('active')}")
                print(f"   State: {stats.get('state')}")
                print(f"   Base Volume: {stats.get('base_volume')}")
            else:
                print(f"   ❌ Error: {data.get('error')}")
        else:
            print(f"   ❌ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # 3. Проверяем баланс
    print(f"\n3. Баланс {CURRENCY}:")
    try:
        response = requests.get(f"{BASE_URL}/api/balance/{CURRENCY}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Available: {data.get('available')}")
            print(f"   Locked: {data.get('locked')}")
        else:
            print(f"   ❌ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print("\n" + "=" * 70)
    print("РЕКОМЕНДАЦИИ:")
    print("1. Проверьте логи сервера (консоль где запущен mTrade.py)")
    print("2. Проверьте логи автотрейдера: python check_autotrader_logs.py")
    print("3. Проверьте файл состояния: python check_cycle_state.py")
    print("=" * 70)

if __name__ == "__main__":
    check_current_state()
