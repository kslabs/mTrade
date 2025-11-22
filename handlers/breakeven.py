from flask import request, jsonify
import time
import traceback

from state_manager import get_state_manager
from config import Config
from gate_api_client import GateAPIClient


def get_breakeven_table_impl():
    try:
        from breakeven_calculator import calculate_breakeven_table
        state_manager = get_state_manager()

        # Определяем тип запроса (legacy или per-currency)
        has_currency_arg = ('base_currency' in request.args) or ('currency' in request.args)
        base_currency = (request.args.get('base_currency') or request.args.get('currency') or '')
        base_currency = base_currency.upper() if base_currency else ''
        use_legacy = not has_currency_arg or base_currency == '' or base_currency == 'LEGACY'

        # Загружаем сохраненные параметры
        if use_legacy:
            try:
                # Попытка получить TRADE_PARAMS из mTrade (если доступно)
                from mTrade import TRADE_PARAMS
            except Exception:
                TRADE_PARAMS = {}
            params = TRADE_PARAMS.copy() if isinstance(TRADE_PARAMS, dict) else {}
            base_for_price = 'BTC'
        else:
            params = state_manager.get_breakeven_params(base_currency).copy()
            base_for_price = base_currency

        # Переопределяем параметры из query string
        for key, caster in (
            ('steps', int), ('start_volume', float), ('start_price', float),
            ('pprof', float), ('kprof', float), ('target_r', float), ('rk', float),
            ('geom_multiplier', float)
        ):
            if key in request.args:
                try:
                    params[key] = caster(request.args.get(key))
                except Exception:
                    pass
        if 'rebuy_mode' in request.args:
            rebuy_mode = str(request.args.get('rebuy_mode')).lower()
            if rebuy_mode in ('fixed', 'geometric', 'martingale'):
                params['rebuy_mode'] = rebuy_mode

        # Получаем текущую цену из WS
        current_price = 0.0
        try:
            from handlers.websocket import ws_get_data
            if base_for_price:
                pd = ws_get_data(f"{base_for_price}_USDT")
                if pd and pd.get('ticker') and pd['ticker'].get('last'):
                    current_price = float(pd['ticker']['last'])
        except Exception:
            current_price = 0.0

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
