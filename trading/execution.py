"""ساخت درگاه سفارش واقعی، بدون حدس‌زدن بدنهٔ سفارش صرافی.

مسیر زنده تا وقتی یک اجراکنندهٔ تأییدشده تزریق نشود، باید بلند شکست
بخورد. payload سفارش LBank یا Toobit اینجا ساخته نمی‌شود؛ سند رسمی
آن را تأیید نکرده و یک سفارش حدسی از نبود سفارش بدتر است.
"""

from __future__ import annotations

from typing import Any

from trading.auto_trader import LiveOrderGateway


def build_gateway(
    exchange_name: str,
    executor: Any | None = None,
) -> LiveOrderGateway:
    """
    درگاه سفارش برای موتور خودکار.

    `executor=None` یعنی زیرساخت وصل است ولی ارسال واقعی هنوز ممنوع است.
    """
    return LiveOrderGateway(exchange_name, executor=executor)
