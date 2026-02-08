"""Check API structure for flexible/fixed lists"""
import urllib.request
import json

url = "https://www.gate.com/apiw/v2/uni-loan/earn/market/list?available=false&limit=7&have_balance=2&have_award=0&is_subscribed=0&sort_business=1&search_type=0&page=1"

with urllib.request.urlopen(url, timeout=10) as resp:
    data = json.loads(resp.read().decode('utf-8'))

items = data.get('data', {}).get('list', [])

if items:
    first = items[0]
    print("First item keys:")
    print(json.dumps(list(first.keys()), indent=2))
    
    print("\nFirst item full structure:")
    print(json.dumps(first, indent=2, ensure_ascii=False))
    
    # Check for flexible/fixed fields
    print("\nChecking for list fields:")
    for key in first.keys():
        if 'list' in key.lower() or 'fix' in key.lower() or 'flex' in key.lower():
            print(f"  {key}: {first[key]}")
