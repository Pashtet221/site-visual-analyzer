from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .capture import login_if_needed, safe_goto
from .utils import normalize_url, slugify


DEFAULT_EMAILS = [
    ('new_order', 'Новый заказ (администратору)'),
    ('customer_processing_order', 'Заказ в обработке (клиенту)'),
    ('customer_completed_order', 'Выполненный заказ (клиенту)'),
    ('customer_invoice', 'Счёт / ожидание оплаты (клиенту)'),
    ('customer_refunded_order', 'Возврат средств (клиенту)'),
    ('cancelled_order', 'Отменённый заказ (администратору)'),
    ('customer_on_hold_order', 'Заказ получен / ожидание оплаты (клиенту)'),
]


@dataclass
class RenderedWooEmail:
    name: str
    path: Path
    email_type: str


def _with_type(url: str, email_type: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query['type'] = [email_type]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


async def render_woocommerce_email_previews(page, config: dict, output_dir: Path, order_number: str = '') -> list[RenderedWooEmail]:
    settings = config.get('woocommerce_email_capture', {})
    if not settings.get('enabled'):
        return []

    await login_if_needed(page, config)
    settings_url = normalize_url(
        config['site']['base_url'],
        settings.get('settings_url', '/wp-admin/admin.php?page=wc-settings&tab=email'),
    )
    await safe_goto(page, settings_url, config)
    await page.wait_for_timeout(int(settings.get('wait_after_open_ms', 1200)))

    preview = page.locator('a[href*="preview_woocommerce_mail"]').first
    if not await preview.count():
        raise RuntimeError('Не найдена ссылка предпросмотра WooCommerce email. Проверьте права пользователя и версию WooCommerce.')

    preview_href = await preview.get_attribute('href')
    if not preview_href:
        raise RuntimeError('Ссылка предпросмотра WooCommerce email пустая')
    preview_url = normalize_url(config['site']['base_url'], preview_href)

    configured = settings.get('emails') or DEFAULT_EMAILS
    emails: list[tuple[str, str]] = []
    for item in configured:
        if isinstance(item, dict):
            emails.append((str(item.get('type', '')).strip(), str(item.get('name', '')).strip()))
        else:
            emails.append((str(item[0]).strip(), str(item[1]).strip()))
    emails = [(email_type, name or email_type) for email_type, name in emails if email_type]

    rendered: list[RenderedWooEmail] = []
    for email_type, name in emails:
        url = _with_type(preview_url, email_type)
        response = await safe_goto(page, url, config)
        status = response.status if response else 200
        if status >= 400:
            raise RuntimeError(f'WooCommerce вернул HTTP {status} для шаблона {email_type}')
        await page.wait_for_timeout(int(settings.get('wait_after_preview_ms', 500)))
        html_content = await page.content()
        body_text = await page.locator('body').inner_text()
        if 'Security check' in body_text or 'Invalid email type' in body_text:
            raise RuntimeError(f'WooCommerce не смог отрисовать шаблон {email_type}: {body_text[:200]}')
        title = f'Email WooCommerce — {name}'
        path = output_dir / f'woocommerce-email-{slugify(email_type)}.html'
        path.write_text(html_content, encoding='utf-8')
        rendered.append(RenderedWooEmail(title, path, email_type))
    return rendered
