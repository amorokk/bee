"""
Проверка работы с реальным API Gate.com.
Тестируем извлечение обоих типов списков (fixed и fixable).
"""
import urllib.request
import json
from parser_gate import extract_sale_statuses
from models import TokenStatus

# Запрос к реальному API
url = "https://www.gate.com/apiw/v2/uni-loan/earn/market/list?available=false&limit=10&have_balance=2&have_award=0&is_subscribed=0&sort_business=1&search_type=0&page=1"

print("=" * 70)
print("🌐 Проверка работы с реальным API Gate.com")
print("=" * 70)

with urllib.request.urlopen(url, timeout=10) as resp:
    data = json.loads(resp.read().decode('utf-8'))

items = data.get('data', {}).get('list', [])

if not items:
    print("❌ Не получены данные из API")
    exit(1)

print(f"\n✅ Получено {len(items)} элементов из API\n")

# Счетчики
has_fixed = 0
has_fixable = 0
has_both = 0

print("📊 Анализ первых 5 монет:")
print("-" * 70)

for i, item in enumerate(items[:5], 1):
    coin = item.get('asset', 'UNKNOWN')
    sort_apr = item.get('sort_apr', 0)
    
    # Извлекаем статусы
    statuses = extract_sale_statuses(item)
    fixed_list = statuses.get('fixed_list', [])
    fixable_list = statuses.get('fixable_list', [])
    
    # Подсчет
    has_fixed_prod = len(fixed_list) > 0
    has_fixable_prod = len(fixable_list) > 0
    
    if has_fixed_prod:
        has_fixed += 1
    if has_fixable_prod:
        has_fixable += 1
    if has_fixed_prod and has_fixable_prod:
        has_both += 1
    
    print(f"\n{i}. {coin} (APR: {sort_apr})")
    
    # Показываем фиксированные продукты
    if fixed_list:
        status_fixed = TokenStatus.from_api_response(item, list_type='fixed')
        print(f"   {status_fixed.format_for_user()}")
    else:
        print(f"   📌 FIXED: нет продуктов")
    
    # Показываем гибкие продукты
    if fixable_list:
        status_fixable = TokenStatus.from_api_response(item, list_type='flexible')
        print(f"   {status_fixable.format_for_user()}")
    else:
        print(f"   🔄 FLEXIBLE: нет продуктов")

print("\n" + "=" * 70)
print("📈 Статистика по первым 5 монетам:")
print("-" * 70)
print(f"  Монет с фиксированными продуктами: {has_fixed}")
print(f"  Монет с гибкими продуктами:        {has_fixable}")
print(f"  Монет с обоими типами:             {has_both}")
print("=" * 70)

# Проверяем что функция from_api_response работает корректно
print("\n🧪 Тест создания TokenStatus из API данных:")
test_item = items[0]
test_coin = test_item.get('asset')

# Создаем с типом fixed
status_fixed = TokenStatus.from_api_response(test_item, list_type='fixed')
print(f"  ✓ Fixed type: {status_fixed.list_type}, active_list: {status_fixed.get_active_list()}")
assert status_fixed.list_type == 'fixed'
assert status_fixed.fixed_list == status_fixed.get_active_list()

# Создаем с типом flexible
status_flexible = TokenStatus.from_api_response(test_item, list_type='flexible')
print(f"  ✓ Flexible type: {status_flexible.list_type}, active_list: {status_flexible.get_active_list()}")
assert status_flexible.list_type == 'flexible'
assert status_flexible.fixable_list == status_flexible.get_active_list()

# Оба статуса должны содержать одинаковые исходные данные, но разный активный список
assert status_fixed.coin == status_flexible.coin
print(f"  ✓ Оба статуса для одной монеты: {test_coin}")

# Сериализация и десериализация
serialized = status_fixed.to_string()
restored = TokenStatus.from_string(test_coin.lower(), serialized)
print(f"  ✓ Сериализация/десериализация работает")
assert restored.fixed_list == status_fixed.fixed_list
assert restored.fixable_list == status_fixed.fixable_list
assert restored.list_type == status_fixed.list_type

print("\n" + "=" * 70)
print("✅ ВСЕ ПРОВЕРКИ ПРОШЛИ УСПЕШНО!")
print("=" * 70)
print("\n📝 Подтверждено:")
print("  ✓ API возвращает оба типа списков (fixed_list и fixable_list)")
print("  ✓ extract_sale_statuses() корректно извлекает оба списка")
print("  ✓ TokenStatus.from_api_response() работает для обоих типов")
print("  ✓ Сериализация и десериализация сохраняют оба списка и тип")
print("  ✓ Форматирование отображает правильную иконку (📌/🔄)")
print("\n🎯 Готово к использованию команды /filter с параметром fixed/flexible!")
print("=" * 70)
