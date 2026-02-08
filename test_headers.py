"""Тест отдельных заголовков для определения проблемного"""
import json
import urllib.request
import urllib.parse

url = "https://www.gate.com/apiw/v2/uni-loan/earn/market/list?search_coin=algo&available=false&limit=7&have_balance=2&have_award=0&is_subscribed=0&sort_business=1&search_type=0&page=1"

tests = [
    ("Только User-Agent", {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}),
    ("Только Accept", {"Accept": "application/json, text/plain, */*"}),
    ("Только Accept-Language", {"Accept-Language": "en-US,en;q=0.9"}),
    ("Только Referer", {"Referer": "https://www.gate.com/"}),
    ("User-Agent + Accept", {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*"
    }),
    ("User-Agent + Accept + Accept-Language", {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9"
    }),
]

for name, headers in tests:
    print(f"\n{'='*60}")
    print(f"Тест: {name}")
    print(f"{'='*60}")
    
    try:
        req = urllib.request.Request(url)
        for key, value in headers.items():
            req.add_header(key, value)
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"✅ Успех! Статус: {resp.status}")
            print(f"Получено записей: {len(data.get('data', {}).get('list', []))}")
    except Exception as e:
        print(f"❌ Ошибка: {type(e).__name__}: {e}")

print(f"\n{'='*60}")
print("Вывод: какие заголовки вызывают проблему?")
print(f"{'='*60}")
