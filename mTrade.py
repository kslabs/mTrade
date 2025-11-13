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
import hmac
import hashlib
import signal
import atexit
import random  # добавлено для автотрейдера
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
import requests
from threading import Thread
from typing import Dict, List, Optional
from data_limits import DataLimits

# Импорт WebSocket модуля
from gateio_websocket import init_websocket_manager, get_websocket_manager
# Импорт State Manager
from state_manager import get_state_manager

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

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

class Config:
    """Конфигурация приложения"""
    
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
    WORK_SECRETS_FILE = os.path.join('config', 'secrets.json')        # рабочая сеть
    TEST_SECRETS_FILE = os.path.join('config', 'secrets_test.json')   # тестовая сеть
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
                Config.TEST_SECRETS_FILE,
                'secret_test.json',      # старое имя
                'secrets_test.json'      # возможный вариант
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

# Загружаем режим сети из state_manager (единственный источник истины)
state_mgr = get_state_manager()
CURRENT_NETWORK_MODE = state_mgr.get_network_mode()
print(f"[NETWORK] Текущий режим сети загружен из state_manager: {CURRENT_NETWORK_MODE}")

# --- Реинициализация сетевого режима (work/test) ---
_ws_reinit_lock = None
try:
    from threading import Lock
    _ws_reinit_lock = Lock()
except Exception:
    pass

# Инициализация дефолтного watchlist для WebSocket (безопасный no-op при ошибке)
def _init_default_watchlist():
    try:
        ws_manager = get_websocket_manager()
        if not ws_manager:
            return
        # Минимальный набор популярных пар, чтобы данные появились сразу
        for pair in ('BTC_USDT', 'ETH_USDT'):
            try:
                ws_manager.create_connection(pair)
            except Exception:
                pass
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
        print(f"[NETWORK] ========================================")
        print(f"[NETWORK] Переключение режима: {CURRENT_NETWORK_MODE} -> {new_mode}")
        
        # Сохраняем файл конфигурации режима
        Config.save_network_mode(new_mode)
        CURRENT_NETWORK_MODE = new_mode
        
        # Определяем хост API для нового режима
        api_host = Config.TEST_API_HOST if new_mode == 'test' else Config.API_HOST
        print(f"[NETWORK] API Host: {api_host}")
        
        # Закрываем текущие WS соединения
        ws_manager = get_websocket_manager()
        if ws_manager:
            try:
                ws_manager.close_all()
                print(f"[NETWORK] WebSocket соединения закрыты")
            except Exception as e:
                print(f"[NETWORK] Ошибка закрытия WS: {e}")
        
        # Инициализация нового менеджера
        try:
            ak, sk = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
            if ak and sk:
                print(f"[NETWORK] Загружены ключи для режима '{new_mode}':")
                print(f"[NETWORK]   API Key: {ak}")
                print(f"[NETWORK]   Файл: {Config.TEST_SECRETS_FILE if new_mode == 'test' else Config.WORK_SECRETS_FILE}")
            else:
                print(f"[NETWORK] ⚠️  Не удалось загрузить ключи для режима '{new_mode}'!")
            
            init_websocket_manager(ak, sk, CURRENT_NETWORK_MODE)
            _init_default_watchlist()
            print(f"[NETWORK] ✓ WS менеджер переинициализирован")
        except Exception as e:
            print(f"[NETWORK] ❌ Ошибка инициализации WS менеджера: {e}")
        
        print(f"[NETWORK] ========================================")
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
        if self.api_key and self.api_secret:
            headers.update(self._generate_sign(method, url, query_string, payload))
        full_url = f"{self.host}{url}"
        if query_string:
            full_url += f"?{query_string}"
        if endpoint.startswith('/spot/accounts'):
            print(f"[API DEBUG] Balance request -> mode={self.network_mode}, host={self.host}, url={full_url}")
        response = requests.request(method, full_url, headers=headers, data=payload if data else None)
        status = response.status_code
        text_raw = ''
        try:
            text_raw = response.text[:500]
        except Exception:
            pass
        try:
            js = response.json()
        except Exception as je:
            print(f"[API DEBUG] JSON parse error status={status} err={je} raw={text_raw}")
            js = {'error': 'json_parse_error', 'status': status, 'raw': text_raw}
        if endpoint.startswith('/spot/accounts'):
            if status != 200:
                print(f"[API DEBUG] NON-200 status={status} raw={text_raw}")
            else:
                # Сокращённый вывод для списков
                if isinstance(js, list):
                    print(f"[API DEBUG] Balance list len={len(js)}")
                elif isinstance(js, dict):
                    print(f"[API DEBUG] Balance dict keys={list(js.keys())[:6]}")
        # Добавляем статус внутрь ответа при ошибке, чтобы фронт мог его увидеть
        if status != 200 and isinstance(js, dict) and 'status' not in js:
            js['status'] = status
        return js
    
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
# TRADING ENGINE
# =============================================================================

class TradingEngine:
    """Движок для управления торговлей"""
    
    def __init__(self, api_client: GateAPIClient, mode: str = Config.MODE_NORMAL):
        self.client = api_client
        self.mode = mode
        self.is_running = False
        self.active_orders = []
    
    def set_mode(self, mode: str):
        """Переключить режим торговли"""
        if mode in [Config.MODE_NORMAL, Config.MODE_COPY]:
            self.mode = mode
            print(f"[INFO] Режим изменен на: {mode}")
            return True
        return False
    
    def get_mode(self) -> str:
        """Получить текущий режим"""
        return self.mode
    
    def start(self):
        """Запустить торговлю"""
        self.is_running = True
        print(f"[INFO] Торговля запущена в режиме: {self.mode}")
    
    def stop(self):
        """Остановить торговлю"""
        self.is_running = False
        print(f"[INFO] Торговля остановлена")
    
    def execute_trade(self, params: dict):
        """Выполнить сделку"""
        if self.mode == Config.MODE_NORMAL:
            return self._execute_normal_trade(params)
        elif self.mode == Config.MODE_COPY:
            return self._execute_copy_trade(params)
    
    def _execute_normal_trade(self, params: dict):
        """Выполнить обычную сделку"""
        try:
            result = self.client.create_spot_order(
                currency_pair=params.get('currency_pair'),
                side=params.get('side'),
                amount=params.get('amount'),
                price=params.get('price'),
                order_type=params.get('type', 'limit')
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_copy_trade(self, params: dict):
        """Выполнить копитрейдинг сделку"""
        # Здесь будет логика для копитрейдинга
        # Пока возвращаем заглушку
        return {
            "success": True,
            "message": "Copy trading функционал в разработке",
            "mode": "copy_trading"
        }


# =============================================================================
# ACCOUNT MANAGER
# =============================================================================

class AccountManager:
    """Менеджер для управления несколькими аккаунтами"""
    
    def __init__(self):
        self.accounts = self._load_accounts()
        self.active_account = None
    
    def _load_accounts(self) -> dict:
        """Загрузить аккаунты из файла"""
        if os.path.exists(Config.ACCOUNTS_FILE):
            with open(Config.ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_accounts(self):
        """Сохранить аккаунты в файл"""
        # Ограничиваем количество аккаунтов
        if len(self.accounts) > DataLimits.MAX_ACCOUNTS:
            print(f"[WARNING] Количество аккаунтов ({len(self.accounts)}) превышает лимит {DataLimits.MAX_ACCOUNTS}")
            # Оставляем только последние N аккаунтов
            sorted_accounts = sorted(
                self.accounts.items(),
                key=lambda x: x[1].get('created_at', ''),
                reverse=True
            )
            self.accounts = dict(sorted_accounts[:DataLimits.MAX_ACCOUNTS])
        
        with open(Config.ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.accounts, f, indent=2, ensure_ascii=False)
        
        # Проверка размера файла
        file_size_kb = os.path.getsize(Config.ACCOUNTS_FILE) / 1024
        if file_size_kb > DataLimits.MAX_ACCOUNTS_FILE_SIZE_KB:
            print(f"[WARNING] Размер accounts.json ({file_size_kb:.2f} KB) превышает лимит")
    
    def add_account(self, name: str, api_key: str, api_secret: str):
        """Добавить новый аккаунт"""
        # Проверка лимита
        if len(self.accounts) >= DataLimits.MAX_ACCOUNTS:
            return {
                "success": False,
                "error": f"Достигнут максимальный лимит аккаунтов ({DataLimits.MAX_ACCOUNTS})"
            }
        
        self.accounts[name] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "created_at": datetime.now().isoformat()
        }
        self._save_accounts()
        return {"success": True}
    
    def get_account(self, name: str) -> Optional[dict]:
        """Получить аккаунт по имени"""
        return self.accounts.get(name)
    
    def list_accounts(self) -> List[str]:
        """Список всех аккаунтов"""
        return list(self.accounts.keys())
    
    def set_active_account(self, name: str):
        """Установить активный аккаунт"""
        if name in self.accounts:
            self.active_account = name
            return True
        return False


# =============================================================================
# FLASK ROUTES (WEB INTERFACE)
# =============================================================================

# Глобальные объекты
account_manager = AccountManager()
trading_engines = {}
# Добавляем глобальный автотрейдер
from autotrader import AutoTrader
auto_trader = None

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
    # Загружаем режим из state_manager (единственный источник истины)
    mode = state_mgr.get_trading_mode()
    return jsonify({"success": True, "mode": mode})

@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Переключить режим торговли"""
    try:
        data = request.json or {}
        mode = str(data.get('mode', '')).lower()
        
        if mode not in ('trade', 'copy'):
            return jsonify({"success": False, "error": "mode must be trade or copy"}), 400
        
        # Сохраняем режим в state_manager
        if state_mgr.set_trading_mode(mode):
            print(f"[STATE] Trading mode сохранен: {mode}")
            return jsonify({"success": True, "mode": mode})
        else:
            return jsonify({"success": False, "error": "Failed to save trading mode"}), 500
    except Exception as e:
        print(f"[ERROR] set_mode: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

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

# =============================
# UI STATE ENDPOINTS (синхронизация с фронтендом)
# =============================
@app.route('/api/ui/state', methods=['GET'])
def ui_state_get():
    try:
        return jsonify({
            'success': True,
            'state': {
                'auto_trade_enabled': state_mgr.get_auto_trade_enabled(),
                'enabled_currencies': state_mgr.get_trading_permissions(),
                'network_mode': CURRENT_NETWORK_MODE,
                'trading_mode': state_mgr.get_trading_mode(),
                'active_base_currency': state_mgr.get_active_base_currency(),
                'active_quote_currency': state_mgr.get_active_quote_currency(),
                'breakeven_params': state_mgr.get_breakeven_params()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/state', methods=['POST'])
def ui_state_save():
    try:
        data = request.get_json(silent=True) or {}
        state = data.get('state', {})
        # Автоторговля
        if 'auto_trade_enabled' in state:
            enabled = bool(state['auto_trade_enabled'])
            state_mgr.set_auto_trade_enabled(enabled)
            _ensure_autotrader_running(enabled)
        # Разрешения по валютам
        if 'enabled_currencies' in state and isinstance(state['enabled_currencies'], dict):
            for cur, val in state['enabled_currencies'].items():
                state_mgr.set_trading_permission(cur, val)
        # Режим торговли
        if 'trading_mode' in state:
            tm = str(state['trading_mode']).lower()
            if tm in ('trade', 'copy'):
                state_mgr.set_trading_mode(tm)
        # Режим сети
        if 'network_mode' in state:
            nm = str(state['network_mode']).lower()
            if nm in ('work','test') and nm != CURRENT_NETWORK_MODE:
                if _reinit_network_mode(nm):
                    state_mgr.set_network_mode(nm)
        # Активные валюты
        if 'active_base_currency' in state:
            state_mgr.set_active_base_currency(state['active_base_currency'])
        if 'active_quote_currency' in state:
            state_mgr.set_active_quote_currency(state['active_quote_currency'])
        # Параметры безубыточности (массово)
        if 'breakeven_params' in state and isinstance(state['breakeven_params'], dict):
            for cur, params in state['breakeven_params'].items():
                try:
                    state_mgr.set_breakeven_params(cur, params)
                except Exception as e:
                    print(f"[BREAKEVEN] save error {cur}: {e}")
        return jsonify({'success': True, 'message': 'UI state saved'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ui/state/partial', methods=['POST'])
def ui_state_partial():
    try:
        data = request.get_json(silent=True) or {}
        updated = []
        if 'auto_trade_enabled' in data:
            enabled = bool(data['auto_trade_enabled'])
            state_mgr.set_auto_trade_enabled(enabled)
            _ensure_autotrader_running(enabled)
            updated.append(f'auto_trade_enabled={enabled}')
        if 'active_base_currency' in data:
            bc = str(data['active_base_currency']).upper()
            state_mgr.set_active_base_currency(bc)
            updated.append(f'active_base_currency={bc}')
        if 'active_quote_currency' in data:
            qc = str(data['active_quote_currency']).upper()
            state_mgr.set_active_quote_currency(qc)
            updated.append(f'active_quote_currency={qc}')
        if 'network_mode' in data:
            nm = str(data['network_mode']).lower()
            if nm in ('work','test') and nm != CURRENT_NETWORK_MODE:
                if _reinit_network_mode(nm):
                    state_mgr.set_network_mode(nm)
                    updated.append(f'network_mode={nm}')
        if 'trading_mode' in data:
            tm = str(data['trading_mode']).lower()
            if tm in ('trade','copy','normal'):
                norm = 'trade' if tm == 'normal' else tm
                state_mgr.set_trading_mode(norm)
                updated.append(f'trading_mode={norm}')
        if 'breakeven_params' in data and isinstance(data['breakeven_params'], dict) and 'currency' in data['breakeven_params']:
            cur = str(data['breakeven_params']['currency']).upper()
            state_mgr.set_breakeven_params(cur, data['breakeven_params'])
            updated.append(f'breakeven_params[{cur}]')
        return jsonify({'success': True, 'message': 'partial saved', 'updated': updated})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================
# NETWORK MODE ENDPOINTS (ожидаются фронтендом)
# =============================
@app.route('/api/network', methods=['GET'])
@app.route('/api/network/mode', methods=['GET'])
def api_get_network_mode():
    try:
        ak, sk = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        return jsonify({
            'success': True,
            'mode': CURRENT_NETWORK_MODE,
            'api_host': Config.TEST_API_HOST if CURRENT_NETWORK_MODE=='test' else Config.API_HOST,
            'keys_loaded': bool(ak and sk)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network', methods=['POST'])
@app.route('/api/network/mode', methods=['POST'])
def api_set_network_mode():
    try:
        data = request.get_json(silent=True) or {}
        nm = str(data.get('mode','')).lower()
        if nm not in ('work','test'):
            return jsonify({'success': False, 'error': "mode must be 'work' or 'test'"}), 400
        if nm == CURRENT_NETWORK_MODE:
            return jsonify({'success': True, 'mode': CURRENT_NETWORK_MODE, 'message': 'already set'})
        if _reinit_network_mode(nm):
            state_mgr.set_network_mode(nm)
            return jsonify({'success': True, 'mode': nm, 'message': 'network mode switched'})
        return jsonify({'success': False, 'error': 'failed to switch network mode'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================
# AUTOTRADE ENDPOINTS
# =============================

def _ensure_autotrader_running(enabled: bool):
    global auto_trader
    if enabled:
        if auto_trader is None:
            def _api_client_provider():
                if not account_manager.active_account:
                    return None
                acc = account_manager.get_account(account_manager.active_account)
                if not acc:
                    return None
                return GateAPIClient(acc['api_key'], acc['api_secret'], CURRENT_NETWORK_MODE)
            ws_manager = get_websocket_manager()
            from autotrader import AutoTrader as _AT
            auto_trader = _AT(_api_client_provider, ws_manager, state_mgr)
        if not auto_trader.running:
            auto_trader.start()
    else:
        if auto_trader and auto_trader.running:
            auto_trader.stop()

@app.route('/api/autotrade/start', methods=['POST'])
def api_autotrade_start():
    try:
        state_mgr.set_auto_trade_enabled(True)
        _ensure_autotrader_running(True)
        return jsonify({'success': True, 'enabled': True, 'running': auto_trader.running if auto_trader else False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/autotrade/stop', methods=['POST'])
def api_autotrade_stop():
    try:
        state_mgr.set_auto_trade_enabled(False)
        _ensure_autotrader_running(False)
        return jsonify({'success': True, 'enabled': False, 'running': auto_trader.running if auto_trader else False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/autotrade/status', methods=['GET'])
def api_autotrade_status():
    try:
        enabled = state_mgr.get_auto_trade_enabled()
        return jsonify({'success': True, 'enabled': enabled, 'running': auto_trader.running if auto_trader else False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
    return jsonify({"success": True, "message": "Сервер останавлиется..."})


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
    """Получить балансы для пары.
    Только реальные приватные данные с Gate.io.
    Если нет ключей или API не вернул список – показываем нули (UI может отобразить прочерк).
    Добавлена расширенная диагностика: если ответ не список, возвращаем ошибку для фронтенда.
    """
    try:
        base_currency = request.args.get('base_currency', 'BTC')
        quote_currency = request.args.get('quote_currency', 'USDT')
        api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        used_source = f"config/{'secrets_test.json' if CURRENT_NETWORK_MODE=='test' else 'secrets.json'}"
        if not (api_key and api_secret) and account_manager.active_account:
            acc = account_manager.get_account(account_manager.active_account)
            if acc and acc.get('api_key') and acc.get('api_secret'):
                api_key, api_secret = acc['api_key'], acc['api_secret']
                used_source = f"accounts:{account_manager.active_account}"
        raw = None
        balance_list = []
        source = 'empty'
        auth_error = False
        if api_key and api_secret:
            try:
                client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)
                print(f"[BALANCES] mode={CURRENT_NETWORK_MODE}, host={client.host}, keys=YES, src={used_source}")
                raw = client.get_account_balance()  # может быть list или dict
                print(f"[BALANCES RAW] type={type(raw).__name__} preview={(str(raw)[:200])}")
                if isinstance(raw, list):
                    balance_list = raw
                    if balance_list:
                        source = 'private'
                elif isinstance(raw, dict):  # Ошибка или нестандартный ответ
                    # Проверяем типичные поля ошибки Gate.io
                    err_fields = [raw.get('label'), raw.get('message'), raw.get('error'), raw.get('status')]
                    auth_error = True
                    return jsonify({
                        'success': False,
                        'error': 'Gate.io API error',
                        'api_error': raw,
                        'auth_error': auth_error,
                        'source': 'error',
                        'mode': CURRENT_NETWORK_MODE,
                        'used_source': used_source
                    })
                else:
                    # Неизвестный формат
                    return jsonify({
                        'success': False,
                        'error': 'Unknown balance response type',
                        'api_error_type': str(type(raw)),
                        'source': 'error',
                        'mode': CURRENT_NETWORK_MODE,
                        'used_source': used_source
                    })
            except Exception as e:
                print(f"[BALANCES] API exception: {e}")
        else:
            print(f"[BALANCES] mode={CURRENT_NETWORK_MODE}, keys=NO, src={used_source}")
        base_balance = {"currency": base_currency, "available": "0", "locked": "0"}
        quote_balance = {"currency": quote_currency, "available": "0", "locked": "0"}
        if isinstance(balance_list, list):
            for item in balance_list:
                cur = str(item.get('currency', '')).upper()
                if cur == base_currency.upper():
                    base_balance = {"currency": base_currency, "available": item.get('available', '0'), "locked": item.get('locked', '0')}
                elif cur == quote_currency.upper():
                    quote_balance = {"currency": quote_currency, "available": item.get('available', '0'), "locked": item.get('locked', '0')}
        ws_manager = get_websocket_manager()
        current_price = 0.0
        if ws_manager:
            pair_data = ws_manager.get_data(f"{base_currency}_{quote_currency}")
            if pair_data and pair_data.get('ticker') and pair_data['ticker'].get('last'):
                try:
                    current_price = float(pair_data['ticker']['last'])
                except Exception:
                    pass
        try:
            base_available = float(base_balance['available'])
        except Exception:
            base_available = 0.0
        base_equivalent = base_available * current_price if current_price > 0 else 0.0
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
            'success': True,
            'balances': {'base': base_balance, 'quote': quote_balance},
            'price': current_price,
            'base_equivalent': base_equivalent,
            'quote_equivalent': quote_equivalent,
            'source': source,
            'auth_error': auth_error,
            'mode': CURRENT_NETWORK_MODE,
            'used_source': used_source
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test/balance', methods=['GET','POST'])
def api_test_balance_removed():
    return jsonify({'success': False, 'error': 'test balance API отключен. Используются только реальные приватные данные.'}), 410

# =============================================================================
# API: Параметры торговли и таблица безубыточности
# =============================================================================

@app.route('/api/trade/params', methods=['GET', 'POST'])
def api_trade_params():
    """
    GET: Получить параметры торговли для валюты
    POST: Сохранить параметры торговли для валюты
    """
    state_mgr = get_state_manager()
    
    if request.method == 'GET':
        base_currency = request.args.get('base_currency', '').upper()
        if not base_currency:
            return jsonify({'success': False, 'error': 'base_currency required'})
        
        params = state_mgr.get_breakeven_params(base_currency)
        return jsonify({
            'success': True,
            'currency': base_currency,
            'params': params
        })
    
    elif request.method == 'POST':
        try:
            data = request.get_json() or {}
            base_currency = data.get('base_currency', '').upper()
            if not base_currency:
                return jsonify({'success': False, 'error': 'base_currency required'})
            
            # Извлекаем параметры
            params = {
                'steps': int(data.get('steps', 16)),
                'start_volume': float(data.get('start_volume', 3.0)),
                'start_price': float(data.get('start_price', 0.0)),
                'pprof': float(data.get('pprof', 0.6)),
                'kprof': float(data.get('kprof', 0.02)),
                'target_r': float(data.get('target_r', 3.65)),
                'geom_multiplier': float(data.get('geom_multiplier', 2.0)),
                'rebuy_mode': data.get('rebuy_mode', 'geometric'),
                'keep': float(data.get('keep', 0.0))
            }
            
            # Сохраняем в state manager
            state_mgr.set_breakeven_params(base_currency, params)
            
            return jsonify({
                'success': True,
                'currency': base_currency,
                'params': params
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/breakeven/table', methods=['GET'])
def api_breakeven_table():
    """
    Получить таблицу безубыточности с параметрами из запроса или сохранёнными
    """
    try:
        from breakeven_calculator import calculate_breakeven_table
        
        state_mgr = get_state_manager()
        ws_mgr = get_websocket_manager()
        
        base_currency = request.args.get('base_currency', 'BTC').upper()
        
        # Получаем параметры из запроса или из сохранённых
        params = {
            'steps': int(request.args.get('steps', 0)),
            'start_volume': float(request.args.get('start_volume', 0)),
            'start_price': float(request.args.get('start_price', 0)),
            'pprof': float(request.args.get('pprof', 0)),
            'kprof': float(request.args.get('kprof', 0)),
            'target_r': float(request.args.get('target_r', 0)),
            'geom_multiplier': float(request.args.get('geom_multiplier', 0)),
            'rebuy_mode': request.args.get('rebuy_mode', ''),
            'keep': float(request.args.get('keep', 0))
        }
        
        # Если параметры не заданы в запросе, берём сохранённые
        if params['steps'] == 0:
            saved_params = state_mgr.get_breakeven_params(base_currency)
            params.update(saved_params)
        
        # Получаем текущую цену для валюты
        current_price = 0.0
        try:
            pair = f"{base_currency}_USDT"
            ticker_data = ws_mgr.get_ticker(pair)
            if ticker_data and 'last' in ticker_data:
                current_price = float(ticker_data['last'])
        except Exception:
            pass
        
        # Рассчитываем таблицу
        table = calculate_breakeven_table(params, current_price)
        
        return jsonify({
            'success': True,
            'currency': base_currency,
            'current_price': current_price,
            'params': params,
            'table': table
        })
    except Exception as e:
        print(f"[BREAKEVEN] Ошибка расчёта таблицы: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# =============================================================================
# ENTRYPOINT (запуск сервера)
# =============================================================================
if __name__ == '__main__':
    # Записываем PID для вспомогательных скриптов (start/restart/stop)
    try:
        ProcessManager.write_pid()
    except Exception:
        pass
    # Параметры запуска (можно переопределить через переменные окружения)
    host = os.environ.get('MTRADE_HOST', '0.0.0.0')
    try:
        port = int(os.environ.get('MTRADE_PORT', '5000'))
    except Exception:
        port = 5000
    print(f"[START] Flask сервер запускается: http://{host}:{port} (mode={CURRENT_NETWORK_MODE})")
    # Явно выключаем debug, включаем threaded для одновременных запросов
    app.run(host=host, port=port, debug=False, threaded=True)