"""Очистка тестовых записей из БД"""
from database import Database

db = Database('bot_data.db')

# Показываем текущее состояние
print("До очистки:")
print(f"Подписчики: {db.get_all_subscribers()}")
print(f"Watches: {db.get_all_watches()}")

# Удаляем тестовые chat_id
test_ids = ['123', '456']
for chat_id in test_ids:
    # Удаляем все watches для этого chat_id
    watches = db.get_all_watches()
    for c_id, coin, status in watches:
        if c_id == chat_id:
            db.remove_watch(chat_id, coin)
            print(f"Удалён watch: {chat_id} -> {coin}")
    
    # Удаляем подписчика
    db.remove_subscriber(chat_id)
    print(f"Удалён подписчик: {chat_id}")

print("\nПосле очистки:")
print(f"Подписчики: {db.get_all_subscribers()}")
print(f"Watches: {db.get_all_watches()}")

print("\n✅ Тестовые данные удалены!")
