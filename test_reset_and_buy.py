"""
Скрипт для тестирования P0:
1. Сбрасывает активный цикл
2. Продаёт всю базовую валюту
3. Ждёт стартовую покупку
4. Проверяет P0 в таблице
"""
import requests
import time
import json

BASE_URL = "http://localhost:5000"
BASE_CURRENCY = "DOGE"
QUOTE_CURRENCY = "USDT"

def reset_cycle():
    """Сброс активного цикла"""
    print(f"\n{'='*60}")
    print("ШАГ 1: Сброс активного цикла")
    print('='*60)
    
    url = f"{BASE_URL}/api/autotrader/reset_cycle"
    payload = {
        "base_currency": BASE_CURRENCY,
        "quote_currency": QUOTE_CURRENCY
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Результат: {json.dumps(data, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ Ошибка: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

def sell_all():
    """Продажа всей базовой валюты"""
    print(f"\n{'='*60}")
    print("ШАГ 2: Продажа всей базовой валюты")
    print('='*60)
    
    # Получаем баланс
    url = f"{BASE_URL}/api/balances"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"❌ Не удалось получить баланс: {response.status_code}")
            return False
        
        balances = response.json()
        base_balance = 0.0
        
        for bal in balances:
            if bal.get('currency') == BASE_CURRENCY:
                base_balance = float(bal.get('available', 0))
                break
        
        print(f"Текущий баланс {BASE_CURRENCY}: {base_balance:.8f}")
        
        if base_balance < 0.01:
            print(f"✅ Баланс {BASE_CURRENCY} уже близок к нулю, продавать нечего")
            return True
        
        # Получаем текущую цену
        ticker_url = f"{BASE_URL}/api/ticker/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
        ticker_response = requests.get(ticker_url, timeout=10)
        if ticker_response.status_code != 200:
            print(f"❌ Не удалось получить цену: {ticker_response.status_code}")
            return False
        
        ticker = ticker_response.json()
        current_price = float(ticker.get('last', 0))
        print(f"Текущая цена: {current_price:.8f} {QUOTE_CURRENCY}")
        
        # Размещаем ордер на продажу
        sell_url = f"{BASE_URL}/api/trade/sell"
        sell_payload = {
            "base": BASE_CURRENCY,
            "quote": QUOTE_CURRENCY,
            "amount": base_balance,
            "price": current_price * 0.99  # Продаём чуть ниже рынка для гарантии исполнения
        }
        
        print(f"Размещаем ордер: {base_balance:.8f} {BASE_CURRENCY} по цене {sell_payload['price']:.8f}")
        
        sell_response = requests.post(sell_url, json=sell_payload, timeout=10)
        print(f"Статус: {sell_response.status_code}")
        
        if sell_response.status_code == 200:
            result = sell_response.json()
            print(f"✅ Результат продажи: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ Ошибка продажи: {sell_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Исключение при продаже: {e}")
        return False

def wait_for_buy_and_check_p0():
    """Ждём стартовую покупку и проверяем P0"""
    print(f"\n{'='*60}")
    print("ШАГ 3: Ожидание стартовой покупки и проверка P0")
    print('='*60)
    
    print("Ожидаю стартовую покупку (до 60 секунд)...")
    
    for i in range(60):
        time.sleep(1)
        
        # Проверяем состояние цикла
        url = f"{BASE_URL}/api/market_data/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue
            
            data = response.json()
            levels = data.get('autotrade_levels', {})
            
            if levels.get('active_cycle'):
                print(f"\n✅ Цикл активирован на {i+1} секунде!")
                
                # Получаем таблицу безубыточности
                table_url = f"{BASE_URL}/api/breakeven_table/{BASE_CURRENCY}_{QUOTE_CURRENCY}"
                table_response = requests.get(table_url, timeout=10)
                
                if table_response.status_code == 200:
                    table_data = table_response.json()
                    table = table_data.get('table', [])
                    
                    if table and len(table) > 0:
                        p0_in_table = table[0].get('rate', 0)
                        start_price_cycle = levels.get('start_price', 0)
                        last_buy_price = levels.get('last_buy_price', 0)
                        
                        print(f"\n{'='*60}")
                        print("РЕЗУЛЬТАТЫ ПРОВЕРКИ P0:")
                        print('='*60)
                        print(f"Цена последней покупки (last_buy_price): {last_buy_price:.8f}")
                        print(f"Цена старта цикла (start_price):         {start_price_cycle:.8f}")
                        print(f"P0 в таблице (table[0]['rate']):         {p0_in_table:.8f}")
                        print('='*60)
                        
                        if abs(last_buy_price - p0_in_table) < 0.00000001:
                            print("✅ SUCCESS! P0 в таблице совпадает с ценой покупки!")
                            return True
                        else:
                            diff = abs(last_buy_price - p0_in_table)
                            print(f"❌ FAIL! P0 в таблице НЕ совпадает с ценой покупки!")
                            print(f"❌ Разница: {diff:.8f}")
                            return False
                else:
                    print(f"❌ Не удалось получить таблицу: {table_response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"⚠️ Ошибка при проверке: {e}")
            continue
    
    print("\n❌ Таймаут: стартовая покупка не произошла за 60 секунд")
    return False

def main():
    print("\n" + "="*60)
    print("ТЕСТ P0: Сброс -> Ожидание покупки -> Проверка")
    print("="*60)
    
    # Шаг 1: Сброс цикла
    if not reset_cycle():
        print("\n❌ Не удалось сбросить цикл, останавливаю тест")
        return
    
    print("\n⚠️ ВНИМАНИЕ: Цикл сброшен!")
    print("⚠️ Теперь ВРУЧНУЮ продайте всю базовую валюту через интерфейс")
    print("⚠️ После продажи нажмите ENTER для продолжения теста...")
    input()
    
    # Шаг 2: Ждём покупку и проверяем P0
    success = wait_for_buy_and_check_p0()
    
    print("\n" + "="*60)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН! P0 работает корректно!")
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! P0 не совпадает с ценой покупки!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
