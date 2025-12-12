"""
Autotrader & Server Control Routes Module
Содержит эндпоинты для управления автотрейдером и сервером
"""

import os
import sys
import time
from flask import request, jsonify
from threading import Thread
import traceback

from config import Config
from process_manager import ProcessManager
from state_manager import get_state_manager
from gateio_websocket import get_websocket_manager
from gate_api_client import GateAPIClient
from autotrader import AutoTrader


class ServerControlRoutes:
    """Класс для управления серверными и автотрейдер маршрутами"""
    
    def __init__(self, app, account_manager, current_network_mode_getter, server_start_time, trading_engines):
        """
        Инициализация Server Control Routes
        
        Args:
            app: Flask приложение
            account_manager: Менеджер аккаунтов
            current_network_mode_getter: Функция для получения текущего режима сети
            server_start_time: Время старта сервера
            trading_engines: Словарь торговых движков
        """
        self.app = app
        self.account_manager = account_manager
        self.get_current_network_mode = current_network_mode_getter
        self.server_start_time = server_start_time
        self.trading_engines = trading_engines
        self.state_manager = get_state_manager()
        self.auto_trader = None
        
        # Регистрация всех маршрутов
        self._register_routes()
    
    def _register_routes(self):
        """Регистрация всех маршрутов"""
        # Server control
        self.app.add_url_rule('/api/server/status', 'server_status', self.server_status, methods=['GET'])
        self.app.add_url_rule('/api/server/restart', 'server_restart', self.server_restart, methods=['POST'])
        self.app.add_url_rule('/api/server/shutdown', 'server_shutdown', self.server_shutdown, methods=['POST'])
        
        # Network mode
        self.app.add_url_rule('/api/network', 'get_network_mode', self.get_network_mode, methods=['GET'])
        self.app.add_url_rule('/api/network/mode', 'get_network_mode_alt', self.get_network_mode, methods=['GET'])
        self.app.add_url_rule('/api/network', 'set_network_mode', self.set_network_mode, methods=['POST'])
        self.app.add_url_rule('/api/network/mode', 'set_network_mode_alt', self.set_network_mode, methods=['POST'])
        
        # Autotrader
        self.app.add_url_rule('/api/autotrade/start', 'start_autotrade', self.start_autotrade, methods=['POST'])
        self.app.add_url_rule('/api/autotrade/stop', 'stop_autotrade', self.stop_autotrade, methods=['POST'])
        self.app.add_url_rule('/api/autotrade/status', 'get_autotrade_status', self.get_autotrade_status, methods=['GET'])
        self.app.add_url_rule('/api/autotrader/stats', 'get_autotrader_stats', self.get_autotrader_stats, methods=['GET'])
        
        # Trade indicators
        self.app.add_url_rule('/api/trade/indicators', 'get_trade_indicators', self.get_trade_indicators, methods=['GET'])
        
        # UI state
        self.app.add_url_rule('/api/ui/state', 'get_ui_state', self.get_ui_state, methods=['GET'])
        self.app.add_url_rule('/api/ui/state', 'save_ui_state', self.save_ui_state, methods=['POST'])
        self.app.add_url_rule('/api/ui/state/partial', 'save_ui_state_partial', self.save_ui_state_partial, methods=['POST'])
    
    # =============================================================================
    # SERVER CONTROL
    # =============================================================================
    
    def server_status(self):
        """Получить статус сервера"""
        pid = ProcessManager.read_pid()
        return jsonify({
            "running": True,
            "pid": pid,
            "uptime": time.time() - self.server_start_time
        })
    
    def server_restart(self):
        """Перезапустить сервер"""
        def restart():
            time.sleep(1)
            print("\n[RESTART] Перезапуск сервера...")
            
            python = sys.executable
            script = None
            try:
                script = os.path.abspath(__file__)
            except Exception:
                try:
                    script = os.path.abspath(sys.argv[0])
                except Exception:
                    script = None
            
            app_dir = os.path.abspath(os.path.dirname(script)) if script else os.path.abspath('.')
            
            try:
                ProcessManager.remove_pid()
                import subprocess
                
                if os.name == 'nt':
                    bat_file = os.path.join(app_dir, 'START.bat')
                    restart_py = os.path.join(app_dir, 'restart.py')
                    
                    if os.path.exists(bat_file):
                        try:
                            subprocess.Popen(
                                f'start "mTrade Server" cmd /c "{bat_file}"',
                                shell=True,
                                cwd=app_dir
                            )
                            print(f"[RESTART] Запущен батник: {bat_file}")
                        except Exception as e:
                            print(f"[RESTART] Ошибка при запуске батника: {e}")
                    
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
                    
                    elif script and os.path.exists(script):
                        try:
                            subprocess.Popen(
                                f'start "mTrade Server" cmd /c "{python}" "{script}"',
                                shell=True,
                                cwd=app_dir
                            )
                            print(f"[RESTART] Запущен новый процесс: {script}")
                        except Exception as e:
                            print(f"[RESTART] Ошибка при запуске: {e}")
                    else:
                        print('[RESTART] Не найдены файлы для перезапуска')
                else:
                    if script and os.path.exists(script):
                        try:
                            subprocess.Popen([python, script])
                            print(f"[RESTART] Новый процесс запущен: {python} {script}")
                        except Exception as e:
                            print(f"[RESTART] Ошибка при запуске нового процесса: {e}")
                    else:
                        print('[RESTART] Не найден скрипт для перезапуска')
            except Exception as e:
                print(f"[RESTART] Не удалось перезапустить: {e}")
            
            try:
                os._exit(0)
            except SystemExit:
                pass
            except Exception:
                os._exit(0)
        
        Thread(target=restart, daemon=True).start()
        return jsonify({"success": True, "message": "Сервер перезапускается..."})
    
    def server_shutdown(self):
        """Остановить сервер"""
        def shutdown():
            time.sleep(1)
            print("\n[SHUTDOWN] Остановка сервера...")
            ws_manager = get_websocket_manager()
            if ws_manager:
                ws_manager.close_all()
            ProcessManager.remove_pid()
            os._exit(0)
        
        Thread(target=shutdown, daemon=True).start()
        return jsonify({"success": True, "message": "Сервер останавливается..."})
    
    # =============================================================================
    # NETWORK MODE
    # =============================================================================
    
    def get_network_mode(self):
        """Получить текущий режим сети"""
        current_mode = self.get_current_network_mode()
        return jsonify({
            "success": True,
            "mode": current_mode,
            "modes": {
                "work": "Рабочая сеть (Real trading)",
                "test": "Тестовая сеть (Paper trading)"
            }
        })
    
    def set_network_mode(self):
        """Переключить режим сети"""
        try:
            from gateio_websocket import init_websocket_manager
            
            data = request.json
            new_mode = data.get('mode', '').lower()
            if new_mode not in ('work', 'test'):
                return jsonify({"success": False, "error": "Неверный режим. Доступны: 'work' или 'test'"}), 400
            
            # Используем функцию переключения режима сети
            if self._reinit_network_mode(new_mode):
                try:
                    self.state_manager.set_network_mode(new_mode)
                except Exception as e:
                    print(f"[STATE] Не удалось сохранить network_mode: {e}")
                return jsonify({"success": True, "mode": new_mode, "message": f"Режим сети изменен на '{new_mode}'"})
            else:
                return jsonify({"success": False, "error": "Не удалось переключить режим сети"}), 500
        except Exception as e:
            print(f"[ERROR] Ошибка переключения режима сети: {e}")
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _reinit_network_mode(self, new_mode: str) -> bool:
        """Переключение режима сети с переинициализацией WebSocket менеджера"""
        from gateio_websocket import init_websocket_manager
        
        new_mode = str(new_mode).lower()
        if new_mode not in ('work', 'test'):
            return False
        
        current_mode = self.get_current_network_mode()
        if new_mode == current_mode:
            return True
        
        try:
            print(f"[NETWORK] Переключение режима: {current_mode} -> {new_mode}")
            Config.save_network_mode(new_mode)
            
            ws_manager = get_websocket_manager()
            if ws_manager:
                try:
                    ws_manager.close_all()
                except Exception as e:
                    print(f"[NETWORK] Ошибка закрытия WS: {e}")
            
            try:
                ak, sk = Config.load_secrets_by_mode(new_mode)
                init_websocket_manager(ak, sk, new_mode)
                print(f"[NETWORK] WS менеджер переинициализирован (mode={new_mode})")
            except Exception as e:
                print(f"[NETWORK] Ошибка инициализации WS менеджера: {e}")
            
            return True
        except Exception as e:
            print(f"[NETWORK] Ошибка переключения режима: {e}")
            return False
    
    # =============================================================================
    # AUTOTRADER
    # =============================================================================
    
    def start_autotrade(self):
        """Включить автоторговлю"""
        try:
            self.state_manager.set_auto_trade_enabled(True)
            
            # Ленивая инициализация автотрейдера
            if self.auto_trader is None:
                def _api_client_provider():
                    if not self.account_manager.active_account:
                        return None
                    acc = self.account_manager.get_account(self.account_manager.active_account)
                    if not acc:
                        return None
                    current_network_mode = self.get_current_network_mode()
                    return GateAPIClient(acc['api_key'], acc['api_secret'], current_network_mode)
                
                ws_manager = get_websocket_manager()
                self.auto_trader = AutoTrader(_api_client_provider, ws_manager, self.state_manager)
            
            if not self.auto_trader.running:
                self.auto_trader.start()
            
            print(f"[AUTOTRADE] Автоторговля включена")
            return jsonify({
                "success": True,
                "enabled": True,
                "running": self.auto_trader.running if self.auto_trader else False,
                "message": "Автоторговля включена"
            })
        except Exception as e:
            print(f"[ERROR] Start autotrade: {e}\n{traceback.format_exc()}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def stop_autotrade(self):
        """Выключить автоторговлю"""
        try:
            self.state_manager.set_auto_trade_enabled(False)
            if self.auto_trader and self.auto_trader.running:
                self.auto_trader.stop()
            
            print(f"[AUTOTRADE] Автоторговля выключена")
            return jsonify({
                "success": True,
                "enabled": False,
                "running": self.auto_trader.running if self.auto_trader else False,
                "message": "Автоторговля выключена"
            })
        except Exception as e:
            print(f"[ERROR] Stop autotrade: {e}\n{traceback.format_exc()}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def get_autotrade_status(self):
        """Получить статус автоторговли + статистику"""
        try:
            enabled = self.state_manager.get_auto_trade_enabled()
            stats = {}
            if self.auto_trader and self.auto_trader.running:
                stats = self.auto_trader.stats
            
            return jsonify({
                "success": True,
                "enabled": enabled,
                "running": self.auto_trader.running if self.auto_trader else False,
                "stats": stats
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def get_autotrader_stats(self):
        """Получить статистику автотрейдера для конкретной валюты"""
        try:
            base_currency = request.args.get('base_currency', '').upper()
            if not base_currency:
                return jsonify({"success": False, "error": "Не указана валюта"}), 400
            
            enabled = self.state_manager.get_auto_trade_enabled()
            stats = {
                "base_currency": base_currency,
                "enabled": enabled,
                "running": self.auto_trader.running if self.auto_trader else False,
                "trades_count": 0,
                "profit": 0.0,
                "last_trade_time": None
            }
            
            if self.auto_trader and self.auto_trader.running and hasattr(self.auto_trader, 'stats'):
                all_stats = self.auto_trader.stats
                if base_currency in all_stats:
                    stats.update(all_stats[base_currency])
            
            return jsonify({"success": True, "stats": stats})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =============================================================================
    # TRADE INDICATORS
    # =============================================================================
    
    def get_trade_indicators(self):
        """Получить торговые индикаторы для конкретной пары"""
        try:
            base_currency = request.args.get('base_currency', 'BTC').upper()
            quote_currency = request.args.get('quote_currency', 'USDT').upper()
            currency_pair = f"{base_currency}_{quote_currency}"
            
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
    
    # =============================================================================
    # UI STATE
    # =============================================================================
    
    def get_ui_state(self):
        """Получить состояние UI"""
        try:
            return jsonify({
                "success": True,
                "state": {
                    "auto_trade_enabled": self.state_manager.get_auto_trade_enabled(),
                    "enabled_currencies": self.state_manager.get_trading_permissions(),
                    "network_mode": self.state_manager.get_network_mode(),
                    "trading_mode": self.state_manager.get_trading_mode(),
                    "active_base_currency": self.state_manager.get_active_base_currency(),
                    "active_quote_currency": self.state_manager.get_active_quote_currency(),
                    "breakeven_params": self.state_manager.get_breakeven_params()
                }
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def save_ui_state(self):
        """Сохранить состояние UI"""
        try:
            data = request.get_json(silent=True) or {}
            state = data.get('state', {})
            
            if 'auto_trade_enabled' in state:
                self.state_manager.set_auto_trade_enabled(bool(state['auto_trade_enabled']))
            
            if 'enabled_currencies' in state and isinstance(state['enabled_currencies'], dict):
                for currency, enabled in state['enabled_currencies'].items():
                    self.state_manager.set_trading_permission(currency, enabled)
            
            if 'trading_mode' in state:
                mode = str(state['trading_mode']).lower()
                if mode in ('trade', 'copy'):
                    self.state_manager.set_trading_mode(mode)
            
            if 'network_mode' in state:
                nm = str(state['network_mode']).lower()
                current_mode = self.get_current_network_mode()
                if nm in ('work', 'test') and nm != current_mode:
                    if self._reinit_network_mode(nm):
                        self.state_manager.set_network_mode(nm)
            
            if 'breakeven_params' in state and isinstance(state['breakeven_params'], dict):
                for currency, params in state['breakeven_params'].items():
                    try:
                        cur = currency.upper()
                        existing = self.state_manager.get_breakeven_params(cur)
                        for k in ('steps', 'start_volume', 'start_price', 'pprof', 'kprof', 'target_r', 'geom_multiplier', 'rebuy_mode'):
                            if k in params:
                                existing[k] = params[k]
                        self.state_manager.set_breakeven_params(cur, existing)
                    except Exception as e:
                        print(f"[STATE] Ошибка сохранения breakeven для {currency}: {e}")
            
            return jsonify({"success": True, "message": "Состояние UI сохранено"})
        except Exception as e:
            print(f"[ERROR] Save UI state: {e}")
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    def save_ui_state_partial(self):
        """Частичное сохранение состояния UI (только указанные поля)"""
        try:
            data = request.get_json(silent=True) or {}
            
            updated_fields = []
            
            # Активная базовая валюта
            if 'active_base_currency' in data:
                currency = str(data['active_base_currency']).upper()
                self.state_manager.set_active_base_currency(currency)
                updated_fields.append(f'active_base_currency={currency}')
            
            # Активная котировочная валюта
            if 'active_quote_currency' in data:
                currency = str(data['active_quote_currency']).upper()
                self.state_manager.set_active_quote_currency(currency)
                updated_fields.append(f'active_quote_currency={currency}')
            
            # AutoTrade включен/выключен
            if 'auto_trade_enabled' in data:
                enabled = bool(data['auto_trade_enabled'])
                self.state_manager.set_auto_trade_enabled(enabled)
                updated_fields.append(f'auto_trade_enabled={enabled}')
            
            # Режим сети
            if 'network_mode' in data:
                mode = str(data['network_mode']).lower()
                if mode in ('work', 'test'):
                    self.state_manager.set_network_mode(mode)
                    updated_fields.append(f'network_mode={mode}')
            
            # Режим торговли
            if 'trading_mode' in data:
                mode = str(data['trading_mode']).lower()
                if mode in ('trade', 'copy', 'normal'):
                    # Нормализуем 'normal' -> 'trade'
                    normalized_mode = 'trade' if mode == 'normal' else mode
                    self.state_manager.set_trading_mode(normalized_mode)
                    updated_fields.append(f'trading_mode={normalized_mode}')
            
            # Параметры безубыточности
            if 'breakeven_params' in data:
                params = data['breakeven_params']
                if isinstance(params, dict) and 'currency' in params:
                    currency = str(params['currency']).upper()
                    self.state_manager.set_breakeven_params(currency, params)
                    updated_fields.append(f'breakeven_params[{currency}]')
            
            print(f"[UI STATE] Частичное сохранение: {', '.join(updated_fields) if updated_fields else 'нет изменений'}")
            
            return jsonify({
                "success": True,
                "message": "Состояние частично сохранено",
                "updated": updated_fields
            })
            
        except Exception as e:
            print(f"[ERROR] Save UI state partial: {e}")
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def initialize_autotrader(self):
        """Инициализация автотрейдера при старте сервера"""
        try:
            if self.state_manager.get_auto_trade_enabled():
                def _api_client_provider():
                    if not self.account_manager.active_account:
                        return None
                    acc = self.account_manager.get_account(self.account_manager.active_account)
                    if not acc:
                        return None
                    current_network_mode = self.get_current_network_mode()
                    return GateAPIClient(acc['api_key'], acc['api_secret'], current_network_mode)
                
                ws_manager = get_websocket_manager()
                self.auto_trader = AutoTrader(_api_client_provider, ws_manager, self.state_manager)
                self.auto_trader.start()
                print('[INIT] Автотрейдер запущен (восстановлено из состояния)')
        except Exception as e:
            print(f"[INIT] Не удалось запустить автотрейдер: {e}")
