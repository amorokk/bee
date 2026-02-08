"""Тест формата APR из API"""
import urllib.request
import json

url = "https://www.gate.com/apiw/v2/uni-loan/earn/market/list?available=false&limit=7&have_balance=2&have_award=0&is_subscribed=0&sort_business=1&search_type=0&page=1"

with urllib.request.urlopen(url, timeout=10) as resp:
    data = json.loads(resp.read().decode('utf-8'))

items = data.get('data', {}).get('list', [])

print("Первые 5 монет из API:")
print("-" * 70)
for item in items[:5]:
    coin = item.get('asset')
    sort_apr = item.get('sort_apr')
    print(f"Coin: {coin:8} | sort_apr: {sort_apr:8} | type: {type(sort_apr).__name__}")

print("\n" + "=" * 70)
print("ВЫВОД: Если sort_apr показывает числа типа 246.5, то это проценты.")
print("       Если показывает 2.465, то это доли (и нужно * 100).")
print("=" * 70)
