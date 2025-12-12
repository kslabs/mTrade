# =============================================================================
# QUICK TRADE API (Быстрая торговля)
# =============================================================================

import math
import time
import traceback
from flask import jsonify, request

# Импорт модулей проекта
from config import Config
from gate_api_client import GateAPIClient
from state_manager import get_state_manager
from trade_logger import get_trade_logger
from gateio_websocket import get_websocket_manager

# Глобальные переменные (импортируем из основного файла)
CURRENT_NETWORK_MODE = None  # Будет установлен при импорте

# Вспомогательные константы и утилиты для QUICK TRADE API
_QUICK_TRADE_DEFAULT_MIN_QUOTE = 3.0


def _build_quick_trade_diag_base() -> dict:
    """Базовый шаблон diagnostic_info для quick trade эндпоинтов.
    Структура ключей сохранена, используются значения по умолчанию.
    """
    return {
        'pair': None,
        'base_currency': None,
        'quote_currency': None,
        'balance_usdt': None,
        'balance': None,
        'best_ask': None,
        'best_bid': None,
        'orderbook_bids': None,
        'orderbook_asks': None,
        'amount': None,
        'execution_price': None,
        'start_volume': None,
        'api_min_quote': None,
        'total': None,
        'cancelled_orders': 0,
        'network_mode': CURRENT_NETWORK_MODE,
        'orderbook_level': None,
        'error_stage': None,
    }


def _quick_trade_error(message: str, info: dict, status: int = 400):
    """Единообразный ответ об ошибке для QUICK TRADE API.
    Формат ответа полностью совпадает с существующим: поля success и details сохранены.
    """
    return jsonify({'success': False, 'error': message, 'details': info}), status


def quick_buy_min():
    """Купить минимальный ордер по текущей цене"""

    diagnostic_info = _build_quick_trade_diag_base()
    try:
        data = request.get_json() or {}
        base_currency = data.get('base_currency')
        quote_currency = data.get('quote_currency', 'USDT')
        diagnostic_info.update({'base_currency': base_currency, 'quote_currency': quote_currency})
        if not base_currency:
            diagnostic_info['error_stage'] = 'validation'
            return _quick_trade_error('Не указана базовая валюта', diagnostic_info, 400)

        pair = f"{base_currency}_{quote_currency}"
        diagnostic_info['pair'] = pair

        # API ключи
        api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        if not api_key or not api_secret:
            diagnostic_info['error_stage'] = 'api_keys'
            return _quick_trade_error('API ключи не настроены для текущего режима', diagnostic_info, 400)

        api_client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)

        # Баланс котируемой валюты
        diagnostic_info['error_stage'] = 'get_balance'
        try:
            balance = api_client.get_account_balance()
            for item in balance:
                if item.get('currency', '').upper() == quote_currency.upper():
                    diagnostic_info['balance_usdt'] = float(item.get('available', '0'))
                    break
        except Exception as e:
            print(f"[WARNING] Не удалось получить баланс: {e}")

        # Пара
        diagnostic_info['error_stage'] = 'get_pair_info'
        pair_info = api_client.get_currency_pair_details_exact(pair)
        if not pair_info or 'error' in pair_info:
            diagnostic_info['error_stage'] = 'pair_not_found'
            return _quick_trade_error(f'Пара {pair} не найдена', diagnostic_info, 400)

        try:
            diagnostic_info['api_min_quote'] = float(pair_info.get('min_quote_amount', str(_QUICK_TRADE_DEFAULT_MIN_QUOTE)))
        except Exception:
            diagnostic_info['api_min_quote'] = _QUICK_TRADE_DEFAULT_MIN_QUOTE

        # Рыночные данные
        diagnostic_info['error_stage'] = 'get_market_data'
        ws_manager = get_websocket_manager()
        market_data = ws_manager.get_pair_data(base_currency, quote_currency) if ws_manager else None
        if not market_data or 'orderbook' not in market_data:
            diagnostic_info['error_stage'] = 'no_market_data'
            return _quick_trade_error('Нет данных рынка', diagnostic_info, 400)

        orderbook = market_data['orderbook']
        if orderbook.get('bids'):
            diagnostic_info['orderbook_bids'] = [[float(b[0]), float(b[1])] for b in orderbook['bids'][:5]]
            diagnostic_info['best_bid'] = float(orderbook['bids'][0][0])
        if orderbook.get('asks'):
            diagnostic_info['orderbook_asks'] = [[float(a[0]), float(a[1])] for a in orderbook['asks'][:5]]
            diagnostic_info['best_ask'] = float(orderbook['asks'][0][0])
        if not orderbook.get('asks'):
            diagnostic_info['error_stage'] = 'no_asks'
            return _quick_trade_error('Нет цен продажи в стакане', diagnostic_info, 400)

        # Параметры безубыточности и уровень стакана
        state_manager = get_state_manager()
        breakeven_params = state_manager.get_breakeven_params(base_currency)
        orderbook_level = int(breakeven_params.get('orderbook_level', 1))
        diagnostic_info['orderbook_level'] = orderbook_level
        if len(orderbook['asks']) < orderbook_level:
            diagnostic_info['error_stage'] = 'orderbook_level_unavailable'
            return _quick_trade_error(
                f'Уровень стакана {orderbook_level} недоступен (доступно уровней: {len(orderbook["asks"])})',
                diagnostic_info,
                400,
            )

        # Выбранная цена
        best_ask = float(orderbook['asks'][orderbook_level - 1][0])
        diagnostic_info['selected_ask'] = best_ask

        # Стартовый объём
        try:
            start_volume = float(breakeven_params.get('start_volume', 10.0))
        except Exception:
            start_volume = 10.0
        diagnostic_info['start_volume'] = start_volume

        api_min_quote = diagnostic_info['api_min_quote'] or _QUICK_TRADE_DEFAULT_MIN_QUOTE
        if start_volume < api_min_quote:
            print(f"[WARNING] start_volume ({start_volume}) < API минимум ({api_min_quote}), используем {api_min_quote}")
            start_volume = api_min_quote
            diagnostic_info['start_volume'] = start_volume

        # Достаточность баланса
        if diagnostic_info.get('balance_usdt') is not None and diagnostic_info['balance_usdt'] < start_volume:
            diagnostic_info['error_stage'] = 'insufficient_balance'
            return _quick_trade_error(
                f'Недостаточно {quote_currency} для покупки (баланс: {diagnostic_info["balance_usdt"]}, требуется: {start_volume})',
                diagnostic_info,
                400,
            )

        # Кол-во базовой валюты
        amount = start_volume / best_ask
        amount_precision = int(pair_info.get('amount_precision', 8))
        amount = round(amount, amount_precision)
        diagnostic_info['amount'] = amount
        amount_str = f"{amount:.{amount_precision}f}"

        # Создание ордера
        diagnostic_info['error_stage'] = 'create_order'
        execution_price = best_ask
        diagnostic_info['execution_price'] = execution_price
        if CURRENT_NETWORK_MODE == 'test':
            price_precision = int(pair_info.get('precision', 8))
            price_str = f"{execution_price:.{price_precision}f}"
            print(
                f"[INFO] quick_buy_min: создание ЛИМИТНОГО ордера {pair}, amount={amount_str}, "
                f"price={price_str} (testnet, покупка по best_ask)"
            )
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='buy',
                amount=amount_str,
                price=price_str,
                order_type='limit',
            )
        else:
            print(f"[INFO] quick_buy_min: создание РЫНОЧНОГО ордера {pair}, amount={amount_str}")
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='buy',
                amount=amount_str,
                order_type='market',
            )

        print(f"[INFO] quick_buy_min: ответ API: {result}")
        print(f"[INFO] quick_buy_min: type(result) = {type(result)}")
        print(f"[INFO] quick_buy_min: 'label' in result = {'label' in result if isinstance(result, dict) else 'N/A'}")

        # Разбор результата
        if isinstance(result, dict) and 'label' in result:
            error_msg = result.get('message', 'Неизвестная ошибка API')
            error_label = result.get('label', 'UNKNOWN_ERROR')
            diagnostic_info['error_stage'] = f'api_error_{error_label}'
            diagnostic_info['api_error'] = {'label': error_label, 'message': error_msg}
            print(f"[ERROR] quick_buy_min: ошибка API [{error_label}] - {error_msg}")
            return _quick_trade_error(f'[{error_label}] {error_msg}', diagnostic_info, 400)

        if not isinstance(result, dict) or 'id' not in result:
            diagnostic_info['error_stage'] = 'no_order_id'
            diagnostic_info['api_response'] = str(result)[:200]
            print(f"[ERROR] quick_buy_min: нет ID в ответе - {result}")
            return _quick_trade_error('Ордер не создан (нет ID в ответе)', diagnostic_info, 400)

        # Логирование сделки
        trade_logger = get_trade_logger()
        trade_logger.log_buy(
            currency=base_currency,
            volume=amount,
            price=best_ask,
            delta_percent=0.0,
            total_drop_percent=0.0,
            investment=start_volume,
        )

        return jsonify({
            'success': True,
            'order': result,
            'amount': amount,
            'price': best_ask,
            'execution_price': execution_price,
            'total': start_volume,
            'order_id': result.get('id', 'unknown'),
            'details': {
                'pair': pair,
                'side': 'buy',
                'order_type': 'limit' if CURRENT_NETWORK_MODE == 'test' else 'market',
                'best_ask': best_ask,
                'best_bid': diagnostic_info.get('best_bid'),
                'amount': amount,
                'start_volume_usdt': start_volume,
                'balance_usdt': diagnostic_info.get('balance_usdt'),
                'network_mode': CURRENT_NETWORK_MODE,
                'orderbook_snapshot': {
                    'bids': diagnostic_info.get('orderbook_bids'),
                    'asks': diagnostic_info.get('orderbook_asks'),
                },
            },
        })

    except Exception as e:
        diagnostic_info['error_stage'] = 'exception'
        diagnostic_info['exception'] = str(e)
        print(f"[ERROR] quick_buy_min: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e), 'details': diagnostic_info}), 500


def quick_sell_all():
    """Продать весь доступный баланс базовой валюты"""

    diagnostic_info = _build_quick_trade_diag_base()
    try:
        data = request.get_json() or {}
        base_currency = data.get('base_currency')
        quote_currency = data.get('quote_currency', 'USDT')
        diagnostic_info.update({'base_currency': base_currency, 'quote_currency': quote_currency})
        if not base_currency:
            diagnostic_info['error_stage'] = 'validation'
            return _quick_trade_error('Не указана базовая валюта', diagnostic_info, 400)

        pair = f"{base_currency}_{quote_currency}"
        diagnostic_info['pair'] = pair

        # API ключи
        api_key, api_secret = Config.load_secrets_by_mode(CURRENT_NETWORK_MODE)
        if not api_key or not api_secret:
            diagnostic_info['error_stage'] = 'api_keys'
            return _quick_trade_error('API ключи не настроены для текущего режима', diagnostic_info, 400)

        api_client = GateAPIClient(api_key, api_secret, CURRENT_NETWORK_MODE)

        # Testnet: отмена открытых ордеров
        cancel_result = {'count': 0}
        if CURRENT_NETWORK_MODE == 'test':
            try:
                cancel_result = api_client.cancel_all_open_orders(pair)
                diagnostic_info['cancelled_orders'] = cancel_result.get('count', 0)
                if cancel_result.get('count', 0) > 0:
                    print(f"[INFO] Отменено {cancel_result['count']} открытых ордеров для {pair}")
                    time.sleep(1)
            except Exception as e:
                print(f"[WARNING] Не удалось отменить открытые ордера: {e}")

        # Баланс базовой валюты
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
            return _quick_trade_error(
                f'Недостаточно {base_currency} для продажи (баланс: {base_balance or 0})',
                diagnostic_info,
                400,
            )

        # Пара
        diagnostic_info['error_stage'] = 'get_pair_info'
        pair_info = api_client.get_currency_pair_details_exact(pair)
        if not pair_info or 'error' in pair_info:
            diagnostic_info['error_stage'] = 'pair_not_found'
            return _quick_trade_error(f'Пара {pair} не найдена', diagnostic_info, 400)

        # Рыночные данные
        diagnostic_info['error_stage'] = 'get_market_data'
        ws_manager = get_websocket_manager()
        market_data = ws_manager.get_pair_data(base_currency, quote_currency) if ws_manager else None
        if not market_data or 'orderbook' not in market_data:
            diagnostic_info['error_stage'] = 'no_market_data'
            return _quick_trade_error('Нет данных рынка', diagnostic_info, 400)

        orderbook = market_data['orderbook']
        if orderbook.get('bids'):
            diagnostic_info['orderbook_bids'] = [[float(b[0]), float(b[1])] for b in orderbook['bids'][:5]]
            diagnostic_info['best_bid'] = float(orderbook['bids'][0][0])
        if orderbook.get('asks'):
            diagnostic_info['orderbook_asks'] = [[float(a[0]), float(a[1])] for a in orderbook['asks'][:5]]
            diagnostic_info['best_ask'] = float(orderbook['asks'][0][0])
        if not orderbook.get('bids'):
            diagnostic_info['error_stage'] = 'no_bids'
            return _quick_trade_error('Нет цен покупки в стакане', diagnostic_info, 400)

        # Параметры безубыточности и уровень стакана
        state_manager = get_state_manager()
        breakeven_params = state_manager.get_breakeven_params(base_currency)
        orderbook_level = int(breakeven_params.get('orderbook_level', 1))
        diagnostic_info['orderbook_level'] = orderbook_level
        if len(orderbook['bids']) < orderbook_level:
            diagnostic_info['error_stage'] = 'orderbook_level_unavailable'
            return _quick_trade_error(
                f'Уровень стакана {orderbook_level} недоступен (доступно уровней: {len(orderbook["bids"])})',
                diagnostic_info,
                400,
            )

        # Выбранная цена
        best_bid = float(orderbook['bids'][orderbook_level - 1][0])
        diagnostic_info['selected_bid'] = best_bid

        # Кол-во (округление вниз по точности пары)
        amount_precision = int(pair_info.get('amount_precision', 8))
        amount = math.floor(base_balance * (10 ** amount_precision)) / (10 ** amount_precision)
        diagnostic_info['amount'] = amount

        total = amount * best_bid
        diagnostic_info['total'] = total
        amount_str = f"{amount:.{amount_precision}f}"

        # Создание ордера
        diagnostic_info['error_stage'] = 'create_order'
        execution_price = best_bid
        diagnostic_info['execution_price'] = execution_price
        if CURRENT_NETWORK_MODE == 'test':
            price_precision = int(pair_info.get('precision', 8))
            price_str = f"{execution_price:.{price_precision}f}"
            print(
                f"[INFO] quick_sell_all: создание ЛИМИТНОГО ордера {pair}, amount={amount_str}, "
                f"price={price_str} (testnet, продажа по best_bid)"
            )
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='sell',
                amount=amount_str,
                price=price_str,
                order_type='limit',
            )
        else:
            print(f"[INFO] quick_sell_all: создание РЫНОЧНОГО ордера {pair}, amount={amount_str}")
            result = api_client.create_spot_order(
                currency_pair=pair,
                side='sell',
                amount=amount_str,
                order_type='market',
            )

        print(f"[INFO] quick_sell_all: ответ API: {result}")

        if isinstance(result, dict) and 'label' in result:
            error_msg = result.get('message', 'Неизвестная ошибка API')
            error_label = result.get('label', 'UNKNOWN_ERROR')
            diagnostic_info['error_stage'] = f'api_error_{error_label}'
            diagnostic_info['api_error'] = {'label': error_label, 'message': error_msg}
            print(f"[ERROR] quick_sell_all: ошибка API [{error_label}] - {error_msg}")
            return _quick_trade_error(f'[{error_label}] {error_msg}', diagnostic_info, 400)

        if not isinstance(result, dict) or 'id' not in result:
            diagnostic_info['error_stage'] = 'no_order_id'
            diagnostic_info['api_response'] = str(result)[:200]
            print(f"[ERROR] quick_sell_all: нет ID в ответе - {result}")
            return _quick_trade_error('Ордер не создан (нет ID в ответе)', diagnostic_info, 400)

        # Логирование сделки с расчётом метрик
        trade_logger = get_trade_logger()
        
        # Пытаемся получить данные цикла для расчёта метрик
        delta_percent = 0.0
        pnl = 0.0
        
        try:
            # Получаем последнюю покупку для расчёта дельты
            last_buy = trade_logger.get_last_entry(base_currency, entry_type='buy')
            if last_buy and 'price' in last_buy:
                buy_price = float(last_buy['price'])
                if buy_price > 0:
                    delta_percent = ((best_bid - buy_price) / buy_price) * 100.0
                
                # Рассчитываем PnL
                if 'volume_quote' in last_buy:
                    invested = float(last_buy.get('volume_quote', 0))
                    revenue = amount * best_bid
                    pnl = revenue - invested
                    print(f"[INFO] quick_sell_all: метрики рассчитаны - дельта={delta_percent:.2f}%, PnL={pnl:.4f}")
                else:
                    print(f"[WARN] quick_sell_all: нет volume_quote в last_buy, PnL=0")
            else:
                print(f"[WARN] quick_sell_all: нет данных о последней покупке для {base_currency}, метрики=0")
        except Exception as metrics_error:
            print(f"[WARN] quick_sell_all: ошибка расчёта метрик - {metrics_error}")
        
        trade_logger.log_sell(
            currency=base_currency,
            volume=amount,
            price=best_bid,
            delta_percent=delta_percent,
            pnl=pnl,
        )

        return jsonify({
            'success': True,
            'order': result,
            'amount': amount,
            'price': best_bid,
            'execution_price': execution_price,
            'total': total,
            'order_id': result.get('id', 'unknown'),
            'details': {
                'pair': pair,
                'side': 'sell',
                'order_type': 'limit' if CURRENT_NETWORK_MODE == 'test' else 'market',
                'best_bid': best_bid,
                'best_ask': diagnostic_info.get('best_ask'),
                'amount': amount,
                'total_usdt': total,
                'balance': base_balance,
                'network_mode': CURRENT_NETWORK_MODE,
                'cancelled_orders': diagnostic_info['cancelled_orders'],
                'orderbook_snapshot': {
                    'bids': diagnostic_info.get('orderbook_bids'),
                    'asks': diagnostic_info.get('orderbook_asks'),
                },
            },
        })

    except Exception as e:
        diagnostic_info['error_stage'] = 'exception'
        diagnostic_info['exception'] = str(e)
        print(f"[ERROR] quick_sell_all: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e), 'details': diagnostic_info}), 500
