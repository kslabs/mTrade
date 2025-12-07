"""
Проверка отображения данных автотрейдера через API
"""
import requests
import json

def check_autotrader_stats(base_currency='ETH'):
    """Проверяет статистику автотрейдера для валюты"""
    url = f'http://localhost:5000/api/autotrader/stats?base_currency={base_currency}'
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        print(f"\n{'='*60}")
        print(f"Статистика автотрейдера для {base_currency}")
        print(f"{'='*60}")
        
        if data.get('success'):
            stats = data.get('stats', {})
            print(f"\nОбщая информация:")
            print(f"  Включен: {stats.get('enabled')}")
            print(f"  Запущен: {stats.get('running')}")
            print(f"  Версия: {stats.get('version')}")
            
            print(f"\nСостояние цикла:")
            print(f"  Состояние: {stats.get('state', 'N/A')}")
            print(f"  Активен: {stats.get('active', False)}")
            print(f"  Текущий шаг: {stats.get('active_step', 'N/A')}")
            
            print(f"\nПараметры цикла:")
            print(f"  Стартовая цена: {stats.get('start_price', 0)}")
            print(f"  Последняя покупка: {stats.get('last_buy_price', 0)}")
            print(f"  Объём базовой валюты: {stats.get('base_volume', 0)}")
            print(f"  Инвестировано USDT: {stats.get('total_invested_usd', 0)}")
            
            print(f"\n{'='*60}")
        else:
            print(f"Ошибка: {data.get('error')}")
            
        return data
        
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        return None

if __name__ == '__main__':
    # Проверяем несколько валют
    currencies = ['ETH', 'XRP', 'SOL', 'DOGE']
    
    for currency in currencies:
        check_autotrader_stats(currency)
