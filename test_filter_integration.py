"""
Интеграционный тест для проверки работы команды /filter с выбором типа списка.
"""
import json
from models import TokenStatus
from parser_gate import extract_sale_statuses

# Тестовые данные из API
test_item_with_both = {
    "id": 1,
    "asset": "USDT",
    "sort_apr": "2.5",
    "fixed_list": [
        {"sale_status": 1},
        {"sale_status": 2},
    ],
    "fixable_list": [
        {"sale_status": 1}
    ]
}

test_item_only_fixed = {
    "id": 2,
    "asset": "BTC",
    "sort_apr": "3.0",
    "fixed_list": [
        {"sale_status": 1}
    ],
    "fixable_list": []
}

test_item_only_fixable = {
    "id": 3,
    "asset": "ETH",
    "sort_apr": "4.0",
    "fixed_list": [],
    "fixable_list": [
        {"sale_status": 1}
    ]
}

def test_extract_sale_statuses_both():
    """Тест: извлечение обоих типов списков."""
    result = extract_sale_statuses(test_item_with_both)
    print(f"✅ Извлечение обоих списков: {result}")
    assert result["fixed_list"] == [1, 2]
    assert result["fixable_list"] == [1]

def test_extract_sale_statuses_only_fixed():
    """Тест: только фиксированные продукты."""
    result = extract_sale_statuses(test_item_only_fixed)
    print(f"✅ Только fixed: {result}")
    assert result["fixed_list"] == [1]
    assert result["fixable_list"] == []

def test_extract_sale_statuses_only_fixable():
    """Тест: только гибкие продукты."""
    result = extract_sale_statuses(test_item_only_fixable)
    print(f"✅ Только fixable: {result}")
    assert result["fixed_list"] == []
    assert result["fixable_list"] == [1]

def test_token_status_with_fixed():
    """Тест: создание TokenStatus для фиксированных продуктов."""
    status = TokenStatus.from_api_response(test_item_with_both, list_type='fixed')
    print(f"✅ TokenStatus (fixed): {status}")
    assert status.list_type == 'fixed'
    assert status.get_active_list() == [1, 2]
    formatted = status.format_for_user()
    print(f"   Форматирование: {formatted}")
    assert "📌" in formatted  # Иконка фиксированного
    assert "USDT" in formatted

def test_token_status_with_flexible():
    """Тест: создание TokenStatus для гибких продуктов."""
    status = TokenStatus.from_api_response(test_item_with_both, list_type='flexible')
    print(f"✅ TokenStatus (flexible): {status}")
    assert status.list_type == 'flexible'
    assert status.get_active_list() == [1]
    formatted = status.format_for_user()
    print(f"   Форматирование: {formatted}")
    assert "🔄" in formatted  # Иконка гибкого
    assert "USDT" in formatted

def test_serialization_with_both_lists():
    """Тест: сериализация и десериализация с обоими списками."""
    status = TokenStatus(
        coin="algo",
        fixed_list=[1, 2],
        fixable_list=[1],
        list_type='fixed',
        sort_apr=0.025
    )
    
    # Сериализация
    serialized = status.to_string()
    data = json.loads(serialized)
    print(f"✅ Сериализация: {data}")
    
    assert data["fixed_list"] == [1, 2]
    assert data["fixable_list"] == [1]
    assert data["list_type"] == 'fixed'
    
    # Десериализация
    restored = TokenStatus.from_string("algo", serialized)
    print(f"✅ Десериализация: {restored}")
    
    assert restored.fixed_list == [1, 2]
    assert restored.fixable_list == [1]
    assert restored.list_type == 'fixed'
    assert restored.get_active_list() == [1, 2]

def test_monitoring_change_detection():
    """Тест: обнаружение изменений при мониторинге."""
    # Старый статус
    old_status = TokenStatus(
        coin="algo",
        fixed_list=[1, 2],
        fixable_list=[1],
        list_type='fixed'
    )
    
    # Новый статус (изменился fixed_list)
    new_status = TokenStatus(
        coin="algo",
        fixed_list=[2, 2],
        fixable_list=[1],
        list_type='fixed'
    )
    
    # Должно обнаружить изменение
    assert old_status.get_active_list() != new_status.get_active_list()
    print("✅ Изменение fixed_list обнаружено")
    
    # Изменение list_type тоже должно обнаруживаться
    status_changed_type = TokenStatus(
        coin="algo",
        fixed_list=[1, 2],
        fixable_list=[2],  # Изменился
        list_type='flexible'  # Переключили тип
    )
    
    # При том же coin, но другом list_type, статусы разные
    assert old_status != status_changed_type
    print("✅ Изменение list_type обнаружено")

def test_filter_logic_simulation():
    """Тест: симуляция логики команды /filter."""
    print("\n🔍 Симуляция команды /filter:")
    
    items = [test_item_with_both, test_item_only_fixed, test_item_only_fixable]
    
    # Фильтр для fixed продуктов
    print("\n📌 Поиск фиксированных продуктов:")
    for item in items:
        coin = item["asset"]
        statuses = extract_sale_statuses(item)
        fixed_list = statuses.get("fixed_list", [])
        
        if fixed_list:
            status = TokenStatus.from_api_response(item, list_type='fixed')
            print(f"  ✓ {coin}: {status.format_for_user()}")
        else:
            print(f"  ✗ {coin}: нет фиксированных продуктов")
    
    # Фильтр для flexible продуктов
    print("\n🔄 Поиск гибких продуктов:")
    for item in items:
        coin = item["asset"]
        statuses = extract_sale_statuses(item)
        fixable_list = statuses.get("fixable_list", [])
        
        if fixable_list:
            status = TokenStatus.from_api_response(item, list_type='flexible')
            print(f"  ✓ {coin}: {status.format_for_user()}")
        else:
            print(f"  ✗ {coin}: нет гибких продуктов")

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 Интеграционный тест команды /filter")
    print("=" * 70)
    
    try:
        test_extract_sale_statuses_both()
        test_extract_sale_statuses_only_fixed()
        test_extract_sale_statuses_only_fixable()
        test_token_status_with_fixed()
        test_token_status_with_flexible()
        test_serialization_with_both_lists()
        test_monitoring_change_detection()
        test_filter_logic_simulation()
        
        print("\n" + "=" * 70)
        print("✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("=" * 70)
        print("\n📝 Проверенная функциональность:")
        print("  ✓ Извлечение обоих типов списков из API")
        print("  ✓ Создание TokenStatus для fixed и flexible")
        print("  ✓ Правильная иконка для каждого типа (📌/🔄)")
        print("  ✓ Сериализация/десериализация с обоими списками")
        print("  ✓ Обнаружение изменений при мониторинге")
        print("  ✓ Логика фильтрации по типу продукта")
    except AssertionError as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        raise
