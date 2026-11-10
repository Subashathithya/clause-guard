import re
import urllib.request

hits = {}

def scan(url, label):
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            js = r.read(500_000).decode("utf-8", "replace")
            found = []
            for host in ("localhost:8011", "127.0.0.1:8011", "127.0.0.1:8000", "localhost:8000"):
                for m in re.finditer(host, js):
                    s = max(0, m.start() - 60)
                    found.append(host + "  ..." + js[s:m.start() + 40].replace("\n", " "))
            hits[label] = (len(js), found)
    except Exception as e:
        hits[label] = (0, [f"ERR {type(e).__name__}: {e}"])

# Locate the script tags on the index to discover chunk names
try:
    with urllib.request.urlopen("http://127.0.0.1:3000/", timeout=8) as r:
        html = r.read(100_000).decode("utf-8", "replace")
except Exception as e:
    html = ""
    print("index fetch fail:", e)

scripts = re.findall(r'src="(/static/js/[^"]+)"', html)
print("js chunks served by CRA:", scripts or "(none found)")

for s in scripts:
    scan("http://127.0.0.1:3000" + s, s)

for label, (n, found) in hits.items():
    print(f"\n--- {label} ({n} bytes) ---")
    if not found:
        print("  no host literals")
    for f in found:
        print("  ·", f[:130])