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
    
    # API Gate.io
    API_HOST = "https://api.gateio.ws"
    API_PREFIX = "/api/v4"
    
    # Режимы работы
    MODE_NORMAL = "normal"  # Обычный трейдинг
    MODE_COPY = "copy"      # Копитрейдинг
    
    # Настройки по умолчанию
    DEFAULT_MODE = MODE_NORMAL
    DEFAULT_MARKET = "spot"  # spot, futures
    
    # Файл для хранения настроек
    CONFIG_FILE = "config.json"
    ACCOUNTS_FILE = "accounts.json"
    # Перенос секретов в папку config/
    SECRETS_FILE = os.path.join('config', 'secrets.json')
    CURRENCIES_FILE = "currencies.json"
    UI_STATE_FILE = "ui_state.json"  # Файл для сохранения состояния UI
    WORK_SECRETS_FILE = os.path.join('config', 'secrets.json')        # рабочая сеть
    TEST_SECRETS_FILE = os.path.join('config', 'secrets_test1.json')  # тестовая сеть (новые ключи)
    TEST_API_HOST = "https://api-testnet.gateapi.io"  # Правильный домен тестовой сети Gate.io
    NETWORK_CONFIG_FILE = "network_mode.json"

    @staticmethod
    def load_network_mode() -> str:
        try:
            if os.path.exists(Config.NETWORK_CONFIG_FILE):
                with open(Config.NETWORK_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    js = json.load(f)
                    m = str(js.get('mode', 'work')).lower()
                    return 'test' if m == 'test' else 'work'
        except Exception:
            pass
        return 'work'

    @staticmethod
    def save_network_mode(mode: str) -> bool:
        try:
            if mode not in ('work','test'): return False
            with open(Config.NETWORK_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'mode': mode, 'saved_at': time.time()}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def load_secrets():
        """Загрузить API ключи из secrets.json"""
        if os.path.exists(Config.SECRETS_FILE):
            try:
                with open(Config.SECRETS_FILE, 'r') as f:
                    secrets = json.load(f)
                    return secrets.get('GATEIO_API_KEY'), secrets.get('GATEIO_API_SECRET')
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки secrets.json: {e}")
        return None, None
    
    @staticmethod
    def load_secrets_by_mode(mode: str):
        """Загрузить ключи по режиму work|test, учитывая новые пути config/ и старые имена для обратной совместимости."""
        candidates = []
        if mode == 'work':
            candidates = [
                Config.WORK_SECRETS_FILE,
                Config.SECRETS_FILE,
                'secret.json',           # старое имя
                'secrets.json'           # возможный вариант
            ]
        else:
            candidates = [
                Config.TEST_SECRETS_FILE,   # config/secrets_test1.json (новые ключи)
                os.path.join('config', 'secrets_test.json'),  # старые тестовые ключи
                'secret_test.json',         # старое имя
                'secrets_test.json'         # возможный вариант
            ]
        for file in candidates:
            try:
                if os.path.exists(file):
                    with open(file,'r',encoding='utf-8') as f:
                        j = json.load(f)
                        ak = j.get('GATEIO_API_KEY')
                        sk = j.get('GATEIO_API_SECRET')
                        if ak and sk:
                            return ak, sk
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки {file}: {e}")
        return None, None
    
    @staticmethod
    def load_currencies():
        """Загрузить список базовых валют из currencies.json"""
        default_currencies = [
            { "code": "WLD", "symbol": "🌐" },
            { "code": "BTC", "symbol": "₿" },
            { "code": "ETH", "symbol": "Ξ" },
            { "code": "SOL", "symbol": "◎" },
            { "code": "BNB", "symbol": "🔶" },
            { "code": "XRP", "symbol": "✕" },
            { "code": "ADA", "symbol": "₳" },
            { "code": "AVAX", "symbol": "🔺" },
            { "code": "DOT", "symbol": "⬤" },
            { "code": "MATIC", "symbol": "🔷" }
        ]
        
        if os.path.exists(Config.CURRENCIES_FILE):
            try:
                with open(Config.CURRENCIES_FILE, 'r', encoding='utf-8') as f:
                    currencies = json.load(f)
                    return currencies if currencies else default_currencies
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки currencies.json: {e}")
                return default_currencies
        else:
            # Создать файл с дефолтными валютами
            Config.save_currencies(default_currencies)
            return default_currencies
    
    @staticmethod
    def save_currencies(currencies):
        """Сохранить список базовых валют в currencies.json"""
        try:
            # Ограничиваем количество валют
            if len(currencies) > DataLimits.MAX_CURRENCIES:
                currencies = currencies[:DataLimits.MAX_CURRENCIES]
                print(f"[WARNING] Количество валют ограничено до {DataLimits.MAX_CURRENCIES}")
            
            with open(Config.CURRENCIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(currencies, f, ensure_ascii=False, indent=2)
            
            # Проверка размера файла
            file_size_kb = os.path.getsize(Config.CURRENCIES_FILE) / 1024
            if file_size_kb > DataLimits.MAX_CURRENCIES_FILE_SIZE_KB:
                print(f"[WARNING] Размер currencies.json ({file_size_kb:.2f} KB) превышает лимит")
            
            return True
        except Exception as e:
            print(f"[ERROR] Ошибка сохранения currencies.json: {e}")
            return False

    @staticmethod
    def load_ui_state():
        """Загрузить состояние UI из файла"""
        default_state = {
            "enabled_currencies": {},  # {BASE_CURRENCY: true/false}
            "auto_trade_enabled": False,
            "network_mode": "work",
            "active_base_currency": "BTC",
            "active_quote_currency": "USDT",
            "theme": "dark",
            "show_indicators": True,
            "show_orderbook": True,
            "show_trades": True,
            "orderbook_depth": 20,
            "last_updated": None
        }
        
        if os.path.exists(Config.UI_STATE_FILE):
            try:
                with open(Config.UI_STATE_FILE, 'r', encoding='utf-8') as f:
                    saved_state = json.load(f)
                    # Объединяем с дефолтными значениями
                    default_state.update(saved_state)
                    return default_state
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки ui_state.json: {e}")
                return default_state
        else:
            # Создаем файл с дефолтными настройками
            Config.save_ui_state(default_state)
            return default_state
    
    @staticmethod
    def save_ui_state(state):
        """Сохранить состояние UI в файл"""
        try:
            state['last_updated'] = time.time()
            with open(Config.UI_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ERROR] Ошибка сохранения ui_state.json: {e}")
            return False


# =============================================================================
# PROCESS MANAGER (Управление процессом)
# =============================================================================

class ProcessManager:
    """Менеджер для управления процессом сервера"""
    
    PID_FILE = "mtrade_server.pid"
    
    @staticmethod
    def write_pid():
        """Записать PID текущего процесса"""
        pid = os.getpid()
        with open(ProcessManager.PID_FILE, 'w') as f:
            f.write(str(pid))
        print(f"[PID] Процесс запущен с PID: {pid}")
        
    @staticmethod
    def read_pid():
        """Прочитать PID из файла"""
        if os.path.exists(ProcessManager.PID_FILE):
            try:
                with open(ProcessManager.PID_FILE, 'r') as f:
                    return int(f.read().strip())
            except:
                return None
        return None
    
    @staticmethod
    def remove_pid():
        """Удалить PID файл"""
        if os.path.exists(ProcessManager.PID_FILE):
            os.remove(ProcessManager.PID_FILE)
            print("[PID] PID файл удален")
    
    @staticmethod
    def is_running():
        """Проверить, запущен ли процесс"""
        pid = ProcessManager.read_pid()
        if pid is None:
            return False
        
        # Проверяем, существует ли процесс
        try:
            # На Windows используем tasklist
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True
            )
            return str(pid) in result.stdout
        except:
            return False
    
    @staticmethod
    def kill_process(pid=None):
        """Убить процесс по PID"""
        if pid is None:
            pid = ProcessManager.read_pid()
        
        if pid is None:
            print("[PID] PID не найден")
            return False
        
        try:
            import subprocess
            # На Windows используем taskkill
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], check=True)
            print(f"[PID] Процесс {pid} завершен")
            ProcessManager.remove_pid()
            return True
        except Exception as e:
            print(f"[PID] Ошибка при завершении процесса: {e}")
            return False
    
    @staticmethod
    def setup_cleanup():
        """Настроить автоматическую очистку при выходе"""
        atexit.register(ProcessManager.remove_pid)
        
        # Обработчики сигналов для graceful shutdown
        def signal_handler(signum, frame):
            print("\n[SHUTDOWN] Получен сигнал завершения...")
            ProcessManager.remove_pid()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


# =============================================================================
# GATE.IO API CLIENT
# =============================================================================

# Инициализация глобальных служебных переменных — выполняется здесь, после определения Config
server_start_time = time.time()
PAIR_INFO_CACHE = {}
PAIR_INFO_CACHE_TTL = 3600  # 1 час
CURRENT_NETWORK_MODE = Config.load_network_mode()
print(f"[NETWORK] Текущий режим сети: {CURRENT_NETWORK_MODE}")

# --- Реинициализация сетевого режима (work/test) ---
_ws_reinit_lock = None
try:
    from threading import Lock
    _ws_reinit_lock = Lock()
except Exception:
    pass

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
# PROCESS MANAGER (Управление процессом)
# =============================================================================

class ProcessManager:
    """Менеджер для управления процессом сервера"""
    
    PID_FILE = "mtrade_server.pid"
    
    @staticmethod
    def write_pid():
        """Записать PID текущего процесса"""
        pid = os.getpid()
        with open(ProcessManager.PID_FILE, 'w') as f:
            f.write(str(pid))
        print(f"[PID] Процесс запущен с PID: {pid}")
        
    @staticmethod
    def read_pid():
        """Прочитать PID из файла"""
        if os.path.exists(ProcessManager.PID_FILE):
            try:
                with open(ProcessManager.PID_FILE, 'r') as f:
                    return int(f.read().strip())
            except:
                return None
        return None
    
    @staticmethod
    def remove_pid():
        """Удалить PID файл"""
        if os.path.exists(ProcessManager.PID_FILE):
            os.remove(ProcessManager.PID_FILE)
            print("[PID] PID файл удален")
    
    @staticmethod
    def is_running():
        """Проверить, запущен ли процесс"""
        pid = ProcessManager.read_pid()
        if pid is None:
            return False
        
        # Проверяем, существует ли процесс
        try:
            # На Windows используем tasklist
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True
            )
            return str(pid) in result.stdout
        except:
            return False
    
    @staticmethod
    def kill_process(pid=None):
        """Убить процесс по PID"""
        if pid is None:
            pid = ProcessManager.read_pid()
        
        if pid is None:
            print("[PID] PID не найден")
            return False
        
        try:
            import subprocess
            # На Windows используем taskkill
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], check=True)
            print(f"[PID] Процесс {pid} завершен")
            ProcessManager.remove_pid()
            return True
        except Exception as e:
            print(f"[PID] Ошибка при завершении процесса: {e}")
            return False
    
    @staticmethod
    def setup_cleanup():
        """Настроить автоматическую очистку при выходе"""
        atexit.register(ProcessManager.remove_pid)
        
        # Обработчики сигналов для graceful shutdown
        def signal_handler(signum, frame):
            print("\n[SHUTDOWN] Получен сигнал завершения...")
            ProcessManager.remove_pid()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


# =============================================================================
# GATE.IO API CLIENT
# =============================================================================

# Инициализация глобальных служебных переменных — выполняется здесь, после определения Config
server_start_time = time.time()
PAIR_INFO_CACHE = {}
PAIR_INFO_CACHE_TTL = 3600  # 1 час
CURRENT_NETWORK_MODE = Config.load_network_mode()
print(f"[NETWORK] Текущий режим сети: {CURRENT_NETWORK_MODE}")

class GateAPIClient:
    """Клиент для работы с Gate.io API"""
    
    def __init__(self, api_key: str, api_secret: str, network_mode: str = 'work'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.network_mode = network_mode
        # Выбор хоста по режиму
        self.host = Config.API_HOST if network_mode == 'work' else Config.TEST_API_HOST
        self.prefix = Config.API_PREFIX
    
    def _generate_sign(self, method: str, url: str, query_string: str = '', payload: str = ''):
        """Генерация подписи для API запроса"""
        t = str(int(time.time()))
        m = hashlib.sha512()
        m.update(payload.encode('utf-8'))
        hashed_payload = m.hexdigest()
        
        s = f"{method}\n{url}\n{query_string}\n{hashed_payload}\n{t}"
        sign = hmac.new(
            self.api_secret.encode('utf-8'),
            s.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return {
            'KEY': self.api_key,
            'Timestamp': t,
            'SIGN': sign
        }
    
    def _request(self, method: str, endpoint: str, params: dict = None, data: dict = None):
        """Выполнение API запроса"""
        url = f"{self.prefix}{endpoint}"
        query_string = ''
        payload = ''
        
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        
        if data:
            payload = json.dumps(data)
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        # Подпись добавляем только при наличии ключей (публичные эндпойнты работают без подписи)
        if self.api_key and self.api_secret:
            headers.update(self._generate_sign(method, url, query_string, payload))
        
        full_url = f"{self.host}{url}"
        if query_string:
            full_url += f"?{query_string}"
        
        response = requests.request(
            method,
            full_url,
            headers=headers,
            data=payload if data else None
        )
        
        return response.json()
    
    # -------------------------------------------------------------------------
    # SPOT TRADING (Обычный трейдинг)
    # -------------------------------------------------------------------------
    
    def get_account_balance(self):
        """Получить баланс спот счета"""
        return self._request('GET', '/spot/accounts')
    
    def create_spot_order(self, currency_pair: str, side: str, amount: str, price: str = None, order_type: str = "limit"):
        """Создать спотовый ордер"""
        order_data = {
            "currency_pair": currency_pair,
            "side": side,  # buy или sell
            "amount": amount,
            "type": order_type  # limit или market
        }
        
        if price and order_type == "limit":
            order_data["price"] = price
        
        return self._request('POST', '/spot/orders', data=order_data)
    
    def get_spot_orders(self, currency_pair: str, status: str = "open"):
        """Получить список ордеров"""
        params = {
            "currency_pair": currency_pair,
            "status": status
        }
        return self._request('GET', '/spot/orders', params=params)
    
    def cancel_spot_order(self, order_id: str, currency_pair: str):
        """Отменить ордер"""
        return self._request('DELETE', f'/spot/orders/{order_id}', params={"currency_pair": currency_pair})
    
    # -------------------------------------------------------------------------
    # FUTURES TRADING
    # -------------------------------------------------------------------------
    
    def get_futures_balance(self, settle: str = "usdt"):
        """Получить баланс фьючерсного счета"""
        return self._request('GET', f'/futures/{settle}/accounts')
    
    def create_futures_order(self, contract: str, size: int, price: str = None, settle: str = "usdt"):
        """Создать фьючерсный ордер"""
        order_data = {
            "contract": contract,
            "size": size,
        }
        
        if price:
            order_data["price"] = price
        
        return self._request('POST', f'/futures/{settle}/orders', data=order_data)
    
    # -------------------------------------------------------------------------
    # COPY TRADING (Копитрейдинг)
    # -------------------------------------------------------------------------
    
    def get_account_detail(self):
        """Получить детали аккаунта (включая copy_trading_role)"""
        return self._request('GET', '/account/detail')
    
    def transfer_to_copy_trading(self, currency: str, amount: str, direction: str = "to"):
        """
        Перевод средств в/из копитрейдинг аккаунта
        direction: 'to' - в копитрейдинг, 'from' - из копитрейдинга
        """
        # Для фьючерсного копитрейдинга используем специальные endpoints
        # Примечание: точный endpoint может отличаться, нужно проверить в документации
        transfer_data = {
            "currency": currency,
            "amount": amount,
            "from": "spot" if direction == "to" else "copy_trading",
            "to": "copy_trading" if direction == "to" else "spot"
        }
        return self._request('POST', '/wallet/transfers', data=transfer_data)
    
    def get_currency_pair_details_exact(self, currency_pair: str):
        """Точный запрос одной пары через endpoint /spot/currency_pairs/{pair}."""
        try:
            ep = f"/spot/currency_pairs/{currency_pair.upper()}"
            return self._request('GET', ep)
        except Exception as e:
            return {"error": str(e)}
    
    def get_currency_pair_details(self, currency_pair: str):
        """Старый метод (возвращает список)."""
        try:
            params = {"currency_pair": currency_pair.upper()}
            return self._request('GET', '/spot/currency_pairs', params=params)
        except Exception as e:
            return {"error": str(e)}


# =============================================================================
# TRADING ENGINE & ACCOUNT MANAGER (импорт из отдельных модулей)
# =============================================================================

from trading_engine import TradingEngine, AccountManager


# =============================================================================
# FLASK ROUTES (WEB INTERFACE)
# =============================================================================

# Глобальные объекты
account_manager = AccountManager()
trading_engines = {}

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
    """Получить текущий режим"""
    if account_manager.active_account and account_manager.active_account in trading_engines:
        engine = trading_engines[account_manager.active_account]
        return jsonify({"mode": engine.get_mode()})
    return jsonify({"mode": Config.DEFAULT_MODE})

@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Переключить режим торговли"""
    data = request.json
    mode = data.get('mode')
    
    if account_manager.active_account and account_manager.active_account in trading_engines:
        engine = trading_engines[account_manager.active_account]
        if engine.set_mode(mode):
            return jsonify({"success": True, "mode": mode})
    
    return jsonify({"success": False, "error": "Нет активного аккаунта"})

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
                # Ищем RESTART.bat или START.bat в рабочей директории
                bat_candidates = [os.path.join(app_dir, 'RESTART.bat'), os.path.join(app_dir, 'START.bat')]
                bat_to_run = next((b for b in bat_candidates if os.path.exists(b)), None)
                if bat_to_run:
                    try:
                        # Запуск батника в новом окне (start)
                        subprocess.Popen(['cmd', '/c', 'start', '"mTrade Restart"', bat_to_run], shell=False)
                        print(f"[RESTART] Запущен батник: {bat_to_run}")
                    except Exception as e:
                        print(f"[RESTART] Ошибка при запуске батника {bat_to_run}: {e}")
                else:
                    # fallback: пробуем запустить python скрипт напрямую
                    if script and os.path.exists(script):
                        try:
                            if hasattr(subprocess, 'CREATE_NEW_CONSOLE'):
                                subprocess.Popen([python, script], creationflags=subprocess.CREATE_NEW_CONSOLE)
                            else:
                                subprocess.Popen([python, script])
                            print(f"[RESTART] Новый процесс запущен: {python} {script}")
                        except Exception as e:
                            print(f"[RESTART] Ошибка при запуске нового процесса на Windows: {e}")
                    else:
                        print('[RESTART] Не найден скрипт для перезапуска')
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

WATCHED_PAIRS = set()
MULTI_PAIRS_CACHE = {}  # { pair: { ts: <float>, data: <dict> } }


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


def _init_default_watchlist():
    try:
        bases = Config.load_currencies()
        default_pairs = []
        for c in bases:
            code = (c or {}).get('code')
            if code:
                default_pairs.append(f"{str(code).upper()}_USDT")
        if default_pairs:
            _add_pairs_to_watchlist(default_pairs)
    except Exception:
        pass


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
    """Получить текущие параметры торговли"""
    try:
        return jsonify({
            "success": True,
            "params": TRADE_PARAMS
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/params', methods=['POST'])
def save_trade_params():
    """Сохранить параметры торговли"""
    try:
        data = request.get_json(silent=True) or {}
        
        # Обновляем глобальные параметры
        if 'steps' in data:
            TRADE_PARAMS['steps'] = int(data['steps'])
        if 'start_volume' in data:
            TRADE_PARAMS['start_volume'] = float(data['start_volume'])
        if 'start_price' in data:
            TRADE_PARAMS['start_price'] = float(data['start_price'])
        if 'pprof' in data:
            TRADE_PARAMS['pprof'] = float(data['pprof'])
        if 'kprof' in data:
            TRADE_PARAMS['kprof'] = float(data['kprof'])
        if 'target_r' in data:
            TRADE_PARAMS['target_r'] = float(data['target_r'])
        if 'geom_multiplier' in data:
            TRADE_PARAMS['geom_multiplier'] = float(data['geom_multiplier'])
        if 'rebuy_mode' in data:
            TRADE_PARAMS['rebuy_mode'] = str(data['rebuy_mode'])
        
        return jsonify({
            "success": True,
            "message": "Параметры сохранены",
            "params": TRADE_PARAMS
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/breakeven/table', methods=['GET'])
def get_breakeven_table():
    """Рассчитать и вернуть таблицу безубыточности"""
    try:
        from breakeven_calculator import calculate_breakeven_table
        base_currency = request.args.get('base_currency', 'BTC').upper()
        table_data = calculate_breakeven_table(TRADE_PARAMS)
        return jsonify({
            "success": True,
            "table": table_data,
            "params": TRADE_PARAMS
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Breakeven table calculation: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


# =============================
# МУЛЬТИ-БАЗОВЫЙ АВТОТРЕЙДЕР
# =============================

# Глобальные разрешения торговли по каждой базовой валюте (инициализируем True)
try:
    TRADING_PERMISSIONS = { (c or {}).get('code','').upper(): True for c in Config.load_currencies() if (c or {}).get('code') }
except Exception:
    TRADING_PERMISSIONS = {}

# Глобальный флаг автозапуска новых циклов (включение автотрейдинга влияет только на старт новых циклов)
AUTO_TRADE_GLOBAL_ENABLED = True

# Параметры торговли для расчета таблицы безубыточности
TRADE_PARAMS = {
    'steps': 16,                    # Число шагов (вкл. 0)
    'start_volume': 3.0,            # Стартовый объём
    'start_price': 0.0,             # Начальная цена (P0), 0 = текущий курс
    'pprof': 0.6,                   # Pprof, %
    'kprof': 0.02,                  # Kprof
    'target_r': 3.65,               # ↑ БезУб, % (цель R)
    'geom_multiplier': 2.0,         # Множитель геометрии
    'rebuy_mode': 'geometric'       # Режим сумм докупок (fixed, geometric, martingale)
}

# Импорт автотрейдера из отдельного модуля
# from autotrader import AutoTrader  # Пока не используется


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