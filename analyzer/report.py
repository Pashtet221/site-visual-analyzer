import html, json
from collections import defaultdict

def write_json(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def build_html_report(output_dir, results, title):
    grouped=defaultdict(dict); meta={}
    for item in results:
        key=(item.name,item.url); grouped[key][item.device]=item; meta[key]=item
    cards=[]
    for key, devices in grouped.items():
        name,url=key; m=meta[key]; shots=[]
        for device in ['desktop','tablet','mobile']:
            item=devices.get(device)
            if not item: continue
            if item.status=='ok' and item.screenshot:
                shots.append(f'<article class="shot"><div class="shot__head"><strong>{html.escape(device.title())}</strong><span>{item.http_status or ""}</span></div><a href="{html.escape(item.screenshot)}" target="_blank"><img loading="lazy" src="{html.escape(item.screenshot)}" alt="{html.escape(name)}"></a></article>')
            else:
                shots.append(f'<article class="shot error"><div class="shot__head"><strong>{html.escape(device.title())}</strong></div><p>{html.escape(item.error or "Ошибка")}</p></article>')
        cards.append(f'<section class="card"><header><div><span>{html.escape(m.kind)}</span><h2>{html.escape(name)}</h2></div><a href="{html.escape(url)}" target="_blank">Открыть страницу</a></header><div class="url">{html.escape(url)}</div><div class="shots">{"".join(shots)}</div></section>')
    css='''*{box-sizing:border-box}body{margin:0;background:#f3f4f6;color:#171717;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.top{position:sticky;top:0;z-index:9;padding:18px 28px;background:rgba(255,255,255,.95);border-bottom:1px solid #e5e7eb}.top h1{margin:0;font-size:22px}.top p{margin:5px 0 0;color:#6b7280}main{max-width:1800px;margin:auto;padding:24px}.card{background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:20px;margin-bottom:28px}.card header{display:flex;justify-content:space-between;gap:20px;align-items:center}.card h2{margin:4px 0}.card header span{background:#eef2ff;color:#4338ca;padding:4px 8px;border-radius:20px;font-size:12px;font-weight:700}.card header a{color:#111;text-decoration:none;border:1px solid #d1d5db;padding:9px 13px;border-radius:10px;font-weight:600}.url{margin-top:10px;color:#6b7280;font-size:13px;overflow-wrap:anywhere}.shots{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:18px;align-items:start}.shot{border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;background:#fafafa}.shot__head{display:flex;justify-content:space-between;padding:10px 12px;background:#fff;border-bottom:1px solid #e5e7eb;font-size:13px}.shot img{display:block;width:100%;height:auto}.error p{padding:12px;color:#b91c1c}@media(max-width:1100px){.shots{grid-template-columns:1fr}.shot img{max-height:720px;object-fit:contain;object-position:top}}@media(max-width:640px){main{padding:12px}.top{padding:14px 16px}.card{padding:14px}.card header{align-items:flex-start;flex-direction:column}}'''
    page=f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style></head><body><header class="top"><h1>{html.escape(title)}</h1><p>Страниц: {len(grouped)} · Скриншотов: {sum(1 for r in results if r.status=="ok")}</p></header><main>{"".join(cards)}</main></body></html>'
    path=output_dir/'index.html'; path.write_text(page,encoding='utf-8'); return path
