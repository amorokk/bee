"""
База данных для хранения подписок, отслеживаемых монет и логов API.
Использует SQLite для простоты и надежности.
"""

import sqlite3
import json
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime


class Database:
    """Класс для работы с SQLite базой данных бота."""
    
    def __init__(self, db_path: str = 'bot_data.db'):
        """
        Инициализация базы данных.
        
        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для безопасной работы с соединением."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Доступ к колонкам по имени
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Создание таблиц при первом запуске."""
        with self.get_connection() as conn:
            conn.executescript('''
                -- Подписчики бота
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id TEXT PRIMARY KEY,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paused INTEGER DEFAULT 0  -- 0 = активен, 1 = на паузе
                );
                
                -- Отслеживаемые монеты
                CREATE TABLE IF NOT EXISTS watches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    current_status TEXT,  -- JSON строка статуса
                    last_check TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, coin)
                );
                
                CREATE INDEX IF NOT EXISTS idx_watches_chat_coin 
                ON watches(chat_id, coin);
                
                -- Логи запросов к API (для мониторинга)
                CREATE TABLE IF NOT EXISTS api_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    endpoint TEXT,
                    status_code INTEGER,
                    response_time_ms INTEGER,
                    error TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_api_logs_timestamp 
                ON api_logs(timestamp);
            ''')
            
            # Миграция: добавить поле paused если его нет
            cursor = conn.execute("PRAGMA table_info(subscribers)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'paused' not in columns:
                conn.execute('ALTER TABLE subscribers ADD COLUMN paused INTEGER DEFAULT 0')
    
    # =========================
    # Subscribers
    # =========================
    
    def add_subscriber(self, chat_id: str) -> bool:
        """
        Добавить подписчика.
        
        Returns:
            True если добавлен, False если уже существовал
        """
        try:
            with self.get_connection() as conn:
                conn.execute(
                    'INSERT INTO subscribers (chat_id) VALUES (?)',
                    (chat_id,)
                )
                return True
        except sqlite3.IntegrityError:
            return False  # Уже существует
    
    def remove_subscriber(self, chat_id: str) -> bool:
        """
        Удалить подписчика и все его отслеживания.
        
        Returns:
            True если удален, False если не существовал
        """
        with self.get_connection() as conn:
            # Удаляем watches
            conn.execute('DELETE FROM watches WHERE chat_id = ?', (chat_id,))
            # Удаляем subscriber
            cursor = conn.execute(
                'DELETE FROM subscribers WHERE chat_id = ?',
                (chat_id,)
            )
            return cursor.rowcount > 0
    
    def get_all_subscribers(self) -> Set[str]:
        """Получить всех подписчиков."""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT chat_id FROM subscribers')
            return {row['chat_id'] for row in cursor.fetchall()}
    
    def is_paused(self, chat_id: str) -> bool:
        """Проверить, на паузе ли подписчик."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT paused FROM subscribers WHERE chat_id = ?',
                (chat_id,)
            )
            row = cursor.fetchone()
            return bool(row['paused']) if row else False
    
    def set_paused(self, chat_id: str, paused: bool) -> None:
        """Установить статус паузы для подписчика."""
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE subscribers SET paused = ? WHERE chat_id = ?',
                (1 if paused else 0, chat_id)
            )
    
    # =========================
    # Watches
    # =========================
    
    def add_watch(self, chat_id: str, coin: str, status: str) -> None:
        """
        Добавить или обновить отслеживание монеты.
        
        Args:
            chat_id: ID чата
            coin: Название монеты
            status: JSON строка со статусом
        """
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO watches (chat_id, coin, current_status, last_check)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id, coin) DO UPDATE SET
                    current_status = excluded.current_status,
                    last_check = excluded.last_check
            ''', (chat_id, coin, status, datetime.now()))
    
    def update_watch_status(self, chat_id: str, coin: str, status: str) -> None:
        """Обновить статус отслеживаемой монеты."""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE watches 
                SET current_status = ?, last_check = ?
                WHERE chat_id = ? AND coin = ?
            ''', (status, datetime.now(), chat_id, coin))
    
    def remove_watch(self, chat_id: str, coin: str) -> bool:
        """
        Удалить отслеживание монеты.
        
        Returns:
            True если удалено, False если не существовало
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                'DELETE FROM watches WHERE chat_id = ? AND coin = ?',
                (chat_id, coin)
            )
            return cursor.rowcount > 0
    
    def get_watches_for_chat(self, chat_id: str) -> Dict[str, str]:
        """
        Получить все отслеживания для конкретного чата.
        
        Returns:
            Словарь {coin: status}
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT coin, current_status FROM watches WHERE chat_id = ?',
                (chat_id,)
            )
            return {row['coin']: row['current_status'] for row in cursor.fetchall()}
    
    def get_all_watches(self) -> List[Tuple[str, str, str]]:
        """
        Получить все отслеживания.
        
        Returns:
            Список кортежей (chat_id, coin, status)
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT chat_id, coin, current_status FROM watches'
            )
            return [
                (row['chat_id'], row['coin'], row['current_status'])
                for row in cursor.fetchall()
            ]
    
    # =========================
    # API Logs
    # =========================
    
    def log_api_request(
        self,
        endpoint: str,
        status_code: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Записать лог запроса к API.
        
        Args:
            endpoint: URL endpoint
            status_code: HTTP статус код
            response_time_ms: Время ответа в миллисекундах
            error: Текст ошибки (если была)
        """
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO api_logs (endpoint, status_code, response_time_ms, error)
                VALUES (?, ?, ?, ?)
            ''', (endpoint, status_code, response_time_ms, error))
    
    def get_recent_api_logs(self, limit: int = 100) -> List[Dict]:
        """
        Получить последние логи API.
        
        Args:
            limit: Количество записей
            
        Returns:
            Список словарей с данными логов
        """
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT timestamp, endpoint, status_code, response_time_ms, error
                FROM api_logs
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_logs(self, days: int = 30) -> int:
        """
        Удалить старые логи.
        
        Args:
            days: Удалить логи старше N дней
            
        Returns:
            Количество удаленных записей
        """
        with self.get_connection() as conn:
            cursor = conn.execute('''
                DELETE FROM api_logs
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            ''', (days,))
            return cursor.rowcount
    
    # =========================
    # Maintenance
    # =========================
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику базы данных."""
        with self.get_connection() as conn:
            stats = {}
            
            cursor = conn.execute('SELECT COUNT(*) as count FROM subscribers')
            stats['subscribers'] = cursor.fetchone()['count']
            
            cursor = conn.execute('SELECT COUNT(*) as count FROM watches')
            stats['watches'] = cursor.fetchone()['count']
            
            cursor = conn.execute('SELECT COUNT(*) as count FROM api_logs')
            stats['api_logs'] = cursor.fetchone()['count']
            
            return stats
    
    def vacuum(self) -> None:
        """Оптимизировать базу данных (освободить место)."""
        with self.get_connection() as conn:
            conn.execute('VACUUM')
