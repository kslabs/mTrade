"""
Проверка всех критичных API-эндпоинтов для загрузки параметров
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_all_apis():
    print("=" * 80)
    print("ПРОВЕРКА ВСЕХ КРИТИЧНЫХ API")
    print("=" * 80)
    print()
    
    tests = [
        ("Server Status", "GET", "/api/server/status", None),
        ("Trade Params (ETH)", "GET", "/api/trade/params?base_currency=ETH", None),
        ("Currencies List", "GET", "/api/currencies", None),
        ("Network Mode", "GET", "/api/network/mode", None),
        ("Auto Trade Status", "GET", "/api/autotrade/status", None),
        ("Trade Permissions", "GET", "/api/trade/permissions", None),
        ("UI State", "GET", "/api/ui/state", None),
        ("Breakeven Table", "GET", "/api/breakeven/table?base_currency=ETH&steps=16&start_volume=10&pprof=0.45&kprof=0.01&target_r=0.6&rk=0.13&geom_multiplier=1.371&rebuy_mode=geometric&orderbook_level=0.26", None),
    ]
    
    results = []
    
    for name, method, endpoint, data in tests:
        print(f"[{len(results)+1}] {name}")
        print(f"    {method} {endpoint}")
        
        try:
            if method == "GET":
                r = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            else:
                r = requests.post(f"{BASE_URL}{endpoint}", json=data, timeout=5)
            
            status = r.status_code
            print(f"    Status: {status}")
            
            if status == 200:
                try:
                    response_data = r.json()
                    success = response_data.get('success', None)
                    if success is not None:
                        print(f"    Success: {success}")
                    
                    # Показать часть ответа
                    response_str = json.dumps(response_data, ensure_ascii=False)
                    if len(response_str) > 150:
                        print(f"    Response: {response_str[:150]}...")
                    else:
                        print(f"    Response: {response_str}")
                    
                    results.append((name, "✅ OK"))
                except Exception as e:
                    print(f"    ⚠️  Не JSON ответ: {r.text[:100]}")
                    results.append((name, "⚠️  Not JSON"))
            else:
                print(f"    ❌ HTTP {status}")
                print(f"    Error: {r.text[:200]}")
                results.append((name, f"❌ HTTP {status}"))
        
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            results.append((name, f"❌ {type(e).__name__}"))
        
        print()
    
    print("=" * 80)
    print("ИТОГИ:")
    print("=" * 80)
    for name, status in results:
        print(f"{status} {name}")
    print("=" * 80)

if __name__ == "__main__":
    test_all_apis()
