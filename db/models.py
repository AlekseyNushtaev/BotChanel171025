import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship

# Настройка асинхронного подключения к SQLite3
DB_URL = "sqlite+aiosqlite:///db/database.db"
engine = create_async_engine(DB_URL)  # Асинхронный движок SQLAlchemy
Session = async_sessionmaker(expire_on_commit=False, bind=engine)  # Фабрика сессий


class Base(DeclarativeBase, AsyncAttrs):
    """Базовый класс для декларативных моделей с поддержкой асинхронных атрибутов"""
    pass


class Chanel(Base):
    """Модель для хранения информации о каналах"""
    __tablename__ = "channel"

    id = Column(Integer, primary_key=True)  # ID канала
    link = Column(String, default="https://telegram.org/")  # Ссылка на канал


class SubscriptionRequest(Base):
    """Модель для хранения запросов на подписку"""
    __tablename__ = "subscription_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)  # ID пользователя Telegram
    username = Column(String)  # @username пользователя
    first_name = Column(String)  # Имя пользователя
    last_name = Column(String)  # Фамилия пользователя
    channel_id = Column(BigInteger, nullable=False)  # ID канала
    channel_name = Column(String)  # Название канала
    time_request = Column(DateTime, default=datetime.datetime.now)  # Время запроса
    user_is_block = Column(Boolean, default=False)  # Флаг блокировки пользователя


async def create_tables():
    """Создает таблицы в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
