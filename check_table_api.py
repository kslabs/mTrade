"""
Проверка корректности работы таблицы безубыточности через API
"""
import requests
import json

def check_indicators_api(base_currency='ETH'):
    """Проверяет API /api/trade/indicators с include_table=1"""
    url = f'http://localhost:5000/api/trade/indicators?base_currency={base_currency}&quote_currency=USDT&include_table=1'
    
    try:
        response = requests.get(url)
        data = response.json()
        
        print(f"\n{'='*60}")
        print(f"ПРОВЕРКА API ДЛЯ {base_currency}")
        print(f"{'='*60}")
        
        if not data.get('success'):
            print(f"❌ ОШИБКА: {data.get('error')}")
            return False
        
        levels = data.get('autotrade_levels', {})
        
        print(f"\n📊 Статус цикла:")
        print(f"  active_cycle: {levels.get('active_cycle')}")
        print(f"  active_step: {levels.get('active_step')}")
        print(f"  start_price: {levels.get('start_price')}")
        print(f"  last_buy_price: {levels.get('last_buy_price')}")
        
        table = levels.get('table')
        if table:
            print(f"\n✅ Таблица получена: {len(table)} шагов")
            print(f"\n📈 Первые 3 шага таблицы:")
            for i in range(min(3, len(table))):
                step = table[i]
                print(f"  Шаг {step['step']}: rate={step['rate']}, BE={step['breakeven_price']:.2f}")
            
            p0 = table[0]['rate']
            start_price = levels.get('start_price')
            
            print(f"\n🔍 Проверка корректности:")
            print(f"  P0 (table[0].rate): {p0}")
            print(f"  start_price (cycle): {start_price}")
            
            # Проверяем, что P0 близок к start_price (допустимое отклонение 1%)
            if start_price:
                diff_pct = abs(p0 - start_price) / start_price * 100
                if diff_pct < 1.0:
                    print(f"  ✅ P0 зафиксирован корректно (отклонение {diff_pct:.2f}%)")
                else:
                    print(f"  ⚠️ P0 отличается от start_price на {diff_pct:.2f}%")
            
            return True
        else:
            print(f"\n❌ Таблица отсутствует (table=null)")
            print(f"  Возможные причины:")
            print(f"  - Цикл не активен")
            print(f"  - Таблица не сохранена в файле состояния")
            print(f"  - Параметр include_table не передан")
            return False
            
    except Exception as e:
        print(f"\n❌ ОШИБКА подключения к API: {e}")
        return False

if __name__ == '__main__':
    print("\n🔍 ПРОВЕРКА ТАБЛИЦЫ БЕЗУБЫТОЧНОСТИ ЧЕРЕЗ API\n")
    
    # Проверяем все валюты с активными циклами
    currencies = ['BTC', 'ETH', 'WLD']
    
    results = {}
    for currency in currencies:
        result = check_indicators_api(currency)
        results[currency] = result
    
    print(f"\n{'='*60}")
    print("ИТОГОВАЯ СВОДКА")
    print(f"{'='*60}")
    
    for currency, success in results.items():
        status = "✅ OK" if success else "❌ FAIL"
        print(f"  {currency}: {status}")
    
    print()
