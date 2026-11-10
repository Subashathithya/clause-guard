import json
import urllib.request

SAMPLE = (
    "This Agreement is entered into effective January 1 2026 between the Company and the Customer. "
    "1. Term. This Agreement shall commence on the Effective Date and continue for an initial term "
    "of twelve (12) months. Thereafter, this Agreement shall automatically renew for successive "
    "one-year renewal periods unless either party provides written notice of non-renewal at least "
    "thirty (30) days prior to the end of the then-current term. "
    "2. Payment. Customer shall pay the Company the sum of $12,000 per year, payable in advance. "
    "Late payments shall accrue interest at the rate of 1.5% per month. "
    "3. Confidentiality. Each party shall hold all confidential information in strict confidence and "
    "shall not disclose it to any third party. Confidential information shall be returned within "
    "thirty (30) days of termination of this Agreement. "
    "4. Termination. Either party may terminate this Agreement upon thirty (30) days written notice. "
    "5. Limitation of Liability. Neither party shall be liable for any indirect, incidental, or "
    "consequential damages. Total liability shall not exceed the amount paid under this Agreement. "
    "6. Governing Law. This Agreement shall be governed by and construed in accordance with the laws "
    "of the State of Delaware."
)

req = urllib.request.Request(
    "http://127.0.0.1:8002/analyze",
    data=json.dumps({"text": SAMPLE, "document_name": "probe"}).encode(),
    headers={"Content-Type": "application/json", "Origin": "http://localhost:3000"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read().decode("utf-8", "replace")
        print("HTTP", r.status)
        print("BODY (first 600 chars):")
        print(body[:600])
except urllib.error.HTTPError as e:
    print("HTTPError", e.code)
    print(e.read().decode("utf-8", "replace")[:600])
except Exception as e:
    print("EXC", type(e).__name__, e)