import json
import re
import urllib.request

BASE = "https://clause-guard-virid.vercel.app"


def get(path, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()
    except Exception as exc:
        return None, {"error": str(exc)}, b""


st, hd, body = get("/")
html = body.decode("utf-8", "replace")
print(f"GET /                     -> {st}")
print(f"  title                   : {(re.search(r'<title[^>]*>(.*?)</title>', html, re.S) or [None,'?'])[1].strip()}")
print(f"  cache-control           : {hd.get('Cache-Control')}")
manifest_linked = ("rel=\"manifest\"" in html) or ("rel=manifest" in html)
print(f"  manifest linked         : {manifest_linked}")

for path, expect in (
    ("/manifest.json", "application/manifest+json"),
    ("/service-worker.js", "javascript"),
    ("/offline.html", "text/html"),
    ("/logo192.png", "image/png"),
    ("/logo512-maskable.png", "image/png"),
    ("/apple-touch-icon.png", "image/png"),
    ("/privacy.html", "text/html"),
):
    st, hd, bd = get(path)
    extra = ""
    if path == "/manifest.json" and st == 200:
        m = json.loads(bd)
        extra = (
            f" | display={m.get('display')} start={m.get('start_url')} "
            f"icons={[i['sizes'] for i in m.get('icons', [])]} shortcuts={len(m.get('shortcuts', []))}"
        )
    print(f"GET {path:26}-> {st} {hd.get('Content-Type','?'):32} cache={hd.get('Cache-Control','-')}{extra}")

print()
print("--- which API does the deployed bundle call? ---")
for src in re.findall(r'src="([^"]+\.js)"', html):
    st, hd, bd = get(src)
    js = bd.decode("utf-8", "replace")
    apis = sorted(set(re.findall(r"https://[a-z0-9.\-]*onrender\.com", js)))
    local = ("127.0.0.1:8002" in js) or ("localhost:8002" in js)
    print(f"  {src:32} api={apis or '(none)'} localApi={local}")

print()
print("--- service worker behaviour (does it avoid caching the API?) ---")
st, hd, bd = get("/service-worker.js")
sw = bd.decode("utf-8", "replace")
for probe in ("/contracts", "/analyze", "/auth", "authorization", "isApiPath"):
    print(f"  mentions {probe:14}: {probe in sw}")
