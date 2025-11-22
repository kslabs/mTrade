from flask import request, jsonify
import time
import traceback

from config import Config
from gate_api_client import GateAPIClient
from trade_logger import get_trade_logger
from breakeven_calculator import calculate_breakeven_table
from state_manager import get_state_manager
import math


def quick_buy_min_impl():
    import traceback as _tb
    state_manager = get_state_manager()
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
        'network_mode': Config.load_network_mode() if hasattr(Config, 'load_network_mode') else None,
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
            return jsonify({'success': False, 'error': 'Не указана базовая валюта', 'details': diagnostic_info}), 400

        pair = f"{base_currency}_{quote_currency}"
        diagnostic_info['pair'] = pair

        api_key, api_secret = Config.load_secrets_by_mode(Config.load_network_mode())
        if not api_key or not api_secret:
            diagnostic_info['error_stage'] = 'api_keys'
            return jsonify({'success': False, 'error': 'API ключи не настроены для текущего режима', 'details': diagnostic_info}), 400

        api_client = GateAPIClient(api_key, api_secret, Config.load_network_mode())

        # balance
        diagnostic_info['error_stage'] = 'get_balance'
        try:
            balance = api_client.get_account_balance()
            for item in balance:
                if item.get('currency', '').upper() == quote_currency.upper():
                    diagnostic_info['balance_usdt'] = float(item.get('available', '0'))
                    break
        except Exception:
            pass

        # pair info
        diagnostic_info['error_stage'] = 'get_pair_info'
        pair_info = api_client.get_currency_pair_details_exact(pair)
        if not pair_info or 'error' in pair_info:
            diagnostic_info['error_stage'] = 'pair_not_found'
            return jsonify({'success': False, 'error': f'Пара {pair} не найдена', 'details': diagnostic_info}), 400

        diagnostic_info['api_min_quote'] = float(pair_info.get('min_quote_amount', '3'))

        # market data
        diagnostic_info['error_stage'] = 'get_market_data'
        from handlers.websocket import ws_get_data
        market_data = ws_get_data(f"{base_currency}_{quote_currency}")
        if not market_data or 'orderbook' not in market_data:
            diagnostic_info['error_stage'] = 'no_market_data'
            return jsonify({'success': False, 'error': 'Нет данных рынка', 'details': diagnostic_info}), 400

        orderbook = market_data['orderbook']
        if orderbook.get('bids'):
            diagnostic_info['orderbook_bids'] = [[float(b[0]), float(b[1])] for b in orderbook['bids'][:5]]
            diagnostic_info['best_bid'] = float(orderbook['bids'][0][0])
        if orderbook.get('asks'):
            diagnostic_info['orderbook_asks'] = [[float(a[0]), float(a[1])] for a in orderbook['asks'][:5]]
            diagnostic_info['best_ask'] = float(orderbook['asks'][0][0])

        if not orderbook.get('asks'):
            diagnostic_info['error_stage'] = 'no_asks'
            return jsonify({'success': False, 'error': 'Нет цен продажи в стакане', 'details': diagnostic_info}), 400

        breakeven_params = state_manager.get_breakeven_params(base_currency)
        orderbook_level = int(breakeven_params.get('orderbook_level', 1))
        diagnostic_info['orderbook_level'] = orderbook_level
        if len(orderbook['asks']) < orderbook_level:
            diagnostic_info['error_stage'] = 'orderbook_level_unavailable'
            return jsonify({'success': False, 'error': f'Уровень стакана {orderbook_level} недоступен', 'details': diagnostic_info}), 400

        best_ask = float(orderbook['asks'][orderbook_level - 1][0])
        diagnostic_info['selected_ask'] = best_ask

        # Use the breakeven table's first row purchase_usd as the authoritative "start" amount
        start_volume = float(breakeven_params.get('start_volume', 10.0))
        try:
            table = calculate_breakeven_table(breakeven_params, diagnostic_info.get('selected_ask') or best_ask)
            if isinstance(table, list) and len(table) > 0 and table[0].get('purchase_usd') is not None:
                # table[0]['purchase_usd'] may be string or numeric
                pu = float(table[0]['purchase_usd'])
                start_volume = pu
                diagnostic_info['start_from_table'] = True
        except Exception:
            # fallback to configured start_volume on any error
            pass
        diagnostic_info['start_volume'] = start_volume
        api_min_quote = diagnostic_info['api_min_quote']
        if start_volume < api_min_quote:
            start_volume = api_min_quote
            diagnostic_info['start_volume'] = start_volume

        if diagnostic_info.get('balance_usdt') is not None and diagnostic_info['balance_usdt'] < start_volume:
            diagnostic_info['error_stage'] = 'insufficient_balance'
            return jsonify({'success': False, 'error': f'Недостаточно {quote_currency} для покупки', 'details': diagnostic_info}), 400
        # compute amount based on authoritative start_volume and apply rounding up to precision
        amount = start_volume / best_ask
        amount_precision = int(pair_info.get('amount_precision', 8))
        unit = 1.0 / (10 ** amount_precision)
        # округляем вверх до ближайшей минимальной единицы (ceil), чтобы сумма >= start_volume
        amount = math.ceil(amount / unit) * unit
        # Убедимся, что количество не меньше min_base_amount (если указано)
        try:
            min_b = float(pair_info.get('min_base_amount') or 0)
            if amount < min_b:
                amount = math.ceil(min_b / unit) * unit
        except Exception:
            pass
        # Проверим, чтобы итоговая сумма в котируемой валюте была >= api_min_quote
        total = amount * best_ask
        api_min = float(api_min_quote or 0)
        while api_min > 0 and total < api_min:
            amount += unit
            total = amount * best_ask
        diagnostic_info['amount'] = amount
        amount_str = f"{amount:.{amount_precision}f}"

        diagnostic_info['error_stage'] = 'create_order'
        if Config.load_network_mode() == 'test':
            execution_price = best_ask
            diagnostic_info['execution_price'] = execution_price
            price_precision = int(pair_info.get('precision', 8))
            price_str = f"{execution_price:.{price_precision}f}"
            result = api_client.create_spot_order(currency_pair=pair, side='buy', amount=amount_str, price=price_str, order_type='limit')
        else:
            execution_price = best_ask
            diagnostic_info['execution_price'] = execution_price
            result = api_client.create_spot_order(currency_pair=pair, side='buy', amount=amount_str, order_type='market')

        if isinstance(result, dict) and 'label' in result:
            error_msg = result.get('message', 'Неизвестная ошибка API')
            error_label = result.get('label', 'UNKNOWN_ERROR')
            diagnostic_info['error_stage'] = f'api_error_{error_label}'
            diagnostic_info['api_error'] = {'label': error_label, 'message': error_msg}
            return jsonify({'success': False, 'error': f'[{error_label}] {error_msg}', 'details': diagnostic_info}), 400

        if not isinstance(result, dict) or 'id' not in result:
            diagnostic_info['error_stage'] = 'no_order_id'
            diagnostic_info['api_response'] = str(result)[:200]
            return jsonify({'success': False, 'error': 'Ордер не создан (нет ID в ответе)', 'details': diagnostic_info}), 400

        trade_logger = get_trade_logger()
        trade_logger.log_buy(currency=base_currency, volume=amount, price=best_ask, delta_percent=0.0, total_drop_percent=0.0, investment=start_volume)

        return jsonify({'success': True, 'order': result, 'amount': amount, 'price': best_ask, 'execution_price': diagnostic_info['execution_price'], 'total': start_volume, 'order_id': result.get('id', 'unknown'), 'details': {'pair': pair}})

    except Exception as e:
        diagnostic_info['error_stage'] = 'exception'
        diagnostic_info['exception'] = str(e)
        return jsonify({'success': False, 'error': str(e), 'details': diagnostic_info}), 500


def quick_sell_all_impl():
    state_manager = get_state_manager()
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
        'network_mode': Config.load_network_mode() if hasattr(Config, 'load_network_mode') else None,
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
            return jsonify({'success': False, 'error': 'Не указана базовая валюта', 'details': diagnostic_info}), 400

        pair = f"{base_currency}_{quote_currency}"
        diagnostic_info['pair'] = pair

        api_key, api_secret = Config.load_secrets_by_mode(Config.load_network_mode())
        if not api_key or not api_secret:
            diagnostic_info['error_stage'] = 'api_keys'
            return jsonify({'success': False, 'error': 'API ключи не настроены для текущего режима', 'details': diagnostic_info}), 400

        api_client = GateAPIClient(api_key, api_secret, Config.load_network_mode())

        cancel_result = {'count': 0}
        if Config.load_network_mode() == 'test':
            try:
                cancel_result = api_client.cancel_all_open_orders(pair)
                diagnostic_info['cancelled_orders'] = cancel_result.get('count', 0)
                if cancel_result.get('count', 0) > 0:
                    time.sleep(1)
            except Exception:
                pass

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
            return jsonify({'success': False, 'error': f'Недостаточно {base_currency} для продажи', 'details': diagnostic_info}), 400

        pair_info = api_client.get_currency_pair_details_exact(pair)
        if not pair_info or 'error' in pair_info:
            diagnostic_info['error_stage'] = 'pair_not_found'
            return jsonify({'success': False, 'error': f'Пара {pair} не найдена', 'details': diagnostic_info}), 400

        from handlers.websocket import ws_get_data
        market_data = ws_get_data(f"{base_currency}_{quote_currency}")
        if not market_data or 'orderbook' not in market_data:
            diagnostic_info['error_stage'] = 'no_market_data'
            return jsonify({'success': False, 'error': 'Нет данных рынка', 'details': diagnostic_info}), 400

        orderbook = market_data['orderbook']
        if orderbook.get('bids'):
            diagnostic_info['orderbook_bids'] = [[float(b[0]), float(b[1])] for b in orderbook['bids'][:5]]
            diagnostic_info['best_bid'] = float(orderbook['bids'][0][0])
        if orderbook.get('asks'):
            diagnostic_info['orderbook_asks'] = [[float(a[0]), float(a[1])] for a in orderbook['asks'][:5]]
            diagnostic_info['best_ask'] = float(orderbook['asks'][0][0])

        if not orderbook.get('bids'):
            diagnostic_info['error_stage'] = 'no_bids'
            return jsonify({'success': False, 'error': 'Нет цен покупки в стакане', 'details': diagnostic_info}), 400

        breakeven_params = state_manager.get_breakeven_params(base_currency)
        orderbook_level = int(breakeven_params.get('orderbook_level', 1))
        diagnostic_info['orderbook_level'] = orderbook_level
        if len(orderbook['bids']) < orderbook_level:
            diagnostic_info['error_stage'] = 'orderbook_level_unavailable'
            return jsonify({'success': False, 'error': f'Уровень стакана {orderbook_level} недоступен', 'details': diagnostic_info}), 400

        best_bid = float(orderbook['bids'][orderbook_level - 1][0])
        diagnostic_info['selected_bid'] = best_bid
        import math
        amount_precision = int(pair_info.get('amount_precision', 8))
        amount = math.floor(base_balance * (10 ** amount_precision)) / (10 ** amount_precision)
        diagnostic_info['amount'] = amount
        total = amount * best_bid
        diagnostic_info['total'] = total
        amount_str = f"{amount:.{amount_precision}f}"

        diagnostic_info['error_stage'] = 'create_order'
        if Config.load_network_mode() == 'test':
            execution_price = best_bid
            diagnostic_info['execution_price'] = execution_price
            price_precision = int(pair_info.get('precision', 8))
            price_str = f"{execution_price:.{price_precision}f}"
            result = api_client.create_spot_order(currency_pair=pair, side='sell', amount=amount_str, price=price_str, order_type='limit')
        else:
            execution_price = best_bid
            diagnostic_info['execution_price'] = execution_price
            result = api_client.create_spot_order(currency_pair=pair, side='sell', amount=amount_str, order_type='market')

        if isinstance(result, dict) and 'label' in result:
            error_msg = result.get('message', 'Неизвестная ошибка API')
            error_label = result.get('label', 'UNKNOWN_ERROR')
            diagnostic_info['error_stage'] = f'api_error_{error_label}'
            diagnostic_info['api_error'] = {'label': error_label, 'message': error_msg}
            return jsonify({'success': False, 'error': f'[{error_label}] {error_msg}', 'details': diagnostic_info}), 400

        if not isinstance(result, dict) or 'id' not in result:
            diagnostic_info['error_stage'] = 'no_order_id'
            diagnostic_info['api_response'] = str(result)[:200]
            return jsonify({'success': False, 'error': 'Ордер не создан (нет ID в ответе)', 'details': diagnostic_info}), 400

        trade_logger = get_trade_logger()
        # TradeLogger.log_sell signature: (currency, volume, price, delta_percent, pnl)
        # We don't have pnl calculation here (requires purchase history), so pass 0.0 for pnl and 0.0 for delta_percent.
        trade_logger.log_sell(currency=base_currency, volume=amount, price=best_bid, delta_percent=0.0, pnl=0.0)

        return jsonify({'success': True, 'order': result, 'amount': amount, 'price': best_bid, 'execution_price': diagnostic_info['execution_price'], 'total': total, 'order_id': result.get('id', 'unknown'), 'details': {'pair': pair}})

    except Exception as e:
        diagnostic_info['error_stage'] = 'exception'
        diagnostic_info['exception'] = str(e)
        return jsonify({'success': False, 'error': str(e), 'details': diagnostic_info}), 500
