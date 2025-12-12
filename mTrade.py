"""
Gate.io Multi-Trading Application
Поддержка обычного трейдинга и копитрейдинга
Автор: Ваше имя
Дата: 4 ноября 2025
"""

import os
import sys
import json
import time
import random  # добавлено для автотрейдера
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
import requests
from threading import Thread
from typing import Dict, List, Optional
import traceback

# Импорт модулей проекта
from config import Config
from process_manager import ProcessManager
from gate_api_client import GateAPIClient
from trading_engine import TradingEngine, AccountManager
from gateio_websocket import init_websocket_manager, get_websocket_manager
from state_manager import get_state_manager
# СТАРЫЙ АВТОТРЕЙДЕР (DEPRECATED, багует с множественными покупками!)
# from autotrader import AutoTrader
# from dual_thread_autotrader import DualThreadAutoTrader

# НОВЫЙ АВТОТРЕЙДЕР V2 (чистая архитектура, без багов!)
try:
    # Импорт автотрейдера выполняем лениво: если модуль некорректен — не ломаем весь сервер.
    from autotrader_v2 import AutoTraderV2
except Exception as e:
    AutoTraderV2 = None
    print(f"[WARN] Не удалось импортировать autotrader_v2: {e}")
    import traceback
    print(traceback.format_exc())

from trade_logger import get_trade_logger
from currency_sync import CurrencySync  # Синхронизация валют с Gate.io
from quick_trade_handler import handle_buy_min, handle_sell_all  # Обработчики быстрой торговли
from trade_events import get_trade_events, add_trade_event  # Очередь торговых событий для DEBUG PANEL

# Конфигурация Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)
# Полностью отключаем кеширование шаблонов/статических и ETag
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['ETAG_DISABLED'] = True

# Отключить кеширование для всех ответов
@app.after_request
def add_header(response):
    """Добавить заголовки для отключения кеша"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    # Диагностический заголовок с mtime шаблона index.html
    try:
        template_path = os.path.join(app.root_path, 'templates', 'index.html')
        if os.path.exists(template_path):
            response.headers['X-Template-MTime'] = str(os.path.getmtime(template_path))
    except Exception:
        pass
    return response

# Глобальный обработчик ошибок для API endpoints
@app.errorhandler(Exception)
def handle_error(error):
    """Обработка всех необработанных исключений"""
    # Если это API запрос (начинается с /api/), возвращаем JSON
    if request.path.startswith('/api/'):
        import traceback
        error_message = str(error)
        error_traceback = traceback.format_exc()
        print(f"[ERROR] API Exception: {error_message}")
        print(f"[ERROR] Traceback:\n{error_traceback}")
        return jsonify({
            "success": False,
            "error": error_message,
            "path": request.path
        }), 500
    # Для обычных запросов пробрасываем стандартную обработку
    raise error

# =============================================================================
# ИНИЦИАЛИЗАЦИЯ ГЛОБАЛЬНЫХ ПЕРЕМЕННЫХ
# =============================================================================

# Инициализация глобальных служебных переменных
server_start_time = time.time()
PAIR_INFO_CACHE = {}
PAIR_INFO_CACHE_TTL = 3600  # 1 час
CURRENT_NETWORK_MODE = Config.load_network_mode()
print(f"[NETWORK] Текущий режим сети: {CURRENT_NETWORK_MODE}")

# Multi-pairs watcher глобальные переменные
WATCHED_PAIRS = set()
MULTI_PAIRS_CACHE = {}  # { pair: { ts: <float>, data: <dict> } }

# --- Реинициализация сетевого режима (work/test) ---
_ws_reinit_lock = None
try:
    from threading import Lock
    _ws_reinit_lock = Lock()
except Exception:
    pass

def _init_default_watchlist():
    """Инициализирует watchlist валютными парами по умолчанию из currencies.json"""
    try:
        bases = Config.load_currencies()
        default_pairs = []
        for c in bases:
            code = (c or {}).get('code')
            if code:
                default_pairs.append(f"{str(code).upper()}_USDT")
        if default_pairs:
            from threading import Lock as _Lock
            # Используем WATCHED_PAIRS напрямую
            for pair in default_pairs:
                WATCHED_PAIRS.add(pair)
    except Exception as e:
        print(f"[WATCHLIST] Ошибка инициализации: {e}")

def _reinit_network_mode(new_mode: str) -> bool:
    """Переключение режима сети с переинициализацией WebSocket менеджера.
    - Закрывает старые соединения
    - Сохраняет новый режим на диск
    - Инициализирует менеджер с ключами соответствующей сети
    - Пересоздает базовый watchlist
    """
    global CURRENT_NETWORK_MODE
    new_mode = str(new_mode).lower()
    if new_mode not in ('work','test'):
        return False
    if new_mode == CURRENT_NETWORK_MODE:
        return True  # уже установлен
    if _ws_reinit_lock:
        _ws_reinit_lock.acquire()
    try:
        print(f"[NETWORK] Переключение режима: {CURRENT_NETWORK_MODE} -> {new_mode}")
        # Сохраняем файл конфигурации режима
        Config.save_network_mode(new_mode)
        CURRENT_NETWORK_MODE = new_mode
        # Закрываем текущие WS соединения
        ws_manager = get_websocket_manager()
        if ws_manager:
            try:
                ws_manager.close_all()
            except Exception as e:
                print(f"[NETWORK] Ошибка закрытия WS: {e}")
        # Инициализация нового менеджера
        try:
            ak, sk = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
            init_websocket_manager(ak, sk, CURRENT_NETWORK_MODE)
            _init_default_watchlist()
            print(f"[NETWORK] WS менеджер переинициализирован (mode={CURRENT_NETWORK_MODE}, keys={'yes' if ak and sk else 'no'})")
        except Exception as e:
            print(f"[NETWORK] Ошибка инициализации WS менеджера: {e}")
        return True
    finally:
        if _ws_reinit_lock:
            _ws_reinit_lock.release()


# =============================================================================
# FLASK ROUTES (WEB INTERFACE)
# =============================================================================

# Глобальные объекты
account_manager = AccountManager()
trading_engines = {}

# Параметры торговли по умолчанию (глобальные, используются как базовые для всех валют)
DEFAULT_TRADE_PARAMS = {
    'steps': 16,
    'start_volume': 3.0,
    'start_price': 0.0,
    'pprof': 0.6,
    'kprof': 0.02,
    'target_r': 3.65,
    'geom_multiplier': 2.0,
    'rebuy_mode': 'geometric',
    'orderbook_level': 0  # Базовый множитель для уровня стакана (формула: (шаг × orderbook_level) + 1)
}

# Инициализация State Manager (раньше, чтобы он был доступен во всех эндпойнтах)
state_manager = get_state_manager()

# Глобальная функция для создания API клиента (нужна для multiprocessing - локальные функции не pickle-able)
def _create_api_client():
    """
    Создать API клиент для текущего активного аккаунта.
    Эта функция должна быть глобальной для работы с multiprocessing.
    """
    if not account_manager.active_account:
        return None
    acc = account_manager.get_account(account_manager.active_account)
    if not acc:
        return None
    return GateAPIClient(acc['api_key'], acc['api_secret'], CURRENT_NETWORK_MODE)

# Глобальный экземпляр автотрейдера (инициализируется позже)
AUTO_TRADER = None

# Глобальные переменные для торговли (загружаются из state_manager)
TRADING_MODE = state_manager.get_trading_mode()
TRADING_PERMISSIONS = state_manager.get_trading_permissions()
AUTO_TRADE_GLOBAL_ENABLED = state_manager.get_auto_trade_enabled()
TRADE_PARAMS = state_manager.get("legacy_trade_params", DEFAULT_TRADE_PARAMS.copy())

@app.route('/')
def index():
    """Главная страница"""
    print('[ROUTE] GET / index served')
    import time, hashlib
    # Генерируем подпись содержимого шаблона для контроля версии
    template_path = os.path.join(app.root_path, 'templates', 'index.html')
    sig = ''
    try:
        with open(template_path, 'rb') as f:
            sig = hashlib.md5(f.read()).hexdigest()[:8]
    except Exception:
        sig = 'nosig'
    response = app.make_response(render_template('index.html', cache_buster=int(time.time()), tpl_sig=sig))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Template-Sig'] = sig
    return response

@app.route('/v2')
@app.route('/v2/')
def index_v2():
    """Альтернативная главная страница (для обхода кеша по новому URL)"""
    print('[ROUTE] GET /v2 index served')
    import time
    response = app.make_response(render_template('index.html', cache_buster=int(time.time())))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/test_params')
@app.route('/test_params/')
def test_params():
    """Тестовая страница для проверки загрузки параметров"""
    print('[ROUTE] GET /test_params served')
    import time
    response = app.make_response(render_template('test_params.html', cache_buster=int(time.time())))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/diagnostic_report')
@app.route('/diagnostic_report/')
def diagnostic_report():
    """Страница с итоговым отчётом диагностики"""
    print('[ROUTE] GET /diagnostic_report served')
    import time
    response = app.make_response(render_template('diagnostic_report.html', cache_buster=int(time.time())))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/version')
def version():
    """Версия и аптайм сервера для диагностики кеша/перезапуска."""
    return jsonify({
        "ok": True,
        "pid": os.getpid(),
        "server_start_time": server_start_time,
        "now": time.time()
    })

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/favicon.ico')
def favicon():
    """Глушим запрос favicon, чтобы убрать 404 в консоли"""
    return ('', 204)

@app.route('/test')
def test_orderbook():
    """Тестовая страница для проверки стакана"""
    return render_template('test_orderbook.html')

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Получить список аккаунтов"""
    return jsonify({
        "accounts": account_manager.list_accounts(),
        "active": account_manager.active_account
    })

@app.route('/api/accounts', methods=['POST'])
def add_account():
    """Добавить новый аккаунт"""
    data = request.json
    account_manager.add_account(
        data['name'],
        data['api_key'],
        data['api_secret']
    )
    return jsonify({"success": True, "message": "Аккаунт добавлен"})

@app.route('/api/mode', methods=['GET'])
def get_mode():
    """Получить текущий режим торговли (trade/copy) (совместимость)"""
    mode = state_manager.get_trading_mode()
    internal_mode = 'normal' if mode == 'trade' else 'copy'
    return jsonify({"mode": mode, "internal_mode": internal_mode, "success": True})

@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Переключить режим торговли (trade/copy)"""
    global TRADING_MODE
    try:
        data = request.get_json(silent=True) or {}
        mode = str(data.get('mode','')).lower().strip()
        if mode not in ('trade','copy'):
            return jsonify({"success": False, "error": "Неверный режим"}), 400
        TRADING_MODE = mode
        state_manager.set_trading_mode(mode)
        stored = state_manager.get_trading_mode()
        # Применяем ко всем активным движкам
        internal_mode = 'normal' if stored == 'trade' else 'copy'
        for eng in trading_engines.values():
            try:
                eng.set_mode(internal_mode)
            except Exception:
                pass
        print(f"[MODE] Установлен режим: {stored} (internal={internal_mode})")
        return jsonify({"mode": stored, "internal_mode": internal_mode, "success": True})
    except Exception as e:
        import traceback
        print(f"[ERROR] set_mode: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/mode/legacy', methods=['GET'])
def get_mode_legacy():
    """Legacy формат ответа только с полем mode"""
    return jsonify({"mode": state_manager.get_trading_mode()})

# =============================================================================
# CURRENCIES API (Управление валютами)
# =============================================================================

@app.route('/api/currencies', methods=['GET'])
def get_currencies():
    """Получить список базовых валют"""
    currencies = Config.load_currencies()
    return jsonify({"success": True, "currencies": currencies})

@app.route('/api/currencies', methods=['POST'])
def save_currencies():
    """Сохранить список базовых валют"""
    try:
        data = request.json
        currencies = data.get('currencies', [])
        
        # Валидация
        if not currencies or not isinstance(currencies, list):
            return jsonify({"success": False, "error": "Неверный формат данных"}), 400
        
        # Проверка на дубликаты
        codes = [c.get('code') for c in currencies]
        if len(codes) != len(set(codes)):
            return jsonify({"success": False, "error": "Обнаружены дублирующиеся коды валют"}), 400
        
        # Проверка на пустые значения
        for currency in currencies:
            if not currency.get('code') or not isinstance(currency.get('code'), str):
                return jsonify({"success": False, "error": "Все валюты должны иметь код"}), 400
        
        # Сохранение
        if Config.save_currencies(currencies):
            # Инициализируем разрешения для новых валют (по умолчанию включены)
            state_manager.init_currency_permissions(currencies)
            return jsonify({"success": True, "message": "Валюты сохранены"})
        else:
            return jsonify({"success": False, "error": "Ошибка сохранения"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/currencies/sync', methods=['POST'])
def sync_currencies_from_gateio():
    """Синхронизация символов валют с Gate.io (НЕ меняет названия, корректирует символы)"""
    try:
        # Используем модуль currency_sync для синхронизации
        currency_sync = CurrencySync()
        quote_currency = request.json.get('quote_currency', 'USDT') if request.json else 'USDT'
        
        # Выполняем синхронизацию символов
        result = currency_sync.sync_symbols_from_gate(quote_currency=quote_currency)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except requests.exceptions.RequestException as e:
        print(f"[CURRENCY_SYNC] Ошибка сети: {e}")
        return jsonify({
            "success": False,
            "error": f"Ошибка подключения к Gate.io: {str(e)}"
        }), 500
    except Exception as e:
        print(f"[CURRENCY_SYNC] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/currencies/sync-info', methods=['GET'])
def get_currency_sync_info():
    """Получить информацию о последней синхронизации"""
    try:
        sync_info_file = os.path.join(os.path.dirname(__file__), 'currency_sync_info.json')
        
        if os.path.exists(sync_info_file):
            with open(sync_info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
            # Бэккомпат для фронтенда: добавим отсутствующие ключи
            if isinstance(info, dict):
                if 'timestamp' in info and 'last_update' not in info:
                    info['last_update'] = info['timestamp']
                if 'total' in info and 'total_currencies' not in info:
                    info['total_currencies'] = info['total']
                if 'updated' in info and 'custom_symbols' not in info:
                    info['custom_symbols'] = info['updated']
            return jsonify({"success": True, "info": info})
        else:
            return jsonify({"success": True, "info": None})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/balance', methods=['GET'])
def get_balance():
    """Получить баланс"""
    if not account_manager.active_account:
        return jsonify({"error": "Нет активного аккаунта"}), 400
    account = account_manager.get_account(account_manager.active_account)
    client = GateAPIClient(account['api_key'], account['api_secret'], CURRENT_NETWORK_MODE)
    try:
        balance = client.get_account_balance()
        return jsonify({"success": True, "data": balance})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trade', methods=['POST'])
def execute_trade():
    """Выполнить сделку"""
    if not account_manager.active_account:
        return jsonify({"error": "Нет активного аккаунта"}), 400
    data = request.json
    # Получаем или создаем trading engine для аккаунта
    if account_manager.active_account not in trading_engines:
        # Инициализация движка для аккаунта при первом обращении
        acc = account_manager.get_account(account_manager.active_account)
        api_client = GateAPIClient(acc['api_key'], acc['api_secret'], CURRENT_NETWORK_MODE)
        trading_engines[account_manager.active_account] = TradingEngine(api_client)
    engine = trading_engines[account_manager.active_account]
    trade_params = {
        'currency_pair': data.get('currency_pair'),
        'side': data.get('side'),
        'amount': data.get('amount'),
        'price': data.get('price'),
        'type': data.get('type', 'limit')
    }
    result = engine.execute_trade(trade_params)
    return jsonify(result)

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Получить список ордеров"""
    if not account_manager.active_account:
        return jsonify({"error": "Нет активного аккаунта"}), 400
    account = account_manager.get_account(account_manager.active_account)
    client = GateAPIClient(account['api_key'], account['api_secret'], CURRENT_NETWORK_MODE)
    currency_pair = request.args.get('currency_pair', 'BTC_USDT')
    try:
        orders = client.get_spot_orders(currency_pair)
        return jsonify({"success": True, "data": orders})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# SERVER CONTROL API (Управление сервером)
# =============================================================================

@app.route('/api/server/status', methods=['GET'])
def server_status():
    """Получить статус сервера"""
    pid = ProcessManager.read_pid()
    return jsonify({
        "running": True,  # Если мы отвечаем, значит работаем
        "pid": pid,
        "uptime": time.time() - server_start_time if 'server_start_time' in globals() else 0
    })

@app.route('/api/server/restart', methods=['POST'])
def server_restart():
    """Перезапустить сервер"""
    def restart():
        time.sleep(1)  # Даем время отправить ответ
        print("\n[RESTART] Перезапуск сервера...")

        # Получаем путь к текущему скрипту и Python
        python = sys.executable
        script = None
        try:
            script = os.path.abspath(__file__)
        except Exception:
            try:
                script = os.path.abspath(sys.argv[0])
            except Exception:
                script = None

        # Путь к рабочей папке приложения (где лежат батники)
        app_dir = os.path.abspath(os.path.dirname(script)) if script else os.path.abspath('.')

        # Попытка выполнить RESTART.bat или START.bat, если они существуют (удобно при запуске через батники на Windows)
        try:
            ProcessManager.remove_pid()
            import subprocess

            if os.name == 'nt':
                # Ищем START.bat или используем restart.py в рабочей директории
                bat_file = os.path.join(app_dir, 'START.bat')
                restart_py = os.path.join(app_dir, 'restart.py')
                
                # Приоритет 1: START.bat
                if os.path.exists(bat_file):
                    try:
                        # Запуск батника в новом окне с правильным синтаксисом
                        subprocess.Popen(
                            f'start "mTrade Server" cmd /c "{bat_file}"',
                            shell=True,
                            cwd=app_dir
                        )
                        print(f"[RESTART] Запущен батник: {bat_file}")
                    except Exception as e:
                        print(f"[RESTART] Ошибка при запуске батника: {e}")
                
                # Приоритет 2: restart.py
                elif os.path.exists(restart_py):
                    try:
                        subprocess.Popen(
                            [python, restart_py],
                            cwd=app_dir,
                            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
                        )
                        print(f"[RESTART] Запущен скрипт перезапуска: {restart_py}")
                    except Exception as e:
                        print(f"[RESTART] Ошибка при запуске restart.py: {e}")
                
                # Приоритет 3: прямой запуск mTrade.py в новом окне
                elif script and os.path.exists(script):
                    try:
                        # Запуск в новом окне PowerShell
                        subprocess.Popen(
                            f'start "mTrade Server" cmd /c "{python}" "{script}"',
                            shell=True,
                            cwd=app_dir
                        )
                        print(f"[RESTART] Запущен новый процесс: {script}")
                    except Exception as e:
                        print(f"[RESTART] Ошибка при запуске: {e}")
                else:
                    print('[RESTART] Не найдены файлы для перезапуска (START.bat, restart.py, mTrade.py)')
            else:
                # POSIX: пробуем запустить python скрипт в фоне
                if script and os.path.exists(script):
                    try:
                        subprocess.Popen([python, script])
                        print(f"[RESTART] Новый процесс запущен: {python} {script}")
                    except Exception as e:
                        print(f"[RESTART] Ошибка при запуске нового процесса на POSIX: {e}")
                else:
                    print('[RESTART] Не найден скрипт для перезапуска (POSIX)')
        except Exception as e:
            print(f"[RESTART] Не удалось перезапустить: {e}")

        # Завершаем текущий процесс
        try:
            os._exit(0)
        except SystemExit:
            pass
        except Exception:
            os._exit(0)

    Thread(target=restart, daemon=True).start()
    return jsonify({"success": True, "message": "Сервер перезапускается..."})

@app.route('/api/server/shutdown', methods=['POST'])
def server_shutdown():
    """Остановить сервер"""
    def shutdown():
        time.sleep(1)
        print("\n[SHUTDOWN] Остановка сервера...")
        # Закрыть все WebSocket соединения
        ws_manager = get_websocket_manager()
        if ws_manager:
            ws_manager.close_all()
        ProcessManager.remove_pid()
        os._exit(0)
    
    Thread(target=shutdown, daemon=True).start()
    return jsonify({"success": True, "message": "Сервер останавливается..."})


# =============================================================================
# NETWORK MODE API (Управление режимом сети)
# =============================================================================

@app.route('/api/network', methods=['GET'])
@app.route('/api/network/mode', methods=['GET'])
def get_network_mode():
    """Получить текущий режим сети"""
    return jsonify({
        "success": True,
        "mode": CURRENT_NETWORK_MODE,
        "modes": {
            "work": "Рабочая сеть (Real trading)",
            "test": "Тестовая сеть (Paper trading)"
        }
    })

@app.route('/api/network', methods=['POST'])
@app.route('/api/network/mode', methods=['POST'])
def set_network_mode():
    """Переключить режим сети"""
    try:
        data = request.json
        new_mode = data.get('mode', '').lower()
        if new_mode not in ('work', 'test'):
            return jsonify({"success": False, "error": "Неверный режим. Доступны: 'work' или 'test'"}), 400
        # Используем функцию _reinit_network_mode для переключения
        if _reinit_network_mode(new_mode):
            # Сохраняем в State Manager
            try:
                state_manager.set_network_mode(new_mode)
            except Exception as e:
                print(f"[STATE] Не удалось сохранить network_mode: {e}")
            return jsonify({"success": True, "mode": new_mode, "message": f"Режим сети изменен на '{new_mode}'"})
        else:
            return jsonify({"success": False, "error": "Не удалось переключить режим сети"}), 500
    except Exception as e:
        import traceback
        print(f"[ERROR] Ошибка переключения режима сети: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# WEBSOCKET API ENDPOINTS
# =============================================================================

@app.route('/api/pair/subscribe', methods=['POST'])
def subscribe_pair():
    """Подписаться на данные торговой пары через WebSocket"""
    try:
        data = request.json
        base_currency = data.get('base_currency', 'BTC')
        quote_currency = data.get('quote_currency', 'USDT')
        currency_pair = f"{base_currency}_{quote_currency}"
        ws_manager = get_websocket_manager()
        # Ленивая инициализация менеджера даже без ключей (публичный режим)
        if not ws_manager:
            ak, sk = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
            init_websocket_manager(ak, sk, CURRENT_NETWORK_MODE)
            ws_manager = get_websocket_manager()
            _init_default_watchlist()
            print(f"[WEBSOCKET] Lazy init manager (mode={CURRENT_NETWORK_MODE}, keys={'yes' if ak and sk else 'no'})")
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket менеджер не инициализирован"})
        ws_manager.create_connection(currency_pair)
        return jsonify({"success": True, "pair": currency_pair, "message": f"Подписка на {currency_pair} создана"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/pair/data', methods=['GET'])
def get_pair_data():
    """Получить данные торговой пары из WebSocket кэша, с REST fallback."""
    try:
        base_currency = request.args.get('base_currency', 'BTC')
        quote_currency = request.args.get('quote_currency', 'USDT')
        force_refresh = request.args.get('force', '0') == '1'
        currency_pair = f"{base_currency}_{quote_currency}"
        ws_manager = get_websocket_manager()
        data = None
        if ws_manager:
            data = ws_manager.get_data(currency_pair)
            # Если force=1 или данных нет, создаём новое соединение
            if data is None or force_refresh:
                print(f"[PAIR_DATA] Creating/refreshing connection for {currency_pair} (force={force_refresh})")
                ws_manager.create_connection(currency_pair)
                # Ждём немного, чтобы получить первые данные
                import time
                time.sleep(0.5)
                data = ws_manager.get_data(currency_pair)
        if not data:
            # REST fallback тикер + стакан
            # ВАЖНО: Для рыночных данных (orderbook, ticker) ВСЕГДА используем основной API Gate.io,
            # даже в тестовом режиме, т.к. тестовая сеть не предоставляет рыночные данные
            api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
            # Для публичных данных используем 'work' режим (основной API)
            market_data_client = GateAPIClient(api_key, api_secret, 'work')
            try:
                # Запрос реальных рыночных данных из основного API
                ob = market_data_client._request('GET', '/spot/order_book', params={'currency_pair': currency_pair.upper(), 'limit': 20})
                ticker = market_data_client._request('GET', '/spot/tickers', params={'currency_pair': currency_pair.upper()})
                
                data = {
                    'ticker': ticker[0] if isinstance(ticker, list) and ticker else {},
                    'orderbook': {'asks': ob.get('asks', []), 'bids': ob.get('bids', [])} if isinstance(ob, dict) else ob,
                    'trades': []
                }
                
                print(f"[PAIR_DATA] Loaded real market data for {currency_pair} (mode={CURRENT_NETWORK_MODE}, asks={len(data['orderbook'].get('asks',[]))}, bids={len(data['orderbook'].get('bids',[]))})")
            except Exception as rest_err:
                print(f"[ERROR] Failed to load real market data for {currency_pair}: {rest_err}")
                return jsonify({'success': False, 'error': f'Не удалось загрузить данные рынка: {str(rest_err)}'})
        
        return jsonify({'success': True, 'pair': currency_pair, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/pair/unsubscribe', methods=['POST'])
def unsubscribe_pair():
    """Отписаться от данных торговой пары"""
    try:
        data = request.json
        base_currency = data.get('base_currency', 'BTC')
        quote_currency = data.get('quote_currency', 'USDT')
        
        currency_pair = f"{base_currency}_{quote_currency}"
        
        ws_manager = get_websocket_manager()
        if not ws_manager:
            return jsonify({"success": False, "error": "WebSocket менеджер не инициализирован"})
        
        # Закрыть соединение для пары
        ws_manager.close_connection(currency_pair)
        
        return jsonify({
            "success": True,
            "pair": currency_pair,
            "message": f"Отписка от {currency_pair} выполнена"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/pair/balances', methods=['GET'])
def get_pair_balances():
    """Получить балансы для конкретной торговой пары (с поддержкой симуляции в test)."""
    try:
        base_currency = request.args.get('base_currency', 'BTC')
        quote_currency = request.args.get('quote_currency', 'USDT')
        api_key = None
        api_secret = None
        if account_manager.active_account:
            account = account_manager.get_account(account_manager.active_account)
            api_key = account['api_key']
            api_secret = account['api_secret']
        else:
            api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        no_keys = (not api_key or not api_secret)
        client = None
        balance_response = []
        if not no_keys:
            client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)
            try:
                balance_response = client.get_account_balance()
            except Exception:
                balance_response = []
        base_balance = {"currency": base_currency, "available": "0", "locked": "0"}
        quote_balance = {"currency": quote_currency, "available": "0", "locked": "0"}
        if isinstance(balance_response, list):
            for item in balance_response:
                cur = item.get('currency','').upper()
                if cur == base_currency.upper():
                    base_balance = {"currency": base_currency, "available": item.get('available','0'), "locked": item.get('locked','0')}
                elif cur == quote_currency.upper():
                    quote_balance = {"currency": quote_currency, "available": item.get('available','0'), "locked": item.get('locked','0')}
        ws_manager = get_websocket_manager()
        current_price = 0
        if ws_manager:
            pair_data = ws_manager.get_data(f"{base_currency}_{quote_currency}")
            if pair_data and pair_data.get('ticker') and pair_data['ticker'].get('last'):
                try:
                    current_price = float(pair_data['ticker']['last'])
                except Exception:
                    current_price = 0
        try:
            base_available = float(base_balance['available'])
        except Exception:
            base_available = 0.0
        base_equivalent = base_available * current_price if current_price > 0 else 0
        try:
            quote_available = float(quote_balance['available'])
        except Exception:
            quote_available = 0.0
        quote_equivalent = quote_available
        if quote_currency.upper() != 'USDT' and ws_manager:
            usdt_data = ws_manager.get_data(f"{quote_currency}_USDT")
            if usdt_data and usdt_data.get('ticker') and usdt_data['ticker'].get('last'):
                try:
                    quote_equivalent = quote_available * float(usdt_data['ticker']['last'])
                except Exception:
                    pass
        return jsonify({
            "success": True,
            "balances": {"base": base_balance, "quote": quote_balance},
            "price": current_price,
            "base_equivalent": base_equivalent,
            "quote_equivalent": quote_equivalent
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/pair/info', methods=['GET'])
def get_pair_info():
    """Получить параметры точности и минимальных квот торговой пары (кеш).
    Параметры:
    - force=1 — игнорировать кеш
    - ttl=<sec> — переопределить TTL
    - short=1 — установить временной TTL=10
    - debug=1 — вернуть сырой ответ raw_exact/raw_list
    """
    base_currency = request.args.get('base_currency', 'BTC').upper()
    quote_currency = request.args.get('quote_currency', 'USDT').upper()
    currency_pair = f"{base_currency}_{quote_currency}".upper()
    force = str(request.args.get('force', '0')).lower() in ('1','true','yes')
    ttl_override = request.args.get('ttl')
    short = str(request.args.get('short','0')).lower() in ('1','true','yes')
    debug = str(request.args.get('debug','0')).lower() in ('1','true','yes')

    now = time.time()
    ttl = PAIR_INFO_CACHE_TTL
    if short:
        ttl = 10
    try:
        if ttl_override is not None:
            ttl = max(0, int(ttl_override))
    except Exception:
        pass

    cached = PAIR_INFO_CACHE.get(currency_pair)
    if not force and cached and (now - cached['ts'] < ttl):
        resp = {"success": True, "pair": currency_pair, "data": cached['data'], "cached": True}
        if debug:
            resp['debug'] = cached.get('debug')
        return jsonify(resp)

    # API ключи (необязательны для публичных эндпоинтов)
    api_key = None
    api_secret = None
    if account_manager.active_account:
        acc = account_manager.get_account(account_manager.active_account)
        api_key = acc['api_key']
        api_secret = acc['api_secret']
    else:
        api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)

    # Всегда позволяем публичный запрос без ключей
    client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)

    raw_exact = client.get_currency_pair_details_exact(currency_pair)
    pair_info = {"min_quote_amount": None,"min_base_amount": None,"amount_precision": None,"price_precision": None}

    used_source = 'exact'
    # Если точный ответ корректный (dict с нужными ключами)
    if isinstance(raw_exact, dict) and raw_exact.get('id') and str(raw_exact.get('id')).upper() == currency_pair:
        pair_info = {
            "min_quote_amount": raw_exact.get('min_quote_amount'),
            "min_base_amount": raw_exact.get('min_base_amount'),
            "amount_precision": raw_exact.get('amount_precision'),
            "price_precision": raw_exact.get('precision')
        }
    else:
        # fallback на список
        raw_list = client.get_currency_pair_details(currency_pair)
        used_source = 'list'
        if isinstance(raw_list, list):
            for item in raw_list:
                if str(item.get('id','')).upper() == currency_pair:
                    pair_info = {
                        "min_quote_amount": item.get('min_quote_amount'),
                        "min_base_amount": item.get('min_base_amount'),
                        "amount_precision": item.get('amount_precision'),
                        "price_precision": item.get('precision')
                    }
                    break
        elif isinstance(raw_list, dict) and raw_list.get('error'):
            return jsonify({"success": False, "pair": currency_pair, "data": pair_info, "error": raw_list.get('error')})
    
    # Простая валидация: если price_precision отсутствует или выглядит одинаково у многих и =5 (частая жалоба), логируем предупреждение
    warn = None
    if pair_info['price_precision'] is None:
        warn = 'price_precision_not_found'
    elif pair_info['price_precision'] == 5 and base_currency in ('BTC','WLD'):
        warn = 'suspect_same_precision_for_BTC_WLD'

    debug_block = {
        'source': used_source,
        'raw_exact_keys': list(raw_exact.keys()) if isinstance(raw_exact, dict) else None,
        'warn': warn
    }

    PAIR_INFO_CACHE[currency_pair] = {"ts": now, "data": pair_info, "debug": debug_block}

    resp = {"success": True, "pair": currency_pair, "data": pair_info, "cached": False}
    if debug:
        resp['debug'] = debug_block
        resp['raw_exact'] = raw_exact
    return jsonify(resp)


# =============================================================================
# MULTI-PAIRS WATCHER (Постоянное считывание данных по нескольким парам)
# =============================================================================

from threading import Thread as _Thread


def _add_pairs_to_watchlist(pairs: List[str]):
    ws = get_websocket_manager()
    for p in (pairs or []):
        pair = str(p).upper()
        WATCHED_PAIRS.add(pair)
        try:
            if ws:
                ws.create_connection(pair)
        except Exception:
            pass


def _remove_pairs_from_watchlist(pairs: List[str]):
    ws = get_websocket_manager()
    for p in (pairs or []):
        pair = str(p).upper()
        WATCHED_PAIRS.discard(pair)
        try:
            if ws:
                ws.close_connection(pair)
        except Exception:
            pass


class _PairsUpdater(_Thread):
    daemon = True

    def run(self):
        while True:
            try:
                ws = get_websocket_manager()
                if ws:
                    for pair in list(WATCHED_PAIRS):
                        try:
                            ws.create_connection(pair)
                            data = ws.get_data(pair)
                            if data is not None:
                                MULTI_PAIRS_CACHE[pair] = {"ts": time.time(), "data": data}
                        except Exception:
                            pass
                time.sleep(1.0)
            except Exception:
                time.sleep(1.0)


@app.route('/api/pairs/watchlist', methods=['GET'])
def api_get_watchlist():
    return jsonify({"success": True, "pairs": sorted(list(WATCHED_PAIRS))})


@app.route('/api/pairs/watch', methods=['POST'])
def api_watch_pairs():
    try:
        payload = request.get_json(silent=True) or {}
        pairs = payload.get('pairs', [])
        if not pairs:
            return jsonify({"success": False, "error": "pairs[] пуст"}), 400
        _add_pairs_to_watchlist(pairs)
        return jsonify({"success": True, "added": [p.upper() for p in pairs]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/pairs/unwatch', methods=['POST'])
def api_unwatch_pairs():
    try:
        payload = request.get_json(silent=True) or {}
        pairs = payload.get('pairs', [])
        if not pairs:
            return jsonify({"success": False, "error": "pairs[] пуст"}), 400
        _remove_pairs_from_watchlist(pairs)
        return jsonify({"success": True, "removed": [p.upper() for p in pairs]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/pairs/data', methods=['GET'])
def api_pairs_data():
    """Вернуть данные по нескольким парам.
    Параметры:
    - pairs=BTC_USDT,ETH_USDT (необяз.) — список пар через запятую; иначе все из watchlist
    - fresh=1 — попытаться взять из WS немедленно
    """
    try:
        pairs_qs = request.args.get('pairs', '').strip()
        fresh = str(request.args.get('fresh', '0')).lower() in ('1', 'true', 'yes')
        if pairs_qs:
            pairs = [p.strip().upper() for p in pairs_qs.split(',') if p.strip()]
        else:
            pairs = sorted(list(WATCHED_PAIRS))

        ws = get_websocket_manager()
        result = {}
        for pair in pairs:
            if fresh and ws:
                try:
                    ws.create_connection(pair)
                    data_now = ws.get_data(pair)
                    if data_now is not None:
                        MULTI_PAIRS_CACHE[pair] = {"ts": time.time(), "data": data_now}
                except Exception:
                    pass
            cached = MULTI_PAIRS_CACHE.get(pair, {})
            result[pair] = {"ts": cached.get('ts'), "data": cached.get('data')}
        return jsonify({"success": True, "pairs": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# TRADE PARAMETERS & BREAK-EVEN TABLE API
# =============================================================================

# Поля параметров торговли и их типы (per-currency)
_TRADE_PARAM_FIELDS = (
    ('steps', int),
    ('start_volume', float),
    ('start_price', float),
    ('pprof', float),
    ('kprof', float),
    ('target_r', float),
    ('rk', float),
    ('geom_multiplier', float),
    ('rebuy_mode', str),
    ('keep', float),
    ('orderbook_level', float),
)

# Поля legacy-параметров торговли и их типы (глобальные)
_LEGACY_TRADE_PARAM_FIELDS = (
    ('steps', int),
    ('start_volume', float),
    ('start_price', float),
    ('pprof', float),
    ('kprof', float),
    ('target_r', float),
    ('geom_multiplier', float),
    ('rebuy_mode', str),
    ('orderbook_level', int),
)


def _apply_param_updates(src: dict, fields, updates: dict) -> dict:
    """Аккуратно обновляет параметры в src значениями из updates с приведением типов.
    Ошибки кастинга игнорируются (как и раньше в эндпоинтах).
    """
    dst = src.copy()
    for key, caster in fields:
        if key in updates and updates[key] is not None:
            try:
                dst[key] = caster(updates[key])
            except Exception:
                # Полностью повторяем старое поведение: тихо пропускаем невалидные значения
                pass
    return dst


@app.route('/api/trade/params', methods=['GET'])
def get_trade_params():
    """Получить параметры торговли для конкретной валюты (per-currency)"""
    try:
        base_currency = (request.args.get('base_currency') or request.args.get('currency') or 'BTC').upper()
        params = state_manager.get_breakeven_params(base_currency)
        return jsonify({"success": True, "params": params, "currency": base_currency})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/params', methods=['POST'])
def save_trade_params():
    """Сохранить параметры торговли для конкретной валюты (per-currency)"""
    try:
        data = request.get_json(silent=True) or {}
        base_currency = (data.get('base_currency') or data.get('currency') or 'BTC').upper()
        current = state_manager.get_breakeven_params(base_currency)
        updated = _apply_param_updates(current, _TRADE_PARAM_FIELDS, data)
        state_manager.set_breakeven_params(base_currency, updated)
        print(f"[PARAMS] {base_currency} -> {updated}")
        return jsonify({
            "success": True,
            "message": f"Параметры для {base_currency} сохранены",
            "params": updated,
            "currency": base_currency,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/params/legacy', methods=['GET'])
def get_trade_params_legacy():
    """Получить глобальные (legacy) параметры торговли для совместимости со старым UI"""
    try:
        return jsonify({"success": True, "params": TRADE_PARAMS, "legacy": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/params/legacy', methods=['POST'])
def save_trade_params_legacy():
    """Сохранить глобальные (legacy) параметры торговли (не влияет на per-currency)"""
    global TRADE_PARAMS
    try:
        data = request.get_json(silent=True) or {}
        updated = _apply_param_updates(TRADE_PARAMS, _LEGACY_TRADE_PARAM_FIELDS, data)
        TRADE_PARAMS = updated
        state_manager.set("legacy_trade_params", TRADE_PARAMS)
        print(f"[PARAMS][LEGACY] -> {TRADE_PARAMS}")
        return jsonify({"success": True, "params": TRADE_PARAMS, "legacy": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/breakeven/table', methods=['GET'])
def get_breakeven_table():
    """Рассчитать таблицу безубыточности.
    По умолчанию возвращает per-currency (если указан base_currency / currency),
    если параметры не указаны (старый UI), использует глобальные TRADE_PARAMS.
    Добавлено вычисление current_price из WebSocket (fallback: 0).
    Поддержка передачи параметров через query string для мгновенного предпросмотра.
    """
    try:
        from breakeven_calculator import calculate_breakeven_table
        # Определяем тип запроса (legacy или per-currency)
        has_currency_arg = ('base_currency' in request.args) or ('currency' in request.args)
        base_currency = (request.args.get('base_currency') or request.args.get('currency') or '')
        base_currency = base_currency.upper() if base_currency else ''
        use_legacy = not has_currency_arg or base_currency == '' or base_currency == 'LEGACY'
        
        # Загружаем сохраненные параметры
        if use_legacy:
            params = TRADE_PARAMS.copy()
            base_for_price = 'BTC'  # legacy UI чаще по BTC
        else:
            params = state_manager.get_breakeven_params(base_currency).copy()
            base_for_price = base_currency
        
        # Переопределяем параметры из query string (для мгновенного предпросмотра)
        overrides = {}
        for key, caster in (
            ('steps', int),
            ('start_volume', float),
            ('start_price', float),
            ('pprof', float),
            ('kprof', float),
            ('target_r', float),
            ('rk', float),
            ('geom_multiplier', float),
        ):
            if key in request.args:
                try:
                    overrides[key] = caster(request.args.get(key))
                except (ValueError, TypeError):
                    pass
        if 'rebuy_mode' in request.args:
            rebuy_mode = str(request.args.get('rebuy_mode')).lower()
            if rebuy_mode in ('fixed', 'geometric', 'martingale'):
                overrides['rebuy_mode'] = rebuy_mode
        params.update(overrides)

        # Получаем текущую цену из WS
        current_price = 0.0
        try:
            ws_manager = get_websocket_manager()
            if ws_manager and base_for_price:
                pd = ws_manager.get_data(f"{base_for_price}_USDT")
                if pd and pd.get('ticker') and pd['ticker'].get('last'):
                    current_price = float(pd['ticker']['last'])
        except Exception:
            current_price = 0.0

        # Если start_price в параметрах 0, передаем current_price калькулятору
        # Калькулятор сам решит, использовать ли current_price или дефолт 1.0
        table_data = calculate_breakeven_table(params, current_price=current_price)
        return jsonify({
            "success": True,
            "table": table_data,
            "params": params,
            "currency": base_currency if not use_legacy else 'LEGACY',
            "legacy": use_legacy,
            "current_price": current_price,
        })
    except Exception as e:
        print(f"[ERROR] Breakeven table calculation: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/permissions', methods=['GET'])
def get_trading_permissions():
    """Получить разрешения торговли для всех валют"""
    try:
        return jsonify({"success": True, "permissions": state_manager.get_trading_permissions()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/permission', methods=['POST'])
def set_trading_permission():
    """Установить разрешение торговли для конкретной валюты"""
    global TRADING_PERMISSIONS
    try:
        data = request.get_json(silent=True) or {}
        base_currency = str(data.get('base_currency', '')).upper()
        if not base_currency:
            return jsonify({"success": False, "error": "Не указана валюта (base_currency)"}), 400
        enabled = bool(data.get('enabled', True))
        TRADING_PERMISSIONS[base_currency] = enabled
        state_manager.set_trading_permission(base_currency, enabled)
        print(f"[TRADING] Разрешение торговли для {base_currency}: {enabled}")
        return jsonify({
            "success": True,
            "base_currency": base_currency,
            "enabled": enabled,
            "message": f"Торговля {base_currency}: {'разрешена' if enabled else 'запрещена'}"
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Set trading permission: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrade/start', methods=['POST'])
def start_autotrade():
    """Включить автоторговлю (запустить двухпроцессный автотрейдер)"""
    global AUTO_TRADE_GLOBAL_ENABLED, AUTO_TRADER
    try:
        AUTO_TRADE_GLOBAL_ENABLED = True
        state_manager.set_auto_trade_enabled(True)

        if AUTO_TRADER is None:
            ws_manager = get_websocket_manager()
            currencies = Config.load_currencies()
            
            # Формируем список кодов валют для торговли
            # Используем только разрешённые к торговле валюты
            trading_permissions = state_manager.get_trading_permissions()
            enabled_currencies = [
                c['code'] for c in currencies 
                if trading_permissions.get(c['code'], False)
            ]
            
            if not enabled_currencies:
                print("[AUTOTRADE] ⚠️ Нет валют, разрешённых к торговле")
                return jsonify({
                    "success": False,
                    "error": "Нет валют, разрешённых к торговле"
                }), 400
            
            print(f"[AUTOTRADE] Валюты для торговли: {enabled_currencies}")
            
            # Используем глобальную функцию _create_api_client вместо локальной
            # ✅ НОВЫЙ АВТОТРЕЙДЕР V2 - чистая архитектура без багов!
            # Никаких race conditions, никаких дублирующих покупок!
            AUTO_TRADER = AutoTraderV2(
                api_client_provider=_create_api_client,
                ws_manager=ws_manager,
                state_manager=state_manager
            )
            
            print('[AUTOTRADE] ✅ AutoTraderV2 инициализирован (ЭТАП 1: каркас)')
            print('[AUTOTRADE] � Состояние хранится в памяти')
            print('[AUTOTRADE] 🔒 Атомарные операции через Lock на валюту')
            print('[AUTOTRADE] � Торговля ещё не реализована (только мониторинг)')

        if not AUTO_TRADER.running:
            AUTO_TRADER.start()

        print("[AUTOTRADE] ✅ Двухпоточный автотрейдер включен")
        return jsonify({
            "success": True,
            "enabled": True,
            "running": AUTO_TRADER.running if AUTO_TRADER else False,
            "message": "Двухпоточный автотрейдер включен"
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Start autotrade: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrade/stop', methods=['POST'])
def stop_autotrade():
    """Выключить автоторговлю (остановить двухпроцессный автотрейдер)"""
    global AUTO_TRADE_GLOBAL_ENABLED, AUTO_TRADER
    try:
        AUTO_TRADE_GLOBAL_ENABLED = False
        state_manager.set_auto_trade_enabled(False)
        if AUTO_TRADER and AUTO_TRADER.running:
            AUTO_TRADER.stop()
        print("[AUTOTRADE] ✅ Двухпроцессный автотрейдер выключен")
        return jsonify({
            "success": True,
            "enabled": False,
            "running": AUTO_TRADER.running if AUTO_TRADER else False,
            "message": "Двухпроцессный автотрейдер выключен"
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Stop autotrade: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrade/status', methods=['GET'])
def get_autotrade_status():
    """Получить статус автоторговли + краткую статистику"""
    try:
        enabled = state_manager.get_auto_trade_enabled()
        stats = AUTO_TRADER.get_stats() if AUTO_TRADER and AUTO_TRADER.running else {}
        return jsonify({
            "success": True,
            "enabled": enabled,
            "running": AUTO_TRADER.running if AUTO_TRADER else False,
            "stats": stats
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrader/stats', methods=['GET'])
def get_autotrader_stats():
    """Получить статистику автотрейдера для конкретной валюты (V2)"""
    try:
        base_currency = str(request.args.get('base_currency', '')).upper()
        if not base_currency:
            return jsonify({"success": False, "error": "Не указана валюта"}), 400

        # Базовые данные
        stats = {
            "base_currency": base_currency,
            "enabled": AUTO_TRADE_GLOBAL_ENABLED,
            "running": AUTO_TRADER.running if AUTO_TRADER else False,
            "version": "v2",
            "trades_count": 0,
            "profit": 0.0,
            "last_trade_time": None
        }

        # Получаем информацию о цикле из нового API
        print(f"[API] /api/autotrader/stats вызван для {base_currency}")
        print(f"[API] AUTO_TRADER exists: {AUTO_TRADER is not None}")
        if AUTO_TRADER:
            cycle_info = AUTO_TRADER.get_cycle_info(base_currency)
            print(f"[API] cycle_info returned: {cycle_info}")
            if cycle_info:
                stats.update({
                    "state": cycle_info.get('state'),
                    "active": cycle_info.get('active', False),
                    "active_step": cycle_info.get('active_step', -1),
                    "start_price": cycle_info.get('start_price', 0.0),
                    "last_buy_price": cycle_info.get('last_buy_price', 0.0),
                    "base_volume": cycle_info.get('base_volume', 0.0),
                    "total_invested_usd": cycle_info.get('total_invested_usd', 0.0),
                    "last_action_at": cycle_info.get('last_action_at', 0.0)
                })
            else:
                print(f"[API] WARNING: cycle_info is None for {base_currency}")
        print(f"[API] Final stats: active={stats.get('active')}, base_volume={stats.get('base_volume')}")
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        import traceback
        print(f"[API] ERROR in get_autotrader_stats: {e}")
        print(f"[API] Traceback:\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrader/reset_cycle', methods=['POST'])
def reset_autotrader_cycle():
    """Сбросить цикл автотрейдера для конкретной валюты (V2)"""
    try:
        data = request.get_json(silent=True) or {}
        base_currency = str(data.get('base_currency', '')).upper()
        if not base_currency:
            return jsonify({"success": False, "error": "Не указана валюта"}), 400
        if not AUTO_TRADER:
            return jsonify({"success": False, "error": "Автотрейдер не инициализирован"}), 500

        # Получаем Lock для валюты (теперь быстро, т.к. никаких API запросов под lock!)
        lock = AUTO_TRADER._get_lock(base_currency)
        
        with lock:
            # Получаем старое состояние (быстро, всё в памяти)
            AUTO_TRADER._ensure_cycle(base_currency)
            cycle = AUTO_TRADER.cycles[base_currency]
            
            old_state = cycle.state.value
            old_active = cycle.is_active()
            
            # Сбрасываем цикл (быстро, только изменение памяти)
            cycle.reset(manual=True)
            
            # Сохраняем состояние в файл
            AUTO_TRADER._save_state(base_currency)
            
            print(f"[RESET_CYCLE][{base_currency}] Цикл сброшен: {old_state} -> IDLE (manual pause)")
            
            return jsonify({
                "success": True,
                "message": f"Цикл {base_currency} сброшен и поставлен на паузу.\n\nДля запуска нажмите 'Старт цикла'.",
                "old_state": old_state,
                "old_active": old_active,
                "new_state": "IDLE (MANUAL PAUSE)"
            })
            
    except Exception as e:
        print(f"[API] Ошибка сброса цикла: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrader/resume_cycle', methods=['POST'])
def resume_autotrader_cycle():
    """Возобновить цикл автотрейдера для конкретной валюты (снять ручную паузу)"""
    try:
        data = request.get_json(silent=True) or {}
        base_currency = str(data.get('base_currency', '')).upper()
        if not base_currency:
            return jsonify({"success": False, "error": "Не указана валюта"}), 400
        if not AUTO_TRADER:
            return jsonify({"success": False, "error": "Автотрейдер не инициализирован"}), 500

        # Получаем Lock для валюты (теперь быстро, т.к. никаких API запросов под lock!)
        lock = AUTO_TRADER._get_lock(base_currency)
        
        with lock:
            # Проверяем, существует ли цикл (быстро, всё в памяти)
            AUTO_TRADER._ensure_cycle(base_currency)
            cycle = AUTO_TRADER.cycles[base_currency]
            
            # Снимаем флаг ручной паузы (быстро, только изменение памяти)
            old_pause = cycle.manual_pause
            cycle.manual_pause = False
            
            # Сохраняем состояние в файл
            AUTO_TRADER._save_state(base_currency)
            
            print(f"[RESUME_CYCLE][{base_currency}] Снят флаг ручной паузы (было: {old_pause})")
            print(f"[RESUME_CYCLE][{base_currency}] Автотрейдер возобновит работу")
            
            return jsonify({
                "success": True,
                "message": f"Цикл {base_currency} возобновлён.\n\nАвтотрейдер начнёт новый цикл автоматически.",
                "was_paused": old_pause,
                "new_state": "ACTIVE (автостарт разрешён)"
            })
            
    except Exception as e:
        print(f"[API] Ошибка возобновления цикла: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/indicators', methods=['GET'])
def get_trade_indicators():
    """Получить торговые индикаторы + уровни автотрейдера для пары.
    Поведение и структура ответа сохранены.
    """
    try:
        base_currency = request.args.get('base_currency', 'BTC').upper()
        quote_currency = request.args.get('quote_currency', 'USDT').upper()
        include_table = str(request.args.get('include_table', '0')).lower() in ('1', 'true', 'yes')
        currency_pair = f"{base_currency}_{quote_currency}"

        ws_manager = get_websocket_manager()
        pair_data = ws_manager.get_data(currency_pair) if ws_manager else None

        indicators = {
            "pair": currency_pair,
            "price": 0.0,
            "change_24h": 0.0,
            "volume_24h": 0.0,
            "high_24h": 0.0,
            "low_24h": 0.0,
            "bid": 0.0,
            "ask": 0.0,
            "spread": 0.0
        }
        if pair_data and pair_data.get('ticker'):
            ticker = pair_data['ticker']
            try:
                indicators['price'] = float(ticker.get('last') or 0)
                indicators['change_24h'] = float(ticker.get('change_percentage') or 0)
                indicators['volume_24h'] = float(ticker.get('quote_volume') or 0)
                indicators['high_24h'] = float(ticker.get('high_24h') or 0)
                indicators['low_24h'] = float(ticker.get('low_24h') or 0)
            except (ValueError, TypeError):
                pass
            try:
                ob = pair_data.get('orderbook') or {}
                if ob.get('asks') and ob.get('bids'):
                    ask = float(ob['asks'][0][0])
                    bid = float(ob['bids'][0][0])
                    indicators['ask'] = ask
                    indicators['bid'] = bid
                    indicators['spread'] = ((ask - bid) / bid * 100.0) if bid > 0 else 0.0
            except Exception:
                pass

        autotrade_levels = {
            'active_cycle': False,
            'active_step': None,
            'total_steps': None,
            'next_rebuy_step': None,
            'next_rebuy_decrease_step_pct': None,
            'next_rebuy_cumulative_drop_pct': None,
            'next_rebuy_purchase_usd': None,
            'target_sell_delta_pct': None,
            'breakeven_price': None,
            'breakeven_pct': None,
            'start_price': None,
            'last_buy_price': None,
            'invested_usd': None,
            'base_volume': None,
            'current_growth_pct': None,
            'progress_to_sell': None,
            'table': None,
            'current_price': None,
            'sell_price': None,
            'next_buy_price': None
        }

        # Базовая цена из тикера (fallback)
        price = indicators['price']

        # Получаем информацию о цикле из нового AutoTraderV2
        cycle_info = None
        cycle = None
        table = None
        
        if AUTO_TRADER and hasattr(AUTO_TRADER, 'cycles'):
            cycle_obj = AUTO_TRADER.cycles.get(base_currency)
            if cycle_obj:
                # Преобразуем TradingCycle в словарь для совместимости
                cycle = {
                    'active': cycle_obj.is_active(),
                    'active_step': cycle_obj.active_step,
                    'start_price': cycle_obj.start_price,
                    'last_buy_price': cycle_obj.last_buy_price,
                    'total_invested_usd': cycle_obj.total_invested_usd,
                    'base_volume': cycle_obj.base_volume,
                    'table': cycle_obj.table,
                    'cycle_started_at': cycle_obj.cycle_started_at,
                    'last_action_at': cycle_obj.last_action_at
                }
                table = cycle_obj.table if cycle_obj.table else None

        if not table:
            params = state_manager.get_breakeven_params(base_currency)
            if params and price:
                try:
                    from breakeven_calculator import calculate_breakeven_table
                    table = calculate_breakeven_table(params, price)
                except Exception as e:
                    print(f"[INDICATORS] Ошибка расчёта таблицы для {base_currency}: {e}")
        
        # УМНЫЙ РАСЧЁТ ТЕКУЩЕЙ ЦЕНЫ ИЗ СТАКАНА
        # Берём цену из уровня стакана, указанного в столбце "Ст." (orderbook_level)
        # Если текущая цена ниже последней покупки — берём из asks (потенциальная цена покупки)
        # Если текущая цена выше последней покупки — берём из bids (потенциальная цена продажи)
        current_price_from_orderbook = None
        if table and len(table) > 0 and pair_data and pair_data.get('orderbook'):
            try:
                active_step = cycle.get('active_step', -1) if cycle else -1
                current_step = active_step if active_step >= 0 else 0
                
                if current_step < len(table):
                    row = table[current_step]
                    # Получаем orderbook_level из таблицы (1-based для пользователя)
                    table_orderbook_level = int(row.get('orderbook_level', 1))
                    # Преобразуем в индекс массива (0-based)
                    orderbook_level = max(0, table_orderbook_level - 1)
                    last_buy_price = cycle.get('last_buy_price', 0) if cycle else 0
                    
                    orderbook = pair_data['orderbook']
                    asks = orderbook.get('asks', [])
                    bids = orderbook.get('bids', [])
                    
                    print(f"[INDICATORS] {base_currency}: Уровень стакана из таблицы: {table_orderbook_level} → индекс массива: {orderbook_level}")
                    
                    # Если есть last_buy_price и цикл активен — сравниваем с ним
                    # Иначе просто берём из asks (для начала цикла)
                    if last_buy_price > 0:
                        if price < last_buy_price:
                            # Цена упала ниже последней покупки — берём из asks (будем докупать)
                            if asks and orderbook_level < len(asks):
                                current_price_from_orderbook = float(asks[orderbook_level][0])
                                print(f"[INDICATORS] {base_currency}: Цена из asks[{orderbook_level}] = {current_price_from_orderbook:.8f} (цена упала ниже last_buy={last_buy_price:.8f})")
                        else:
                            # Цена выше последней покупки — берём из bids (готовимся к продаже)
                            if bids and orderbook_level < len(bids):
                                current_price_from_orderbook = float(bids[orderbook_level][0])
                                print(f"[INDICATORS] {base_currency}: Цена из bids[{orderbook_level}] = {current_price_from_orderbook:.8f} (цена выше last_buy={last_buy_price:.8f})")
                    else:
                        # Цикл не начат — берём из asks (для начала цикла всегда покупка)
                        if asks and orderbook_level < len(asks):
                            current_price_from_orderbook = float(asks[orderbook_level][0])
                            print(f"[INDICATORS] {base_currency}: Цена из asks[{orderbook_level}] = {current_price_from_orderbook:.8f} (цикл не начат)")
                    
                    if current_price_from_orderbook is None:
                        # Fallback на ticker.last если уровень недоступен
                        print(f"[INDICATORS] {base_currency}: Уровень стакана {orderbook_level} недоступен, используем ticker.last = {price:.8f}")
            except Exception as e:
                print(f"[INDICATORS] Ошибка получения цены из стакана для {base_currency}: {e}")
        
        # Используем цену из стакана, если получена, иначе ticker.last
        price = current_price_from_orderbook if current_price_from_orderbook else price
        autotrade_levels['current_price'] = price

        if table and len(table) > 0:
            active_step = cycle.get('active_step', -1) if cycle else -1
            autotrade_levels['active_cycle'] = bool(cycle and cycle.get('active'))
            autotrade_levels['active_step'] = active_step if active_step >= 0 else None
            autotrade_levels['total_steps'] = len(table) - 1

            if cycle:
                autotrade_levels['start_price'] = cycle.get('start_price') or None
                autotrade_levels['last_buy_price'] = cycle.get('last_buy_price') or None
                autotrade_levels['invested_usd'] = cycle.get('total_invested_usd') or None
                autotrade_levels['base_volume'] = cycle.get('base_volume') or None
            else:
                autotrade_levels['start_price'] = table[0].get('rate')

            start_price = autotrade_levels['start_price']
            if start_price and price:
                try:
                    autotrade_levels['current_growth_pct'] = (price - start_price) / start_price * 100.0
                except Exception:
                    autotrade_levels['current_growth_pct'] = None

            current_step = active_step if active_step >= 0 else 0
            if current_step < len(table):
                row = table[current_step]
                
                # Добавляем уровень стакана из текущей строки таблицы (1-based, для отображения пользователю)
                autotrade_levels['orderbook_level'] = int(row.get('orderbook_level', 1))
                
                # ИСПРАВЛЕНИЕ: Используем РЕАЛЬНЫЙ BE из цикла, а не прогнозный из таблицы
                if cycle and cycle.get('active') and cycle.get('total_invested_usd', 0) > 0 and cycle.get('base_volume', 0) > 0:
                    # Реальный BE = invested / volume
                    real_be = cycle['total_invested_usd'] / cycle['base_volume']
                    autotrade_levels['breakeven_price'] = real_be
                    
                    # Пересчитываем breakeven_pct относительно текущей цены
                    if price and price > 0:
                        autotrade_levels['breakeven_pct'] = ((price - real_be) / real_be) * 100.0
                    else:
                        autotrade_levels['breakeven_pct'] = row.get('breakeven_pct')
                    
                    print(
                        f"[DEBUG] autotrade_levels для {currency_pair}: step={current_step}, "
                        f"REAL_BE={real_be:.8f} (invested={cycle['total_invested_usd']:.2f}, volume={cycle['base_volume']:.8f}), "
                        f"active={autotrade_levels['active_cycle']}"
                    )
                else:
                    # Если цикл не активен или нет данных - используем прогнозный BE из таблицы
                    autotrade_levels['breakeven_price'] = row.get('breakeven_price')
                    autotrade_levels['breakeven_pct'] = row.get('breakeven_pct')

                    
                    print(
                        f"[DEBUG] autotrade_levels для {currency_pair}: step={current_step}, "
                        f"TABLE_BE={row.get('breakeven_price')}, active={autotrade_levels['active_cycle']}"
                    )
                
                autotrade_levels['target_sell_delta_pct'] = row.get('target_delta_pct')

                # Цена продажи рассчитывается от РЕАЛЬНОГО BE
                breakeven = autotrade_levels.get('breakeven_price')
                if breakeven and row.get('target_delta_pct'):
                    try:
                        target_pct = row['target_delta_pct']
                        autotrade_levels['sell_price'] = breakeven * (1 + target_pct / 100.0)
                    except Exception:
                        pass

                cg = autotrade_levels['current_growth_pct']
                tgt = row.get('target_delta_pct')
                if cg is not None and tgt:
                    autotrade_levels['progress_to_sell'] = max(0.0, min(1.0, cg / tgt)) if tgt > 0 else None

            next_step = current_step + 1 if autotrade_levels['active_cycle'] else current_step
            if next_step < len(table):
                nrow = table[next_step]
                autotrade_levels['next_rebuy_step'] = next_step
                autotrade_levels['next_rebuy_decrease_step_pct'] = abs(nrow.get('decrease_step_pct', 0))
                autotrade_levels['next_rebuy_cumulative_drop_pct'] = nrow.get('cumulative_decrease_pct')
                autotrade_levels['next_rebuy_purchase_usd'] = nrow.get('purchase_usd')

                if autotrade_levels['active_cycle'] and cycle and cycle.get('last_buy_price') and nrow.get('decrease_step_pct'):
                    try:
                        last_buy = cycle['last_buy_price']
                        decrease_pct = abs(nrow['decrease_step_pct'])
                        autotrade_levels['next_buy_price'] = last_buy * (1 - decrease_pct / 100.0)
                    except Exception:
                        pass
                else:
                    autotrade_levels['next_buy_price'] = nrow.get('rate')
                    if not autotrade_levels['last_buy_price'] and start_price:
                        autotrade_levels['last_buy_price'] = start_price

            if include_table:
                autotrade_levels['table'] = [{
                    'step': r.get('step'),
                    'rate': r.get('rate'),
                    'purchase_usd': r.get('purchase_usd'),
                    'total_invested': r.get('total_invested'),
                    'breakeven_price': r.get('breakeven_price'),
                    'breakeven_pct': r.get('breakeven_pct'),
                    'target_delta_pct': r.get('target_delta_pct'),
                    'decrease_step_pct': r.get('decrease_step_pct'),
                    'cumulative_decrease_pct': r.get('cumulative_decrease_pct')
                } for r in table]

        return jsonify({"success": True, "indicators": indicators, "autotrade_levels": autotrade_levels})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ui/state', methods=['GET'])
def get_ui_state():
    """Получить состояние UI (разрешения торговли, автоторговля, режимы, параметры безубыточности)"""
    try:
        return jsonify({
            "success": True,
            "state": {
                "auto_trade_enabled": state_manager.get_auto_trade_enabled(),
                "enabled_currencies": state_manager.get_trading_permissions(),
                "network_mode": state_manager.get_network_mode(),
                "trading_mode": state_manager.get_trading_mode(),
                "breakeven_params": state_manager.get_breakeven_params(),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ui/state', methods=['POST'])
def save_ui_state():
    """Сохранить состояние UI (поддержка пакетного обновления параметров для валют)"""
    try:
        global AUTO_TRADE_GLOBAL_ENABLED, TRADING_PERMISSIONS, TRADING_MODE, CURRENT_NETWORK_MODE
        data = request.get_json(silent=True) or {}
        state = data.get('state', {}) or {}

        # Автоторговля
        if 'auto_trade_enabled' in state:
            AUTO_TRADE_GLOBAL_ENABLED = bool(state['auto_trade_enabled'])
            state_manager.set_auto_trade_enabled(AUTO_TRADE_GLOBAL_ENABLED)

        # Разрешения торговли
        enabled_currencies = state.get('enabled_currencies')
        if isinstance(enabled_currencies, dict):
            TRADING_PERMISSIONS.update(enabled_currencies)
            for currency, enabled in enabled_currencies.items():
                state_manager.set_trading_permission(currency, enabled)

        # Режим торговли
        if 'trading_mode' in state:
            mode = str(state['trading_mode']).lower()
            if mode in ('trade', 'copy'):
                TRADING_MODE = mode
                state_manager.set_trading_mode(TRADING_MODE)

        # Режим сети
        if 'network_mode' in state:
            nm = str(state['network_mode']).lower()
            if nm in ('work', 'test') and nm != CURRENT_NETWORK_MODE:
                if _reinit_network_mode(nm):
                    CURRENT_NETWORK_MODE = nm
                    state_manager.set_network_mode(nm)

        # Параметры безубыточности (пакетное обновление)
        breakeven_all = state.get('breakeven_params')
        if isinstance(breakeven_all, dict):
            for currency, params in breakeven_all.items():
                try:
                    cur = str(currency).upper()
                    if not cur:
                        continue
                    existing = state_manager.get_breakeven_params(cur)
                    if not isinstance(existing, dict):
                        existing = {}
                    for k in (
                        'steps', 'start_volume', 'start_price', 'pprof', 'kprof',
                        'target_r', 'geom_multiplier', 'rebuy_mode', 'orderbook_level'
                    ):
                        if k in params:
                            existing[k] = params[k]
                    state_manager.set_breakeven_params(cur, existing)
                except Exception as e:
                    print(f"[STATE] Ошибка сохранения breakeven для {currency}: {e}")

        return jsonify({"success": True, "message": "Состояние UI сохранено"})
    except Exception as e:
        print(f"[ERROR] Save UI state: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ui/state/partial', methods=['POST'])
def save_ui_state_partial():
    """Частичное сохранение состояния UI (используется фронтендом UIStateManager)."""
    try:
        global AUTO_TRADE_GLOBAL_ENABLED, TRADING_MODE, CURRENT_NETWORK_MODE
        payload = request.get_json(silent=True) or {}

        # Загружаем текущее состояние из файла (для совместимости с Config)
        try:
            full_state = Config.load_ui_state()
        except Exception:
            full_state = {
                "enabled_currencies": {},
                "auto_trade_enabled": False,
                "network_mode": CURRENT_NETWORK_MODE,
                "active_base_currency": "BTC",
                "active_quote_currency": "USDT",
                "theme": "dark",
                "show_indicators": True,
                "show_orderbook": True,
                "show_trades": True,
                "orderbook_depth": 20,
                "last_updated": None,
            }

        # Базовая валюта
        if 'active_base_currency' in payload:
            base = str(payload['active_base_currency']).upper()
            if base:
                full_state['active_base_currency'] = base

        # Котируемая валюта
        if 'active_quote_currency' in payload:
            quote = str(payload['active_quote_currency']).upper()
            if quote:
                full_state['active_quote_currency'] = quote

        # Автоторговля
        if 'auto_trade_enabled' in payload:
            AUTO_TRADE_GLOBAL_ENABLED = bool(payload['auto_trade_enabled'])
            full_state['auto_trade_enabled'] = AUTO_TRADE_GLOBAL_ENABLED
            state_manager.set_auto_trade_enabled(AUTO_TRADE_GLOBAL_ENABLED)

        # Режим сети
        if 'network_mode' in payload:
            nm = str(payload['network_mode']).lower()
            if nm in ('work', 'test') and nm != CURRENT_NETWORK_MODE:
                if _reinit_network_mode(nm):
                    CURRENT_NETWORK_MODE = nm
                    full_state['network_mode'] = nm
                    state_manager.set_network_mode(nm)

        # Режим торговли
        if 'trading_mode' in payload:
            mode = str(payload['trading_mode']).lower()
            if mode in ('trade', 'copy'):
                TRADING_MODE = mode
                state_manager.set_trading_mode(TRADING_MODE)

        # Параметры безубыточности (возможно частичное обновление)
        be_updates = payload.get('breakeven_params')
        if isinstance(be_updates, dict):
            existing_all = state_manager.get("breakeven_params", {}) or {}
            for currency, params in be_updates.items():
                try:
                    cur = str(currency).upper()
                    if not cur:
                        continue
                    existing = existing_all.get(cur) or state_manager.get_breakeven_params(cur)
                    if not isinstance(existing, dict):
                        existing = {}
                    for k in (
                        'steps', 'start_volume', 'start_price', 'pprof', 'kprof',
                        'target_r', 'geom_multiplier', 'rebuy_mode', 'orderbook_level'
                    ):
                        if k in params:
                            existing[k] = params[k]
                    existing_all[cur] = existing
                    state_manager.set_breakeven_params(cur, existing)
                except Exception as e:
                    print(f"[STATE] Ошибка partial breakeven для {currency}: {e}")
            full_state['breakeven_params'] = existing_all

        # Сохраняем объединённое состояние через Config
        try:
            Config.save_ui_state(full_state)
        except Exception as e:
            print(f"[STATE] Не удалось сохранить ui_state.json: {e}")

        return jsonify({"success": True, "state": full_state})
    except Exception as e:
        print(f"[ERROR] Save UI state partial: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# TRADE LOGS API (Логи торговых операций)
# =============================================================================

# Константы для TRADE LOGS API
_TRADE_LOGS_DEFAULT_LIMIT = 100

def _get_trade_logger_safe():
    """Безопасное получение экземпляра trade_logger с обработкой ошибок."""
    try:
        return get_trade_logger()
    except Exception as e:
        print(f"[ERROR] Failed to get trade logger: {e}")
        raise

def _handle_trade_logs_error(e, endpoint_name):
    """Универсальная обработка ошибок для trade logs эндпоинтов."""
    import traceback
    print(f"[ERROR] {endpoint_name}: {e}")
    print(traceback.format_exc())
    return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trade/logs', methods=['GET'])
def get_trade_logs():
    """Получить логи торговых операций"""
    try:
        trade_logger = _get_trade_logger_safe()
        
        # Параметры запроса
        limit_str = request.args.get('limit', str(_TRADE_LOGS_DEFAULT_LIMIT))
        currency = request.args.get('currency')
        formatted = request.args.get('formatted', '0') == '1'
        
        try:
            limit = int(limit_str)
        except ValueError:
            limit = _TRADE_LOGS_DEFAULT_LIMIT
        
        if formatted:
            logs = trade_logger.get_formatted_logs(limit=limit, currency=currency)
        else:
            logs = trade_logger.get_logs(limit=limit, currency=currency)
        
        return jsonify({
            'success': True,
            'logs': logs,
            'count': len(logs)
        })
    except Exception as e:
        return _handle_trade_logs_error(e, 'get_trade_logs')

@app.route('/api/trade/logs/stats', methods=['GET'])
def get_trade_logs_stats():
    """Получить статистику по логам"""
    try:
        trade_logger = _get_trade_logger_safe()
        currency = request.args.get('currency')
        stats = trade_logger.get_stats(currency=currency)
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return _handle_trade_logs_error(e, 'get_trade_logs_stats')

@app.route('/api/trade/logs/clear', methods=['POST'])
def clear_trade_logs():
    """Очистить логи"""
    try:
        trade_logger = _get_trade_logger_safe()
        data = request.get_json() or {}
        currency = data.get('currency')
        trade_logger.clear_logs(currency=currency)
        message = f"Логи {'для ' + currency if currency else 'все'} очищены"
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        return _handle_trade_logs_error(e, 'clear_trade_logs')


@app.route('/api/trade/events', methods=['GET'])
def get_trade_events_endpoint():
    """Получить последние торговые события для DEBUG PANEL"""
    try:
        # Получаем параметр last_id (ID последнего полученного события)
        last_id = request.args.get('last_id', type=int, default=-1)
        
        # Получаем новые события
        new_events, current_last_id = get_trade_events(last_id)
        
        return jsonify({
            'success': True,
            'events': new_events,
            'last_id': current_last_id
        })
    except Exception as e:
        print(f"[ERROR] get_trade_events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# QUICK TRADE API (Быстрая торговля)
# =============================================================================

@app.route('/api/trade/buy-min', methods=['POST'])
def quick_buy_min():
    """Купить минимальный ордер по текущей цене"""
    data = request.get_json() or {}
    return handle_buy_min(data, CURRENT_NETWORK_MODE)


@app.route('/api/trade/sell-all', methods=['POST'])
def quick_sell_all():
    """Продать весь доступный баланс базовой валюты"""
    data = request.get_json() or {}
    return handle_sell_all(data, CURRENT_NETWORK_MODE)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Gate.io Multi-Trading Platform - mTrade")
    print("=" * 60)
    print(f"[INFO] Режим сети: {CURRENT_NETWORK_MODE}")
    print(f"[INFO] PID: {os.getpid()}")
    print("=" * 60)
    
    # Записываем PID
    ProcessManager.write_pid()
    ProcessManager.setup_cleanup()
    
    # Инициализация разрешений торговли для всех валют
    print("[INIT] Инициализация разрешений торговли...")
    try:
        currencies = Config.load_currencies()
        state_manager.init_currency_permissions(currencies)
        perms = state_manager.get_trading_permissions()
        enabled_count = sum(1 for v in perms.values() if v)
        print(f"[INIT] Разрешения торговли: {enabled_count}/{len(perms)} валют включено")
    except Exception as e:
        print(f"[WARNING] Ошибка инициализации разрешений: {e}")
    
    # Установка активного аккаунта (если есть доступные)
    print("[INIT] Проверка доступных аккаунтов...")
    available_accounts = account_manager.list_accounts()
    if available_accounts:
        first_account = available_accounts[0]
        account_manager.set_active_account(first_account)
        print(f"[INIT] Активный аккаунт установлен: {first_account}")
    else:
        print("[WARNING] Нет доступных аккаунтов, автотрейдер будет работать в режиме симуляции")
    
    # Инициализация WebSocket менеджера
    print("[INIT] Инициализация WebSocket менеджера...")
    api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
    if api_key and api_secret:
        init_websocket_manager(api_key, api_secret, CURRENT_NETWORK_MODE)
        print("[INIT] WebSocket менеджер инициализирован")
    else:
        print("[WARNING] API ключи не найдены, WebSocket работает в ограниченном режиме")
    
    # Автоинициализация автотрейдера при старте если был включен ранее
    try:
        if state_manager.get_auto_trade_enabled():
            def _api_client_provider():
                if not account_manager.active_account:
                    return None
                acc = account_manager.get_account(account_manager.active_account)
                if not acc:
                    return None
                from gate_api_client import GateAPIClient
                return GateAPIClient(acc['api_key'], acc['api_secret'], CURRENT_NETWORK_MODE)
            
            ws_manager = get_websocket_manager()
            
            # ✅ НОВЫЙ АВТОТРЕЙДЕР V2 - чистая архитектура
            AUTO_TRADER = AutoTraderV2(
                api_client_provider=_api_client_provider,
                ws_manager=ws_manager,
                state_manager=state_manager
            )
            
            AUTO_TRADER.start()
            print('[INIT] [OK] AutoTraderV2 запущен (ЭТАП 1: каркас без торговли)')
    except Exception as e:
        print(f"[INIT] [ERROR] Не удалось запустить автотрейдер: {e}")
        print(traceback.format_exc())
    
    # После запуска WS и перед запуском Flask – синхронизируем режимы движков с сохраненным TRADING_MODE
    try:
        internal_mode = 'normal' if TRADING_MODE == 'trade' else 'copy'
        for eng in trading_engines.values():
            eng.set_mode(internal_mode)
        print(f"[INIT] Синхронизация режимов движков: {TRADING_MODE} -> {internal_mode}")
    except Exception as e:
        print(f"[INIT] Ошибка синхронизации режимов движков: {e}")
    # Запуск Flask приложения
    # Flask 3.0+ изменил дефолтный порт с 5000 на 5001
    # Явно устанавливаем переменную окружения и параметр
    os.environ['FLASK_RUN_PORT'] = '5000'
    print(f"[FLASK] Запуск веб-сервера на http://localhost:5000")
    print("=" * 60)
    
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Остановка сервера...")
        ProcessManager.remove_pid()
    except Exception as e:
        print(f"[ERROR] Ошибка запуска сервера: {e}")
        ProcessManager.remove_pid()
        sys.exit(1)