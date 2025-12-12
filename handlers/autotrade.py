from flask import jsonify, request
import os
import time
import threading


def start_autotrade_impl():
    try:
        # Импортируем mTrade внутри функции чтобы избежать циклического импорта при загрузке модуля
        import mTrade as app_main
        # Устанавливаем флаг
        app_main.AUTO_TRADE_GLOBAL_ENABLED = True
        try:
            app_main.state_manager.set_auto_trade_enabled(True)
        except Exception:
            pass

        # Ленивая инициализация автотрейдера
        if app_main.AUTO_TRADER is None:
            def _api_client_provider():
                if not app_main.account_manager.active_account:
                    return None
                acc = app_main.account_manager.get_account(app_main.account_manager.active_account)
                if not acc:
                    return None
                from gate_api_client import GateAPIClient
                return GateAPIClient(acc['api_key'], acc['api_secret'], app_main.CURRENT_NETWORK_MODE)

            from handlers.websocket import get_ws_manager
            ws_manager = get_ws_manager()
            app_main.AUTO_TRADER = app_main.AutoTrader(_api_client_provider, ws_manager, app_main.state_manager)

            # Если файл состояния циклов не привязан к модулю — закрепляем его рядом с handlers
            try:
                module_dir = os.path.dirname(os.path.abspath(__file__))
                cycles_file = os.path.join(module_dir, '..', 'autotrader_cycles_state.json')
                cycles_file = os.path.abspath(cycles_file)
                app_main.AUTO_TRADER._cycles_state_file = cycles_file

                # Запускаем фоновый автосейв только если он ещё не запущен
                if not hasattr(app_main.AUTO_TRADER, '_cycles_autosave_thread'):
                    def _cycles_autosave_loop():
                        while True:
                            try:
                                app_main.AUTO_TRADER._save_cycles_state()
                            except Exception:
                                pass
                            time.sleep(30)

                    t = threading.Thread(target=_cycles_autosave_loop, daemon=True)
                    app_main.AUTO_TRADER._cycles_autosave_thread = t
                    t.start()
            except Exception:
                pass

        if not app_main.AUTO_TRADER.running:
            app_main.AUTO_TRADER.start()

        return jsonify({
            "success": True,
            "enabled": True,
            "running": app_main.AUTO_TRADER.running if app_main.AUTO_TRADER else False,
            "message": "Автоторговля включена"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def stop_autotrade_impl():
    try:
        import mTrade as app_main
        app_main.AUTO_TRADE_GLOBAL_ENABLED = False
        try:
            app_main.state_manager.set_auto_trade_enabled(False)
        except Exception:
            pass
        if app_main.AUTO_TRADER and app_main.AUTO_TRADER.running:
            try:
                app_main.AUTO_TRADER.stop()
            except Exception:
                pass
        return jsonify({
            "success": True,
            "enabled": False,
            "running": app_main.AUTO_TRADER.running if app_main.AUTO_TRADER else False,
            "message": "Автотрейдер выключен"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def get_autotrade_status_impl():
    try:
        import mTrade as app_main
        enabled = app_main.state_manager.get_auto_trade_enabled()
        stats = {}
        if app_main.AUTO_TRADER and app_main.AUTO_TRADER.running:
            stats = getattr(app_main.AUTO_TRADER, 'stats', {})
        return jsonify({
            "success": True,
            "enabled": enabled,
            "running": app_main.AUTO_TRADER.running if app_main.AUTO_TRADER else False,
            "stats": stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def get_autotrader_stats_impl():
    try:
        import mTrade as app_main
        base_currency = request.args.get('base_currency', '').upper()
        if not base_currency:
            return jsonify({"success": False, "error": "Не указана валюта"}), 400

        stats = {
            "base_currency": base_currency,
            "enabled": app_main.AUTO_TRADE_GLOBAL_ENABLED,
            "running": app_main.AUTO_TRADER.running if app_main.AUTO_TRADER else False,
            "trades_count": 0,
            "profit": 0.0,
            "last_trade_time": None
        }

        if app_main.AUTO_TRADER and app_main.AUTO_TRADER.running and hasattr(app_main.AUTO_TRADER, 'stats'):
            all_stats = app_main.AUTO_TRADER.stats
            if base_currency in all_stats:
                stats.update(all_stats[base_currency])

        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def reset_autotrader_cycle_impl():
    try:
        import mTrade as app_main
        data = request.get_json() or {}
        base_currency = data.get('base_currency', '').upper()
        if not base_currency:
            return jsonify({"success": False, "error": "Не указана валюта"}), 400

        if not app_main.AUTO_TRADER:
            return jsonify({"success": False, "error": "Автотрейдер не инициализирован"}), 500

        if base_currency in app_main.AUTO_TRADER.cycles:
            # Используем правильный API AutoTraderV2 для сброса цикла
            lock = app_main.AUTO_TRADER._get_lock(base_currency)
            with lock:
                # Сохраняем старое состояние для отчёта
                old_info = app_main.AUTO_TRADER.get_cycle_info(base_currency)
                
                # Сбрасываем цикл
                cycle_obj = app_main.AUTO_TRADER.cycles[base_currency]
                cycle_obj.reset()
                
                print(f"[RESET_CYCLE][{base_currency}] Цикл сброшен через handlers/autotrade.py")
                
                return jsonify({
                    "success": True,
                    "message": f"Цикл {base_currency} успешно сброшен.",
                    "old_state": old_info if old_info else {
                        "active": False,
                        "step": -1,
                        "invested": 0.0
                    }
                })
        else:
            # Создаём новый цикл и сразу сбрасываем
            lock = app_main.AUTO_TRADER._get_lock(base_currency)
            with lock:
                app_main.AUTO_TRADER._ensure_cycle(base_currency)
                cycle_obj = app_main.AUTO_TRADER.cycles[base_currency]
                cycle_obj.reset()
                
                print(f"[RESET_CYCLE][{base_currency}] Новый цикл создан и сброшен через handlers/autotrade.py")
                
                return jsonify({"success": True, "message": f"Цикл {base_currency} готов к запуску."})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
