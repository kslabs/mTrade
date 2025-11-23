import os
import json
import requests
from datetime import datetime
from flask import request, jsonify

from config import Config
from gate_api_client import GateAPIClient
from state_manager import get_state_manager


def sync_currencies_from_gateio_impl():
    """Реализация синхронизации валют с Gate.io (вынесена из `mTrade.py`)."""
    try:
        print("\n[CURRENCY_SYNC] Начало синхронизации символов с Gate.io...")

        # Загрузка текущего списка
        current_currencies = Config.load_currencies()
        current_dict = {c['code']: c for c in current_currencies}

        # Получаем котируемую валюту из параметров запроса (по умолчанию USDT)
        quote_currency = request.json.get('quote_currency', 'USDT') if request.json else 'USDT'

        # 1. Проверяем торговые пары (какие валюты торгуются с котируемой)
        pairs_url = f"https://api.gateio.ws/api/v4/spot/currency_pairs"
        pairs_response = requests.get(pairs_url, timeout=10)

        if pairs_response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"Ошибка API Gate.io (пары): {pairs_response.status_code}"
            }), 500

        # Получаем список валют, которые торгуются с котируемой валютой
        all_pairs = pairs_response.json()
        tradeable_bases = set()
        for pair in all_pairs:
            pair_id = pair.get('id', '')
            if pair_id.endswith(f'_{quote_currency}') and pair.get('trade_status') == 'tradable':
                base = pair_id.replace(f'_{quote_currency}', '')
                tradeable_bases.add(base)

        print(f"[CURRENCY_SYNC] Найдено {len(tradeable_bases)} валют, торгующихся с {quote_currency}")

        # 2. Получаем информацию о валютах (включая символы)
        currencies_url = "https://api.gateio.ws/api/v4/spot/currencies"
        currencies_response = requests.get(currencies_url, timeout=10)

        if currencies_response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"Ошибка API Gate.io (валюты): {currencies_response.status_code}"
            }), 500

        gate_currencies = currencies_response.json()

        # Создаём словарь валют Gate.io по коду
        gate_dict = {}
        for gc in gate_currencies:
            code = gc.get('currency', '').upper()
            if code:
                gate_dict[code] = gc

        added_count = 0
        updated_count = 0
        skipped_count = 0

        # Обрабатываем только существующие валюты пользователя
        for code, curr in current_dict.items():
            # Проверяем, торгуется ли валюта с котируемой
            if code not in tradeable_bases:
                print(f"[CURRENCY_SYNC] {code} не торгуется с {quote_currency}, пропускаем")
                skipped_count += 1
                continue

            # Проверяем, есть ли информация о валюте в Gate.io
            if code not in gate_dict:
                print(f"[CURRENCY_SYNC] {code} не найдена в API Gate.io, пропускаем")
                skipped_count += 1
                continue

            gate_curr = gate_dict[code]

            # Словарь популярных символов криптовалют (можно расширить)
            crypto_symbols = {
                'BTC': '₿', 'ETH': 'Ξ', 'USDT': '₮', 'USDC': '$', 'BNB': 'Ⓑ',
                'XRP': 'Ʀ', 'ADA': '₳', 'DOGE': 'Ð', 'DOT': '●', 'MATIC': 'Ⓜ',
                'SOL': '◎', 'AVAX': '▲', 'LINK': '◬', 'UNI': '🦄', 'ATOM': '⚛',
                'LTC': 'Ł', 'ETC': 'Ξ', 'XLM': '*', 'ALGO': '△', 'VET': 'Ⓥ'
            }

            expected_symbol = crypto_symbols.get(code)
            current_symbol = (curr.get('symbol') or '').strip()

            # Если символ пустой ИЛИ не совпадает с ожидаемым — обновим на стандартный
            if expected_symbol and current_symbol != expected_symbol:
                action = "добавлен" if current_symbol == '' else "обновлён"
                current_dict[code]['symbol'] = expected_symbol
                updated_count += 1
                print(f"[CURRENCY_SYNC] {code}: {action} символ '{expected_symbol}'")
            else:
                skipped_count += 1

        # Сохраняем обновлённый список (порядок сохраняется)
        updated_currencies = [current_dict[c['code']] for c in current_currencies if c['code'] in current_dict]

        if Config.save_currencies(updated_currencies):
            print(f"[CURRENCY_SYNC] Успешно: обновлено {updated_count}, пропущено {skipped_count}")

            # Сохраняем информацию о синхронизации
            sync_info = {
                'timestamp': datetime.now().isoformat(),
                'quote_currency': quote_currency,
                'updated': updated_count,
                'skipped': skipped_count,
                'total': len(updated_currencies),
                'tradeable_count': len(tradeable_bases)
            }
            sync_info['last_update'] = sync_info['timestamp']
            sync_info['total_currencies'] = sync_info['total']
            sync_info['custom_symbols'] = sync_info['updated']

            sync_info_file = os.path.join(os.path.dirname(__file__), 'currency_sync_info.json')
            with open(sync_info_file, 'w', encoding='utf-8') as f:
                json.dump(sync_info, f, ensure_ascii=False, indent=2)

            # Инициализируем разрешения для новых валют (по умолчанию включены)
            try:
                state_manager = get_state_manager()
                state_manager.init_currency_permissions(updated_currencies)
            except Exception:
                # не критично — просто лог
                print("[CURRENCY_SYNC] Не удалось инициализировать permissions в state_manager")

            return jsonify({
                "success": True,
                "updated": updated_count,
                "skipped": skipped_count,
                "total": len(updated_currencies),
                "quote_currency": quote_currency,
                "tradeable_count": len(tradeable_bases),
                "timestamp": sync_info['timestamp']
            })
        else:
            return jsonify({
                "success": False,
                "error": "Не удалось сохранить валюты"
            }), 500

    except requests.exceptions.RequestException as e:
        print(f"[CURRENCY_SYNC] Ошибка сети: {e}")
        return jsonify({
            "success": False,
            "error": f"Ошибка подключения к Gate.io: {str(e)}"
        }), 500
    except Exception as e:
        print(f"[CURRENCY_SYNC] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
