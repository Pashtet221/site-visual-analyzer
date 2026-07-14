from __future__ import annotations

import re
from dataclasses import dataclass

from .capture import safe_goto
from .utils import normalize_url


@dataclass
class CreatedOrder:
    url: str
    order_number: str


async def _fill(page, selector: str, value: str) -> None:
    if not value:
        return
    locator = page.locator(selector).first
    if await locator.count():
        await locator.fill(str(value))


async def _select(page, selector: str, value: str) -> None:
    if not value:
        return
    locator = page.locator(selector).first
    if await locator.count():
        try:
            await locator.select_option(str(value))
        except Exception:
            pass


async def create_test_order(page, config: dict) -> CreatedOrder | None:
    settings = config.get('order_flow', {})
    if not settings.get('enabled'):
        return None

    checkout_url = normalize_url(config['site']['base_url'], settings.get('checkout_url', '/checkout/'))
    await safe_goto(page, checkout_url, config)
    await page.wait_for_timeout(int(settings.get('wait_before_fill_ms', 3500)))

    billing = settings.get('billing', {})
    fields = {
        '#billing_first_name': billing.get('first_name', 'Тест'),
        '#billing_last_name': billing.get('last_name', 'Заказ'),
        '#billing_company': billing.get('company', ''),
        '#billing_address_1': billing.get('address_1', 'Тестовая улица, 1'),
        '#billing_address_2': billing.get('address_2', ''),
        '#billing_city': billing.get('city', 'Москва'),
        '#billing_postcode': billing.get('postcode', '101000'),
        '#billing_phone': billing.get('phone', '+79990000000'),
        '#billing_email': billing.get('email', ''),
        '#order_comments': settings.get('order_comments', 'Автоматический тестовый заказ. Можно удалить.'),
    }
    for selector, value in fields.items():
        await _fill(page, selector, str(value or ''))

    await _select(page, '#billing_country', billing.get('country', 'RU'))
    await _select(page, '#billing_state', billing.get('state', ''))

    # WooCommerce checkout plugins often need time to recalculate shipping/payment.
    try:
        await page.locator('body').click(position={'x': 5, 'y': 5})
    except Exception:
        pass
    await page.wait_for_timeout(int(settings.get('wait_after_fill_ms', 4500)))

    payment_id = str(settings.get('payment_method', 'cod')).strip()
    payment = page.locator(f'#payment_method_{payment_id}').first
    if await payment.count():
        await payment.check(force=True)
        await page.wait_for_timeout(1000)

    terms = page.locator('#terms').first
    if await terms.count() and not await terms.is_checked():
        await terms.check(force=True)

    place_order_selector = settings.get('place_order_selector', '#place_order')
    place_order = page.locator(place_order_selector).first
    if not await place_order.count():
        raise RuntimeError('Не найдена кнопка оформления заказа #place_order')

    await place_order.click(force=True)
    success_pattern = str(settings.get('success_url_contains', '/order-received/'))
    try:
        await page.wait_for_url(f'**{success_pattern}**', timeout=int(settings.get('submit_timeout_ms', 90000)))
    except Exception:
        errors = page.locator('.woocommerce-error, .woocommerce-NoticeGroup-checkout').first
        if await errors.count() and await errors.is_visible():
            raise RuntimeError('Заказ не оформлен: ' + (await errors.inner_text()).strip())
        if success_pattern not in page.url:
            raise RuntimeError(f'После отправки формы не открылась страница заказа. Текущий URL: {page.url}')

    await page.wait_for_timeout(int(settings.get('wait_after_submit_ms', 3000)))
    order_number = ''
    number_locator = page.locator('.woocommerce-order-overview__order strong, .woocommerce-order-overview__order').first
    if await number_locator.count():
        raw = (await number_locator.inner_text()).strip()
        match = re.search(r'\d+', raw)
        order_number = match.group(0) if match else raw
    if not order_number:
        match = re.search(r'/order-received/(\d+)', page.url)
        if match:
            order_number = match.group(1)

    return CreatedOrder(url=page.url, order_number=order_number)
