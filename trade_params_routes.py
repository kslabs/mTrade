"""
Trade Parameters & Break-Even Routes Module
Содержит эндпоинты для работы с торговыми параметрами и таблицей безубыточности
"""

from flask import request, jsonify
import traceback

from state_manager import get_state_manager
from gateio_websocket import get_websocket_manager


class TradeParamsRoutes:
    """Класс для управления маршрутами торговых параметров"""
    
    def __init__(self, app, trade_params_dict):
        """
        Инициализация Trade Params Routes
        
        Args:
            app: Flask приложение
            trade_params_dict: Словарь с глобальными торговыми параметрами
        """
        self.app = app
        self.trade_params = trade_params_dict
        self.state_manager = get_state_manager()
        
        # Регистрация всех маршрутов
        self._register_routes()
    
    def _register_routes(self):
        """Регистрация всех маршрутов"""
        # Trade parameters
        self.app.add_url_rule('/api/trade/params', 'get_trade_params', self.get_trade_params, methods=['GET'])
        self.app.add_url_rule('/api/trade/params', 'save_trade_params', self.save_trade_params, methods=['POST'])
        self.app.add_url_rule('/api/trade/params/legacy', 'get_trade_params_legacy', self.get_trade_params_legacy, methods=['GET'])
        self.app.add_url_rule('/api/trade/params/legacy', 'save_trade_params_legacy', self.save_trade_params_legacy, methods=['POST'])
        
        # Break-even table
        self.app.add_url_rule('/api/breakeven/table', 'get_breakeven_table', self.get_breakeven_table, methods=['GET'])
        
        # Trading permissions
        self.app.add_url_rule('/api/trade/permissions', 'get_trading_permissions', self.get_trading_permissions, methods=['GET'])
        self.app.add_url_rule('/api/trade/permission', 'set_trading_permission', self.set_trading_permission, methods=['POST'])
    
    # =============================================================================
    # TRADE PARAMETERS
    # =============================================================================
    
    def get_trade_params(self):
        """Получить параметры торговли для конкретной валюты (per-currency)"""
        try:
            base_currency = (request.args.get('base_currency') or request.args.get('currency') or 'BTC').upper()
            params = self.state_manager.get_breakeven_params(base_currency)
            return jsonify({"success": True, "params": params, "currency": base_currency})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def save_trade_params(self):
        """Сохранить параметры торговли для конкретной валюты (per-currency)"""
        try:
            data = request.get_json(silent=True) or {}
            base_currency = (data.get('base_currency') or data.get('currency') or 'BTC').upper()
            params = self.state_manager.get_breakeven_params(base_currency)
            
            for k, caster in (
                ('steps', int), ('start_volume', float), ('start_price', float),
                ('pprof', float), ('kprof', float), ('target_r', float),
                ('geom_multiplier', float), ('rebuy_mode', str)
            ):
                if k in data and data[k] is not None:
                    try:
                        params[k] = caster(data[k])
                    except Exception:
                        pass
            
            self.state_manager.set_breakeven_params(base_currency, params)
            print(f"[PARAMS] {base_currency} -> {params}")
            return jsonify({"success": True, "message": f"Параметры для {base_currency} сохранены", "params": params, "currency": base_currency})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def get_trade_params_legacy(self):
        """Получить глобальные (legacy) параметры торговли для совместимости со старым UI"""
        try:
            return jsonify({"success": True, "params": self.trade_params, "legacy": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def save_trade_params_legacy(self):
        """Сохранить глобальные (legacy) параметры торговли (не влияет на per-currency)"""
        try:
            data = request.get_json(silent=True) or {}
            updated = self.trade_params.copy()
            
            for k, caster in (
                ('steps', int), ('start_volume', float), ('start_price', float),
                ('pprof', float), ('kprof', float), ('target_r', float),
                ('geom_multiplier', float), ('rebuy_mode', str)
            ):
                if k in data and data[k] is not None:
                    try:
                        updated[k] = caster(data[k])
                    except Exception:
                        pass
            
            self.trade_params.clear()
            self.trade_params.update(updated)
            self.state_manager.set("legacy_trade_params", self.trade_params)
            print(f"[PARAMS][LEGACY] -> {self.trade_params}")
            return jsonify({"success": True, "params": self.trade_params, "legacy": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =============================================================================
    # BREAK-EVEN TABLE
    # =============================================================================
    
    def get_breakeven_table(self):
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
                params = self.trade_params.copy()
                base_for_price = 'BTC'  # legacy UI чаще по BTC
            else:
                params = self.state_manager.get_breakeven_params(base_currency).copy()
                base_for_price = base_currency
            
            # 🔍 ОТЛАДКА: Выводим входящие параметры
            print(f"[BREAKEVEN_TABLE] 🔍 Входящие query params: {dict(request.args)}")
            print(f"[BREAKEVEN_TABLE] 📋 Загруженные params: {params}")
            print(f"[BREAKEVEN_TABLE] 💱 Currency: {base_currency if not use_legacy else 'LEGACY'}")
            
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
            if 'geom_multiplier' in request.args:
                try:
                    new_geom = float(request.args.get('geom_multiplier'))
                    params['geom_multiplier'] = new_geom
                    print(f"[BREAKEVEN_TABLE] ✅ geom_multiplier переопределён: {new_geom}")
                except (ValueError, TypeError):
                    print(f"[BREAKEVEN_TABLE] ❌ Ошибка парсинга geom_multiplier")
                    pass
            if 'rebuy_mode' in request.args:
                rebuy_mode = str(request.args.get('rebuy_mode')).lower()
                if rebuy_mode in ('fixed', 'geometric', 'martingale'):
                    params['rebuy_mode'] = rebuy_mode
            
            # 🔍 ОТЛАДКА: Финальные параметры перед расчётом
            print(f"[BREAKEVEN_TABLE] 🎯 Финальные params перед расчётом: {params}")
            
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
            print(f"[ERROR] Breakeven table calculation: {e}")
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =============================================================================
    # TRADING PERMISSIONS
    # =============================================================================
    
    def get_trading_permissions(self):
        """Получить разрешения торговли для всех валют"""
        try:
            permissions = self.state_manager.get_trading_permissions()
            return jsonify({
                "success": True,
                "permissions": permissions
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def set_trading_permission(self):
        """Установить разрешение торговли для конкретной валюты"""
        try:
            data = request.get_json(silent=True) or {}
            base_currency = data.get('base_currency', '').upper()
            enabled = data.get('enabled', True)
            
            if not base_currency:
                return jsonify({
                    "success": False,
                    "error": "Не указана валюта (base_currency)"
                }), 400
            
            # Сохраняем в State Manager
            self.state_manager.set_trading_permission(base_currency, enabled)
            
            print(f"[TRADING] Разрешение торговли для {base_currency}: {enabled}")
            
            return jsonify({
                "success": True,
                "base_currency": base_currency,
                "enabled": enabled,
                "message": f"Торговля {base_currency}: {'разрешена' if enabled else 'запрещена'}"
            })
        except Exception as e:
            print(f"[ERROR] Set trading permission: {e}")
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
