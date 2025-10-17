# handlers_admin.py
import io

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from openpyxl import Workbook
from aiogram import types, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot import bot
from config import ADMIN_IDS
from db.models import Session, Chanel, SubscriptionRequest
from keyboard import create_kb, kb_button

router = Router()

class FSMFillForm(StatesGroup):
    link = State()
    send = State()
    text_add_button = State()
    check_text_1 = State()
    check_text_2 = State()
    text_add_button_text = State()
    text_add_button_url = State()
    photo_add_button = State()
    check_photo_1 = State()
    check_photo_2 = State()
    photo_add_button_text = State()
    photo_add_button_url = State()
    video_add_button = State()
    check_video_1 = State()
    check_video_2 = State()
    video_add_button_text = State()
    video_add_button_url = State()
    check_video_note_1 = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def get_all_users_unblock():
    async with Session() as session:
        query = select(SubscriptionRequest).where(SubscriptionRequest.user_is_block == False)
        users = await session.execute(query)
        result = []
        for user in users.scalars():
            if user not in result:
                result.append(user.user_id)
    return result


def admin_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выполнить рассылку", callback_data="admin_mailing")],
        [InlineKeyboardButton(text="Выгрузить юзеров", callback_data="admin_export_users")],
        [InlineKeyboardButton(text="Заменить ссылку", callback_data="admin_change_link")]
    ])
    return keyboard


@router.message(Command("start"), F.from_user.id.in_(ADMIN_IDS))
async def admin_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Добро пожаловать в меню администратора!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "admin_export_users")
async def admin_export_users(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    async with Session() as db:
        result = await db.execute(select(SubscriptionRequest))
        requests = result.scalars().all()

    # Создаем Excel файл
    wb = Workbook()
    ws = wb.active
    ws.title = "Subscription Requests"

    # Заголовки
    headers = ["ID", "User ID", "Username", "First Name", "Last Name", "Channel ID", "Channel Name", "Time Request",
               "User Is Block"]
    ws.append(headers)

    # Данные
    for req in requests:
        ws.append([
            req.id,
            req.user_id,
            req.username,
            req.first_name,
            req.last_name,
            req.channel_id,
            req.channel_name,
            req.time_request.strftime("%Y-%m-%d %H:%M:%S") if req.time_request else None,
            req.user_is_block
        ])

    # Сохраняем в байтовый поток
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    await callback.message.answer_document(
        types.BufferedInputFile(file_stream.read(), filename="subscription_requests.xlsx"),
        caption="Выгрузка данных о подписках"
    )
    await callback.message.answer("Добро пожаловать в меню администратора!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "admin_change_link")
async def admin_change_link(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    async with Session() as db:
        result = await db.execute(select(Chanel))
        chanel = result.scalar_one_or_none()
        current_link = chanel.link if chanel else "не установлена"

    await callback.message.edit_text(
        f"Сейчас ваша ссылка - {current_link}. Введите новую ссылку!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back")]
        ])
    )
    await state.set_state(FSMFillForm.link)


@router.message(F.text, StateFilter(FSMFillForm.link))
async def admin_get_new_link(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # Проверяем, что сообщение похоже на ссылку
    if message.text.startswith(('http://', 'https://', 't.me/')):
        async with Session() as db:
            result = await db.execute(select(Chanel))
            chanel = result.scalar_one_or_none()

            if chanel:
                chanel.link = message.text
            else:
                chanel = Chanel(link=message.text)
                db.add(chanel)

            await db.commit()

        await message.answer("Ссылка изменена!", reply_markup=admin_menu_keyboard())
        await state.set_state(default_state)
        await state.clear()
    else:
        await message.answer("Пожалуйста, введите корректную ссылку (начинается с http://, https:// или t.me/)")


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(default_state)
    await state.clear()
    await callback.message.edit_text("Добро пожаловать в меню администратора!", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "admin_mailing", StateFilter(default_state), F.from_user.id.in_(ADMIN_IDS))
async def send_to_all(callback: types.Message, state: FSMContext):
    await callback.message.answer(text='Сейчас мы подготовим сообщение для рассылки по юзерам!\n'
                              'Отправьте пжл текстовое сообщение или картинку(можно с текстом) или видео(можно с текстом) или видео-кружок')
    await state.set_state(FSMFillForm.send)


#Создание текстового сообщения


@router.message(F.text, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer(text='Добавим кнопку-ссылку?', reply_markup=create_kb(2, yes='Да', no='Нет'))
    await state.set_state(FSMFillForm.text_add_button)


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.text_add_button), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_no(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    await cb.message.answer(text='Проверьте ваше сообщение для отправки')
    await cb.message.answer(text=dct['text'])
    await cb.message.answer(text='Отправляем?', reply_markup=create_kb(2, yes='Да', no='Нет'))
    await state.set_state(FSMFillForm.check_text_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_text_1), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_1(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text=dct['text'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'Сообщение отправлено {count} юзерам', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.text_add_button), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='Введите текст кнопки-ссылки')
    await state.set_state(FSMFillForm.text_add_button_text)


@router.message(F.text, StateFilter(FSMFillForm.text_add_button_text), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_yes_2(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer(text='Теперь введите корректный url(ссылка на сайт, телеграмм)')
    await state.set_state(FSMFillForm.text_add_button_url)


@router.message(F.text, StateFilter(FSMFillForm.text_add_button_url), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_yes_3(message: types.Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    dct = await state.get_data()
    try:
        await message.answer(text='Проверьте ваше сообщение для отправки')
        await message.answer(text=dct['text'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        await message.answer(text='Отправляем?', reply_markup=create_kb(2, yes='Да', no='Нет'))
        await state.set_state(FSMFillForm.check_text_2)
    except Exception:
        await message.answer(text='Скорее всего вы ввели не корректный url. Направьте корректный url')
        await state.set_state(FSMFillForm.text_add_button_url)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_text_2), F.from_user.id.in_(ADMIN_IDS))
async def check_text_yes_2(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text=dct['text'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'Сообщение отправлено {count} юзерам', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.check_text_1, FSMFillForm.check_text_2), F.from_user.id.in_(ADMIN_IDS))
async def check_message_no(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text=f'Сообщение не отправлено', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


#Создание фото-сообщения


@router.message(F.photo, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    try:
        await state.update_data(caption=message.caption)
    except Exception:
        pass
    await message.answer(text='Добавим кнопку-ссылку?', reply_markup=create_kb(2, yes='Да', no='Нет'))
    await state.set_state(FSMFillForm.photo_add_button)


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.photo_add_button), F.from_user.id.in_(ADMIN_IDS))
async def text_add_button_no(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    await cb.message.answer(text='Проверьте ваше сообщение для отправки')
    if dct.get('caption'):
        await cb.message.answer_photo(photo=dct['photo_id'], caption=dct['caption'])
    else:
        await cb.message.answer_photo(photo=dct['photo_id'])
    await cb.message.answer(text='Отправляем?', reply_markup=create_kb(2, yes='Да', no='Нет'))
    await state.set_state(FSMFillForm.check_photo_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_photo_1), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_1(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            if dct.get('caption'):
                await bot.send_photo(user_id, photo=dct['photo_id'], caption=dct['caption'])
            else:
                await bot.send_photo(user_id, photo=dct['photo_id'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'Сообщение отправлено {count} юзерам', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.photo_add_button), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='Введите текст кнопки-ссылки')
    await state.set_state(FSMFillForm.photo_add_button_text)


@router.message(F.text, StateFilter(FSMFillForm.photo_add_button_text), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button_yes_2(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer(text='Теперь введите корректный url(ссылка на сайт, телеграмм)')
    await state.set_state(FSMFillForm.photo_add_button_url)


@router.message(F.text, StateFilter(FSMFillForm.photo_add_button_url), F.from_user.id.in_(ADMIN_IDS))
async def photo_add_button_yes_3(message: types.Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    dct = await state.get_data()
    try:
        await message.answer(text='Проверьте ваше сообщение для отправки')
        if dct.get('caption'):
            await message.answer_photo(photo=dct['photo_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        else:
            await message.answer_photo(photo=dct['photo_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        await message.answer(text='Отправляем?', reply_markup=create_kb(2, yes='Да', no='Нет'))
        await state.set_state(FSMFillForm.check_photo_2)
    except Exception as e:
        print(e)
        await message.answer(text='Скорее всего вы ввели не корректный url. Направьте корректный url')
        await state.set_state(FSMFillForm.photo_add_button_url)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_photo_2), F.from_user.id.in_(ADMIN_IDS))
async def check_photo_yes_2(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            if dct.get('caption'):
                    await bot.send_photo(user_id, photo=dct['photo_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            else:
                await bot.send_photo(user_id, photo=dct['photo_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'Сообщение отправлено {count} юзерам', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.check_text_1, FSMFillForm.check_text_2,
            FSMFillForm.check_photo_1, FSMFillForm.check_photo_2), F.from_user.id.in_(ADMIN_IDS))
async def check_message_no(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text=f'Сообщение не отправлено', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


#Создание видео-сообщения


@router.message(F.video, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button(message: types.Message, state: FSMContext):
    await state.update_data(video_id=message.video.file_id)
    try:
        await state.update_data(caption=message.caption)
    except Exception:
        pass
    await message.answer(text='Добавим кнопку-ссылку?', reply_markup=create_kb(2, yes='Да', no='Нет'))
    await state.set_state(FSMFillForm.video_add_button)


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.video_add_button), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_no(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    await cb.message.answer(text='Проверьте ваше сообщение для отправки')
    if dct.get('caption'):
        await cb.message.answer_video(video=dct['video_id'], caption=dct['caption'])
    else:
        await cb.message.answer_video(video=dct['video_id'])
    await cb.message.answer(text='Отправляем?', reply_markup=create_kb(2, yes='Да', no='Нет'))
    await state.set_state(FSMFillForm.check_video_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_video_1), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_1(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            if dct.get('caption'):
                await bot.send_video(user_id, video=dct['video_id'], caption=dct['caption'])
            else:
                await bot.send_video(user_id, video=dct['video_id'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'Сообщение отправлено {count} юзерам', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.video_add_button), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_yes_1(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text='Введите текст кнопки-ссылки')
    await state.set_state(FSMFillForm.video_add_button_text)


@router.message(F.text, StateFilter(FSMFillForm.video_add_button_text), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_yes_2(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer(text='Теперь введите корректный url(ссылка на сайт, телеграмм)')
    await state.set_state(FSMFillForm.video_add_button_url)


@router.message(F.text, StateFilter(FSMFillForm.video_add_button_url), F.from_user.id.in_(ADMIN_IDS))
async def video_add_button_yes_3(message: types.Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    dct = await state.get_data()
    try:
        await message.answer(text='Проверьте ваше сообщение для отправки')
        if dct.get('caption'):
            await message.answer_video(video=dct['video_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        else:
            await message.answer_video(video=dct['video_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
        await message.answer(text='Отправляем?', reply_markup=create_kb(2, yes='Да', no='Нет'))
        await state.set_state(FSMFillForm.check_video_2)
    except Exception as e:
        print(e)
        await message.answer(text='Скорее всего вы ввели не корректный url. Направьте корректный url')
        await state.set_state(FSMFillForm.video_add_button_url)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_video_2), F.from_user.id.in_(ADMIN_IDS))
async def check_video_yes_2(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            if dct.get('caption'):
                await bot.send_video(user_id, video=dct['video_id'], caption=dct['caption'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            else:
                await bot.send_video(user_id, video=dct['video_id'], reply_markup=kb_button(dct['button_text'], dct['button_url']))
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'Сообщение отправлено {count} юзерам', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


#Создание видео-кружка


@router.message(F.video_note, StateFilter(FSMFillForm.send), F.from_user.id.in_(ADMIN_IDS))
async def video_note_check(message: types.Message, state: FSMContext):
    await state.update_data(video_note_id=message.video_note.file_id)
    await message.answer(text='Проверьте вашу запись в кружке для отправки')
    await message.answer(text='Отправляем?', reply_markup=create_kb(2, yes='Да', no='Нет'))
    await state.set_state(FSMFillForm.check_video_note_1)


@router.callback_query(F.data == 'yes', StateFilter(FSMFillForm.check_video_note_1), F.from_user.id.in_(ADMIN_IDS))
async def check_video_note_yes_1(cb: types.CallbackQuery, state: FSMContext):
    dct = await state.get_data()
    users = await get_all_users_unblock()
    count = 0
    for user_id in users:
        try:
            await bot.send_video_note(user_id, video_note=dct['video_note_id'])
            count += 1
        except Exception as e:
            await bot.send_message(1012882762, str(e))
            await bot.send_message(1012882762, str(user_id))
    await cb.message.answer(text=f'Сообщение отправлено {count} юзерам', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()


# Выход из рассылки без отправки


@router.callback_query(F.data == 'no', StateFilter(FSMFillForm.check_text_1, FSMFillForm.check_text_2,
                       FSMFillForm.check_photo_1, FSMFillForm.check_photo_2, FSMFillForm.check_video_1,
                       FSMFillForm.check_video_2, FSMFillForm.check_video_note_1), F.from_user.id.in_(ADMIN_IDS))
async def check_message_no(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(text=f'Сообщение не отправлено', reply_markup=admin_menu_keyboard())
    await state.set_state(default_state)
    await state.clear()
