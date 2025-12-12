"""
Диагностика проблемы со стартовой покупкой ETH
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def check_eth_balance():
    """Проверить текущий баланс ETH"""
    print("=" * 70)
    print("ПРОВЕРКА БАЛАНСА ETH")
    print("=" * 70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/balance")
        if response.status_code == 200:
            data = response.json()
            balances = data.get('balances', [])
            
            eth_balance = next((b for b in balances if b.get('currency') == 'ETH'), None)
            usdt_balance = next((b for b in balances if b.get('currency') == 'USDT'), None)
            
            print(f"\nETH:")
            if eth_balance:
                print(f"  Available: {eth_balance.get('available', 0)}")
                print(f"  Locked: {eth_balance.get('locked', 0)}")
            else:
                print("  НЕТ ДАННЫХ")
            
            print(f"\nUSDT:")
            if usdt_balance:
                print(f"  Available: {usdt_balance.get('available', 0)}")
                print(f"  Locked: {usdt_balance.get('locked', 0)}")
            else:
                print("  НЕТ ДАННЫХ")
                
        else:
            print(f"Ошибка HTTP {response.status_code}")
    except Exception as e:
        print(f"Ошибка: {e}")

def check_eth_cycle():
    """Проверить состояние цикла ETH"""
    print("\n" + "=" * 70)
    print("СОСТОЯНИЕ ЦИКЛА ETH")
    print("=" * 70)
    
    try:
        # Читаем из файла
        with open("autotrader_cycles_state.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        eth_cycle = data.get("ETH", {})
        
        print(f"\nActive: {eth_cycle.get('active', False)}")
        print(f"Active Step: {eth_cycle.get('active_step', -1)}")
        print(f"Start Price: {eth_cycle.get('start_price', 0.0)}")
        print(f"Base Volume: {eth_cycle.get('base_volume', 0.0)}")
        print(f"Total Invested USD: {eth_cycle.get('total_invested_usd', 0.0)}")
        print(f"Manual Pause: {eth_cycle.get('manual_pause', False)}")
        
        if 'cycle_id' in eth_cycle:
            print(f"Cycle ID: {eth_cycle.get('cycle_id')}")
        if 'total_cycles_count' in eth_cycle:
            print(f"Total Cycles Count: {eth_cycle.get('total_cycles_count')}")
            
    except Exception as e:
        print(f"Ошибка: {e}")

def check_recent_orders():
    """Проверить последние ордера ETH"""
    print("\n" + "=" * 70)
    print("ПОСЛЕДНИЕ ОРДЕРА ETH")
    print("=" * 70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/orders/recent", params={'symbol': 'ETH_USDT', 'limit': 5})
        if response.status_code == 200:
            data = response.json()
            orders = data.get('orders', [])
            
            if not orders:
                print("\nОрдеров нет")
            else:
                for order in orders:
                    print(f"\nOrder ID: {order.get('id')}")
                    print(f"  Side: {order.get('side')}")
                    print(f"  Type: {order.get('type')}")
                    print(f"  Status: {order.get('status')}")
                    print(f"  Amount: {order.get('amount')}")
                    print(f"  Filled: {order.get('filled_amount', 0)}")
                    print(f"  Price: {order.get('price', 'N/A')}")
                    
        else:
            print(f"Ошибка HTTP {response.status_code}")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_eth_balance()
    check_eth_cycle()
    check_recent_orders()
    print("\n" + "=" * 70)
