"""
Структурированные типы данных для работы с токенами и статусами.
Обеспечивает type safety и явное представление данных.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TokenStatus:
    """
    Структурированное представление статуса токена.
    
    Attributes:
        coin: Название монеты (нижний регистр)
        fixed_list: Список статусов fixed продуктов (1=доступен, 2=продан)
        sort_apr: APR процент для сортировки
        timestamp: Время получения данных
    """
    coin: str
    fixed_list: List[int]
    sort_apr: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        """Автоматическая установка timestamp если не указан."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        # Нормализация coin к нижнему регистру
        self.coin = self.coin.lower()
    
    @classmethod
    def from_api_response(cls, item: Dict[str, Any]) -> 'TokenStatus':
        """
        Создать TokenStatus из ответа API.
        
        Args:
            item: Словарь с данными из API
            
        Returns:
            TokenStatus объект
        
        Example:
            >>> item = {"asset": "ALGO", "sale_status": [{"fixed": 1}], "sort_apr": "5.2"}
            >>> status = TokenStatus.from_api_response(item)
            >>> status.coin
            'algo'
        """
        from parser_gate import extract_sale_statuses, _sort_apr_percent
        
        coin = str(item.get('asset', '')).lower()
        statuses = extract_sale_statuses(item)
        fixed_list = statuses.get('fixed_list', [])
        sort_apr = _sort_apr_percent(item)
        
        return cls(
            coin=coin,
            fixed_list=fixed_list,
            sort_apr=sort_apr,
            timestamp=datetime.now()
        )
    
    def to_string(self) -> str:
        """
        Сериализовать в строку для хранения в БД.
        
        Returns:
            JSON строка
        """
        return json.dumps({
            'fixed_list': self.fixed_list,
            'sort_apr': self.sort_apr,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        })
    
    @classmethod
    def from_string(cls, coin: str, data_str: str) -> 'TokenStatus':
        """
        Восстановить из строки из БД.
        
        Args:
            coin: Название монеты
            data_str: JSON строка с данными
            
        Returns:
            TokenStatus объект
        """
        data = json.loads(data_str)
        timestamp = data.get('timestamp')
        if timestamp:
            timestamp = datetime.fromisoformat(timestamp)
        
        return cls(
            coin=coin,
            fixed_list=data.get('fixed_list', []),
            sort_apr=data.get('sort_apr'),
            timestamp=timestamp or datetime.now()
        )
    
    def is_available(self) -> bool:
        """
        Проверить, доступен ли токен для покупки.
        
        Returns:
            True если хотя бы один продукт доступен (status=1)
        """
        return any(s == 1 for s in self.fixed_list)
    
    def is_sold_out(self) -> bool:
        """
        Проверить, распродан ли токен.
        
        Returns:
            True если все продукты распроданы (status=2)
        """
        return len(self.fixed_list) > 0 and all(s == 2 for s in self.fixed_list)
    
    def is_partially_available(self) -> bool:
        """
        Проверить, частично доступен ли токен.
        
        Returns:
            True если есть и доступные (1) и распроданные (2) продукты
        """
        has_available = any(s == 1 for s in self.fixed_list)
        has_sold = any(s == 2 for s in self.fixed_list)
        return has_available and has_sold
    
    def get_status_emoji(self) -> str:
        """
        Получить эмодзи для визуализации статуса.
        
        Returns:
            Строка с эмодзи
        """
        if self.is_partially_available():
            return "🟡"
        elif self.is_available():
            return "🟢"
        elif self.is_sold_out():
            return "🔴"
        else:
            return "⚪"
    
    def get_status_text(self) -> str:
        """
        Получить текстовое описание статуса.
        
        Returns:
            Человекопонятное описание
        """
        if not self.fixed_list:
            return "нет фиксированных продуктов"
        elif self.is_partially_available():
            return "частично доступен"
        elif self.is_available():
            return "доступен для покупки"
        elif self.is_sold_out():
            return "распродан"
        else:
            return f"статус неизвестен ({self.fixed_list})"
    
    def format_for_user(self) -> str:
        """
        Форматировать для отображения пользователю.
        
        Returns:
            Строка в формате "COIN: 🟢 доступен [1, 2] (APR: 5.2%)"
        """
        emoji = self.get_status_emoji()
        status_text = self.get_status_text()
        # API возвращает APR в долях (0.0246 = 2.46%), умножаем на 100
        apr_text = f" (APR: {self.sort_apr * 100:.2f}%)" if self.sort_apr else ""
        
        return f"{self.coin.upper()}: {emoji} {status_text} {self.fixed_list}{apr_text}"
    
    def __eq__(self, other: Any) -> bool:
        """
        Сравнение статусов.
        
        Два статуса равны, если у них одинаковый coin и fixed_list.
        sort_apr и timestamp не учитываются.
        """
        if not isinstance(other, TokenStatus):
            return False
        return self.coin == other.coin and self.fixed_list == other.fixed_list
    
    def __hash__(self) -> int:
        """Хеш для использования в set/dict."""
        return hash((self.coin, tuple(self.fixed_list)))
    
    def __repr__(self) -> str:
        """Представление для отладки."""
        return f"TokenStatus(coin={self.coin!r}, fixed_list={self.fixed_list}, sort_apr={self.sort_apr})"
