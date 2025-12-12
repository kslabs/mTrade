from typing import Optional, Dict, Any


class OrderService:
    """Сервис для работы с ордерами (создание и разбор результатов).

    Обёртка вокруг api_client, чтобы разгрузить AutoTrader.
    Ожидается, что api_client имеет методы create_spot_order и т.п.
    """

    def __init__(self, api_client_provider):
        self._api_client_provider = api_client_provider

    def place_limit_order_all_or_nothing(
        self,
        side: str,
        base: str,
        quote: str,
        amount_base: float,
        limit_price: float,
        pair_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Создать лимитный FOK-ордер и вернуть нормализованный результат.

        Это прямой перенос логики из AutoTrader._place_limit_order_all_or_nothing
        без изменения поведения.
        """
        api_client = self._api_client_provider()
        currency_pair = f"{base}_{quote}".upper()

        if not api_client:
            # SIMULATION: считаем исполнено полностью
            print(f"[OrderService][{base}] ⚠️ СИМУЛЯЦИЯ: API клиент не доступен, ордер считается исполненным")
            return {"success": True, "filled": amount_base, "simulated": True}

        # precision берём из pair_info, если оно передано (кеш в AutoTrader),
        # чтобы OrderService не ходил в сеть сам.
        try:
            amt_prec = int((pair_info or {}).get("amount_precision", 8))
        except Exception:
            amt_prec = 8
        try:
            price_prec = int((pair_info or {}).get("price_precision", 8))
        except Exception:
            price_prec = 8

        print(
            f"[OrderService][{base}] 📤 Отправка {side.upper()} FOK-ордера: "
            f"{amount_base:.{amt_prec}f} {base} по цене {limit_price:.{price_prec}f}"
        )

        try:
            result_fok = api_client.create_spot_order(
                currency_pair=currency_pair,
                side=side,
                amount=f"{amount_base:.{amt_prec}f}",
                price=f"{limit_price:.{price_prec}f}",
                order_type="limit",
                time_in_force="fok",
            )

            filled = self._parse_filled_amount(result_fok)

            if filled >= amount_base * 0.999:
                print(f"[OrderService][{base}] ✅ FOK ордер исполнен: {filled:.{amt_prec}f} {base}")
                return {"success": True, "filled": filled, "order": result_fok, "tif": "fok"}
            else:
                print(
                    f"[OrderService][{base}] ❌ FOK не исполнен полностью: "
                    f"{filled:.{amt_prec}f}/{amount_base:.{amt_prec}f}"
                )
                # Не принимаем частичное исполнение как окончательное — вернём информацию о заполнении
                return {"success": False, "filled": filled, "order": result_fok, "tif": "fok_partial"}

        except Exception as e:
            print(f"[OrderService][{base}] ❌ FOK ошибка: {e}")
            return {"success": False, "filled": 0.0, "error": str(e)}

    def place_limit_fok_sell(
        self,
        base: str,
        quote: str,
        amount_base: float,
        limit_price: float,
        pair_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Удобный синоним для sell-FOK (используется в _try_sell)."""
        return self.place_limit_order_all_or_nothing(
            side="sell",
            base=base,
            quote=quote,
            amount_base=amount_base,
            limit_price=limit_price,
            pair_info=pair_info,
        )

    def _parse_filled_amount(self, order_result: dict) -> float:
        """Ровно та же логика, что была в AutoTrader._parse_filled_amount."""
        if not isinstance(order_result, dict):
            return 0.0
        try:
            order_type = order_result.get("type", "")
            if order_type == "market":
                # For market orders, use filled_amount (base amount for both buy and sell)
                return float(order_result.get("filled_amount", 0))
            else:
                # For limit orders, amount - left
                amount = float(order_result.get("amount", 0))
                left = float(order_result.get("left", 0))
                filled = amount - left if amount > 0 else float(order_result.get("filled_total", 0))
                if filled < 0:
                    filled = 0.0
                return filled
        except Exception:
            return 0.0
