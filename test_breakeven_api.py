"""
Тест проверки API таблицы безубыточности
Проверяет наличие полей total_invested и breakeven_pct в ответе
"""

import requests
import json

# URL вашего приложения
BASE_URL = "http://localhost:5000"

def test_breakeven_api():
    """Тест API таблицы безубыточности"""
    
    print("=" * 80)
    print("ТЕСТ API ТАБЛИЦЫ БЕЗУБЫТОЧНОСТИ")
    print("=" * 80)
    
    # Тестовые валюты
    test_currencies = ['WLD', 'XRP', 'ETH', 'BTC']
    
    for currency in test_currencies:
        print(f"\n{'=' * 80}")
        print(f"📊 Проверка таблицы для {currency}")
        print('=' * 80)
        
        try:
            # Запрос таблицы безубыточности
            url = f"{BASE_URL}/api/breakeven/table?base_currency={currency}"
            print(f"🔗 URL: {url}")
            
            response = requests.get(url, timeout=5)
            print(f"📡 Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    print(f"✅ Запрос успешен")
                    print(f"📦 Валюта: {data.get('currency', 'N/A')}")
                    print(f"💰 Текущая цена: {data.get('current_price', 0)}")
                    
                    table = data.get('table', [])
                    if table:
                        print(f"📊 Строк в таблице: {len(table)}")
                        
                        # Проверяем первую строку (step 0)
                        row0 = table[0]
                        print(f"\n🔍 Анализ первой строки (step 0):")
                        print(f"   Step: {row0.get('step', 'ОТСУТСТВУЕТ')}")
                        print(f"   Rate: {row0.get('rate', 'ОТСУТСТВУЕТ')}")
                        print(f"   Purchase USD: {row0.get('purchase_usd', 'ОТСУТСТВУЕТ')}")
                        print(f"   🎯 Total Invested: {row0.get('total_invested', '❌ ОТСУТСТВУЕТ')}")
                        print(f"   Breakeven Price: {row0.get('breakeven_price', 'ОТСУТСТВУЕТ')}")
                        print(f"   🎯 Breakeven Pct: {row0.get('breakeven_pct', '❌ ОТСУТСТВУЕТ')}")
                        print(f"   Target Delta Pct: {row0.get('target_delta_pct', 'ОТСУТСТВУЕТ')}")
                        
                        # Проверяем наличие ключевых полей
                        missing_fields = []
                        if 'total_invested' not in row0:
                            missing_fields.append('total_invested')
                        if 'breakeven_pct' not in row0:
                            missing_fields.append('breakeven_pct')
                        
                        if missing_fields:
                            print(f"\n❌ ОТСУТСТВУЮЩИЕ ПОЛЯ: {', '.join(missing_fields)}")
                        else:
                            print(f"\n✅ Все необходимые поля присутствуют")
                        
                        # Проверяем последнюю строку
                        if len(table) > 1:
                            last_row = table[-1]
                            print(f"\n🔍 Анализ последней строки (step {last_row.get('step', '?')}):")
                            print(f"   Total Invested: {last_row.get('total_invested', '❌ ОТСУТСТВУЕТ')}")
                            print(f"   Breakeven Pct: {last_row.get('breakeven_pct', '❌ ОТСУТСТВУЕТ')}")
                    else:
                        print("❌ Таблица пустая")
                else:
                    print(f"❌ Ошибка: {data.get('error', 'Неизвестная ошибка')}")
            else:
                print(f"❌ HTTP ошибка: {response.status_code}")
                print(f"   Текст ответа: {response.text[:200]}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Не удалось подключиться к серверу")
            print(f"   Убедитесь, что сервер запущен на {BASE_URL}")
            break
        except Exception as e:
            print(f"❌ Исключение: {e}")
    
    print(f"\n{'=' * 80}")
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 80)

if __name__ == '__main__':
    test_breakeven_api()
