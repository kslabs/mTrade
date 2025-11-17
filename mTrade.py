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
    'rebuy_mode': 'geometric'
}

# Инициализация State Manager (раньше, чтобы он был доступен во всех эндпойнтах)
state_manager = get_state_manager()

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
            return jsonify({"success": True, "message": "Валюты сохранены"})
        else:
            return jsonify({"success": False, "error": "Ошибка сохранения"}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/currencies/sync', methods=['POST'])
def sync_currencies_from_gateio():
    """Синхронизация символов валют с Gate.io (НЕ меняет названия, только проверяет символы)"""
    try:
        print("\n[CURRENCY_SYNC] Начало синхронизации символов с Gate.io...")
        
        # Загрузка текущего списка
        current_currencies = Config.load_currencies()
        current_dict = {c['code']: c for c in current_currencies}
        
        # Получаем котируемую валюту из параметров запроса (по умолчанию USDT)
        quote_currency = request.json.get('quote_currency', 'USDT') if request.json else 'USDT'
        
        # 1. Проверяем торговые пары (какие валюты торгуются с котируемой)
        pairs_url = f"https://api.gateio.ws/api/v4/spot/currency_pairs"
        pairs_response = requests.get(pairs_url, timeout=10)
        
        if pairs_response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"Ошибка API Gate.io (пары): {pairs_response.status_code}"
            }), 500
        
        # Получаем список валют, которые торгуются с котируемой валютой
        all_pairs = pairs_response.json()
        tradeable_bases = set()
        for pair in all_pairs:
            pair_id = pair.get('id', '')
            if pair_id.endswith(f'_{quote_currency}') and pair.get('trade_status') == 'tradable':
                base = pair_id.replace(f'_{quote_currency}', '')
                tradeable_bases.add(base)
        
        print(f"[CURRENCY_SYNC] Найдено {len(tradeable_bases)} валют, торгующихся с {quote_currency}")
        
        # 2. Получаем информацию о валютах (включая символы)
        currencies_url = "https://api.gateio.ws/api/v4/spot/currencies"
        currencies_response = requests.get(currencies_url, timeout=10)
        
        if currencies_response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"Ошибка API Gate.io (валюты): {currencies_response.status_code}"
            }), 500
        
        gate_currencies = currencies_response.json()
        
        # Создаём словарь валют Gate.io по коду
        gate_dict = {}
        for gc in gate_currencies:
            code = gc.get('currency', '').upper()
            if code:
                gate_dict[code] = gc
        
        added_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Обрабатываем только существующие валюты пользователя
        for code, curr in current_dict.items():
            # Проверяем, торгуется ли валюта с котируемой
            if code not in tradeable_bases:
                print(f"[CURRENCY_SYNC] {code} не торгуется с {quote_currency}, пропускаем")
                skipped_count += 1
                continue
            
            # Проверяем, есть ли информация о валюте в Gate.io
            if code not in gate_dict:
                print(f"[CURRENCY_SYNC] {code} не найдена в API Gate.io, пропускаем")
                skipped_count += 1
                continue
            
            gate_curr = gate_dict[code]
            
            # Получаем символ из Gate.io (если есть)
            # На Gate.io нет прямого поля с emoji, но есть поле chain (может содержать символ)
            # Для криптовалют обычно используются стандартные Unicode-символы
            
            # Словарь популярных символов криптовалют (можно расширить)
            crypto_symbols = {
                'BTC': '₿',
                'ETH': 'Ξ',
                'USDT': '₮',
                'USDC': '$',
                'BNB': 'Ⓑ',
                'XRP': 'Ʀ',
                'ADA': '₳',
                'DOGE': 'Ð',
                'DOT': '●',
                'MATIC': 'Ⓜ',
                'SOL': '◎',
                'AVAX': '▲',
                'LINK': '◬',
                'UNI': '🦄',
                'ATOM': '⚛',
                'LTC': 'Ł',
                'ETC': 'Ξ',
                'XLM': '*',
                'ALGO': '△',
                'VET': 'Ⓥ'
            }
            
            # Если у валюты нет символа или он пустой - добавляем
            if not curr.get('symbol') or curr['symbol'].strip() == '':
                if code in crypto_symbols:
                    current_dict[code]['symbol'] = crypto_symbols[code]
                    updated_count += 1
                    print(f"[CURRENCY_SYNC] {code}: добавлен символ '{crypto_symbols[code]}'")
        
        # Сохраняем обновлённый список (порядок сохраняется)
        updated_currencies = [current_dict[c['code']] for c in current_currencies if c['code'] in current_dict]
        
        if Config.save_currencies(updated_currencies):
            print(f"[CURRENCY_SYNC] Успешно: обновлено {updated_count}, пропущено {skipped_count}")
            
            # Сохраняем информацию о синхронизации
            sync_info = {
                'timestamp': datetime.now().isoformat(),
                'quote_currency': quote_currency,
                'updated': updated_count,
                'skipped': skipped_count,
                'total': len(updated_currencies),
                'tradeable_count': len(tradeable_bases)
            }
            
            sync_info_file = os.path.join(os.path.dirname(__file__), 'currency_sync_info.json')
            with open(sync_info_file, 'w', encoding='utf-8') as f:
                json.dump(sync_info, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                "success": True,
                "updated": updated_count,
                "skipped": skipped_count,
                "total": len(updated_currencies),
                "quote_currency": quote_currency,
                "tradeable_count": len(tradeable_bases),
                "timestamp": sync_info['timestamp']
            })
        else:
            return jsonify({
                "success": False,
                "error": "Не удалось сохранить валюты"
            }), 500
            
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
                            # гарантируем наличие соединения
                            ws.create_connection(pair)
                            data = ws.get_data(pair)
                            if data is not None:
                                MULTI_PAIRS_CACHE[pair] = {"ts": time.time(), "data": data}
                        except Exception:
                            # игнорируем точечные ошибки по конкретной паре
                            pass
                time.sleep(1.0)
            except Exception:
                # защитный блок, чтобы поток не падал
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
            result[pair] = {
                "ts": cached.get('ts'),
                "data": cached.get('data')
            }
        return jsonify({"success": True, "pairs": result})
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
        if 'steps' in request.args:
            try:
                params['steps'] = int(request.args.get('steps'))
            except (ValueError, TypeError):
                pass
        if 'start_volume' in request.args:
            try:
                params['start_volume'] = float(request.args.get('start_volume'))
            except (ValueError, TypeError):
                pass
        if 'start_price' in request.args:
            try:
                params['start_price'] = float(request.args.get('start_price'))
            except (ValueError, TypeError):
                pass
        if 'pprof' in request.args:
            try:
                params['pprof'] = float(request.args.get('pprof'))
            except (ValueError, TypeError):
                pass
        if 'kprof' in request.args:
            try:
                params['kprof'] = float(request.args.get('kprof'))
            except (ValueError, TypeError):
                pass
        if 'target_r' in request.args:
            try:
                params['target_r'] = float(request.args.get('target_r'))
            except (ValueError, TypeError):
                pass
        if 'rk' in request.args:
            try:
                params['rk'] = float(request.args.get('rk'))
            except (ValueError, TypeError):
                pass
        if 'geom_multiplier' in request.args:
            try:
                params['geom_multiplier'] = float(request.args.get('geom_multiplier'))
            except (ValueError, TypeError):
                pass
        if 'rebuy_mode' in request.args:
            rebuy_mode = str(request.args.get('rebuy_mode')).lower()
            if rebuy_mode in ('fixed', 'geometric', 'martingale'):
                params['rebuy_mode'] = rebuy_mode
        
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
            "current_price": current_price
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Breakeven table calculation: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


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
    global AUTO_TRADE_GLOBAL_ENABLED, AUTO_TRADER
    try:
        AUTO_TRADE_GLOBAL_ENABLED = True
        state_manager.set_auto_trade_enabled(True)
        # Ленивая инициализация автотрейдера
        if AUTO_TRADER is None:
            def _api_client_provider():
                if not account_manager.active_account:
                    return None
                acc = account_manager.get_account(account_manager.active_account)
                if not acc:
                    return None
                from gate_api_client import GateAPIClient
                return GateAPIClient(acc['api_key'], acc['api_secret'], CURRENT_NETWORK_MODE)
            ws_manager = get_websocket_manager()
            AUTO_TRADER = AutoTrader(_api_client_provider, ws_manager, state_manager)
        if not AUTO_TRADER.running:
            AUTO_TRADER.start()
        print(f"[AUTOTRADE] Автоторговля включена (per-currency)")
        return jsonify({
            "success": True,
            "enabled": True,
            "running": AUTO_TRADER.running if AUTO_TRADER else False,
            "message": "Автоторговля включена"
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Start autotrade: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/autotrade/stop', methods=['POST'])
def stop_autotrade():
    """Выключить автоторговлю (остановить поток)"""
    global AUTO_TRADE_GLOBAL_ENABLED, AUTO_TRADER
    try:
        AUTO_TRADE_GLOBAL_ENABLED = False
        state_manager.set_auto_trade_enabled(False)
        if AUTO_TRADER and AUTO_TRADER.running:
            AUTO_TRADER.stop()
        print(f"[AUTOTRADE] Автоторговля выключена")
        return jsonify({
            "success": True,
            "enabled": False,
            "running": AUTO_TRADER.running if AUTO_TRADER else False,
            "message": "Автоторговля выключена"
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
        stats = {}
        if AUTO_TRADER and AUTO_TRADER.running:
            stats = AUTO_TRADER.stats
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
    """Получить статистику автотрейдера для конкретной валюты"""
    try:
        base_currency = request.args.get('base_currency', '').upper()
        if not base_currency:
            return jsonify({"success": False, "error": "Не указана валюта"}), 400
        
        stats = {
            "base_currency": base_currency,
            "enabled": AUTO_TRADE_GLOBAL_ENABLED,
            "running": AUTO_TRADER.running if AUTO_TRADER else False,
            "trades_count": 0,
            "profit": 0.0,
            "last_trade_time": None
        }
        
        if AUTO_TRADER and AUTO_TRADER.running and hasattr(AUTO_TRADER, 'stats'):
            # Получаем статистику для конкретной валюты из автотрейдера
            all_stats = AUTO_TRADER.stats
            if base_currency in all_stats:
                stats.update(all_stats[base_currency])
        
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/indicators', methods=['GET'])
def get_trade_indicators():
    """Получить торговые индикаторы для конкретной пары"""
    try:
        base_currency = request.args.get('base_currency', 'BTC').upper()
        quote_currency = request.args.get('quote_currency', 'USDT').upper()
        currency_pair = f"{base_currency}_{quote_currency}"
        
        # Получаем данные из WebSocket
        ws_manager = get_websocket_manager()
        pair_data = None
        if ws_manager:
            pair_data = ws_manager.get_data(currency_pair)
        
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
                indicators['price'] = float(ticker.get('last', 0))
                indicators['change_24h'] = float(ticker.get('change_percentage', 0))
                indicators['volume_24h'] = float(ticker.get('quote_volume', 0))
                indicators['high_24h'] = float(ticker.get('high_24h', 0))
                indicators['low_24h'] = float(ticker.get('low_24h', 0))
                
                # Spread из orderbook
                if pair_data.get('orderbook'):
                    ob = pair_data['orderbook']
                    if ob.get('asks') and ob.get('bids'):
                        try:
                            ask = float(ob['asks'][0][0])
                            bid = float(ob['bids'][0][0])
                            indicators['ask'] = ask
                            indicators['bid'] = bid
                            indicators['spread'] = ((ask - bid) / bid * 100) if bid > 0 else 0
                        except (IndexError, ValueError, TypeError):
                            pass
            except (ValueError, TypeError):
                pass
        
        return jsonify({"success": True, "indicators": indicators})
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
                "breakeven_params": state_manager.get_breakeven_params()  # все валюты
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
        state = data.get('state', {})
        # Автоторговля
        if 'auto_trade_enabled' in state:
            AUTO_TRADE_GLOBAL_ENABLED = bool(state['auto_trade_enabled'])
            state_manager.set_auto_trade_enabled(AUTO_TRADE_GLOBAL_ENABLED)
        # Разрешения торговли
        if 'enabled_currencies' in state and isinstance(state['enabled_currencies'], dict):
            TRADING_PERMISSIONS.update(state['enabled_currencies'])
            for currency, enabled in state['enabled_currencies'].items():
                state_manager.set_trading_permission(currency, enabled)
        # Режим торговли
        if 'trading_mode' in state:
            mode = str(state['trading_mode']).lower()
            if mode in ('trade','copy'):
                TRADING_MODE = mode
                state_manager.set_trading_mode(TRADING_MODE)
        # Режим сети
        if 'network_mode' in state:
            nm = str(state['network_mode']).lower()
            if nm in ('work','test') and nm != CURRENT_NETWORK_MODE:
                if _reinit_network_mode(nm):
                    CURRENT_NETWORK_MODE = nm
                    state_manager.set_network_mode(nm)
        # Параметры безубыточности (пакетное обновление)
        if 'breakeven_params' in state and isinstance(state['breakeven_params'], dict):
            for currency, params in state['breakeven_params'].items():
                try:
                    cur = currency.upper()
                    existing = state_manager.get_breakeven_params(cur)
                    # обновляем допустимые поля
                    for k in ('steps','start_volume','start_price','pprof','kprof','target_r','geom_multiplier','rebuy_mode','orderbook_level'):
                        if k in params:
                            existing[k] = params[k]
                    state_manager.set_breakeven_params(cur, existing)
                except Exception as e:
                    print(f"[STATE] Ошибка сохранения breakeven для {currency}: {e}")
        return jsonify({"success": True, "message": "Состояние UI сохранено"})
    except Exception as e:
        import traceback
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
                "last_updated": None
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
        if 'breakeven_params' in payload and isinstance(payload['breakeven_params'], dict):
            be_updates = payload['breakeven_params']
            existing_all = state_manager.get("breakeven_params", {}) or {}
            for currency, params in be_updates.items():
                try:
                    cur = str(currency).upper()
                    if not cur:
                        continue
                    existing = existing_all.get(cur) or state_manager.get_breakeven_params(cur)
                    if not isinstance(existing, dict):
                        existing = {}
                    for k in ('steps','start_volume','start_price','pprof','kprof','target_r','geom_multiplier','rebuy_mode','orderbook_level'):
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
        import traceback
        print(f"[ERROR] Save UI state partial: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# TRADE LOGS API (Логи торговых операций)
# =============================================================================

@app.route('/api/trade/logs', methods=['GET'])
def get_trade_logs():
    """Получить логи торговых операций"""
    try:
        trade_logger = get_trade_logger()
        
        # Параметры запроса
        limit = request.args.get('limit', '100')
        currency = request.args.get('currency')
        formatted = request.args.get('formatted', '0') == '1'
        
        try:
            limit = int(limit)
        except:
            limit = 100
        
        if formatted:
            # Возвращаем отформатированные строки
            logs = trade_logger.get_formatted_logs(limit=limit, currency=currency)
            return jsonify({
                'success': True,
                'logs': logs,
                'count': len(logs)
            })
        else:
            # Возвращаем сырые данные
            logs = trade_logger.get_logs(limit=limit, currency=currency)
            return jsonify({
                'success': True,
                'logs': logs,
                'count': len(logs)
            })
    except Exception as e:
        import traceback
        print(f"[ERROR] get_trade_logs: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trade/logs/stats', methods=['GET'])
def get_trade_logs_stats():
    """Получить статистику по логам"""
    try:
        trade_logger = get_trade_logger()
        currency = request.args.get('currency')
        
        stats = trade_logger.get_stats(currency=currency)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] get_trade_logs_stats: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trade/logs/clear', methods=['POST'])
def clear_trade_logs():
    """Очистить логи"""
    try:
        trade_logger = get_trade_logger()
        data = request.get_json() or {}
        currency = data.get('currency')
        
        trade_logger.clear_logs(currency=currency)
        
        return jsonify({
            'success': True,
            'message': f"Логи {'для ' + currency if currency else 'все'} очищены"
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] clear_trade_logs: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# QUICK TRADE API (Быстрая торговля)
# =============================================================================

@app.route('/api/trade/buy-min', methods=['POST'])
def quick_buy_min():
    """Купить минимальный ордер по текущей цене"""
    import traceback
    
    # Переменные для диагностики (заполняются по ходу выполнения)
    diagnostic_info = {
        'pair': None,
        'base_currency': None,
        'quote_currency': None,
        'balance_usdt': None,
        'best_ask': None,
        'best_bid': None,
        'orderbook_bids': None,
        'orderbook_asks': None,
        'amount': None,
        'execution_price': None,
        'start_volume': None,
        'api_min_quote': None,
        'network_mode': CURRENT_NETWORK_MODE,
        'error_stage': None
    }
    
    try:
        data = request.get_json() or {}
        base_currency = data.get('base_currency')
        quote_currency = data.get('quote_currency', 'USDT')
        
        diagnostic_info['base_currency'] = base_currency
        diagnostic_info['quote_currency'] = quote_currency
        
        if not base_currency:
            diagnostic_info['error_stage'] = 'validation'
            return jsonify({
                'success': False, 
                'error': 'Не указана базовая валюта',
                'details': diagnostic_info
            }), 400
        
        pair = f"{base_currency}_{quote_currency}"
        diagnostic_info['pair'] = pair
        
        # Получаем API ключи из конфига для текущего режима
        api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        if not api_key or not api_secret:
            diagnostic_info['error_stage'] = 'api_keys'
            return jsonify({
                'success': False, 
                'error': 'API ключи не настроены для текущего режима',
                'details': diagnostic_info
            }), 400
        
        api_client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)
        
        # Получаем баланс USDT для диагностики
        diagnostic_info['error_stage'] = 'get_balance'
        try:
            balance = api_client.get_account_balance()
            for item in balance:
                if item.get('currency', '').upper() == quote_currency.upper():
                    diagnostic_info['balance_usdt'] = float(item.get('available', '0'))
                    break
        except Exception as e:
            print(f"[WARNING] Не удалось получить баланс: {e}")
        
        # Получаем параметры пары
        diagnostic_info['error_stage'] = 'get_pair_info'
        pair_info = api_client.get_currency_pair_details_exact(pair)
        if not pair_info or 'error' in pair_info:
            diagnostic_info['error_stage'] = 'pair_not_found'
            return jsonify({
                'success': False, 
                'error': f'Пара {pair} не найдена',
                'details': diagnostic_info
            }), 400
        
        diagnostic_info['api_min_quote'] = float(pair_info.get('min_quote_amount', '3'))
        
        # Получаем текущую цену (best ask)
        diagnostic_info['error_stage'] = 'get_market_data'
        ws_manager = get_websocket_manager()
        market_data = ws_manager.get_pair_data(base_currency, quote_currency)
        
        if not market_data or 'orderbook' not in market_data:
            diagnostic_info['error_stage'] = 'no_market_data'
            return jsonify({
                'success': False, 
                'error': 'Нет данных рынка',
                'details': diagnostic_info
            }), 400
        
        orderbook = market_data['orderbook']
        
        # Сохраняем информацию об ордербуке для диагностики
        if orderbook.get('bids'):
            diagnostic_info['orderbook_bids'] = [[float(b[0]), float(b[1])] for b in orderbook['bids'][:5]]
            diagnostic_info['best_bid'] = float(orderbook['bids'][0][0])
        if orderbook.get('asks'):
            diagnostic_info['orderbook_asks'] = [[float(a[0]), float(a[1])] for a in orderbook['asks'][:5]]
            diagnostic_info['best_ask'] = float(orderbook['asks'][0][0])
        
        if not orderbook.get('asks'):
            diagnostic_info['error_stage'] = 'no_asks'
            return jsonify({
                'success': False, 
                'error': 'Нет цен продажи в стакане',
                'details': diagnostic_info
            }), 400
        
        # Получаем параметры безубыточности для данной валюты
        breakeven_params = state_manager.get_breakeven_params(base_currency)
        
        # Получаем уровень стакана (по умолчанию 1 = лучшая цена)
        orderbook_level = int(breakeven_params.get('orderbook_level', 1))
        diagnostic_info['orderbook_level'] = orderbook_level
        
        # Проверяем, что уровень стакана доступен
        if len(orderbook['asks']) < orderbook_level:
            diagnostic_info['error_stage'] = 'orderbook_level_unavailable'
            return jsonify({
                'success': False, 
                'error': f'Уровень стакана {orderbook_level} недоступен (доступно уровней: {len(orderbook["asks"])})',
                'details': diagnostic_info
            }), 400
        
        # Берём цену по выбранному уровню стакана (индекс = уровень - 1)
        best_ask = float(orderbook['asks'][orderbook_level - 1][0])
        diagnostic_info['selected_ask'] = best_ask
        
        # ВАЖНО: Берём start_volume из параметров безубыточности для данной валюты!
        start_volume = float(breakeven_params.get('start_volume', 10.0))
        diagnostic_info['start_volume'] = start_volume
        
        # Проверяем минимум API (для безопасности)
        api_min_quote = diagnostic_info['api_min_quote']
        if start_volume < api_min_quote:
            print(f"[WARNING] start_volume ({start_volume}) < API минимум ({api_min_quote}), используем {api_min_quote}")
            start_volume = api_min_quote
            diagnostic_info['start_volume'] = start_volume
        
        # Проверяем достаточность баланса
        if diagnostic_info.get('balance_usdt') is not None and diagnostic_info['balance_usdt'] < start_volume:
            diagnostic_info['error_stage'] = 'insufficient_balance'
            return jsonify({
                'success': False, 
                'error': f'Недостаточно {quote_currency} для покупки (баланс: {diagnostic_info["balance_usdt"]}, требуется: {start_volume})',
                'details': diagnostic_info
            }), 400
        
        # Рассчитываем количество базовой валюты
        amount = start_volume / best_ask
        
        # Округляем до точности пары
        amount_precision = int(pair_info.get('amount_precision', 8))
        amount = round(amount, amount_precision)
        diagnostic_info['amount'] = amount
        
        # Форматируем amount без научной нотации
        amount_str = f"{amount:.{amount_precision}f}"
        
        # В testnet mode используем лимитные ордера (market не поддерживаются)
        diagnostic_info['error_stage'] = 'create_order'
        if CURRENT_NETWORK_MODE == 'test':
            # При ПОКУПКЕ: используем best_ask напрямую (покупаем по цене продавцов)
            # Ордер исполнится мгновенно как taker, т.к. цена = лучшему ask
            execution_price = best_ask
            diagnostic_info['execution_price'] = execution_price
            price_precision = int(pair_info.get('precision', 8))
            price_str = f"{execution_price:.{price_precision}f}"
            print(f"[INFO] quick_buy_min: создание ЛИМИТНОГО ордера {pair}, amount={amount_str}, price={price_str} (testnet, покупка по best_ask)")
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='buy',
                amount=amount_str,
                price=price_str,
                order_type='limit'
            )
        else:
            # В production используем market ордера
            execution_price = best_ask
            diagnostic_info['execution_price'] = execution_price
            print(f"[INFO] quick_buy_min: создание РЫНОЧНОГО ордера {pair}, amount={amount_str}")
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='buy',
                amount=amount_str,
                order_type='market'
            )
        
        print(f"[INFO] quick_buy_min: ответ API: {result}")
        print(f"[INFO] quick_buy_min: type(result) = {type(result)}")
        print(f"[INFO] quick_buy_min: 'label' in result = {'label' in result if isinstance(result, dict) else 'N/A'}")
        
        # Проверяем результат на ошибки (любое наличие 'label' означает ошибку в Gate.io API)
        if isinstance(result, dict) and 'label' in result:
            error_msg = result.get('message', 'Неизвестная ошибка API')
            error_label = result.get('label', 'UNKNOWN_ERROR')
            diagnostic_info['error_stage'] = f'api_error_{error_label}'
            diagnostic_info['api_error'] = {'label': error_label, 'message': error_msg}
            print(f"[ERROR] quick_buy_min: ошибка API [{error_label}] - {error_msg}")
            return jsonify({
                'success': False, 
                'error': f'[{error_label}] {error_msg}',
                'details': diagnostic_info
            }), 400
        
        # Проверяем, что ордер действительно создан (есть поле id)
        if not isinstance(result, dict) or 'id' not in result:
            diagnostic_info['error_stage'] = 'no_order_id'
            diagnostic_info['api_response'] = str(result)[:200]  # Ограничиваем размер
            print(f"[ERROR] quick_buy_min: нет ID в ответе - {result}")
            return jsonify({
                'success': False, 
                'error': 'Ордер не создан (нет ID в ответе)',
                'details': diagnostic_info
            }), 400
        
        # Логируем сделку
        trade_logger = get_trade_logger()
        trade_logger.log_buy(
            currency=base_currency,
            volume=amount,
            price=best_ask,
            delta_percent=0.0,
            total_drop_percent=0.0,
            investment=start_volume
        )
        
        # Успешный результат с полной информацией
        return jsonify({
            'success': True,
            'order': result,
            'amount': amount,
            'price': best_ask,
            'execution_price': diagnostic_info['execution_price'],
            'total': start_volume,
            'order_id': result.get('id', 'unknown'),
            'details': {
                'pair': pair,
                'side': 'buy',
                'order_type': 'limit' if CURRENT_NETWORK_MODE == 'test' else 'market',
                'best_ask': best_ask,
                'best_bid': diagnostic_info.get('best_bid'),
                'amount': amount,
                'start_volume_usdt': start_volume,
                'balance_usdt': diagnostic_info.get('balance_usdt'),
                'network_mode': CURRENT_NETWORK_MODE,
                'orderbook_snapshot': {
                    'bids': diagnostic_info.get('orderbook_bids'),
                    'asks': diagnostic_info.get('orderbook_asks')
                }
            }
        })
        
    except Exception as e:
        diagnostic_info['error_stage'] = 'exception'
        diagnostic_info['exception'] = str(e)
        print(f"[ERROR] quick_buy_min: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False, 
            'error': str(e),
            'details': diagnostic_info
        }), 500


@app.route('/api/trade/sell-all', methods=['POST'])
def quick_sell_all():
    """Продать весь доступный баланс базовой валюты"""
    import time
    import traceback
    
    # Переменные для диагностики (заполняются по ходу выполнения)
    diagnostic_info = {
        'pair': None,
        'base_currency': None,
        'quote_currency': None,
        'balance': None,
        'best_bid': None,
        'best_ask': None,
        'orderbook_bids': None,
        'orderbook_asks': None,
        'amount': None,
        'execution_price': None,
        'total': None,
        'cancelled_orders': 0,
        'network_mode': CURRENT_NETWORK_MODE,
        'error_stage': None
    }
    
    try:
        data = request.get_json() or {}
        base_currency = data.get('base_currency')
        quote_currency = data.get('quote_currency', 'USDT')
        
        diagnostic_info['base_currency'] = base_currency
        diagnostic_info['quote_currency'] = quote_currency
        
        if not base_currency:
            diagnostic_info['error_stage'] = 'validation'
            return jsonify({
                'success': False, 
                'error': 'Не указана базовая валюта',
                'details': diagnostic_info
            }), 400
        
        pair = f"{base_currency}_{quote_currency}"
        diagnostic_info['pair'] = pair
        
        # Получаем API ключи из конфига для текущего режима
        api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        if not api_key or not api_secret:
            diagnostic_info['error_stage'] = 'api_keys'
            return jsonify({
                'success': False, 
                'error': 'API ключи не настроены для текущего режима',
                'details': diagnostic_info
            }), 400
        
        api_client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)
        
        # В testnet режиме: отменяем все открытые ордера по этой паре перед продажей
        cancel_result = {'count': 0}
        if CURRENT_NETWORK_MODE == 'test':
            try:
                cancel_result = api_client.cancel_all_open_orders(pair)
                diagnostic_info['cancelled_orders'] = cancel_result.get('count', 0)
                if cancel_result.get('count', 0) > 0:
                    print(f"[INFO] Отменено {cancel_result['count']} открытых ордеров для {pair}")
                    # Даём время на обновление баланса после отмены
                    time.sleep(1)
            except Exception as e:
                print(f"[WARNING] Не удалось отменить открытые ордера: {e}")
        
        # Получаем баланс базовой валюты
        diagnostic_info['error_stage'] = 'get_balance'
        balance = api_client.get_account_balance()
        base_balance = None
        
        for item in balance:
            if item.get('currency', '').upper() == base_currency.upper():
                base_balance = float(item.get('available', '0'))
                break
        
        diagnostic_info['balance'] = base_balance
        
        if not base_balance or base_balance <= 0:
            diagnostic_info['error_stage'] = 'insufficient_balance'
            return jsonify({
                'success': False, 
                'error': f'Недостаточно {base_currency} для продажи (баланс: {base_balance or 0})',
                'details': diagnostic_info
            }), 400
        
        # Получаем параметры пары
        diagnostic_info['error_stage'] = 'get_pair_info'
        pair_info = api_client.get_currency_pair_details_exact(pair)
        if not pair_info or 'error' in pair_info:
            diagnostic_info['error_stage'] = 'pair_not_found'
            return jsonify({
                'success': False, 
                'error': f'Пара {pair} не найдена',
                'details': diagnostic_info
            }), 400
        
        # Получаем текущую цену (best bid)
        diagnostic_info['error_stage'] = 'get_market_data'
        ws_manager = get_websocket_manager()
        market_data = ws_manager.get_pair_data(base_currency, quote_currency)
        
        if not market_data or 'orderbook' not in market_data:
            diagnostic_info['error_stage'] = 'no_market_data'
            return jsonify({
                'success': False, 
                'error': 'Нет данных рынка',
                'details': diagnostic_info
            }), 400
        
        orderbook = market_data['orderbook']
        
        # Сохраняем информацию об ордербуке для диагностики
        if orderbook.get('bids'):
            diagnostic_info['orderbook_bids'] = [[float(b[0]), float(b[1])] for b in orderbook['bids'][:5]]
            diagnostic_info['best_bid'] = float(orderbook['bids'][0][0])
        if orderbook.get('asks'):
            diagnostic_info['orderbook_asks'] = [[float(a[0]), float(a[1])] for a in orderbook['asks'][:5]]
            diagnostic_info['best_ask'] = float(orderbook['asks'][0][0])
        
        if not orderbook.get('bids'):
            diagnostic_info['error_stage'] = 'no_bids'
            return jsonify({
                'success': False, 
                'error': 'Нет цен покупки в стакане',
                'details': diagnostic_info
            }), 400
        
        # Получаем параметры безубыточности для данной валюты
        breakeven_params = state_manager.get_breakeven_params(base_currency)
        
        # Получаем уровень стакана (по умолчанию 1 = лучшая цена)
        orderbook_level = int(breakeven_params.get('orderbook_level', 1))
        diagnostic_info['orderbook_level'] = orderbook_level
        
        # Проверяем, что уровень стакана доступен
        if len(orderbook['bids']) < orderbook_level:
            diagnostic_info['error_stage'] = 'orderbook_level_unavailable'
            return jsonify({
                'success': False, 
                'error': f'Уровень стакана {orderbook_level} недоступен (доступно уровней: {len(orderbook["bids"])})',
                'details': diagnostic_info
            }), 400
        
        # Берём цену по выбранному уровню стакана (индекс = уровень - 1)
        best_bid = float(orderbook['bids'][orderbook_level - 1][0])
        diagnostic_info['selected_bid'] = best_bid
        
        # Округляем количество до точности пары (ВАЖНО: округляем ВНИЗ, чтобы не превысить доступный баланс)
        amount_precision = int(pair_info.get('amount_precision', 8))
        import math
        # Используем floor вместо round, чтобы гарантировать, что amount <= base_balance
        amount = math.floor(base_balance * (10 ** amount_precision)) / (10 ** amount_precision)
        diagnostic_info['amount'] = amount
        
        # Рассчитываем общую сумму продажи
        total = amount * best_bid
        diagnostic_info['total'] = total
        
        # Форматируем amount без научной нотации
        amount_str = f"{amount:.{amount_precision}f}"
        
        # В testnet mode используем лимитные ордера (market не поддерживаются)
        diagnostic_info['error_stage'] = 'create_order'
        if CURRENT_NETWORK_MODE == 'test':
            # При ПРОДАЖЕ: используем best_bid напрямую (продаём по цене покупателей)
            # Ордер исполнится мгновенно как taker, т.к. цена = лучшему bid
            execution_price = best_bid
            diagnostic_info['execution_price'] = execution_price
            price_precision = int(pair_info.get('precision', 8))
            price_str = f"{execution_price:.{price_precision}f}"
            print(f"[INFO] quick_sell_all: создание ЛИМИТНОГО ордера {pair}, amount={amount_str}, price={price_str} (testnet, продажа по best_bid)")
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='sell',
                amount=amount_str,
                price=price_str,
                order_type='limit'
            )
        else:
            # В production используем market ордера
            execution_price = best_bid
            diagnostic_info['execution_price'] = execution_price
            print(f"[INFO] quick_sell_all: создание РЫНОЧНОГО ордера {pair}, amount={amount_str}")
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='sell',
                amount=amount_str,
                order_type='market'
            )
        
        print(f"[INFO] quick_sell_all: ответ API: {result}")
        
        # Проверяем результат на ошибки (любое наличие 'label' означает ошибку в Gate.io API)
        if isinstance(result, dict) and 'label' in result:
            error_msg = result.get('message', 'Неизвестная ошибка API')
            error_label = result.get('label', 'UNKNOWN_ERROR')
            diagnostic_info['error_stage'] = f'api_error_{error_label}'
            diagnostic_info['api_error'] = {'label': error_label, 'message': error_msg}
            print(f"[ERROR] quick_sell_all: ошибка API [{error_label}] - {error_msg}")
            return jsonify({
                'success': False, 
                'error': f'[{error_label}] {error_msg}',
                'details': diagnostic_info
            }), 400
        
        # Проверяем, что ордер действительно создан (есть поле id)
        if not isinstance(result, dict) or 'id' not in result:
            diagnostic_info['error_stage'] = 'no_order_id'
            diagnostic_info['api_response'] = str(result)[:200]  # Ограничиваем размер
            print(f"[ERROR] quick_sell_all: нет ID в ответе - {result}")
            return jsonify({
                'success': False, 
                'error': 'Ордер не создан (нет ID в ответе)',
                'details': diagnostic_info
            }), 400
        
        # Логируем сделку
        trade_logger = get_trade_logger()
        trade_logger.log_sell(
            currency=base_currency,
            volume=amount,
            price=best_bid,
            delta_percent=0.0,
            pnl=0.0
        )
        
        # Успешный результат с полной информацией
        return jsonify({
            'success': True,
            'order': result,
            'amount': amount,
            'price': best_bid,
            'execution_price': diagnostic_info['execution_price'],
            'total': total,
            'order_id': result.get('id', 'unknown'),
            'details': {
                'pair': pair,
                'side': 'sell',
                'order_type': 'limit' if CURRENT_NETWORK_MODE == 'test' else 'market',
                'best_bid': best_bid,
                'best_ask': diagnostic_info.get('best_ask'),
                'amount': amount,
                'total_usdt': total,
                'balance': base_balance,
                'network_mode': CURRENT_NETWORK_MODE,
                'cancelled_orders': diagnostic_info['cancelled_orders'],
                'orderbook_snapshot': {
                    'bids': diagnostic_info.get('orderbook_bids'),
                    'asks': diagnostic_info.get('orderbook_asks')
                }
            }
        })
        
    except Exception as e:
        diagnostic_info['error_stage'] = 'exception'
        diagnostic_info['exception'] = str(e)
        print(f"[ERROR] quick_sell_all: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False, 
            'error': str(e),
            'details': diagnostic_info
        }), 500


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