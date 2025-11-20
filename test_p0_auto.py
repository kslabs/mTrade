"""
Полностью автоматический тест P0:
1. Проверяет текущее состояние
2. Сбрасывает цикл
3. Продаёт через market order
4. Ждёт покупку
5. Проверяет P0
"""
import requests
import time
import json

BASE_URL = "http://localhost:5000"
BASE_CURRENCY = "DOGE"
QUOTE_CURRENCY = "USDT"

def get_current_state():
    """Получить текущее состояние цикла и P0"""
    print(f"\n{'='*70}")
    print("ТЕКУЩЕЕ СОСТОЯНИЕ")
    print('='*70)
    
    try:
        # Получаем market_data
        url = f"{BASE_URL}/api/market_data/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            levels = data.get('autotrade_levels', {})
            
            print(f"Активный цикл: {levels.get('active_cycle', False)}")
            print(f"Текущий шаг: {levels.get('active_step', 'N/A')}")
            print(f"Start Price: {levels.get('start_price', 'N/A')}")
            print(f"Last Buy Price: {levels.get('last_buy_price', 'N/A')}")
            
            # Получаем таблицу
            table_url = f"{BASE_URL}/api/breakeven_table/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
            table_response = requests.get(table_url, timeout=10)
            
            if table_response.status_code == 200:
                table_data = table_response.json()
                table = table_data.get('table', [])
                if table:
                    p0 = table[0].get('rate', 'N/A')
                    print(f"P0 в таблице: {p0}")
                    return levels, table
        
        return None, None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None, None

def reset_cycle():
    """Сброс цикла"""
    print(f"\n{'='*70}")
    print("ШАГ 1: СБРОС ЦИКЛА")
    print('='*70)
    
    url = f"{BASE_URL}/api/autotrader/reset_cycle"
    payload = {"base_currency": BASE_CURRENCY, "quote_currency": QUOTE_CURRENCY}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Цикл сброшен")
            return True
        else:
            print(f"❌ Ошибка сброса: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

def sell_market():
    """Продать всё по рыночной цене"""
    print(f"\n{'='*70}")
    print("ШАГ 2: ПРОДАЖА ВСЕЙ БАЗОВОЙ ВАЛЮТЫ")
    print('='*70)
    
    try:
        # Получаем market_data для баланса и цены
        market_url = f"{BASE_URL}/api/market_data/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
        market_resp = requests.get(market_url, timeout=10)
        
        if market_resp.status_code != 200:
            print(f"❌ Не могу получить данные: {market_resp.status_code}")
            return False
        
        market_data = market_resp.json()
        
        # Получаем цену
        data = market_data.get('data', {})
        current_price = float(data.get('last', 0))
        
        if current_price == 0:
            print(f"❌ Цена = 0")
            return False
        
        # Получаем баланс
        balances = market_data.get('balances', {})
        base_balance = float(balances.get(BASE_CURRENCY, {}).get('available', 0))
        
        print(f"Баланс {BASE_CURRENCY}: {base_balance:.8f}")
        print(f"Текущая цена: {current_price:.8f}")
        
        if base_balance < 1:
            print("✅ Баланс уже почти нулевой")
            return True
        
        # Продаём по цене чуть ниже рынка
        sell_price = current_price * 0.98
        
        sell_url = f"{BASE_URL}/api/trade/sell"
        sell_payload = {
            "base": BASE_CURRENCY,
            "quote": QUOTE_CURRENCY,
            "amount": base_balance,
            "price": sell_price
        }
        
        print(f"Продаю {base_balance:.8f} {BASE_CURRENCY} по цене {sell_price:.8f}")
        
        sell_resp = requests.post(sell_url, json=sell_payload, timeout=10)
        
        if sell_resp.status_code == 200:
            result = sell_resp.json()
            print(f"✅ Продано: {result}")
            return True
        else:
            print(f"❌ Ошибка продажи: {sell_resp.text}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

def wait_and_check():
    """Ждём покупку и проверяем P0"""
    print(f"\n{'='*70}")
    print("ШАГ 3: ОЖИДАНИЕ ПОКУПКИ И ПРОВЕРКА P0")
    print('='*70)
    print("Жду до 90 секунд...")
    
    for i in range(90):
        time.sleep(1)
        
        try:
            # Проверяем таблицу напрямую
            table_url = f"{BASE_URL}/api/breakeven_table/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
            table_resp = requests.get(table_url, timeout=10)
            
            if table_resp.status_code != 200:
                continue
            
            table_data = table_resp.json()
            table = table_data.get('table', [])
            
            if not table:
                continue
            
            # Получаем данные
            market_url = f"{BASE_URL}/api/market_data/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
            market_resp = requests.get(market_url, timeout=10)
            
            if market_resp.status_code != 200:
                continue
            
            market_data = market_resp.json()
            levels = market_data.get('autotrade_levels', {})
            
            # Проверяем, есть ли покупка (base_volume > 0)
            base_volume = levels.get('base_volume', 0)
            
            if base_volume and base_volume > 0:
                print(f"\n✅ ПОКУПКА ОБНАРУЖЕНА на {i+1} секунде!")
                print(f"Base Volume: {base_volume}")
                
                last_buy = levels.get('last_buy_price', 0)
                start_price = levels.get('start_price', 0)
                p0_table = table[0].get('rate', 0) if table else 0
                
                print(f"\n{'='*70}")
                print("РЕЗУЛЬТАТЫ:")
                print('='*70)
                print(f"Цена последней покупки (last_buy_price): {last_buy:.8f}")
                print(f"Start Price (цикл):                      {start_price:.8f}")
                print(f"P0 в таблице (table[0]['rate']):        {p0_table:.8f}")
                print('='*70)
                
                # Сравниваем
                if abs(last_buy - p0_table) < 0.00000001:
                    print("✅ SUCCESS! P0 = last_buy_price")
                    return True
                else:
                    diff = abs(last_buy - p0_table)
                    print(f"❌ FAIL! Разница: {diff:.8f}")
                    print(f"❌ P0 НЕ РАВЕН цене покупки!")
                    return False
                    
        except Exception as e:
            if i % 10 == 0:
                print(f"[{i}s] Проверка... ({e})")
            continue
    
    print("\n❌ Таймаут 90 секунд")
    return False

def main():
    print("\n" + "="*70)
    print("АВТОМАТИЧЕСКИЙ ТЕСТ P0")
    print("="*70)
    
    # Показываем текущее состояние
    get_current_state()
    
    # Сброс
    if not reset_cycle():
        print("\n❌ ТЕСТ ПРОВАЛЕН: не удалось сбросить цикл")
        return
    
    print("\n⚠️ Цикл сброшен! Теперь ВРУЧНУЮ продайте DOGE через интерфейс")
    print("⚠️ Нажмите ENTER после продажи...")
    input()
    
    time.sleep(2)
    
    # Ждём и проверяем
    success = wait_and_check()
    
    print("\n" + "="*70)
    if success:
        print("✅✅✅ ТЕСТ ПРОЙДЕН! P0 РАБОТАЕТ КОРРЕКТНО! ✅✅✅")
    else:
        print("❌❌❌ ТЕСТ ПРОВАЛЕН! P0 НЕ РАБОТАЕТ! ❌❌❌")
    print("="*70 + "\n")
    
    # Показываем финальное состояние
    print("\nФИНАЛЬНОЕ СОСТОЯНИЕ:")
    get_current_state()

if __name__ == "__main__":
    main()
