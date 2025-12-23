"""
Диагностика проблемы с загрузкой параметров на главной странице
"""
import requests
import json
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:5000"

def check_main_page():
    """Проверка загрузки главной страницы"""
    print("\n" + "="*60)
    print("ПРОВЕРКА ГЛАВНОЙ СТРАНИЦЫ")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            # Проверяем наличие нужных элементов формы
            soup = BeautifulSoup(response.text, 'html.parser')
            
            form_fields = [
                'paramSteps', 'paramStartVolume', 'paramStartPrice',
                'paramPprof', 'paramKprof', 'paramTargetR', 'paramRk',
                'paramGeomMultiplier', 'paramRebuyMode', 'paramKeep',
                'paramOrderbookLevel'
            ]
            
            print("\nПроверка наличия полей формы:")
            for field_id in form_fields:
                element = soup.find(id=field_id)
                if element:
                    print(f"  ✓ {field_id}: найден")
                else:
                    print(f"  ✗ {field_id}: ОТСУТСТВУЕТ")
            
            # Проверяем наличие app.js
            scripts = soup.find_all('script', src=True)
            app_js_found = False
            for script in scripts:
                src = script.get('src', '')
                if 'app.js' in src:
                    app_js_found = True
                    print(f"\n✓ app.js найден: {src}")
            
            if not app_js_found:
                print("\n✗ app.js НЕ НАЙДЕН в HTML")
            
            # Проверяем наличие inline скриптов
            inline_scripts = soup.find_all('script', src=False)
            print(f"\nКоличество inline скриптов: {len(inline_scripts)}")
            
        else:
            print(f"ERROR: {response.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

def check_app_js():
    """Проверка доступности app.js"""
    print("\n" + "="*60)
    print("ПРОВЕРКА app.js")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/static/app.js", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            content = response.text
            print(f"Размер файла: {len(content)} байт")
            
            # Проверяем наличие ключевых функций
            functions_to_check = [
                'loadTradeParams',
                'saveTradeParams',
                'function $(',
                'const $=',
                'getElementById'
            ]
            
            print("\nПроверка наличия ключевых функций:")
            for func in functions_to_check:
                if func in content:
                    print(f"  ✓ {func}: найдена")
                else:
                    print(f"  ✗ {func}: ОТСУТСТВУЕТ")
        else:
            print(f"ERROR: {response.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

def check_params_api():
    """Проверка API параметров"""
    print("\n" + "="*60)
    print("ПРОВЕРКА API ПАРАМЕТРОВ")
    print("="*60)
    
    currencies = ['ETH', 'BTC', None]
    
    for currency in currencies:
        print(f"\n--- {currency or 'DEFAULT'} ---")
        try:
            url = f"{BASE_URL}/api/trade/params"
            if currency:
                url += f"?base_currency={currency}"
            
            response = requests.get(url, timeout=5)
            print(f"Status: {response.status_code}")
            
            if response.ok:
                data = response.json()
                print(f"Success: {data.get('success')}")
                params = data.get('params', {})
                print(f"Параметров получено: {len(params)}")
                
                # Показываем первые несколько параметров
                for i, (key, value) in enumerate(params.items()):
                    if i < 3:
                        print(f"  - {key}: {value}")
            else:
                print(f"ERROR: {response.text}")
        except Exception as e:
            print(f"EXCEPTION: {e}")

def check_console_errors():
    """Инструкция по проверке консоли браузера"""
    print("\n" + "="*60)
    print("ИНСТРУКЦИЯ ПО ПРОВЕРКЕ КОНСОЛИ БРАУЗЕРА")
    print("="*60)
    print("""
1. Откройте главную страницу в браузере: http://127.0.0.1:5000/
2. Откройте консоль разработчика (F12)
3. Перейдите на вкладку "Console" (Консоль)
4. Обновите страницу (F5 или Ctrl+Shift+R для полного обновления)
5. Проверьте наличие ошибок (красные строки)
6. Проверьте, вызывается ли функция loadTradeParams():
   - В консоли введите: loadTradeParams()
   - Должны появиться логи загрузки параметров
7. Проверьте, заполняются ли поля формы после вызова:
   - В консоли введите: $('paramSteps')
   - Должен вернуться элемент input
   - Проверьте его значение: $('paramSteps').value

ВАЖНО:
- Если функция loadTradeParams не определена - значит app.js не загружен
- Если функция $ не определена - значит есть проблема с инициализацией
- Если параметры загружаются в консоли, но не на странице - проблема в timing
""")

def main():
    print("="*60)
    print("ДИАГНОСТИКА ЗАГРУЗКИ ПАРАМЕТРОВ НА СТРАНИЦЕ")
    print("="*60)
    
    check_main_page()
    check_app_js()
    check_params_api()
    check_console_errors()
    
    print("\n" + "="*60)
    print("ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА")
    print("="*60)
    print(f"""
Для интерактивной проверки откройте тестовую страницу:
http://127.0.0.1:5000/test_params

На этой странице вы можете:
1. Выбрать валюту
2. Проверить работу API
3. Проверить заполнение формы
4. Увидеть все логи в реальном времени
""")
    
    print("\n" + "="*60)
    print("ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("="*60)

if __name__ == "__main__":
    main()
