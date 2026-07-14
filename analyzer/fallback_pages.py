from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FallbackPage:
    name: str
    path: Path
    kind: str
    source: str


def _write(path: Path, title: str, body: str) -> Path:
    path.write_text(f'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f4f5f7;color:#1f2933;font-family:Arial,Helvetica,sans-serif;line-height:1.45}}a{{color:#2f5d50}}.page{{max-width:1120px;margin:0 auto;padding:32px 18px}}.notice{{padding:18px 22px;border-left:5px solid #6f8f72;background:#fff;border-radius:10px;box-shadow:0 8px 30px rgba(15,23,42,.08)}}.card{{margin-top:22px;background:#fff;border:1px solid #e5e7eb;border-radius:16px;box-shadow:0 12px 34px rgba(15,23,42,.07);overflow:hidden}}.card__body{{padding:24px}}h1{{font-size:32px;margin:0 0 12px}}h2{{font-size:22px;margin:0 0 14px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:14px 12px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}th{{background:#f8fafc;font-weight:700}}.summary{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:22px}}.summary div{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px}}.summary b{{display:block;font-size:12px;color:#64748b;text-transform:uppercase;margin-bottom:6px}}.total{{font-size:20px;font-weight:700}}.muted{{color:#64748b}}.badge{{display:inline-block;padding:5px 10px;border-radius:999px;background:#ecfdf5;color:#166534;font-weight:700;font-size:13px}}.mail-shell{{max-width:760px;margin:0 auto;background:#fff}}.mail-head{{padding:32px;background:#2f5d50;color:#fff;text-align:center}}.mail-body{{padding:30px}}.button{{display:inline-block;background:#2f5d50;color:#fff;text-decoration:none;padding:13px 20px;border-radius:8px;font-weight:700}}@media(max-width:760px){{.summary{{grid-template-columns:1fr}}.page{{padding:18px 10px}}h1{{font-size:25px}}th,td{{padding:10px 8px}}}}
  </style>
</head>
<body>{body}</body>
</html>''', encoding='utf-8')
    return path


def create_fallback_order_received(output_dir: Path, order_number: str = '1001') -> FallbackPage:
    number = html.escape(order_number or '1001')
    body = f'''<main class="page">
  <section class="notice"><span class="badge">Заказ принят</span><h1>Спасибо. Ваш заказ был получен.</h1><p class="muted">Это локальный макет с тестовыми данными для проверки вёрстки страницы «Заказ принят», если реальный заказ не удалось оформить.</p></section>
  <section class="summary">
    <div><b>Номер заказа</b>№{number}</div><div><b>Дата</b>14 июля 2026</div><div><b>Email</b>test@example.com</div><div><b>Итого</b><span class="total">12 450 ₽</span></div>
  </section>
  <section class="card"><div class="card__body"><h2>Детали заказа</h2><table><thead><tr><th>Товар</th><th>Количество</th><th>Сумма</th></tr></thead><tbody><tr><td>Демо-товар для проверки карточек</td><td>1</td><td>8 900 ₽</td></tr><tr><td>Дополнительная услуга</td><td>1</td><td>3 550 ₽</td></tr><tr><th colspan="2">Итого</th><th>12 450 ₽</th></tr></tbody></table></div></section>
  <section class="card"><div class="card__body"><h2>Платёжный адрес</h2><p>Тест Заказ<br>Тестовая улица, 1<br>Москва, 101000<br>+7 999 000-00-00</p></div></section>
</main>'''
    return FallbackPage('Заказ принят — макет', _write(output_dir / 'fallback-order-received.html', 'Заказ принят — макет', body), 'order-received', 'fallback')


def create_fallback_order_email(output_dir: Path, order_number: str = '1001') -> FallbackPage:
    number = html.escape(order_number or '1001')
    body = f'''<main class="page"><section class="mail-shell"><header class="mail-head"><h1>Ваш заказ принят</h1><p>Тестовое письмо для проверки адаптивной вёрстки email</p></header><section class="mail-body"><p>Здравствуйте, Тест!</p><p>Мы получили заказ <b>№{number}</b>. Ниже показаны произвольные демо-данные: они нужны только для скриншота письма.</p><table><thead><tr><th>Товар</th><th>Кол-во</th><th>Сумма</th></tr></thead><tbody><tr><td>Демо-товар для проверки письма</td><td>1</td><td>8 900 ₽</td></tr><tr><td>Доставка</td><td>1</td><td>600 ₽</td></tr><tr><th colspan="2">Итого</th><th>9 500 ₽</th></tr></tbody></table><p style="margin-top:26px"><a class="button" href="#">Посмотреть заказ</a></p><p class="muted">Адрес доставки: Москва, Тестовая улица, 1.</p></section></section></main>'''
    return FallbackPage('Письмо о заказе — макет', _write(output_dir / 'fallback-order-email.html', 'Письмо о заказе — макет', body), 'order-email', 'fallback')
