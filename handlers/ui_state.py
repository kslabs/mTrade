from flask import jsonify, request


def get_ui_state_impl():
    try:
        import mTrade as app_main
        return jsonify({
            "success": True,
            "state": {
                "auto_trade_enabled": app_main.state_manager.get_auto_trade_enabled(),
                "enabled_currencies": app_main.state_manager.get_trading_permissions(),
                "network_mode": app_main.state_manager.get_network_mode(),
                "trading_mode": app_main.state_manager.get_trading_mode(),
                "breakeven_params": app_main.state_manager.get_breakeven_params()
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def save_ui_state_impl():
    try:
        import mTrade as app_main
        global_vars = app_main
        data = request.get_json(silent=True) or {}
        state = data.get('state', {})

        # Автоторговля
        if 'auto_trade_enabled' in state:
            global_vars.AUTO_TRADE_GLOBAL_ENABLED = bool(state['auto_trade_enabled'])
            try:
                global_vars.state_manager.set_auto_trade_enabled(global_vars.AUTO_TRADE_GLOBAL_ENABLED)
            except Exception:
                pass
        # Разрешения торговли
        if 'enabled_currencies' in state and isinstance(state['enabled_currencies'], dict):
            global_vars.TRADING_PERMISSIONS.update(state['enabled_currencies'])
            for currency, enabled in state['enabled_currencies'].items():
                try:
                    global_vars.state_manager.set_trading_permission(currency, enabled)
                except Exception:
                    pass
        # Режим торговли
        if 'trading_mode' in state:
            mode = str(state['trading_mode']).lower()
            if mode in ('trade', 'copy'):
                global_vars.TRADING_MODE = mode
                try:
                    global_vars.state_manager.set_trading_mode(global_vars.TRADING_MODE)
                except Exception:
                    pass
        # Режим сети
        if 'network_mode' in state:
            nm = str(state['network_mode']).lower()
            if nm in ('work', 'test') and nm != global_vars.CURRENT_NETWORK_MODE:
                try:
                    if global_vars._reinit_network_mode(nm):
                        global_vars.CURRENT_NETWORK_MODE = nm
                        global_vars.state_manager.set_network_mode(nm)
                except Exception:
                    pass
        # Параметры безубыточности (пакетное обновление)
        if 'breakeven_params' in state and isinstance(state['breakeven_params'], dict):
            for currency, params in state['breakeven_params'].items():
                try:
                    cur = currency.upper()
                    existing = global_vars.state_manager.get_breakeven_params(cur)
                    for k in ('steps','start_volume','start_price','pprof','kprof','target_r','geom_multiplier','rebuy_mode','orderbook_level'):
                        if k in params:
                            existing[k] = params[k]
                    global_vars.state_manager.set_breakeven_params(cur, existing)
                except Exception:
                    pass

        # Сохраняем через Config
        try:
            full_state = {
                "enabled_currencies": global_vars.state_manager.get_trading_permissions(),
                "auto_trade_enabled": global_vars.state_manager.get_auto_trade_enabled(),
                "network_mode": global_vars.CURRENT_NETWORK_MODE,
                "active_base_currency": "BTC",
                "active_quote_currency": "USDT",
                "theme": "dark",
                "show_indicators": True,
                "show_orderbook": True,
                "show_trades": True,
                "orderbook_depth": 20,
                "last_updated": None
            }
            try:
                app_main.Config.save_ui_state(full_state)
            except Exception:
                pass
        except Exception:
            pass

        return jsonify({"success": True, "message": "Состояние UI сохранено"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def save_ui_state_partial_impl():
    try:
        import mTrade as app_main
        payload = request.get_json(silent=True) or {}

        try:
            full_state = app_main.Config.load_ui_state()
        except Exception:
            full_state = {
                "enabled_currencies": {},
                "auto_trade_enabled": False,
                "network_mode": app_main.CURRENT_NETWORK_MODE,
                "active_base_currency": "BTC",
                "active_quote_currency": "USDT",
                "theme": "dark",
                "show_indicators": True,
                "show_orderbook": True,
                "show_trades": True,
                "orderbook_depth": 20,
                "last_updated": None
            }

        if 'active_base_currency' in payload:
            base = str(payload['active_base_currency']).upper()
            if base:
                full_state['active_base_currency'] = base
        if 'active_quote_currency' in payload:
            quote = str(payload['active_quote_currency']).upper()
            if quote:
                full_state['active_quote_currency'] = quote
        if 'auto_trade_enabled' in payload:
            app_main.AUTO_TRADE_GLOBAL_ENABLED = bool(payload['auto_trade_enabled'])
            full_state['auto_trade_enabled'] = app_main.AUTO_TRADE_GLOBAL_ENABLED
            try:
                app_main.state_manager.set_auto_trade_enabled(app_main.AUTO_TRADE_GLOBAL_ENABLED)
            except Exception:
                pass
        if 'network_mode' in payload:
            nm = str(payload['network_mode']).lower()
            if nm in ('work', 'test') and nm != app_main.CURRENT_NETWORK_MODE:
                try:
                    if app_main._reinit_network_mode(nm):
                        app_main.CURRENT_NETWORK_MODE = nm
                        full_state['network_mode'] = nm
                        try:
                            app_main.state_manager.set_network_mode(nm)
                        except Exception:
                            pass
                except Exception:
                    pass
        if 'trading_mode' in payload:
            mode = str(payload['trading_mode']).lower()
            if mode in ('trade', 'copy'):
                app_main.TRADING_MODE = mode
                try:
                    app_main.state_manager.set_trading_mode(mode)
                except Exception:
                    pass

        if 'breakeven_params' in payload and isinstance(payload['breakeven_params'], dict):
            be_updates = payload['breakeven_params']
            existing_all = app_main.state_manager.get("breakeven_params", {}) or {}
            for currency, params in be_updates.items():
                try:
                    cur = str(currency).upper()
                    existing = existing_all.get(cur) or app_main.state_manager.get_breakeven_params(cur)
                    if not isinstance(existing, dict):
                        existing = {}
                    for k in ('steps','start_volume','start_price','pprof','kprof','target_r','geom_multiplier','rebuy_mode','orderbook_level'):
                        if k in params:
                            existing[k] = params[k]
                    existing_all[cur] = existing
                    try:
                        app_main.state_manager.set_breakeven_params(cur, existing)
                    except Exception:
                        pass
                except Exception:
                    pass
            full_state['breakeven_params'] = existing_all

        try:
            app_main.Config.save_ui_state(full_state)
        except Exception:
            pass

        return jsonify({"success": True, "state": full_state})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
