"""
Комплексная автоматическая проверка всех компонентов системы
Запускает все тесты и выдаёт итоговый отчёт
"""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

# Цвета для консоли (Windows)
try:
    import colorama
    colorama.init()
    GREEN = colorama.Fore.GREEN
    RED = colorama.Fore.RED
    YELLOW = colorama.Fore.YELLOW
    BLUE = colorama.Fore.BLUE
    RESET = colorama.Style.RESET_ALL
except:
    GREEN = RED = YELLOW = BLUE = RESET = ""

def print_header(text):
    print(f"\n{BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{RESET}")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ {text}{RESET}")

# Тесты
def test_server():
    """Проверка доступности сервера"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.ok:
            print_success("Сервер доступен")
            return True
        else:
            print_error(f"Сервер недоступен (статус {response.status_code})")
            return False
    except Exception as e:
        print_error(f"Сервер недоступен: {e}")
        return False

def test_api_params():
    """Проверка API параметров"""
    currencies = [('ETH', True), ('BTC', True), (None, False)]
    all_ok = True
    
    for currency, should_have_currency in currencies:
        try:
            url = f"{BASE_URL}/api/trade/params"
            if currency:
                url += f"?base_currency={currency}"
            
            response = requests.get(url, timeout=5)
            
            if response.ok:
                data = response.json()
                if data.get('success') and data.get('params'):
                    params_count = len(data['params'])
                    currency_name = currency or 'DEFAULT'
                    print_success(f"API параметров {currency_name}: {params_count} полей")
                else:
                    print_error(f"API параметров {currency or 'DEFAULT'}: нет данных")
                    all_ok = False
            else:
                print_error(f"API параметров {currency or 'DEFAULT'}: статус {response.status_code}")
                all_ok = False
        except Exception as e:
            print_error(f"API параметров {currency or 'DEFAULT'}: {e}")
            all_ok = False
    
    return all_ok

def test_api_resume():
    """Проверка API старта цикла"""
    try:
        url = f"{BASE_URL}/api/autotrader/resume_cycle"
        payload = {'base_currency': 'ETH'}
        
        response = requests.post(url, json=payload, timeout=5)
        
        if response.ok:
            data = response.json()
            if data.get('success'):
                print_success("API старта цикла работает")
                return True
            else:
                print_error(f"API старта цикла: {data.get('error')}")
                return False
        else:
            print_error(f"API старта цикла: статус {response.status_code}")
            return False
    except Exception as e:
        print_error(f"API старта цикла: {e}")
        return False

def test_pages():
    """Проверка доступности страниц"""
    pages = [
        ('/', 'Главная страница'),
        ('/test_params', 'Тестовая страница'),
        ('/diagnostic_report', 'Отчёт диагностики')
    ]
    
    all_ok = True
    for path, name in pages:
        try:
            response = requests.get(f"{BASE_URL}{path}", timeout=5)
            if response.ok:
                print_success(f"{name} доступна")
            else:
                print_error(f"{name}: статус {response.status_code}")
                all_ok = False
        except Exception as e:
            print_error(f"{name}: {e}")
            all_ok = False
    
    return all_ok

def test_app_js():
    """Проверка app.js"""
    try:
        response = requests.get(f"{BASE_URL}/static/app.js", timeout=5)
        if response.ok:
            content = response.text
            functions = [
                'loadTradeParams',
                'saveTradeParams',
                'handleResetCycle',
                'handleResumeCycle',
                'const $='
            ]
            
            missing = []
            for func in functions:
                if func not in content:
                    missing.append(func)
            
            if not missing:
                print_success(f"app.js загружен ({len(content)} байт)")
                return True
            else:
                print_error(f"app.js: отсутствуют функции: {', '.join(missing)}")
                return False
        else:
            print_error(f"app.js: статус {response.status_code}")
            return False
    except Exception as e:
        print_error(f"app.js: {e}")
        return False

def main():
    print_header("КОМПЛЕКСНАЯ ПРОВЕРКА СИСТЕМЫ")
    print_info(f"Сервер: {BASE_URL}")
    
    results = {
        'Сервер': test_server(),
        'API параметров': test_api_params(),
        'API старта цикла': test_api_resume(),
        'Страницы': test_pages(),
        'app.js': test_app_js()
    }
    
    # Итоговый отчёт
    print_header("ИТОГОВЫЙ ОТЧЁТ")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"\nВсего тестов: {total}")
    print(f"{GREEN}Пройдено: {passed}{RESET}")
    if failed > 0:
        print(f"{RED}Не пройдено: {failed}{RESET}")
    
    print("\nДетали:")
    for name, result in results.items():
        if result:
            print_success(name)
        else:
            print_error(name)
    
    # Рекомендации
    print_header("РЕКОМЕНДАЦИИ")
    
    if all(results.values()):
        print_success("Все тесты пройдены!")
        print_info("Система работает корректно.")
        print_info("Если параметры не загружаются на странице - очистите кеш браузера:")
        print("  1. Ctrl+Shift+Delete")
        print("  2. Очистить кеш и cookie")
        print("  3. Закрыть браузер")
        print("  4. Открыть снова")
    else:
        print_warning("Некоторые тесты не пройдены")
        print_info("Проверьте, запущен ли сервер mTrade.py")
        print_info("Проверьте логи сервера на наличие ошибок")
    
    # Полезные ссылки
    print_header("ПОЛЕЗНЫЕ ССЫЛКИ")
    print(f"  • Главная страница: {BASE_URL}/")
    print(f"  • Тестовая страница: {BASE_URL}/test_params")
    print(f"  • Отчёт диагностики: {BASE_URL}/diagnostic_report")
    
    print_header("ПРОВЕРКА ЗАВЕРШЕНА")
    
    # Возвращаем код выхода
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nПроверка прервана пользователем")
        sys.exit(1)
