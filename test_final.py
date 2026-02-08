"""Финальный тест - без заголовков vs с заголовками"""
import urllib.request
import json

url = "https://www.gate.com/apiw/v2/uni-loan/earn/market/list?search_coin=algo&available=false&limit=7&have_balance=2&have_award=0&is_subscribed=0&sort_business=1&search_type=0&page=1"

print("1. Тест БЕЗ заголовков:")
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"   ✅ Успех! Код: {resp.status}, Записей: {len(data.get('data', {}).get('list', []))}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print("\n2. Тест С заголовками (User-Agent + Accept + Accept-Language):")
try:
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    req.add_header('Accept', 'application/json, text/plain, */*')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"   ✅ Успех! Код: {resp.status}, Записей: {len(data.get('data', {}).get('list', []))}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print("\n3. Тест С заголовками + Referer:")
try:
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    req.add_header('Accept', 'application/json, text/plain, */*')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    req.add_header('Referer', 'https://www.gate.com/')
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"   ✅ Успех! Код: {resp.status}, Записей: {len(data.get('data', {}).get('list', []))}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print("\n✅ РЕШЕНИЕ: Убрать Referer из запросов!")
