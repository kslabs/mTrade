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
        # Попытка 1: если автотрейдер запущен — использовать его стартовую логику
        tried_autotrader = False
        try:
            import mTrade
            at = getattr(mTrade, 'AUTO_TRADER', None)
        except Exception:
            at = None

        execution_price = best_ask
        diagnostic_info['execution_price'] = execution_price

        if at:
            tried_autotrader = True
            try:
                # Используем безопасный синхронный метод, который ждёт завершения async покупки
                success = at.try_start_cycle_sync(base_currency, quote_currency, timeout=10.0)
                if success:
                    cycle = at.cycles.get(base_currency.upper())
                    if cycle and float(cycle.get('base_volume', 0) or 0) > 0:
                        filled_base = float(cycle.get('base_volume', 0) or 0)
                        filled_spent = float(cycle.get('total_invested_usd', 0) or 0)
                        details_out = {
                            'pair': pair,
                            'order_type': 'aggregated_start',
                            'network_mode': Config.load_network_mode(),
                            'best_ask': best_ask,
                            'amount': filled_base,
                            'execution_price': cycle.get('last_buy_price') or execution_price,
                            'filled_usd': filled_spent
                        }
                        return jsonify({'success': True, 'order': None, 'amount': filled_base, 'price': details_out['execution_price'], 'execution_price': details_out['execution_price'], 'total': filled_spent, 'order_id': None, 'details': details_out})
                # else — автотрейдер не купил (таймаут или ошибка), падаем к обычной логике
            except Exception as e:
                diagnostic_info['api_error'] = {'label': 'autotrader_exception', 'message': str(e)}

        # ЗАЩИТА: Если автотрейдер запустил покупку, но она ещё не завершилась,
        # НЕ делаем fallback, чтобы избежать дублей
        if at:
            try:
                cycle = at.cycles.get(base_currency.upper(), {})
                state = at._cycle_start_state.get(base_currency.upper(), 0)
                # Если покупка в процессе (state=1) или цикл активен (state=2), НЕ делаем fallback
                if state != 0:
                    if state == 1:
                        diagnostic_info['error_stage'] = 'autotrader_in_progress'
                        return jsonify({'success': False, 'error': 'Покупка уже в процессе через автотрейдер', 'details': diagnostic_info}), 409
                    elif state == 2:
                        # Цикл уже активен - возвращаем текущее состояние
                        filled_base = float(cycle.get('base_volume', 0) or 0)
                        filled_spent = float(cycle.get('total_invested_usd', 0) or 0)
                        return jsonify({'success': True, 'order': None, 'amount': filled_base, 'price': cycle.get('last_buy_price', 0), 'execution_price': cycle.get('last_buy_price', 0), 'total': filled_spent, 'order_id': None, 'details': {'pair': pair, 'order_type': 'already_active'}})
            except Exception:
                pass  # Игнорируем ошибки проверки состояния

        # Если автотрейдер отсутствует или не купил — делаем прямой market (как fallback)
        try:
            result = api_client.create_spot_order(currency_pair=pair, side='buy', amount=amount_str, order_type='market')
        except Exception as e:
            # В редких случаях тестовый хост может не поддерживать market; логируем и пробуем лимит как fallback
            diagnostic_info['api_error'] = {'label': 'create_market_failed', 'message': str(e)}
            try:
                price_precision = int(pair_info.get('precision', 8))
                price_str = f"{execution_price:.{price_precision}f}"
                result = api_client.create_spot_order(currency_pair=pair, side='buy', amount=amount_str, price=price_str, order_type='limit')
            except Exception as e2:
                diagnostic_info['error_stage'] = 'create_order_failed'
                diagnostic_info['api_error'] = {'label': 'create_limit_fallback_failed', 'message': str(e2)}
                return jsonify({'success': False, 'error': 'Ошибка создания ордера', 'details': diagnostic_info}), 500

        # Если API вернул ошибку в теле (label) — попробуем специальные fallback-логики
        if isinstance(result, dict) and 'label' in result:
            error_msg = result.get('message', 'Неизвестная ошибка API')
            error_label = result.get('label', 'UNKNOWN_ERROR')
            diagnostic_info['error_stage'] = f'api_error_{error_label}'
            diagnostic_info['api_error'] = {'label': error_label, 'message': error_msg}

            # Специальный кейс: для market-buy некоторые хосты требуют указания суммы в котируемой валюте (quote).
            # При получении INVALID_PARAM_VALUE попробуем повторить market-buy, передав amount=start_volume (в quote).
            if error_label == 'INVALID_PARAM_VALUE':
                try:
                    diagnostic_info['retry_attempt'] = 'market_with_quote_amount'
                    # Форматируем сумму в quote с приемлемой точностью
                    quote_attempt_amount = f"{start_volume:.8f}"
                    diagnostic_info['retry_amount'] = quote_attempt_amount
                    retry_result = api_client.create_spot_order(currency_pair=pair, side='buy', amount=quote_attempt_amount, order_type='market')
                    diagnostic_info['retry_result_preview'] = str(retry_result)[:400]
                    # Если повторный вызов прошёл без label — используем его как основной результат
                    if not (isinstance(retry_result, dict) and 'label' in retry_result):
                        result = retry_result
                    else:
                        # Сохраним информацию об ошибке повторной попытки
                        diagnostic_info['api_error_retry'] = {'label': retry_result.get('label'), 'message': retry_result.get('message')}
                        # Продолжим дальше — ниже обработка вернёт ошибку пользователю
                except Exception as e:
                    diagnostic_info['api_error_retry'] = {'label': 'retry_exception', 'message': str(e)}

                # Если повторная попытка не помогла — попробуем автотрейдер (если он доступен).
                try:
                    import mTrade
                    at = getattr(mTrade, 'AUTO_TRADER', None)
                except Exception:
                    at = None

                if (isinstance(result, dict) and 'label' in result) and at:
                    try:
                        diagnostic_info['retry_attempt_2'] = 'autotrader_start'
                        # Сохраним текущие параметры и временно установим start_volume
                        state_mgr = get_state_manager()
                        orig_params = state_mgr.get_breakeven_params(base_currency)
                        # Make a shallow copy to avoid mutating stored object unexpectedly
                        params_copy = dict(orig_params)
                        params_copy['start_volume'] = float(start_volume)
                        state_mgr.set_breakeven_params(base_currency, params_copy)
                        # Вызовем автотрейдер непосредственно
                        at._try_start_cycle(base_currency, quote_currency)
                        # Восстановим оригинальные параметры
                        state_mgr.set_breakeven_params(base_currency, orig_params)
                        # Проверим цикл на результат
                        cycle = at.cycles.get(base_currency.upper())
                        if cycle and float(cycle.get('base_volume', 0) or 0) > 0:
                            filled_base = float(cycle.get('base_volume', 0) or 0)
                            filled_spent = float(cycle.get('total_invested_usd', 0) or 0)
                            details_out = {
                                'pair': pair,
                                'order_type': 'aggregated_start_via_quickbuy_fallback',
                                'network_mode': Config.load_network_mode(),
                                'best_ask': best_ask,
                                'amount': filled_base,
                                'execution_price': cycle.get('last_buy_price') or execution_price,
                                'filled_usd': filled_spent
                            }
                            return jsonify({'success': True, 'order': None, 'amount': filled_base, 'price': details_out['execution_price'], 'execution_price': details_out['execution_price'], 'total': filled_spent, 'order_id': None, 'details': details_out})
                        else:
                            diagnostic_info['autotrader_fallback'] = 'no_fill'
                    except Exception as e:
                        diagnostic_info['autotrader_fallback_error'] = str(e)

            # Если после всех попыток всё ещё ошибка — вернём её клиенту
            if isinstance(result, dict) and 'label' in result:
                return jsonify({'success': False, 'error': f'[{error_label}] {error_msg}', 'details': diagnostic_info}), 400

        if not isinstance(result, dict) or 'id' not in result:
            diagnostic_info['error_stage'] = 'no_order_id'
            diagnostic_info['api_response'] = str(result)[:200]
            return jsonify({'success': False, 'error': 'Ордер не создан (нет ID в ответе)', 'details': diagnostic_info}), 400

        # Попытка извлечь фактически исполненный объём (base) из ответа биржи
        filled_base = 0.0
        try:
            if isinstance(result, dict):
                if 'deal_amount' in result:
                    filled_base = float(result.get('deal_amount') or 0)
                elif 'filled_amount' in result:
                    filled_base = float(result.get('filled_amount') or 0)
                elif 'filled_total' in result:
                    filled_base = float(result.get('filled_total') or 0)
                elif 'amount' in result and 'left' in result:
                    try:
                        filled_base = float(result.get('amount') or 0) - float(result.get('left') or 0)
                    except Exception:
                        filled_base = 0.0
                elif result.get('status') in ('closed', 'finished') and 'amount' in result:
                    # assume fully executed
                    filled_base = float(result.get('amount') or 0)
        except Exception:
            filled_base = 0.0

        # Если нет исполнения — не считаем покупку успешной (во избежание ложных уведомлений)
        if filled_base and filled_base > 0:
            trade_logger = get_trade_logger()
            trade_logger.log_buy(currency=base_currency, volume=filled_base, price=best_ask, delta_percent=0.0, total_drop_percent=0.0, investment=start_volume)

            used_order_type = 'limit' if Config.load_network_mode() == 'test' else 'market'
            details_out = {
                'pair': pair,
                'order_type': used_order_type,
                'network_mode': Config.load_network_mode(),
                'best_ask': best_ask,
                'amount': filled_base,
                'execution_price': diagnostic_info.get('execution_price'),
                'order_id': result.get('id') if isinstance(result, dict) else None
            }
            return jsonify({'success': True, 'order': result, 'amount': filled_base, 'price': best_ask, 'execution_price': diagnostic_info['execution_price'], 'total': start_volume, 'order_id': result.get('id', 'unknown'), 'details': details_out})
        else:
            # Order created but not filled (or no execution info). Return informative failure so UI не показывает ложный успех.
            details_out = {
                'pair': pair,
                'order_type': 'limit' if Config.load_network_mode() == 'test' else 'market',
                'network_mode': Config.load_network_mode(),
                'best_ask': best_ask,
                'amount_requested': amount,
                'filled': filled_base,
                'order_id': result.get('id') if isinstance(result, dict) else None,
            }
            diagnostic_info['error_stage'] = 'not_filled'
            return jsonify({'success': False, 'error': 'Order created but not executed (no fills)', 'order': result, 'details': details_out}), 200

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

        # Попытка извлечь исполненный объём
        filled_base = 0.0
        try:
            if isinstance(result, dict):
                if 'deal_amount' in result:
                    filled_base = float(result.get('deal_amount') or 0)
                elif 'filled_amount' in result:
                    filled_base = float(result.get('filled_amount') or 0)
                elif 'filled_total' in result:
                    filled_base = float(result.get('filled_total') or 0)
                elif 'amount' in result and 'left' in result:
                    try:
                        filled_base = float(result.get('amount') or 0) - float(result.get('left') or 0)
                    except Exception:
                        filled_base = 0.0
                elif result.get('status') in ('closed', 'finished') and 'amount' in result:
                    filled_base = float(result.get('amount') or 0)
        except Exception:
            filled_base = 0.0

        if filled_base and filled_base > 0:
            # Log the actual sell
            trade_logger = get_trade_logger()
            trade_logger.log_sell(currency=base_currency, volume=filled_base, price=best_bid, delta_percent=0.0, pnl=0.0)
        else:
            # If nothing filled — do not log as a completed sell
            diagnostic_info['error_stage'] = 'not_filled'

        # Если автотрейдер запущен — принудительно закроем цикл для этой валюты,
        # чтобы ручная "sell all" не привела к немедленному автоматическому ребаю.
        try:
            import mTrade
            import time as time_module
            at = getattr(mTrade, 'AUTO_TRADER', None)
            if at and hasattr(at, 'cycles'):
                b = base_currency.upper()
                # Если цикл присутствует — помечаем неактивным и обнуляем ключевые поля
                if b in at.cycles:
                    # ====== КРИТИЧЕСКИ ВАЖНО: Устанавливаем last_sell_time ДО сброса цикла ======
                    # Это предотвратит немедленный запуск новой стартовой покупки
                    current_time = time_module.time()
                    
                    at.cycles[b].update({
                        'active': False,
                        'active_step': -1,
                        'last_buy_price': 0.0,
                        'start_price': 0.0,
                        'total_invested_usd': 0.0,
                        'base_volume': 0.0,
                        'pending_start': False,  # КРИТИЧНО: Сбрасываем флаг pending_start
                        'last_sell_time': current_time,  # КРИТИЧНО: Устанавливаем метку времени продажи
                        'last_start_attempt': 0  # Сбрасываем метку последней попытки старта
                    })
                    
                    print(f"[MANUAL_SELL][{b}] Цикл сброшен после ручной продажи: active=False, last_sell_time={current_time}")
                    
                    try:
                        # Обновим params в state_manager чтобы таблица не использовала старый start_price
                        current_params = state_manager.get_breakeven_params(b)
                        current_params['start_price'] = 0.0
                        state_manager.set_breakeven_params(b, current_params)
                    except Exception:
                        pass
                    try:
                        # Сразу сохраним состояние автотрейдера
                        if hasattr(at, '_save_cycles_state'):
                            at._save_cycles_state()
                            print(f"[MANUAL_SELL][{b}] Состояние автотрейдера сохранено")
                    except Exception as e:
                        print(f"[MANUAL_SELL][{b}] Ошибка сохранения состояния: {e}")
                    try:
                        if hasattr(at, '_set_last_diagnostic'):
                            at._set_last_diagnostic(b, {'decision': 'manual_sell_all', 'timestamp': current_time, 'reason': 'user_initiated_sell_all'})
                    except Exception:
                        pass
        except Exception as e:
            print(f"[MANUAL_SELL_ERROR] Ошибка при сбросе цикла: {e}")
            import traceback
            traceback.print_exc()

        # Дополняем детали для UI
        used_order_type = 'limit' if Config.load_network_mode() == 'test' else 'market'
        details_out = {
            'pair': pair,
            'order_type': used_order_type,
            'network_mode': Config.load_network_mode(),
            'best_bid': best_bid,
            'amount': amount,
            'execution_price': diagnostic_info.get('execution_price'),
            'cancelled_orders': diagnostic_info.get('cancelled_orders', 0)
        }

        return jsonify({'success': True, 'order': result, 'amount': amount, 'price': best_bid, 'execution_price': diagnostic_info['execution_price'], 'total': total, 'order_id': result.get('id', 'unknown'), 'details': details_out})

    except Exception as e:
        diagnostic_info['error_stage'] = 'exception'
        diagnostic_info['exception'] = str(e)
        return jsonify({'success': False, 'error': str(e), 'details': diagnostic_info}), 500
