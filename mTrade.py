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

# Импорт модулей проекта
from config import Config
from process_manager import ProcessManager
from gate_api_client import GateAPIClient
from trading_engine import TradingEngine, AccountManager
from gateio_websocket import init_websocket_manager, get_websocket_manager
from state_manager import get_state_manager
from autotrader import AutoTrader  # добавлено: новый пер-валютный автотрейдер
from trade_logger import get_trade_logger

# Минимальные значения по умолчанию для legacy параметров (fallback при старте)
DEFAULT_TRADE_PARAMS = {
    'steps': 5,
    'start_volume': 0.0,
    'start_price': 0.0,
    'pprof': 0.0,
    'kprof': 0.0,
    'target_r': 0.0,
    'rk': 0.0,
    'geom_multiplier': 1.0,
    'rebuy_mode': 'percent',
    'keep': 0.0,
    'orderbook_level': 0
}

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
    from handlers.indicators import get_trade_indicators_impl
    return get_trade_indicators_impl()
# Инициализация State Manager (раньше, чтобы он был доступен во всех эндпойнтах)
state_manager = get_state_manager()
CURRENT_NETWORK_MODE = state_manager.get_network_mode()
# Вспомогательные глобальные объекты (fallback инициализация для тестового запуска)
server_start_time = time.time()
try:
    account_manager = AccountManager()
except Exception:
    account_manager = None

# Контейнер для движков по аккаунтам
trading_engines = {}

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
    """Wrapper: вызывает вынесенную реализацию синхронизации из handlers.currencies."""
    try:
        from handlers.currencies import sync_currencies_from_gateio_impl as _sync_impl
    except Exception as _e:
        print(f"[CURRENCY_SYNC] Ошибка импорта обработчика: {_e}")
        return jsonify({"success": False, "error": "Handler import failed"}), 500

    try:
        return _sync_impl()
    except Exception as e:
        print(f"[CURRENCY_SYNC] Ошибка в обработчике: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

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
        from handlers.websocket import ws_close_all
        ws_close_all()
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
    from handlers.websocket import subscribe_pair_impl
    return subscribe_pair_impl()


@app.route('/api/pair/data', methods=['GET'])
def get_pair_data():
    from handlers.websocket import get_pair_data_impl
    return get_pair_data_impl()


@app.route('/api/pair/unsubscribe', methods=['POST'])
def unsubscribe_pair():
    from handlers.websocket import unsubscribe_pair_impl
    return unsubscribe_pair_impl()


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
        from handlers.websocket import ws_get_data
        current_price = 0
        pair_data = ws_get_data(f"{base_currency}_{quote_currency}")
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
        if quote_currency.upper() != 'USDT':
            usdt_data = ws_get_data(f"{quote_currency}_USDT")
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

    # API ключи (необязательны для публичных эндпойнтов)
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


# WebSocket handlers and watchlist moved to handlers/websocket.py
from handlers.websocket import (
    WATCHED_PAIRS,
    MULTI_PAIRS_CACHE,
    api_get_watchlist_impl,
    api_watch_pairs_impl,
    api_unwatch_pairs_impl,
    api_pairs_data_impl,
)


@app.route('/api/pairs/watchlist', methods=['GET'])
def api_get_watchlist():
    return api_get_watchlist_impl()


@app.route('/api/pairs/watch', methods=['POST'])
def api_watch_pairs():
    return api_watch_pairs_impl()


@app.route('/api/pairs/unwatch', methods=['POST'])
def api_unwatch_pairs():
    return api_unwatch_pairs_impl()


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

        return api_pairs_data_impl()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# TRADE PARAMETERS & BREAK-EVEN TABLE API
# =============================================================================

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
        params = state_manager.get_breakeven_params(base_currency)
        for k, caster in (
            ('steps', int), ('start_volume', float), ('start_price', float),
            ('pprof', float), ('kprof', float), ('target_r', float), ('rk', float),
            ('geom_multiplier', float), ('rebuy_mode', str), ('keep', float), ('orderbook_level', float)
        ):
            if k in data and data[k] is not None:
                try:
                    params[k] = caster(data[k])
                except Exception:
                    pass
        state_manager.set_breakeven_params(base_currency, params)
        print(f"[PARAMS] {base_currency} -> {params}")
        return jsonify({"success": True, "message": f"Параметры для {base_currency} сохранены", "params": params, "currency": base_currency})
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
        updated = TRADE_PARAMS.copy()
        for k, caster in (
            ('steps', int), ('start_volume', float), ('start_price', float),
            ('pprof', float), ('kprof', float), ('target_r', float),
            ('geom_multiplier', float), ('rebuy_mode', str), ('orderbook_level', int)
        ):
            if k in data and data[k] is not None:
                try:
                    updated[k] = caster(data[k])
                except Exception:
                    pass
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
    from handlers.breakeven import get_breakeven_table_impl
    return get_breakeven_table_impl()


@app.route('/api/trade/permissions', methods=['GET'])
def get_trading_permissions():
    """Получить разрешения торговли для всех валют"""
    try:
        # Загружаем из State Manager
        permissions = state_manager.get_trading_permissions()
        return jsonify({
            "success": True,
            "permissions": permissions
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/permission', methods=['POST'])
def set_trading_permission():
    """Установить разрешение торговли для конкретной валюты"""
    try:
        global TRADING_PERMISSIONS
        data = request.get_json(silent=True) or {}
        base_currency = data.get('base_currency', '').upper()
        enabled = data.get('enabled', True)
        
        if not base_currency:
            return jsonify({
                "success": False,
                "error": "Не указана валюта (base_currency)"
            }), 400
        
        # Обновляем в глобальной переменной
        TRADING_PERMISSIONS[base_currency] = bool(enabled)
        
        # Сохраняем в State Manager
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
        print(f"[ERROR] Set trading permission: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrade/start', methods=['POST'])
def start_autotrade():
    """Включить автоторговлю (запустить поток per-currency)"""
    from handlers.autotrade import start_autotrade_impl
    return start_autotrade_impl()


@app.route('/api/autotrade/stop', methods=['POST'])
def stop_autotrade():
    """Выключить автоторговлю (остановить поток)"""
    from handlers.autotrade import stop_autotrade_impl
    return stop_autotrade_impl()


@app.route('/api/autotrade/status', methods=['GET'])
def get_autotrade_status():
    """Получить статус автоторговли + краткую статистику"""
    from handlers.autotrade import get_autotrade_status_impl
    return get_autotrade_status_impl()


@app.route('/api/autotrader/stats', methods=['GET'])
def get_autotrader_stats():
    """Получить статистику автотрейдера для конкретной валюты"""
    from handlers.autotrade import get_autotrader_stats_impl
    return get_autotrader_stats_impl()


@app.route('/api/autotrader/reset_cycle', methods=['POST'])
def reset_autotrader_cycle():
    """Сбросить цикл автотрейдера для конкретной валюты"""
    from handlers.autotrade import reset_autotrader_cycle_impl
    return reset_autotrader_cycle_impl()


@app.route('/api/trade/indicators', methods=['GET'])
def get_trade_indicators():
    """Получить торговые индикаторы + уровни автотрейдера для пары.
    Дополнено: возвращает структуру autotrade_levels с:
    - active_cycle, active_step, total_steps
    - next_rebuy_step и параметры следующей покупки (↓Δ,% / cumulative / purchase_usd)
    - current_growth_pct (рост от P0) и target_sell_delta_pct
    - breakeven_price, breakeven_pct текущего активного шага
    - start_price, last_buy_price, invested_usd, base_volume
    - progress_to_sell (0..1)
    Опция include_table=1 добавляет сокращённую таблицу (step, rate, purchase_usd, breakeven_price, target_delta_pct).
    """
    try:
        base_currency = request.args.get('base_currency', 'BTC').upper()
        quote_currency = request.args.get('quote_currency', 'USDT').upper()
        include_table = str(request.args.get('include_table', '0')).lower() in ('1','true','yes')
        currency_pair = f"{base_currency}_{quote_currency}".upper()

        # Данные из WebSocket
        from handlers.websocket import ws_get_data
        pair_data = ws_get_data(currency_pair)

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
                indicators['price'] = float(ticker.get('last', 0) or 0)
                indicators['change_24h'] = float(ticker.get('change_percentage', 0) or 0)
                indicators['volume_24h'] = float(ticker.get('quote_volume', 0) or 0)
                indicators['high_24h'] = float(ticker.get('high_24h', 0) or 0)
                indicators['low_24h'] = float(ticker.get('low_24h', 0) or 0)
            except (ValueError, TypeError):
                pass
            # Spread
            try:
                if pair_data.get('orderbook') and pair_data['orderbook'].get('asks') and pair_data['orderbook'].get('bids'):
                    ask = float(pair_data['orderbook']['asks'][0][0])
                    bid = float(pair_data['orderbook']['bids'][0][0])
                    indicators['ask'] = ask
                    indicators['bid'] = bid
                    indicators['spread'] = ((ask - bid) / bid * 100.0) if bid > 0 else 0.0
            except Exception:
                pass

        # Уровни автотрейдера
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
            # Дополнительные уровни цен для индикатора
            'current_price': None,
            'sell_price': None,
            'next_buy_price': None
        }
        # Всегда устанавливаем текущую цену
        price = indicators['price']
        autotrade_levels['current_price'] = price
        
        # Получаем таблицу: либо из цикла, либо рассчитываем новую
        cycle = None
        table = None
        
        if AUTO_TRADER and hasattr(AUTO_TRADER, 'cycles'):
            cycle = AUTO_TRADER.cycles.get(base_currency)
            if cycle and cycle.get('table'):
                table = cycle['table']
        
        # Если таблицы нет в цикле - рассчитываем из параметров
        if not table:
            params = state_manager.get_breakeven_params(base_currency)
            if params and price:
                try:
                    from breakeven_calculator import calculate_breakeven_table
                    table = calculate_breakeven_table(params, price)
                except Exception as e:
                    print(f"[INDICATORS] Ошибка расчёта таблицы для {base_currency}: {e}")
        
        # Обрабатываем данные таблицы (независимо от активного цикла)
        if table and len(table) > 0:
            active_step = cycle.get('active_step', -1) if cycle else -1
            autotrade_levels['active_cycle'] = bool(cycle and cycle.get('active'))
            autotrade_levels['active_step'] = active_step if active_step >= 0 else None
            autotrade_levels['total_steps'] = (len(table) - 1) if len(table) > 0 else None
            
            # Данные из активного цикла (если есть)
            if cycle:
                autotrade_levels['start_price'] = cycle.get('start_price') or None
                autotrade_levels['last_buy_price'] = cycle.get('last_buy_price') or None
                autotrade_levels['invested_usd'] = cycle.get('total_invested_usd') or None
                autotrade_levels['base_volume'] = cycle.get('base_volume') or None
            else:
                # Если цикла нет - используем первую строку таблицы как стартовую
                autotrade_levels['start_price'] = table[0].get('rate') if table else None
            # Расчёт роста от стартовой цены
            start_price = autotrade_levels['start_price']
            if start_price and price:
                try:
                    autotrade_levels['current_growth_pct'] = (price - start_price) / start_price * 100.0
                except Exception:
                    autotrade_levels['current_growth_pct'] = None
            
            # Определяем текущий шаг: активный из цикла или 0 (стартовый)
            current_step = active_step if active_step >= 0 else 0
            
            # Данные текущего шага (всегда показываем, даже если цикл неактивен)
            if current_step < len(table):
                row = table[current_step]
                autotrade_levels['breakeven_price'] = row.get('breakeven_price')
                autotrade_levels['breakeven_pct'] = row.get('breakeven_pct')
                autotrade_levels['target_sell_delta_pct'] = row.get('target_delta_pct')
                
                # Отладка: логируем BE для диагностики
                if row.get('breakeven_price'):
                    print(f"[DEBUG] autotrade_levels для {currency_pair}: step={current_step}, BE={row.get('breakeven_price'):.8f}, active={autotrade_levels['active_cycle']}")
                else:
                    print(f"[DEBUG] autotrade_levels для {currency_pair}: step={current_step}, BE=None (нет данных в таблице), active={autotrade_levels['active_cycle']}")
                
                # Расчёт цены продажи от цены безубыточности
                breakeven = row.get('breakeven_price')
                if breakeven and row.get('target_delta_pct'):
                    try:
                        target_pct = row['target_delta_pct']
                        autotrade_levels['sell_price'] = breakeven * (1 + target_pct / 100.0)
                    except Exception:
                        pass
                
                # Прогресс до продажи
                if autotrade_levels['current_growth_pct'] is not None and row.get('target_delta_pct'):
                    tgt = row['target_delta_pct']
                    cg = autotrade_levels['current_growth_pct']
                    autotrade_levels['progress_to_sell'] = max(0.0, min(1.0, cg / tgt)) if tgt > 0 else None
            # Следующий шаг покупки (для активного цикла - следующий, для неактивного - текущий стартовый)
            next_step = current_step + 1 if autotrade_levels['active_cycle'] else current_step
            
            if next_step < len(table):
                nrow = table[next_step]
                autotrade_levels['next_rebuy_step'] = next_step
                autotrade_levels['next_rebuy_decrease_step_pct'] = abs(nrow.get('decrease_step_pct', 0))
                autotrade_levels['next_rebuy_cumulative_drop_pct'] = nrow.get('cumulative_decrease_pct')
                autotrade_levels['next_rebuy_purchase_usd'] = nrow.get('purchase_usd')
                
                # Расчёт цены следующей покупки
                # Для неактивного цикла - используем rate из таблицы
                # Для активного - рассчитываем от последней покупки
                if autotrade_levels['active_cycle'] and cycle and cycle.get('last_buy_price') and nrow.get('decrease_step_pct'):
                    try:
                        last_buy = cycle['last_buy_price']
                        decrease_pct = abs(nrow['decrease_step_pct'])
                        autotrade_levels['next_buy_price'] = last_buy * (1 - decrease_pct / 100.0)
                    except Exception:
                        pass
                else:
                    # Для неактивного цикла - показываем rate из таблицы
                    autotrade_levels['next_buy_price'] = nrow.get('rate')
                    # Последняя покупка = стартовая для неактивного
                    if not autotrade_levels['last_buy_price'] and start_price:
                        autotrade_levels['last_buy_price'] = start_price
            # Ограниченный вывод таблицы
            if include_table:
                trimmed = []
                for r in table:
                    trimmed.append({
                        'step': r.get('step'),
                        'rate': r.get('rate'),
                        'purchase_usd': r.get('purchase_usd'),
                        'breakeven_price': r.get('breakeven_price'),
                        'target_delta_pct': r.get('target_delta_pct'),
                        'decrease_step_pct': r.get('decrease_step_pct'),
                        'cumulative_decrease_pct': r.get('cumulative_decrease_pct')
                    })
                autotrade_levels['table'] = trimmed

        return jsonify({"success": True, "indicators": indicators, "autotrade_levels": autotrade_levels})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/ui/state', methods=['GET'])
def get_ui_state():
    """Получить состояние UI (разрешения торговли, автоторговля, режимы, параметры безубыточности)"""
    from handlers.ui_state import get_ui_state_impl
    return get_ui_state_impl()


@app.route('/api/ui/state', methods=['POST'])
def save_ui_state():
    """Сохранить состояние UI (поддержка пакетного обновления параметров для валют)"""
    from handlers.ui_state import save_ui_state_impl
    return save_ui_state_impl()


@app.route('/api/ui/state/partial', methods=['POST'])
def save_ui_state_partial():
    """Частичное сохранение состояния UI (используется фронтендом UIStateManager)."""
    from handlers.ui_state import save_ui_state_partial_impl
    return save_ui_state_partial_impl()


# =============================================================================
# TRADE LOGS API (Логи торговых операций)
# =============================================================================

@app.route('/api/trade/logs', methods=['GET'])
def get_trade_logs():
    """Получить логи торговых операций"""
    from handlers.logs import get_trade_logs_impl
    return get_trade_logs_impl()


@app.route('/api/trade/logs/stats', methods=['GET'])
def get_trade_logs_stats():
    """Получить статистику по логам"""
    from handlers.logs import get_trade_logs_stats_impl
    return get_trade_logs_stats_impl()


@app.route('/api/trade/logs/clear', methods=['POST'])
def clear_trade_logs():
    """Очистить логи"""
    from handlers.logs import clear_trade_logs_impl
    return clear_trade_logs_impl()

# =============================================================================
# QUICK TRADE API (Быстрая торговля)
# =============================================================================

@app.route('/api/trade/buy-min', methods=['POST'])
def quick_buy_min():
    from handlers.quick_trades import quick_buy_min_impl
    return quick_buy_min_impl()


@app.route('/api/trade/sell-all', methods=['POST'])
def quick_sell_all():
    from handlers.quick_trades import quick_sell_all_impl
    return quick_sell_all_impl()


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
        # init_websocket_manager(api_key, api_secret, CURRENT_NETWORK_MODE)
        print("[INIT] WebSocket менеджер временно отключен для тестирования")
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
            from handlers.websocket import get_ws_manager
            ws_manager = get_ws_manager()
            AUTO_TRADER = AutoTrader(_api_client_provider, ws_manager, state_manager)
            AUTO_TRADER.start()
            print('[INIT] Автотрейдер запущен (восстановлено из состояния)')
    except Exception as e:
        print(f"[INIT] Не удалось запустить автотрейдер: {e}")
    
    # После запуска WS и перед запуском Flask – синхронизируем режимы движков с сохраненным TRADING_MODE
    try:
        internal_mode = 'normal' if TRADING_MODE == 'trade' else 'copy'
        for eng in trading_engines.values():
            eng.set_mode(internal_mode)
        print(f"[INIT] Синхронизация режимов движков: {TRADING_MODE} -> {internal_mode}")
    except Exception as e:
        print(f"[INIT] Ошибка синхронизации режимов движков: {e}")
    # Запуск Flask приложения
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