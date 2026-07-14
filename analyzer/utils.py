import re, unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse


def normalize_url(base_url, value):
    """Resolve URL relative to the configured site root, including subdirectory installs.

    Example:
      base_url = http://host.test/gelikon/
      /cart/   -> http://host.test/gelikon/cart/
      cart/    -> http://host.test/gelikon/cart/
      https://other.test/x -> unchanged absolute URL
    """
    value = str(value or '').strip()
    base = str(base_url or '').strip()
    if not value:
        value = '.'

    parsed_value = urlparse(value)
    if parsed_value.scheme in ('http', 'https'):
        url = value
    elif value.startswith('//'):
        scheme = urlparse(base).scheme or 'https'
        url = f'{scheme}:{value}'
    else:
        base_with_slash = base.rstrip('/') + '/'
        # A leading slash means "from the configured site root", not from domain root.
        relative = value.lstrip('/')
        url = urljoin(base_with_slash, relative or '.')

    p = urlparse(url)
    path = re.sub(r'/{2,}', '/', p.path or '/')
    if value.endswith('/') and not path.endswith('/'):
        path += '/'
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, '', p.query, ''))


def same_domain(a, b):
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


def is_inside_site(url, base_url):
    if not same_domain(url, base_url):
        return False
    site_path = urlparse(base_url).path.rstrip('/') + '/'
    path = urlparse(url).path.rstrip('/') + '/'
    return path.startswith(site_path) or path == site_path


def slugify(value, max_length=90):
    value = unicodedata.normalize('NFKD', value).encode('ascii','ignore').decode('ascii')
    value = re.sub(r'https?://', '', value, flags=re.I)
    value = re.sub(r'[^a-zA-Z0-9_-]+', '-', value).strip('-_').lower()
    return (value[:max_length].rstrip('-_') or 'page')


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path
