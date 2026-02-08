import json
import os
import signal
import sys
import threading
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Set, Tuple

from config import config
from database import Database
from logger import logger
from models import TokenStatus
from parser_gate import extract_sale_statuses, fetch_projects_with_apr_gt, fetch_token_info

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
ADMIN_CHATS = config.get_admin_chat_ids()


def _api_request(method: str, data: Optional[Dict] = None) -> Dict:
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("Токен Telegram не задан")
    url = TELEGRAM_API.format(token=token, method=method)
    payload = urllib.parse.urlencode(data or {}).encode("utf-8")
    logger.debug(f"Telegram API request: {method} data={data}")
    with urllib.request.urlopen(url, data=payload, timeout=20) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    logger.debug(f"Telegram API response: {method} ok={result.get('ok')}")
    return result


def send_message(chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> None:
    try:
        logger.info(f"Bot -> chat {chat_id}: {text[:100]}...")  # Логируем только первые 100 символов
        data = {"chat_id": chat_id, "text": text}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        _api_request("sendMessage", data)
    except Exception as exc:
        logger.error(f"Ошибка отправки в Telegram (chat_id={chat_id}): {exc}")


def _answer_callback_query(callback_query_id: str, text: str = None) -> None:
    """Ответ на callback query (уведомление пользователю)."""
    try:
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        _api_request("answerCallbackQuery", data)
    except Exception as exc:
        logger.error(f"Ошибка answerCallbackQuery: {exc}")


def _set_bot_commands() -> None:
    """Устанавливает список команд для отображения в UI Telegram."""
    commands = [
        {"command": "start", "description": "Начать работу с ботом"},
        {"command": "help", "description": "Справка по командам"},
        {"command": "list", "description": "Показать мои подписки"},
        {"command": "info", "description": "Информация о монете"},
        {"command": "filter", "description": "Подписаться на монеты по APR"},
        {"command": "stop", "description": "Отменить подписку"},
        {"command": "clear", "description": "Отменить все подписки"},
        {"command": "pause", "description": "Приостановить уведомления"},
        {"command": "resume", "description": "Возобновить уведомления"},
        {"command": "status", "description": "Состояние бота"},
    ]
    
    try:
        _api_request("setMyCommands", {"commands": json.dumps(commands)})
        logger.info("Bot commands set successfully")
    except Exception as exc:
        logger.error(f"Failed to set bot commands: {exc}")


def _get_updates(offset: int) -> List[Dict]:
    try:
        logger.debug(f"Polling updates offset={offset}")
        result = _api_request("getUpdates", {"offset": offset, "timeout": 1})
        return result.get("result", [])
    except Exception as exc:
        logger.error(f"Ошибка getUpdates: {exc}")
        return []


class BotState:
    def __init__(self, db_path: str = None) -> None:
        if db_path is None:
            db_path = config.DB_PATH
        self.db = Database(db_path)
        self.lock = threading.Lock()
        self.global_failures: int = 0
        self.global_alerted: bool = False
        self.coin_failures: Dict[str, int] = {}
        self.coin_alerted: Set[str] = set()
        # Загружаем данные из БД при старте
        self.subscribers: Set[str] = self.db.get_all_subscribers()
        self.watch: Dict[str, Dict[str, str]] = self._load_watches_from_db()
        logger.info(f"State loaded from DB: {len(self.subscribers)} subscribers, {sum(len(w) for w in self.watch.values())} watches")
    
    def _load_watches_from_db(self) -> Dict[str, Dict[str, str]]:
        """Загрузить все отслеживания из БД в память."""
        watches: Dict[str, Dict[str, str]] = {}
        for chat_id, coin, status in self.db.get_all_watches():
            watches.setdefault(chat_id, {})[coin] = status
        return watches

    def add_subscriber(self, chat_id: str) -> None:
        with self.lock:
            was_new = self.db.add_subscriber(chat_id)
            self.subscribers.add(chat_id)
            self.watch.setdefault(chat_id, {})
            if was_new:
                logger.info(f"New subscriber added: {chat_id}")

    def set_watch(self, chat_id: str, coin: str, status: str) -> None:
        with self.lock:
            self.db.add_watch(chat_id, coin, status)
            self.watch.setdefault(chat_id, {})[coin] = status
            logger.debug(f"Watch set: {chat_id} -> {coin} ({status})")

    def get_watches(self) -> List[Tuple[str, str, str]]:
        with self.lock:
            items: List[Tuple[str, str, str]] = []
            for chat_id, coins in self.watch.items():
                for coin, status in coins.items():
                    items.append((chat_id, coin, status))
            return items

    def get_user_coins(self, chat_id: str) -> List[str]:
        with self.lock:
            coins = self.watch.get(chat_id, {})
            return sorted(coins.keys())

    def remove_watch(self, chat_id: str, coin: str) -> bool:
        with self.lock:
            removed = self.db.remove_watch(chat_id, coin)
            coins = self.watch.get(chat_id, {})
            if coin in coins:
                del coins[coin]
            return removed

    def clear_watches(self, chat_id: str) -> None:
        with self.lock:
            # Удаляем все watches для этого chat_id из БД
            for coin in list(self.watch.get(chat_id, {}).keys()):
                self.db.remove_watch(chat_id, coin)
            self.watch[chat_id] = {}

    def increment_global_failures(self) -> int:
        with self.lock:
            self.global_failures += 1
            return self.global_failures

    def reset_global_failures(self) -> None:
        with self.lock:
            self.global_failures = 0
            self.global_alerted = False

    def increment_coin_failure(self, coin: str) -> int:
        with self.lock:
            self.coin_failures[coin] = self.coin_failures.get(coin, 0) + 1
            return self.coin_failures[coin]

    def reset_coin_failure(self, coin: str) -> None:
        with self.lock:
            if coin in self.coin_failures:
                del self.coin_failures[coin]
            if coin in self.coin_alerted:
                self.coin_alerted.remove(coin)

    def mark_coin_alerted(self, coin: str) -> None:
        with self.lock:
            self.coin_alerted.add(coin)

    def is_coin_alerted(self, coin: str) -> bool:
        with self.lock:
            return coin in self.coin_alerted

    def update_status(self, chat_id: str, coin: str, new_status: str) -> bool:
        with self.lock:
            current = self.watch.get(chat_id, {}).get(coin)
            if current != new_status:
                self.db.update_watch_status(chat_id, coin, new_status)
                self.watch.setdefault(chat_id, {})[coin] = new_status
                return True
            return False


state = BotState()

# Время запуска бота для uptime
import datetime
BOT_START_TIME = datetime.datetime.now()


def _monitor_loop() -> None:
    while True:
        _check_once()
        time.sleep(config.CHECK_INTERVAL_SEC)


def _check_once() -> None:
    def _send_alert(text: str) -> None:
        targets = list(state.subscribers)
        if not targets:
            logger.warning(f"Alert (no subscribers): {text}")
            return
        for t in targets:
            try:
                send_message(t, f"[ALERT] {text}")
            except Exception:
                pass

    # If any fetch fails (exception or empty), send one global alert (once).
    # When we get any successful response after an alert, send one recovery message (once).
    any_success = False
    for chat_id, coin, last_status in state.get_watches():
        # Пропускаем пользователей на паузе
        if state.db.is_paused(chat_id):
            logger.debug(f"Skipping {chat_id} (paused)")
            continue
        
        logger.debug(f"Check token {coin} for chat {chat_id}")
        try:
            info = fetch_token_info(coin)
        except Exception as exc:
            logger.error(f"Error fetching token {coin}: {exc}")
            if not state.global_alerted:
                _send_alert(f"Ошибка при получении данных: {exc}")
                state.global_alerted = True
            # continue checking other watches but do not resend alerts
            continue

        if not info:
            logger.warning(f"Empty response for token {coin}")
            if not state.global_alerted:
                _send_alert(f"Ошибка: пустой ответ для {coin.upper()}")
                state.global_alerted = True
            continue

        # successful fetch
        any_success = True
        
        # Используем TokenStatus для красивого форматирования
        token_status = TokenStatus.from_api_response(info)
        current_status = token_status.to_string()
        
        # Проверяем изменился ли fixed_list (без учета timestamp)
        old_status_str = state.watch.get(chat_id, {}).get(coin)
        if old_status_str:
            old_status = TokenStatus.from_string(coin, old_status_str)
            status_changed = old_status.fixed_list != token_status.fixed_list
        else:
            status_changed = True  # Первая проверка после подписки
        
        # Обновляем статус в БД
        if state.update_status(chat_id, coin, current_status) and status_changed:
            # Формируем красивое сообщение с эмодзи
            emoji = token_status.get_status_emoji()
            status_text = token_status.get_status_text()
            # API возвращает APR в долях (0.0246 = 2.46%), умножаем на 100
            apr_text = f" (APR: {token_status.sort_apr * 100:.2f}%)" if token_status.sort_apr else ""
            
            send_message(
                chat_id, 
                f"{emoji} {coin.upper()}: {status_text}{apr_text}\n"
                f"Статус изменился: {token_status.fixed_list}"
            )
    
    # Если после ошибки получили успешный ответ - уведомляем о восстановлении
    if any_success and state.global_alerted:
        _send_alert("✅ Получение данных восстановлено — API работает снова")
        with state.lock:
            state.global_alerted = False
            state.global_failures = 0
            state.coin_failures.clear()
            state.coin_alerted.clear()


def _handle_callback_query(callback_query: Dict) -> None:
    """Обработка callback query от inline кнопок."""
    callback_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    
    logger.info(f"Callback query from {chat_id}: {data}")
    
    # Обновить список подписок
    if data == "refresh_list":
        coins = state.get_user_coins(chat_id)
        if not coins:
            _answer_callback_query(callback_id, "Список подписок пуст")
            return
        
        lines = ["📋 Мои подписки:\n"]
        for coin in coins:
            info = fetch_token_info(coin)
            if info:
                token_status = TokenStatus.from_api_response(info)
                lines.append(token_status.format_for_user())
            else:
                lines.append(f"{coin.upper()}: ⚪ нет данных")
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Обновить", "callback_data": "refresh_list"},
                    {"text": "🗑 Очистить всё", "callback_data": "clear_confirm"}
                ]
            ]
        }
        
        # Обновляем существующее сообщение
        try:
            message_id = message.get("message_id")
            _api_request("editMessageText", {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "\n".join(lines),
                "reply_markup": json.dumps(keyboard)
            })
            _answer_callback_query(callback_id, "✅ Обновлено")
        except Exception as exc:
            logger.error(f"Error updating message: {exc}")
            _answer_callback_query(callback_id, "❌ Ошибка обновления")
        return
    
    # Подтверждение очистки
    if data == "clear_confirm":
        _answer_callback_query(callback_id)
        return  # Кнопки уже показаны в /clear
    
    # Очистка подтверждена
    if data == "clear_confirmed":
        state.clear_watches(chat_id)
        _answer_callback_query(callback_id, "✅ Все подписки удалены")
        send_message(chat_id, "✅ Все подписки отменены.")
        return
    
    # Отмена очистки
    if data == "clear_cancel":
        _answer_callback_query(callback_id, "Отменено")
        send_message(chat_id, "❌ Действие отменено.")
        return
    
    # Удаление конкретной монеты
    if data.startswith("stop_"):
        coin = data.replace("stop_", "")
        if state.remove_watch(chat_id, coin):
            _answer_callback_query(callback_id, f"✅ {coin.upper()} удалён")
            send_message(chat_id, f"✅ Подписка на {coin.upper()} отменена.")
        else:
            _answer_callback_query(callback_id, f"❌ {coin.upper()} не найден")
        return
    
    _answer_callback_query(callback_id, "❓ Неизвестная команда")


def _handle_text(chat_id: str, text: str) -> None:
    clean = text.strip()
    if not clean:
        return
    logger.info(f"Incoming from {chat_id}: {clean}")
    
    # /start и /help — приветствие и инструкции
    if clean.lower() in ["/start", "/help"]:
        state.add_subscriber(chat_id)
        send_message(
            chat_id,
            "🐝 Bee Bot — мониторинг Gate.com Earn Market\n\n"
            "Команды:\n"
            "📋 /list — показать список моих монет\n"
            "🔍 /info <coin> — информация о монете без подписки\n"
            "❌ /stop <coin> — отменить подписку на монету\n"
            "🔎 /filter <percent> — подписаться на все монеты с APR больше указанного (например: /filter 200)\n"
            "🗑 /clear — отменить все подписки\n"
            "� /pause — приостановить уведомления\n"
            "🔔 /resume — возобновить уведомления\n"
            "�📊 /status — состояние бота\n"
            "❓ /help — эта справка\n\n"
            "Отправь тикер монеты (например: algo), чтобы подписаться на изменения sale_status.",
        )
        return
    
    # /status — информация о состоянии бота
    if clean.lower() == "/status":
        import datetime
        uptime = datetime.datetime.now() - BOT_START_TIME
        uptime_str = str(uptime).split('.')[0]  # Убираем микросекунды
        
        total_subscribers = len(state.subscribers)
        total_watches = sum(len(coins) for coins in state.watch.values())
        user_watches = len(state.get_user_coins(chat_id))
        is_paused = state.db.is_paused(chat_id)
        
        interval_min = int(config.CHECK_INTERVAL_SEC / 60)
        
        pause_status = "🔇 Уведомления на паузе (/resume чтобы возобновить)" if is_paused else "🔔 Уведомления активны"
        
        send_message(
            chat_id,
            f"📊 Статус бота:\n\n"
            f"⏱ Uptime: {uptime_str}\n"
            f"👥 Всего подписчиков: {total_subscribers}\n"
            f"📌 Всего подписок на монеты: {total_watches}\n"
            f"📋 Ваших подписок: {user_watches}\n"
            f"🔄 Интервал проверки: {interval_min} мин\n"
            f"{pause_status}\n"
            f"✅ Бот работает нормально"
        )
        return
    
    # /pause — приостановить уведомления
    if clean.lower() == "/pause":
        state.db.set_paused(chat_id, True)
        send_message(
            chat_id,
            "🔇 Уведомления приостановлены.\n\n"
            "Мониторинг продолжается, но уведомления не будут отправляться.\n"
            "Чтобы возобновить, используй /resume"
        )
        return
    
    # /resume — возобновить уведомления
    if clean.lower() == "/resume":
        state.db.set_paused(chat_id, False)
        send_message(
            chat_id,
            "🔔 Уведомления возобновлены.\n\n"
            "Снова буду присылать оповещения об изменениях статусов."
        )
        return
    
    # /info <coin> — однократный запрос информации без подписки
    if clean.lower().startswith("/info"):
        parts = clean.split()
        if len(parts) < 2:
            send_message(chat_id, "Использование: /info <coin> (например: /info algo)")
            return
        
        coin = parts[1].lower()
        logger.info(f"Info request for token: {coin}")
        
        try:
            info = fetch_token_info(coin)
            if not info:
                send_message(chat_id, f"❌ Монета {coin.upper()} не найдена.")
                return
            
            token_status = TokenStatus.from_api_response(info)
            send_message(
                chat_id,
                f"ℹ️ Информация о {coin.upper()}:\n\n"
                f"{token_status.format_for_user()}\n\n"
                f"Чтобы подписаться, отправь: {coin}"
            )
        except Exception as exc:
            logger.error(f"Error fetching info for {coin}: {exc}")
            send_message(chat_id, f"❌ Ошибка при получении данных: {exc}")
        return

    if clean.lower() == "/list":
        coins = state.get_user_coins(chat_id)
        if not coins:
            send_message(chat_id, "Список подписок пуст.")
        else:
            lines = ["📋 Мои подписки:\n"]
            for coin in coins:
                info = fetch_token_info(coin)
                if info:
                    token_status = TokenStatus.from_api_response(info)
                    lines.append(token_status.format_for_user())
                else:
                    lines.append(f"{coin.upper()}: ⚪ нет данных")
            
            # Inline кнопки для обновления и очистки
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🔄 Обновить", "callback_data": "refresh_list"},
                        {"text": "🗑 Очистить всё", "callback_data": "clear_confirm"}
                    ]
                ]
            }
            
            send_message(chat_id, "\n".join(lines), reply_markup=keyboard)
        return

    if clean.lower().startswith("/stop"):
        parts = clean.split()
        if len(parts) < 2:
            # Показать список монет с кнопками для выбора
            coins = state.get_user_coins(chat_id)
            if not coins:
                send_message(chat_id, "У вас нет активных подписок.")
                return
            
            keyboard_buttons = []
            for coin in coins:
                keyboard_buttons.append([{"text": f"❌ {coin.upper()}", "callback_data": f"stop_{coin}"}])
            
            keyboard = {"inline_keyboard": keyboard_buttons}
            send_message(chat_id, "Выберите монету для отмены подписки:", reply_markup=keyboard)
            return
        
        coin = parts[1].lower()
        if state.remove_watch(chat_id, coin):
            send_message(chat_id, f"✅ Подписка на {coin.upper()} отменена.")
        else:
            send_message(chat_id, f"❌ Подписка на {coin.upper()} не найдена.")
        return

    if clean.lower() == "/clear":
        coins = state.get_user_coins(chat_id)
        if not coins:
            send_message(chat_id, "У вас нет активных подписок.")
            return
        
        # Запрос подтверждения с inline кнопками
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Да, удалить всё", "callback_data": "clear_confirmed"},
                    {"text": "❌ Отмена", "callback_data": "clear_cancel"}
                ]
            ]
        }
        
        send_message(
            chat_id,
            f"⚠️ Удалить все подписки ({len(coins)} шт)?\nЭто действие нельзя отменить.",
            reply_markup=keyboard
        )
        return

    if clean.lower().startswith("/filter"):
        parts = clean.split()
        if len(parts) < 2:
            send_message(chat_id, "Использование: /filter <percent> (например: /filter 200)")
            return
        try:
            percent = float(parts[1])
        except ValueError:
            send_message(chat_id, "Некорректное значение процента.")
            return

        threshold = percent / 100.0
        send_message(chat_id, f"🔍 Ищу монеты с sort_apr > {percent}%...")
        items = fetch_projects_with_apr_gt(threshold)
        if not items:
            send_message(chat_id, "❌ Монеты по фильтру не найдены.")
            return

        state.add_subscriber(chat_id)
        added = 0
        added_lines = []
        for item in items:
            coin = str(item.get("asset", "")).lower()
            if not coin:
                continue
            fixed = extract_sale_statuses(item).get("fixed_list", [])
            if not fixed:
                continue
            
            # Используем TokenStatus для красивого вывода
            token_status = TokenStatus.from_api_response(item)
            status = token_status.to_string()
            state.set_watch(chat_id, coin, status)
            added += 1
            added_lines.append(token_status.format_for_user())

        interval_min = int(config.CHECK_INTERVAL_SEC / 60)
        send_message(
            chat_id,
            f"✅ Подписка по фильтру создана.\n"
            + f"📊 Добавлено монет: {added}. Проверяю каждые {interval_min} минут.\n\n"
            + "ℹ️ [1] = доступен для покупки, [2] = продан.\n"
            + "Текущие статусы:\n"
            + "\n".join(added_lines[:20])  # Показываем первые 20
            + (f"\n... и еще {len(added_lines) - 20}" if len(added_lines) > 20 else "")
            if added_lines else "✅ Подписка создана, но подходящих монет сейчас нет.",
        )
        return
    
    # Административные команды (требуют проверки прав)
    if clean.lower().startswith("/admin"):
        # Проверка admin прав
        if chat_id not in ADMIN_CHATS:
            send_message(chat_id, "❌ У вас нет прав для выполнения этой команды.")
            return
        
        parts = clean.split(maxsplit=2)
        if len(parts) < 2:
            send_message(
                chat_id,
                "🔧 Административные команды:\n\n"
                "/admin stats — статистика бота\n"
                "/admin broadcast <text> — рассылка всем\n"
                "/admin logs — последние ошибки"
            )
            return
        
        admin_cmd = parts[1].lower()
        
        # /admin stats
        if admin_cmd == "stats":
            import datetime
            uptime = datetime.datetime.now() - BOT_START_TIME
            uptime_str = str(uptime).split('.')[0]
            
            db_stats = state.db.get_stats()
            total_subscribers = db_stats['subscribers']
            total_watches = db_stats['watches']
            total_api_logs = db_stats['api_logs']
            
            send_message(
                chat_id,
                f"🔧 Статистика бота (admin):\n\n"
                f"⏱ Uptime: {uptime_str}\n"
                f"👥 Всего подписчиков: {total_subscribers}\n"
                f"📌 Всего подписок: {total_watches}\n"
                f"📊 Записей в api_logs: {total_api_logs}\n"
                f"✅ Бот работает нормально"
            )
            return
        
        # /admin broadcast
        if admin_cmd == "broadcast":
            if len(parts) < 3:
                send_message(chat_id, "Использование: /admin broadcast <текст сообщения>")
                return
            
            broadcast_text = parts[2]
            subscribers = list(state.subscribers)
            sent = 0
            failed = 0
            
            for subscriber_id in subscribers:
                try:
                    send_message(subscriber_id, f"📢 Объявление от администратора:\n\n{broadcast_text}")
                    sent += 1
                except Exception as exc:
                    logger.error(f"Broadcast failed for {subscriber_id}: {exc}")
                    failed += 1
            
            send_message(
                chat_id,
                f"✅ Рассылка завершена:\n"
                f"✔️ Отправлено: {sent}\n"
                f"❌ Ошибок: {failed}"
            )
            return
        
        # /admin logs
        if admin_cmd == "logs":
            recent_logs = state.db.get_recent_api_logs(limit=10)
            
            if not recent_logs:
                send_message(chat_id, "📝 Логов нет")
                return
            
            lines = ["📝 Последние 10 записей API логов:\n"]
            for log in recent_logs:
                timestamp = log['timestamp']
                endpoint = log['endpoint']
                status = log['status_code']
                error = log.get('error', '')
                
                if error:
                    lines.append(f"❌ {timestamp} | {endpoint} | {status} | {error[:50]}")
                else:
                    lines.append(f"✅ {timestamp} | {endpoint} | {status}")
            
            send_message(chat_id, "\n".join(lines))
            return
        
        send_message(chat_id, "❓ Неизвестная команда. Используй /admin для справки.")
        return

    coin = clean.lower()
    
    # Валидация тикера — отклоняем слишком длинные или содержащие недопустимые символы
    if len(coin) > 10:
        send_message(chat_id, "❌ Тикер монеты слишком длинный (макс. 10 символов). Используй /help для справки.")
        return
    
    if ' ' in coin or not coin.isalnum():
        send_message(chat_id, "❌ Некорректный тикер монеты. Тикер должен содержать только буквы и цифры. Используй /help для справки.")
        return
    
    # Проверка на кириллицу
    if any('\u0400' <= c <= '\u04FF' for c in coin):
        send_message(chat_id, "❌ Тикер монеты должен быть на латинице. Используй /help для справки.")
        return
    
    logger.info(f"Lookup token: {coin}")
    try:
        info = fetch_token_info(coin)
    except Exception as exc:
        logger.error(f"Error fetch_token_info for {coin}: {exc}")
        # register subscription anyway so user sees it in /list
        state.add_subscriber(chat_id)
        state.set_watch(chat_id, coin, "no_data")
        send_message(
            chat_id,
            f"Подписка на {coin.upper()} создана, но при получении данных произошла ошибка: {exc}. Буду пытаться и пришлю алерт если проблема останется.",
        )
        return

    if not info:
        state.add_subscriber(chat_id)
        state.set_watch(chat_id, coin, "no_data")
        send_message(chat_id, f"Подписка на {coin.upper()} создана, но данные не найдены.")
        return

    # Используем TokenStatus для красивого вывода
    token_status = TokenStatus.from_api_response(info)
    status = token_status.to_string()
    state.add_subscriber(chat_id)
    state.set_watch(chat_id, coin, status)
    interval_min = int(config.CHECK_INTERVAL_SEC / 60)
    
    # API возвращает APR в долях, форматируем для пользователя
    send_message(
        chat_id,
        f"✅ Подписка на {coin.upper()} создана\n\n"
        f"{token_status.format_for_user()}\n"
        f"🔔 Буду проверять каждые {interval_min} минут.",
    )


def run_bot() -> None:
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

    # Установка команд в Telegram UI
    _set_bot_commands()
    
    # Graceful shutdown handler
    def signal_handler(sig, frame):
        logger.info("🛑 Получен сигнал завершения, останавливаю бота...")
        logger.info("Завершаю соединения...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("🐝 Бот запущен. Ожидаю сообщения...")
    offset = 0
    threading.Thread(target=_monitor_loop, daemon=True).start()

    try:
        while True:
            updates = _get_updates(offset)
            for upd in updates:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                
                # Обработка callback query от inline кнопок
                if "callback_query" in upd:
                    _handle_callback_query(upd["callback_query"])
                    continue
                
                # Обработка обычных сообщений
                message = upd.get("message") or upd.get("channel_post")
                if not message:
                    continue
                chat = message.get("chat") or {}
                chat_id = str(chat.get("id"))
                text = message.get("text") or ""
                _handle_text(chat_id, text)
            time.sleep(config.POLL_INTERVAL_SEC)
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as exc:
        logger.error(f"❌ Критическая ошибка в run_bot: {exc}")
        raise


if __name__ == "__main__":
    run_bot()
