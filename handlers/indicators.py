from flask import request, jsonify
import traceback

from handlers.websocket import ws_get_data
from state_manager import get_state_manager
from trade_logger import get_trade_logger


def get_trade_indicators_impl():
    try:
        state_manager = get_state_manager()
        base_currency = request.args.get('base_currency', 'BTC').upper()
        quote_currency = request.args.get('quote_currency', 'USDT').upper()
        include_table = str(request.args.get('include_table', '0')).lower() in ('1','true','yes')
        currency_pair = f"{base_currency}_{quote_currency}".upper()

        # Данные из WebSocket
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
            'current_price': None,
            'sell_price': None,
            'next_buy_price': None
        }

        price = indicators['price']
        autotrade_levels['current_price'] = price

        # Получаем таблицу: либо из цикла, либо рассчитываем новую
        cycle = None
        table = None
        try:
            from mTrade import AUTO_TRADER
            if AUTO_TRADER and hasattr(AUTO_TRADER, 'cycles'):
                cycle = AUTO_TRADER.cycles.get(base_currency)
                if cycle and cycle.get('table'):
                    table = cycle['table']
        except Exception:
            cycle = None

        if not table:
            params = state_manager.get_breakeven_params(base_currency)
            if params and price:
                try:
                    from breakeven_calculator import calculate_breakeven_table
                    table = calculate_breakeven_table(params, price)
                except Exception:
                    table = None

        if include_table:
            autotrade_levels['table'] = table

        resp = {
            'success': True,
            'indicators': indicators,
            'autotrade_levels': autotrade_levels,
            'pair': currency_pair
        }
        return jsonify(resp)

    except Exception as e:
        print(f"[ERROR] get_trade_indicators: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
