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
                cycle_obj = AUTO_TRADER.cycles.get(base_currency)
                if cycle_obj:
                    # Преобразуем TradingCycle в словарь для совместимости
                    cycle = {
                        'active': cycle_obj.is_active(),
                        'active_step': cycle_obj.active_step,
                        'start_price': cycle_obj.start_price,
                        'last_buy_price': cycle_obj.last_buy_price,
                        'total_invested_usd': cycle_obj.total_invested_usd,
                        'base_volume': cycle_obj.base_volume,
                        'table': cycle_obj.table
                    }
                    table = cycle_obj.table if cycle_obj.table else None
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

        # Обрабатываем данные таблицы (независимо от активного цикла)
        if table and len(table) > 0:
            active_step = cycle.get('active_step', -1) if cycle else -1
            autotrade_levels['active_cycle'] = bool(cycle and cycle.get('active'))
            autotrade_levels['active_step'] = active_step if active_step >= 0 else None
            autotrade_levels['total_steps'] = (len(table) - 1) if len(table) > 0 else None

            # Данные из активного цикла (если есть)
            if cycle:
                autotrade_levels['start_price'] = cycle.get('start_price') or None
                autotrade_levels['last_buy_price'] = cycle.get('last_buy_price') or None
                autotrade_levels['invested_usd'] = cycle.get('total_invested_usd') or None
                autotrade_levels['base_volume'] = cycle.get('base_volume') or None
            else:
                # Если цикла нет - используем первую строку таблицы как стартовую
                autotrade_levels['start_price'] = table[0].get('rate') if table else None

            # Расчёт роста от стартовой цены
            start_price = autotrade_levels['start_price']
            if start_price and price:
                try:
                    autotrade_levels['current_growth_pct'] = (price - start_price) / start_price * 100.0
                except Exception:
                    autotrade_levels['current_growth_pct'] = None

            # Определяем текущий шаг: активный из цикла или 0 (стартовый)
            current_step = active_step if active_step >= 0 else 0

            # Данные текущего шага (всегда показываем, даже если цикл неактивен)
            if current_step < len(table):
                row = table[current_step]
                autotrade_levels['breakeven_price'] = row.get('breakeven_price')
                autotrade_levels['breakeven_pct'] = row.get('breakeven_pct')
                autotrade_levels['target_sell_delta_pct'] = row.get('target_delta_pct')

                # Расчёт цены продажи от цены безубыточности
                breakeven = row.get('breakeven_price')
                if breakeven and row.get('target_delta_pct'):
                    try:
                        target_pct = row['target_delta_pct']
                        autotrade_levels['sell_price'] = breakeven * (1 + target_pct / 100.0)
                    except Exception:
                        pass

                # Прогресс до продажи
                if autotrade_levels['current_growth_pct'] is not None and row.get('target_delta_pct'):
                    tgt = row['target_delta_pct']
                    cg = autotrade_levels['current_growth_pct']
                    autotrade_levels['progress_to_sell'] = max(0.0, min(1.0, cg / tgt)) if tgt > 0 else None

            # Следующий шаг покупки (для активного цикла - следующий, для неактивного - текущий стартовый)
            next_step = current_step + 1 if autotrade_levels['active_cycle'] else current_step

            if next_step < len(table):
                nrow = table[next_step]
                autotrade_levels['next_rebuy_step'] = next_step
                autotrade_levels['next_rebuy_decrease_step_pct'] = abs(nrow.get('decrease_step_pct', 0))
                autotrade_levels['next_rebuy_cumulative_drop_pct'] = nrow.get('cumulative_decrease_pct')
                autotrade_levels['next_rebuy_purchase_usd'] = nrow.get('purchase_usd')

                # Расчёт цены следующей покупки
                if autotrade_levels['active_cycle'] and cycle and cycle.get('last_buy_price') and nrow.get('decrease_step_pct'):
                    try:
                        last_buy = cycle['last_buy_price']
                        decrease_pct = abs(nrow['decrease_step_pct'])
                        autotrade_levels['next_buy_price'] = last_buy * (1 - decrease_pct / 100.0)
                    except Exception:
                        pass
                else:
                    autotrade_levels['next_buy_price'] = nrow.get('rate')
                    if not autotrade_levels['last_buy_price'] and start_price:
                        autotrade_levels['last_buy_price'] = start_price

            # Ограниченный вывод таблицы
            if include_table:
                trimmed = []
                for r in table:
                    trimmed.append({
                        'step': r.get('step'),
                        'rate': r.get('rate'),
                        'purchase_usd': r.get('purchase_usd'),
                        'breakeven_price': r.get('breakeven_price'),
                        'target_delta_pct': r.get('target_delta_pct'),
                        'decrease_step_pct': r.get('decrease_step_pct'),
                        'cumulative_decrease_pct': r.get('cumulative_decrease_pct')
                    })
                autotrade_levels['table'] = trimmed

        # Attach last diagnostics/decision from AutoTrader if available
        try:
            from mTrade import AUTO_TRADER
            if AUTO_TRADER and hasattr(AUTO_TRADER, 'last_diagnostics'):
                dd = AUTO_TRADER.last_diagnostics.get(base_currency.upper())
                if dd:
                    # last_decision is the last diagnostic result (none/sell/buy/attempts)
                    # We will filter stale decisions: if the last decision is a 'sell' but
                    # current price is below computed sell_price, treat it as cleared so
                    # UI does not stay green. Similarly for 'buy' when price is above next_buy_price.
                    raw_decision = dd.get('last_decision')
                    filtered_decision = raw_decision
                    # last_detected contains detection events (sell_detected/buy_detected)
                    # Filter out stale detections: if a previous sell_detected exists but current
                    # price fell back below the recorded sell_level, treat it as not detected.
                    raw_detected = dd.get('last_detected') or {}
                    filtered = {}
                    # only include sell detection if current price still >= recorded sell_level
                    sell_payload = raw_detected.get('sell')
                    try:
                        if sell_payload and sell_payload.get('sell_level') is not None and indicators.get('price') is not None:
                            if float(indicators.get('price')) >= float(sell_payload.get('sell_level')):
                                filtered['sell'] = sell_payload
                        elif sell_payload and sell_payload.get('sell_level') is None:
                            # if there's no explicit sell_level in payload, keep it (conservative)
                            filtered['sell'] = sell_payload
                    except Exception:
                        # if parsing fails — safer to drop stale detection
                        pass

                    # include buy detection only if current_price is at or below next_buy_price (if we have it)
                    buy_payload = raw_detected.get('buy')
                    try:
                        if buy_payload and autotrade_levels.get('next_buy_price') is not None and indicators.get('price') is not None:
                            if float(indicators.get('price')) <= float(autotrade_levels.get('next_buy_price')):
                                filtered['buy'] = buy_payload
                        elif buy_payload:
                            # if we cannot check next_buy_price, keep the payload
                            filtered['buy'] = buy_payload
                    except Exception:
                        pass

                    autotrade_levels['last_detected'] = filtered or None

                    # Now apply filtering for diagnostic_decision based on price vs configured prices
                    if raw_decision and isinstance(raw_decision, dict):
                        try:
                            rdec = (raw_decision.get('decision') or '').lower()
                            # if sell decision but sell_price is known and price below—clear
                            if rdec == 'sell' and autotrade_levels.get('sell_price') is not None and indicators.get('price') is not None:
                                if float(indicators.get('price')) < float(autotrade_levels.get('sell_price')):
                                    filtered_decision = None
                            # if buy decision but next_buy_price is known and price above—clear
                            if rdec == 'buy' and autotrade_levels.get('next_buy_price') is not None and indicators.get('price') is not None:
                                if float(indicators.get('price')) > float(autotrade_levels.get('next_buy_price')):
                                    filtered_decision = None
                        except Exception:
                            # keep original if parsing fails
                            filtered_decision = raw_decision

                    autotrade_levels['diagnostic_decision'] = filtered_decision
                else:
                    autotrade_levels['diagnostic_decision'] = None
                    autotrade_levels['last_detected'] = None
        except Exception:
            autotrade_levels['diagnostic_decision'] = None
            autotrade_levels['last_detected'] = None

        # Add derived detector flags (should_sell / should_buy) so frontend can detect
        # sell/buy conditions even if runtime diagnostics not present
        try:
            current_price = autotrade_levels.get('current_price')
            sell_price = autotrade_levels.get('sell_price')
            next_buy_price = autotrade_levels.get('next_buy_price')
            active_cycle = bool(autotrade_levels.get('active_cycle'))
            base_volume = autotrade_levels.get('base_volume') or 0

            autotrade_levels['should_sell'] = False
            autotrade_levels['should_buy'] = False

            if active_cycle and base_volume and sell_price is not None and current_price is not None:
                try:
                    autotrade_levels['should_sell'] = float(current_price) >= float(sell_price)
                except Exception:
                    autotrade_levels['should_sell'] = False

            if active_cycle and next_buy_price is not None and current_price is not None:
                try:
                    autotrade_levels['should_buy'] = float(current_price) <= float(next_buy_price)
                except Exception:
                    autotrade_levels['should_buy'] = False
        except Exception:
            pass

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
