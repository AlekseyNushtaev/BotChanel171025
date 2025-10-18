import asyncio

from aiogram import types, F, Router
from aiogram.filters import ChatMemberUpdatedFilter, KICKED, MEMBER
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ChatMemberUpdated, InlineKeyboardMarkup, \
    InlineKeyboardButton
from sqlalchemy import select

from bot import bot
from config import ADMIN_IDS
from db.models import SubscriptionRequest, Session, Chanel

# Инициализация роутера для обработки пользовательских событий
router = Router()


@router.chat_join_request()
async def handle_join_request(join_request: types.ChatJoinRequest) -> None:
    """
    Обрабатывает запрос на вступление пользователя в канал.

    Эта функция:
    1. Извлекает информацию о пользователе и канале
    2. Сохраняет запрос на подписку в базу данных
    3. Отправляет пользователю кнопку для подтверждения
    4. Автоматически удаляет сообщение через 60 секунд

    Параметры:
        join_request (types.ChatJoinRequest): Объект запроса на вступление

    Возвращает:
        None
    """
    # Извлекаем данные пользователя и канала из запроса
    user = join_request.from_user
    chat = join_request.chat

    async with Session() as db:
        # Создаем новый объект запроса на подписку
        request = SubscriptionRequest(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            channel_id=chat.id,
            channel_name=chat.title
        )
        # Добавляем запрос в сессию и сохраняем в БД
        db.add(request)
        await db.commit()

    # Создаем клавиатуру с кнопкой подтверждения
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="👤 Я человек!")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    # Отправляем сообщение с кнопкой подтверждения
    await bot.send_message(
        chat_id=user.id,
        text="👋 Доброго времени суток! Благодарим вас за подписку на наш канал! Для принятия вашей заявки, подтвердите, что вы человек, нажав кнопку ниже! ✅",
        reply_markup=keyboard
    )


@router.message(F.text == "👤 Я человек!")
async def handle_step_1(message: types.Message):
    """Обрабатывает нажатие кнопки 'Я человек!'"""

    async with Session() as db:
        # Находим запрос в базе данных
        result = await db.execute(
            select(Chanel))
        chanel = result.scalar_one_or_none()
        if not chanel:
            request = Chanel()
            # Добавляем запрос в сессию и сохраняем в БД
            db.add(request)
            await db.commit()
        result = await db.execute(
            select(Chanel))
        chanel = result.scalar_one_or_none()
        try:
            # Создаем кнопку для подписки на канал
            subscribe_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Подписаться", url=chanel.link)]
            ])

            # Отправляем сообщение с просьбой подписаться
            await bot.send_message(
                chat_id=message.from_user.id,
                text="📢 Пожалуйста, подпишитесь на этот канал!",
                reply_markup=subscribe_keyboard
            )

        except Exception as e:
            print(e)
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"❌ Ошибка при нажатии на кнопку Я человек - {e}"
                    )
                except Exception as e:
                    pass

        # Ждем 60 секунд и отправляем сообщение с благодарностью
        await asyncio.sleep(90)
        await bot.send_message(
            chat_id=message.from_user.id,
            text="🙏 Спасибо за вашу заявку на подписку! Модераторы рассмотрят её в ближайшее время! ⏰"
        )


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot(event: ChatMemberUpdated) -> None:
    """
    Обрабатывает событие блокировки бота пользователем.

    Помечает пользователя как заблокированного в базе данных.

    Параметры:
        event (ChatMemberUpdated): Событие изменения статуса чата

    Возвращает:
        None
    """
    async with Session() as db:
        # Поиск всех записей для указанного пользователя
        result = await db.execute(
            select(SubscriptionRequest).filter(
                SubscriptionRequest.user_id == event.from_user.id,
            )
        )
        requests = result.scalars().all()

        # Обновление статуса блокировки для всех записей
        for request in requests:
            request.user_is_block = True
        await db.commit()


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_unblocked_bot(event: ChatMemberUpdated) -> None:
    """
    Обрабатывает событие разблокировки бота пользователем.

    Помечает пользователя как активного в базе данных.

    Параметры:
        event (ChatMemberUpdated): Событие изменения статуса чата

    Возвращает:
        None
    """
    async with Session() as db:
        # Поиск всех записей для указанного пользователя
        result = await db.execute(
            select(SubscriptionRequest).filter(
                SubscriptionRequest.user_id == event.from_user.id,
            )
        )
        requests = result.scalars().all()

        # Обновление статуса блокировки для всех записей
        for request in requests:
            request.user_is_block = False
        await db.commit()