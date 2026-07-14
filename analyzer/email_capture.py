from __future__ import annotations

import email
import html
import imaplib
import re
import ssl
import time
from email.header import decode_header, make_header
from pathlib import Path


def _decoded(value: str | None) -> str:
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_body(message: email.message.Message) -> str:
    html_body = ''
    text_body = ''
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        content_type = part.get_content_type()
        disposition = str(part.get('Content-Disposition', '')).lower()
        if 'attachment' in disposition:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or 'utf-8'
        try:
            decoded = payload.decode(charset, errors='replace')
        except Exception:
            decoded = payload.decode('utf-8', errors='replace')
        if content_type == 'text/html' and not html_body:
            html_body = decoded
        elif content_type == 'text/plain' and not text_body:
            text_body = decoded
    if html_body:
        return html_body
    return '<pre style="white-space:pre-wrap">' + html.escape(text_body) + '</pre>'


def fetch_order_email(config: dict, order_number: str, output_dir: Path) -> Path | None:
    settings = config.get('email_capture', {})
    if not settings.get('enabled'):
        return None

    host = str(settings.get('imap_host', '')).strip()
    username = str(settings.get('username', '')).strip()
    password = str(settings.get('password', ''))
    if not host or not username or not password:
        raise ValueError('В credentials.yaml не заполнены email_capture.imap_host, username и password')

    port = int(settings.get('imap_port', 993))
    mailbox = str(settings.get('mailbox', 'INBOX'))
    timeout_seconds = int(settings.get('wait_timeout_seconds', 90))
    interval = max(3, int(settings.get('poll_interval_seconds', 5)))
    subject_contains = str(settings.get('subject_contains', '')).strip()
    sender_contains = str(settings.get('sender_contains', '')).strip().lower()
    search_limit = int(settings.get('search_last_messages', 40))

    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        client = None
        try:
            context = ssl.create_default_context()
            client = imaplib.IMAP4_SSL(host, port, ssl_context=context)
            client.login(username, password)
            client.select(mailbox)
            status, data = client.search(None, 'ALL')
            if status != 'OK':
                raise RuntimeError('IMAP search завершился ошибкой')
            ids = data[0].split()[-search_limit:]
            for message_id in reversed(ids):
                status, message_data = client.fetch(message_id, '(RFC822)')
                if status != 'OK' or not message_data:
                    continue
                raw = next((item[1] for item in message_data if isinstance(item, tuple)), None)
                if not raw:
                    continue
                message = email.message_from_bytes(raw)
                subject = _decoded(message.get('Subject'))
                sender = _decoded(message.get('From'))
                searchable = f'{subject} {sender}'
                if order_number and order_number not in searchable:
                    # Some WooCommerce templates mention the order only inside the body.
                    body_preview = _extract_body(message)
                    if order_number not in body_preview:
                        continue
                if subject_contains and subject_contains.lower() not in subject.lower():
                    continue
                if sender_contains and sender_contains not in sender.lower():
                    continue

                body = _extract_body(message)
                wrapped = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(subject)}</title><style>body{{margin:0;background:#f3f4f6;font-family:Arial,sans-serif}}.mail-meta{{max-width:900px;margin:24px auto 0;padding:18px 22px;background:#fff;border:1px solid #ddd;border-radius:12px}}.mail-meta h1{{font-size:20px;margin:0 0 10px}}.mail-meta p{{margin:5px 0;color:#555;overflow-wrap:anywhere}}.mail-body{{max-width:900px;margin:14px auto 30px;background:#fff;overflow:hidden;border:1px solid #ddd;border-radius:12px}}@media(max-width:950px){{.mail-meta,.mail-body{{margin-left:10px;margin-right:10px}}}}</style></head><body><section class="mail-meta"><h1>{html.escape(subject)}</h1><p><b>От:</b> {html.escape(sender)}</p><p><b>Кому:</b> {html.escape(_decoded(message.get('To')))}</p></section><section class="mail-body">{body}</section></body></html>'''
                path = output_dir / 'order-email.html'
                path.write_text(wrapped, encoding='utf-8')
                return path
        except Exception as exc:
            last_error = exc
        finally:
            try:
                if client:
                    client.logout()
            except Exception:
                pass
        time.sleep(interval)

    if last_error:
        raise RuntimeError(f'Письмо о заказе не найдено: {last_error}')
    raise RuntimeError('Письмо о заказе не найдено за отведённое время')
