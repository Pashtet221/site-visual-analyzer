import re
from collections import defaultdict
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from .models import PageTarget
from .utils import normalize_url, same_domain, is_inside_site

LABELS = {'home':'Главная','shop':'Каталог','category':'Категория','product':'Карточка товара','cart':'Корзина','checkout':'Оформление заказа','account':'Личный кабинет','orders':'Заказы','order':'Страница заказа','contacts':'Контакты','blog':'Блог','other':'Другая страница'}


def classify_url(url, base_url):
    path = urlparse(url).path.lower().rstrip('/') or '/'
    base_path = urlparse(base_url).path.lower().rstrip('/') or '/'
    if path in ('/', base_path): return 'home'
    rules = [
      ('checkout',[r'/checkout(?:/|$)',r'/order-received(?:/|$)',r'/oformlen']),
      ('cart',[r'/cart(?:/|$)',r'/basket(?:/|$)',r'/korzin']),
      ('orders',[r'/my-account/orders(?:/|$)',r'/account/orders(?:/|$)']),
      ('order',[r'/view-order/',r'/order/\d+',r'/orders/\d+']),
      ('account',[r'/my-account(?:/|$)',r'/account(?:/|$)',r'/cabinet(?:/|$)']),
      ('product',[r'/product/',r'/tovar/',r'/products/[^/]+/?$']),
      ('category',[r'/product-category/',r'/category/',r'/catalog/.+',r'/shop/.+',r'/collections/']),
      ('shop',[r'/shop(?:/|$)',r'/catalog(?:/|$)',r'/products(?:/|$)']),
      ('contacts',[r'/contacts?(?:/|$)',r'/kontakty?(?:/|$)']),
      ('blog',[r'/blog(?:/|$)',r'/articles?(?:/|$)',r'/news(?:/|$)'])]
    for kind, patterns in rules:
        if any(re.search(x, path, re.I) for x in patterns): return kind
    return 'other'


async def collect_links_from_page(page, page_url, base_url, max_links):
    try:
        await page.goto(page_url, wait_until='domcontentloaded')
        try: await page.wait_for_load_state('networkidle', timeout=4000)
        except Exception: pass
        hrefs = await page.locator('a[href]').evaluate_all('(els)=>els.map(e=>e.href).filter(Boolean)')
    except Exception:
        return []
    out=[]; seen=set()
    for href in hrefs:
        u=normalize_url(base_url, href)
        if u in seen or not same_domain(u, base_url) or not is_inside_site(u, base_url):
            continue
        seen.add(u); out.append(u)
        if len(out)>=max_links: break
    return out


async def collect_sitemap_urls(page, base_url, max_urls):
    candidates=[normalize_url(base_url,p) for p in ['sitemap_index.xml','sitemap.xml','wp-sitemap.xml']]
    found=[]; seen_xml=set(); seen_urls=set()
    async def walk(xml_url, depth=0):
        if depth>2 or xml_url in seen_xml or len(found)>=max_urls: return
        seen_xml.add(xml_url)
        try:
            r=await page.request.get(xml_url, timeout=30000)
            if not r.ok: return
            xml=await r.text()
        except Exception: return
        soup=BeautifulSoup(xml,'xml'); locs=[n.get_text(strip=True) for n in soup.find_all('loc')]
        if soup.find('sitemapindex'):
            for loc in locs[:80]:
                await walk(loc, depth+1)
                if len(found)>=max_urls: break
        else:
            for loc in locs:
                u=normalize_url(base_url,loc)
                if u in seen_urls or not same_domain(u,base_url) or not is_inside_site(u,base_url): continue
                seen_urls.add(u); found.append(u)
                if len(found)>=max_urls: break
    for c in candidates:
        await walk(c)
        if found: break
    return found


async def discover_pages(page, config):
    base=config['site']['base_url']; d=config.get('discovery',{}); limits=d.get('limits',{})
    urls=[(base,'base')]

    seed_paths = d.get('seed_paths', ['/', '/shop/', '/my-account/', '/my-account/orders/', '/cart/', '/checkout/']) or []
    per_seed = int(d.get('max_links_per_seed', 250))
    for seed in seed_paths:
        seed_url = normalize_url(base, seed)
        links = await collect_links_from_page(page, seed_url, base, per_seed)
        urls += [(u, f'page:{seed}') for u in links]

    if d.get('use_sitemap',True):
        urls += [(u,'sitemap') for u in await collect_sitemap_urls(page,base,int(d.get('max_sitemap_urls',2500)))]
    for kind, paths in d.get('common_paths',{}).items():
        urls += [(normalize_url(base,p),f'common:{kind}') for p in (paths or [])]

    grouped=defaultdict(list); seen=set()
    for u,src in urls:
        if u in seen: continue
        seen.add(u)
        if d.get('same_domain_only', True) and (not same_domain(u,base) or not is_inside_site(u,base)): continue
        grouped[classify_url(u,base)].append((u,src))

    result=[]
    for kind in ['home','shop','category','product','cart','checkout','account','orders','order','contacts','blog','other']:
        limit=int(limits.get(kind,0))
        for i,(u,src) in enumerate(grouped.get(kind,[])[:limit],1):
            name=LABELS.get(kind,'Страница') if i==1 else f"{LABELS.get(kind,'Страница')} {i}"
            result.append(PageTarget(name,u,kind,src))
    return result
