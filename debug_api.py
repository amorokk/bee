import json
import urllib.parse
import urllib.request

BASE_URL = "https://www.gate.com/apiw/v2/uni-loan/earn/market/list"
params = {
    "available": "false",
    "limit": "7",
    "have_balance": "2",
    "have_award": "0",
    "is_subscribed": "0",
    "sort_business": "1",
    "search_type": "0",
    "page": "1",
}
url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
with urllib.request.urlopen(url, timeout=30) as resp:
    payload = json.loads(resp.read().decode("utf-8"))

print(payload.keys())

items = None
for key in ("data", "list", "result", "rows"):
    if isinstance(payload.get(key), list):
        items = payload[key]
        break
if items is None and isinstance(payload.get("data"), dict):
    for key in ("list", "rows", "data"):
        if isinstance(payload["data"].get(key), list):
            items = payload["data"][key]
            break

print("items", len(items) if items else 0)
if items:
    sample = items[0]
    print(sample.keys())
    for k in sample.keys():
        if "apr" in k.lower():
            print(k, sample.get(k))
    print("sample", sample)
