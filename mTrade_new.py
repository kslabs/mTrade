"""
Gate.io Multi-Trading Application (Refactored Version)
Поддержка обычного трейдинга и копитрейдинга
"""

import os
import sys
import time
import hashlib
from flask import Flask, render_template, jsonify

# Импорт модулей проекта
from config import Config
from process_manager import ProcessManager
from trading_engine import AccountManager
from gateio_websocket import init_websocket_manager, get_websocket_manager
from state_manager import get_state_manager

# Импорт модулей маршрутов
from api_routes import APIRoutes
from websocket_routes import WebSocketRoutes
from trade_params_routes import TradeParamsRoutes
from server_control_routes import ServerControlRoutes

# =============================================================================
# FLASK CONFIGURATION
# =============================================================================

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['ETAG_DISABLED'] = True

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

server_start_time = time.time()
CURRENT_NETWORK_MODE = Config.load_network_mode()
print(f"[NETWORK] Текущий режим сети: {CURRENT_NETWORK_MODE}")

# Глобальные объекты
account_manager = AccountManager()
trading_engines = {}
state_manager = get_state_manager()

# Параметры торговли по умолчанию
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

# Глобальные переменные для торговли
TRADING_MODE = state_manager.get_trading_mode()
TRADING_PERMISSIONS = state_manager.get_trading_permissions()
TRADE_PARAMS = state_manager.get("legacy_trade_params", DEFAULT_TRADE_PARAMS.copy())

# =============================================================================
# MIDDLEWARE & ERROR HANDLERS
# =============================================================================

@app.after_request
def add_header(response):
    """Добавить заголовки для отключения кеша"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    try:
        template_path = os.path.join(app.root_path, 'templates', 'index.html')
        if os.path.exists(template_path):
            response.headers['X-Template-MTime'] = str(os.path.getmtime(template_path))
    except Exception:
        pass
    return response

@app.errorhandler(Exception)
def handle_error(error):
    """Обработка всех необработанных исключений"""
    from flask import request
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
    raise error

# =============================================================================
# MAIN ROUTES
# =============================================================================

@app.route('/')
def index():
    """Главная страница"""
    print('[ROUTE] GET / index served')
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
    """Альтернативная главная страница"""
    print('[ROUTE] GET /v2 index served')
    response = app.make_response(render_template('index.html', cache_buster=int(time.time())))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/version')
def version():
    """Версия и аптайм сервера"""
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
    return ('', 204)

@app.route('/test')
def test_orderbook():
    """Тестовая страница для проверки стакана"""
    return render_template('test_orderbook.html')

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_current_network_mode():
    """Получить текущий режим сети"""
    return CURRENT_NETWORK_MODE

def set_current_network_mode(mode):
    """Установить текущий режим сети"""
    global CURRENT_NETWORK_MODE
    CURRENT_NETWORK_MODE = mode

# =============================================================================
# INITIALIZE ROUTE MODULES
# =============================================================================

# API Routes (accounts, mode, currencies, balance, orders, trade)
api_routes = APIRoutes(
    app,
    account_manager,
    trading_engines,
    get_current_network_mode
)

# WebSocket Routes (pair subscription, data, multi-pairs watcher)
websocket_routes = WebSocketRoutes(
    app,
    account_manager,
    get_current_network_mode
)

# Trade Parameters Routes (params, break-even table, permissions)
trade_params_routes = TradeParamsRoutes(
    app,
    TRADE_PARAMS
)

# Server Control Routes (server, network mode, autotrader, indicators, UI state)
server_control_routes = ServerControlRoutes(
    app,
    account_manager,
    get_current_network_mode,
    server_start_time,
    trading_engines
)

# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize_app():
    """Инициализация приложения"""
    global TRADING_PERMISSIONS
    
    # Синхронизация network_mode из сохраненного состояния
    try:
        saved_nm = state_manager.get_network_mode()
        if saved_nm in ('work', 'test') and saved_nm != CURRENT_NETWORK_MODE:
            print(f"[STATE] Восстанавливаем сохраненный network_mode: {saved_nm}")
            Config.save_network_mode(saved_nm)
            set_current_network_mode(saved_nm)
    except Exception as e:
        print(f"[STATE] Ошибка восстановления network_mode: {e}")
    
    # Инициализация разрешений для валют
    try:
        currencies = Config.load_currencies()
        state_manager.init_currency_permissions(currencies)
        
        # Инициализация дефолтных параметров безубыточности
        try:
            all_params = state_manager.get("breakeven_params", {}) or {}
            changed = False
            for c in currencies:
                code = (c or {}).get('code', '').upper()
                if code and code not in all_params:
                    all_params[code] = DEFAULT_TRADE_PARAMS.copy()
                    changed = True
            if changed:
                state_manager.set("breakeven_params", all_params)
        except Exception as e:
            print(f"[STATE] Ошибка инициализации breakeven по валютам: {e}")
    except Exception as e:
        print(f"[STATE] Ошибка инициализации разрешений: {e}")
    
    # Обновляем TRADING_PERMISSIONS если пустые
    if not TRADING_PERMISSIONS:
        try:
            TRADING_PERMISSIONS = {
                (c or {}).get('code', '').upper(): True 
                for c in Config.load_currencies() 
                if (c or {}).get('code')
            }
            state_manager.set("trading_permissions", TRADING_PERMISSIONS)
        except Exception:
            TRADING_PERMISSIONS = {}

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Gate.io Multi-Trading Platform - mTrade v2.0")
    print("=" * 60)
    print(f"[INFO] Режим сети: {CURRENT_NETWORK_MODE}")
    print(f"[INFO] PID: {os.getpid()}")
    print("=" * 60)
    
    # Записываем PID
    ProcessManager.write_pid()
    ProcessManager.setup_cleanup()
    
    # Инициализация приложения
    initialize_app()
    
    # Инициализация WebSocket менеджера
    print("[INIT] Инициализация WebSocket менеджера...")
    api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
    if api_key and api_secret:
        init_websocket_manager(api_key, api_secret, CURRENT_NETWORK_MODE)
        print("[INIT] WebSocket менеджер инициализирован")
    else:
        print("[WARNING] API ключи не найдены, WebSocket работает в ограниченном режиме")
    
    # Инициализация автотрейдера при старте
    server_control_routes.initialize_autotrader()
    
    # Синхронизация режимов движков
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
