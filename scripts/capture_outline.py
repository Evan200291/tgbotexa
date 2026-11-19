"""Capture the unmodified official APK web UI locally; no VPN connection is made."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import base64
import json

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8099), partial(
        SimpleHTTPRequestHandler, directory=str(ROOT / "tmp/outline-client")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 640}, device_scale_factor=2)
        demo_key = "ss://" + base64.urlsafe_b64encode(b"chacha20-ietf-poly1305:example-guide-key").decode().rstrip("=") + "@192.0.2.1:443/#My%20VPN"
        seed = [{"id": "guide-demo", "name": "My VPN", "accessKey": demo_key}]
        page.add_init_script("localStorage.setItem('settings', JSON.stringify({'privacy-ack':'true'}));"
                             + "localStorage.setItem('servers_v1', " + json.dumps(json.dumps(seed)) + ");")
        page.route("**/*", lambda route: route.continue_() if
                   route.request.url.startswith("http://127.0.0.1:8099/") else route.abort())
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto("http://127.0.0.1:8099")
        page.get_by_role("heading", name="My VPN", exact=True).wait_for()
        if page.get_by_role("dialog", name="Add VPN access key").is_visible():
            page.get_by_role("dialog", name="Add VPN access key").get_by_role("button", name="Cancel").click()
        page.wait_for_timeout(1200)
        def highlight(locator):
            locator.evaluate("el => { el.style.outline='3px solid #ffb34d'; el.style.outlineOffset='4px'; el.dataset.guideHighlight='true'; }")
        def clear():
            page.locator('[data-guide-highlight]').evaluate_all("els => els.forEach(e=>{ e.style.outline='';e.style.outlineOffset='';delete e.dataset.guideHighlight; })")
        add = page.locator('md-icon-button').filter(has=page.locator('md-icon', has_text='add'))
        highlight(add)
        shots=[]
        shots.append(page.screenshot())
        clear();add.click()
        print(page.locator('body').aria_snapshot())
        page.screenshot(path=str(ROOT/'tmp/outline-add.png'))
        textbox=page.get_by_role('textbox', name='Paste access key here')
        textbox.fill(demo_key.replace('192.0.2.1', '192.0.2.2').replace('My%20VPN', 'Outline%20VPN'))
        highlight(textbox)
        highlight(page.get_by_role('button', name='Confirm', exact=True))
        shots.append(page.screenshot())
        clear();page.get_by_role('button', name='Confirm', exact=True).click()
        page.wait_for_timeout(800)
        highlight(page.get_by_role('button', name='Connect', exact=True).last)
        shots.append(page.screenshot())
        output=ROOT/'exabyte_bot/assets/guides';output.mkdir(parents=True,exist_ok=True)
        for idx, shot in enumerate(shots,1):
            (output/f'outline-screen-{idx}.png').write_bytes(shot)
        layout=browser.new_page(viewport={'width':1260,'height':850},device_scale_factor=1)
        panels=''.join('<article><h2>'+title+'</h2><p>'+sub+'</p><img src="data:image/png;base64,'+base64.b64encode(shot).decode()+'"></article>' for title,sub,shot in zip(
            ['01 · Tap +','02 · Paste your key','03 · Tap Connect'],
            ['Open Outline after copying your key','Tap Confirm to add your server','Allow the VPN request if asked'],shots,strict=True))
        layout.set_content('''<html><style>*{box-sizing:border-box}body{margin:0;background:#f1f5f3;color:#183c32;font-family:Arial,sans-serif;padding:30px}header{display:flex;justify-content:space-between;align-items:baseline;margin:0 8px 24px}h1{font-size:28px;margin:0}header span{font-size:14px;color:#5b7068}main{display:flex;gap:24px}article{width:384px}h2{font-size:21px;margin:0 0 8px}p{font-size:13px;margin:0 0 18px;color:#526b61}img{width:384px;border-radius:18px;border:1px solid #c5d6cc}footer{font-size:12px;margin-top:18px;color:#61786e}</style><header><h1>Outline · Quick start</h1><span>Follow the highlighted buttons</span></header><main>'''+panels+'''</main><footer>Outline 1.23.0 interface · Example server only · Button labels may vary by version</footer></html>''')
        layout.screenshot(path=str(output/'outline-quickstart.jpg'),type='jpeg',quality=92,full_page=True)
        print('Captured official Outline UI and highlighted controls. Errors:',errors)
        browser.close()
    server.shutdown()
