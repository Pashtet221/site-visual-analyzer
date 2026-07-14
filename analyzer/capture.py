from __future__ import annotations

from pathlib import Path
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .models import CaptureResult
from .utils import ensure_dir, normalize_url, slugify


async def make_context(browser, device, config):
    site = config.get('site', {})
    browser_config = config.get('browser', {})
    kwargs = {
        'viewport': {'width': int(device['width']), 'height': int(device['height'])},
        'device_scale_factor': float(device.get('device_scale_factor', 1)),
        'is_mobile': bool(device.get('is_mobile', False)),
        'has_touch': bool(device.get('has_touch', False)),
        'ignore_https_errors': bool(site.get('ignore_https_errors', True)),
    }
    context = await browser.new_context(**kwargs)
    context.set_default_timeout(int(browser_config.get('timeout_ms', 30000)))
    context.set_default_navigation_timeout(int(browser_config.get('navigation_timeout_ms', 45000)))
    cookies = config.get('auth', {}).get('cookies', []) or []
    if cookies:
        await context.add_cookies(cookies)
    return context


async def safe_goto(page, url: str, config: dict):
    """Open slow WooCommerce pages without failing only because load events hang."""
    browser_config = config.get('browser', {})
    timeout = int(browser_config.get('navigation_timeout_ms', 45000))
    response = None

    try:
        response = await page.goto(url, wait_until='commit', timeout=timeout)
    except PlaywrightTimeoutError:
        # A request can be committed and visible even while WooCommerce/CDEK scripts keep loading.
        if page.url in ('about:blank', ''):
            raise

    try:
        await page.locator('body').wait_for(state='attached', timeout=10000)
    except Exception:
        pass

    try:
        await page.wait_for_load_state('domcontentloaded', timeout=12000)
    except Exception:
        pass

    return response


async def login_if_needed(page, config):
    auth = config.get('auth', {})
    if not auth.get('enabled'):
        return
    username = str(auth.get('username', '')).strip()
    password = str(auth.get('password', ''))
    if not username or not password:
        raise ValueError('В credentials.yaml не заполнены auth.username и auth.password')

    login_url = normalize_url(config['site']['base_url'], auth.get('login_url', 'my-account/'))
    await safe_goto(page, login_url, config)
    user_field = page.locator(auth.get('username_selector', '#username')).first
    pass_field = page.locator(auth.get('password_selector', '#password')).first
    submit = page.locator(auth.get('submit_selector', "button[name='login']")).first

    if not await user_field.count() or not await pass_field.count():
        if '/my-account/' in page.url and not await page.locator('form.woocommerce-form-login').count():
            return
        raise RuntimeError('Не найдены поля формы входа. Проверьте селекторы в config.yaml')

    await user_field.fill(username)
    await pass_field.fill(password)
    await submit.click()
    part = str(auth.get('success_url_contains', '')).strip()
    if part:
        try:
            await page.wait_for_url(f'**{part}**', timeout=20000)
        except Exception:
            pass
    await page.wait_for_timeout(int(auth.get('wait_after_login_ms', 1800)))

    error = page.locator('.woocommerce-error, .woocommerce-notices-wrapper .error').first
    if await error.count() and await error.is_visible():
        raise RuntimeError(f'WooCommerce не выполнил вход: {(await error.inner_text()).strip()}')


async def prepare_cart(page, config):
    settings = config.get('prepare', {}).get('add_product_to_cart', {})
    if not settings.get('enabled'):
        return
    product_url = str(settings.get('product_url', '')).strip()
    if not product_url:
        raise ValueError('Не найден товар для добавления в корзину')

    await safe_goto(page, normalize_url(config['site']['base_url'], product_url), config)
    try:
        await page.wait_for_load_state('networkidle', timeout=4000)
    except Exception:
        pass

    for selector, value in (settings.get('variation_selectors', {}) or {}).items():
        loc = page.locator(selector).first
        if await loc.count():
            await loc.select_option(str(value))

    qty = page.locator('input.qty').first
    quantity = int(settings.get('quantity', 1))
    if quantity > 1 and await qty.count():
        await qty.fill(str(quantity))

    button = page.locator(settings.get('add_to_cart_selector', 'button.single_add_to_cart_button')).first
    if not await button.count():
        raise RuntimeError('На странице товара не найдена кнопка добавления в корзину')
    await button.click()
    await page.wait_for_timeout(int(settings.get('wait_after_add_ms', 2200)))


async def page_cleanup(page, config):
    capture = config.get('capture', {})
    interactions = config.get('interactions', {})
    if capture.get('disable_animations', True):
        try:
            await page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important;}')
        except Exception:
            pass

    for selector in interactions.get('click_if_visible', []) or []:
        try:
            locator = page.locator(selector).first
            if await locator.count() and await locator.is_visible():
                await locator.click(timeout=1200)
        except Exception:
            pass

    hide = interactions.get('hide_selectors', []) or []
    remove = interactions.get('remove_selectors', []) or []
    try:
        await page.evaluate(
            '''({hide,remove})=>{hide.forEach(s=>document.querySelectorAll(s).forEach(e=>e.style.setProperty("visibility","hidden","important")));remove.forEach(s=>document.querySelectorAll(s).forEach(e=>e.remove()));}''',
            {'hide': hide, 'remove': remove},
        )
    except Exception:
        pass

    if capture.get('auto_scroll', True):
        try:
            await page.evaluate(
                '''async ({step,delay})=>{let sleep=m=>new Promise(r=>setTimeout(r,m));let h=Math.max(document.body.scrollHeight,document.documentElement.scrollHeight);for(let y=0;y<h;y+=step){scrollTo(0,y);await sleep(delay)}scrollTo(0,0);await sleep(200)}''',
                {'step': int(capture.get('scroll_step_px', 700)), 'delay': int(capture.get('scroll_delay_ms', 120))},
            )
        except Exception:
            pass


async def capture_page(page, target, device_name, output_dir, config, sequence):
    response = None
    screenshot_path = None
    try:
        response = await safe_goto(page, target.url, config)
        await page.wait_for_timeout(int(config.get('capture', {}).get('wait_after_load_ms', 1200)))
        await page_cleanup(page, config)
        title = await page.title()
        final_url = page.url
        directory = ensure_dir(output_dir / device_name)
        screenshot_path = directory / f'{sequence:02d}-{slugify(target.name)}.png'
        await page.screenshot(
            path=str(screenshot_path),
            full_page=bool(config.get('capture', {}).get('full_page', True)),
            type='png',
        )
        return CaptureResult(
            target.name, target.url, target.kind, device_name,
            str(screenshot_path.relative_to(output_dir)), final_url, title, 'ok',
            response.status if response else None,
        )
    except Exception as exc:
        try:
            title = await page.title()
        except Exception:
            title = ''
        return CaptureResult(
            target.name, target.url, target.kind, device_name, None,
            page.url, title, 'error', response.status if response else None,
            f'{type(exc).__name__}: {exc}',
        )
