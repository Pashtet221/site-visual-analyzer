from __future__ import annotations

import argparse
import asyncio
import shutil
import webbrowser
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

from .capture import capture_page, login_if_needed, make_context, prepare_cart
from .discovery import discover_pages
from .email_capture import fetch_order_email
from .models import PageTarget
from .order_flow import create_test_order
from .report import build_html_report, write_json
from .utils import ensure_dir, normalize_url


def args():
    parser = argparse.ArgumentParser(description='Скриншоты основных страниц сайта')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--credentials', default='credentials.yaml')
    parser.add_argument('--url', default='')
    parser.add_argument('--clean', action='store_true')
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--skip-order', action='store_true', help='Не оформлять тестовый заказ')
    return parser.parse_args()


def deep_merge(target, source):
    for key, value in (source or {}).items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def load_credentials(config, config_path, credentials_arg):
    credentials_path = Path(credentials_arg)
    if not credentials_path.is_absolute():
        credentials_path = config_path.parent / credentials_path
    if not credentials_path.exists():
        return config
    credentials = yaml.safe_load(credentials_path.read_text(encoding='utf-8')) or {}
    return deep_merge(config, credentials)


def manual(config):
    base = config['site']['base_url']
    output = []
    for index, item in enumerate(config.get('manual_pages', []) or [], 1):
        if item and item.get('url'):
            output.append(PageTarget(
                str(item.get('name') or f'Страница {index}'),
                normalize_url(base, str(item['url'])),
                str(item.get('kind') or 'manual'),
                'manual',
            ))
    return output


def merge(*groups):
    output = []
    seen = set()
    for group in groups:
        for item in group:
            if item.url not in seen:
                seen.add(item.url)
                output.append(item)
    return output


def choose_cart_product(config, targets):
    settings = config.setdefault('prepare', {}).setdefault('add_product_to_cart', {})
    if not settings.get('enabled') or str(settings.get('product_url', '')).strip():
        return
    product = next((item for item in targets if item.kind == 'product'), None)
    if product:
        settings['product_url'] = product.url
        print('Товар для корзины выбран автоматически:', product.url)


async def run(arguments):
    config_path = Path(arguments.config).resolve()
    config = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
    config = load_credentials(config, config_path, arguments.credentials)
    if arguments.url:
        config['site']['base_url'] = arguments.url
    if arguments.headed:
        config.setdefault('browser', {})['headless'] = False
    if arguments.skip_order:
        config.setdefault('order_flow', {})['enabled'] = False

    config['site']['base_url'] = normalize_url(config['site']['base_url'], '.')
    output_dir = Path(config['site'].get('output_dir', 'report'))
    if not output_dir.is_absolute():
        output_dir = config_path.parent / output_dir
    if arguments.clean and output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_dir(output_dir)

    print('Сайт:', config['site']['base_url'])
    print('Отчёт:', output_dir)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=bool(config.get('browser', {}).get('headless', True))
        )

        context = await make_context(browser, config['devices']['desktop'], config)
        page = await context.new_page()
        try:
            await login_if_needed(page, config)
            if config.get('auth', {}).get('enabled'):
                print('Авторизация выполнена.')
        except Exception as exc:
            print('Ошибка авторизации во время поиска страниц:', exc)

        found = []
        if config.get('discovery', {}).get('enabled', True):
            print('Поиск основных страниц...')
            found = await discover_pages(page, config)

        initial_targets = merge(manual(config), found) or [
            PageTarget('Главная', config['site']['base_url'], 'home', 'fallback')
        ]
        choose_cart_product(config, initial_targets)

        try:
            await prepare_cart(page, config)
            print('Корзина подготовлена.')
        except Exception as exc:
            print('Ошибка подготовки корзины:', exc)

        found_after = []
        if config.get('discovery', {}).get('enabled', True):
            found_after = await discover_pages(page, config)

        targets = merge(manual(config), found, found_after) or initial_targets

        # Create exactly one order and reuse its receipt URL for every viewport.
        created_order = None
        try:
            created_order = await create_test_order(page, config)
            if created_order:
                label = f'Заказ принят №{created_order.order_number}' if created_order.order_number else 'Заказ принят'
                targets = merge(targets, [PageTarget(label, created_order.url, 'order-received', 'created-order')])
                print('Тестовый заказ оформлен:', created_order.order_number or created_order.url)
        except Exception as exc:
            print('Ошибка автоматического оформления заказа:', exc)

        await context.close()

        # Email is fetched after WooCommerce has generated it. IMAP polling runs in a worker thread.
        if created_order and config.get('email_capture', {}).get('enabled'):
            try:
                print('Ожидание письма о заказе...')
                email_path = await asyncio.to_thread(
                    fetch_order_email, config, created_order.order_number, output_dir
                )
                if email_path:
                    targets = merge(targets, [
                        PageTarget('Письмо о заказе', email_path.resolve().as_uri(), 'order-email', 'imap')
                    ])
                    print('Письмо найдено и добавлено в отчёт.')
            except Exception as exc:
                print('Ошибка получения письма:', exc)

        write_json(output_dir / 'pages.json', [item.to_dict() for item in targets])
        print('Найдено страниц:', len(targets))
        for item in targets:
            print(' -', item.name, item.url)

        results = []
        for device_name, device in config.get('devices', {}).items():
            print(f'[{device_name}] запуск')
            context = await make_context(browser, device, config)
            page = await context.new_page()
            try:
                await login_if_needed(page, config)
            except Exception as exc:
                print(f'[{device_name}] ошибка авторизации:', exc)
            try:
                # The initial order emptied the cart, so each viewport gets a fresh cart.
                await prepare_cart(page, config)
            except Exception as exc:
                print(f'[{device_name}] ошибка подготовки корзины:', exc)

            for index, target in enumerate(targets, 1):
                print(f'[{device_name}] {index}/{len(targets)} {target.name}')
                results.append(await capture_page(
                    page, target, device_name, output_dir, config, index
                ))
            await context.close()

        await browser.close()

    write_json(output_dir / 'results.json', [item.to_dict() for item in results])
    write_json(output_dir / 'errors.json', [item.to_dict() for item in results if item.status == 'error'])
    report = build_html_report(
        output_dir, results,
        config.get('report', {}).get('title', 'Визуальный анализ сайта'),
    )
    print('Готово:', report)
    if config.get('report', {}).get('open_after_finish', True):
        try:
            webbrowser.open(report.resolve().as_uri())
        except Exception:
            pass


def main():
    try:
        asyncio.run(run(args()))
    except KeyboardInterrupt:
        raise SystemExit(130)
