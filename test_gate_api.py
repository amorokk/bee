"""Тестовый скрипт для проверки доступа к Gate.com API"""
import json
import urllib.request
import urllib.parse

# Параметры запроса как в parser_gate.py
params = {
    "search_coin": "algo",
    "available": "false",
    "limit": "7",
    "have_balance": "2",
    "have_award": "0",
    "is_subscribed": "0",
    "sort_business": "1",
    "search_type": "0",
    "page": "1",
}

url = f"https://www.gate.com/apiw/v2/uni-loan/earn/market/list?{urllib.parse.urlencode(params)}"

print(f"URL: {url}\n")

# Тест 1: Без заголовков
print("=" * 60)
print("Тест 1: Запрос БЕЗ заголовков")
print("=" * 60)
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"✅ Успех! Статус: {resp.status}")
        print(f"Получено записей: {len(data.get('data', {}).get('list', []))}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print(f"Тип ошибки: {type(e)}")

# Тест 2: С заголовками как в коде
print("\n" + "=" * 60)
print("Тест 2: Запрос С заголовками (как в parser_gate.py)")
print("=" * 60)
try:
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    req.add_header('Accept', 'application/json, text/plain, */*')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    req.add_header('Referer', 'https://www.gate.com/')
    
    print("Заголовки запроса:")
    for header, value in req.headers.items():
        print(f"  {header}: {value}")
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"\n✅ Успех! Статус: {resp.status}")
        print(f"Получено записей: {len(data.get('data', {}).get('list', []))}")
        
        # Показываем первую монету если есть
        coin_list = data.get('data', {}).get('list', [])
        if coin_list:
            first = coin_list[0]
            print(f"\nПервая монета: {first.get('coin')} - APR: {first.get('sort_apr')}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print(f"Тип ошибки: {type(e)}")
    if hasattr(e, 'code'):
        print(f"HTTP код: {e.code}")
    if hasattr(e, 'headers'):
        print(f"Заголовки ответа: {dict(e.headers)}")

# Тест 3: С расширенными заголовками
print("\n" + "=" * 60)
print("Тест 3: Запрос с РАСШИРЕННЫМИ заголовками")
print("=" * 60)
try:
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    req.add_header('Accept', 'application/json, text/plain, */*')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    req.add_header('Accept-Encoding', 'gzip, deflate, br')
    req.add_header('Referer', 'https://www.gate.com/')
    req.add_header('Origin', 'https://www.gate.com')
    req.add_header('Connection', 'keep-alive')
    req.add_header('Sec-Fetch-Dest', 'empty')
    req.add_header('Sec-Fetch-Mode', 'cors')
    req.add_header('Sec-Fetch-Site', 'same-origin')
    
    print("Заголовки запроса:")
    for header, value in req.headers.items():
        print(f"  {header}: {value}")
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"\n✅ Успех! Статус: {resp.status}")
        print(f"Получено записей: {len(data.get('data', {}).get('list', []))}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print(f"Тип ошибки: {type(e)}")

print("\n" + "=" * 60)
print("Тестирование завершено")
print("=" * 60)
