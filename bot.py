import asyncio
import aiohttp
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

# ===== КОНФИГ =====
FLASHGRAM_BOT_TOKEN = "1780244829:fi5IEFAljHni0Iy7NlVrXLnz5LFxglS7TPn"
API_BASE = "http://31.76.29.36:8081"
ADMIN_ID = 1780243448  # твой Telegram ID (число)
MINIAPP_URL = "https://harmony-fudge-de7464.netlify.app"  # НОВАЯ ССЫЛКА

# ===== НАСТРОЙКА БОТА =====
session = AiohttpSession(api=TelegramAPIServer.from_base(API_BASE))
bot = Bot(token=FLASHGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
dp = Dispatcher()

# ===== FIREBASE URL =====
FIREBASE_URL = "https://nft-app-8eda5-default-rtdb.firebaseio.com"

async def firebase_update(path, data):
    async with aiohttp.ClientSession() as sess:
        url = f"{FIREBASE_URL}/{path}.json"
        async with sess.patch(url, json=data) as resp:
            return await resp.json()

async def firebase_get(path):
    async with aiohttp.ClientSession() as sess:
        url = f"{FIREBASE_URL}/{path}.json"
        async with sess.get(url) as resp:
            return await resp.json()

# ===== ОБРАБОТЧИКИ =====
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть апгрейдер", web_app=types.WebAppInfo(url=MINIAPP_URL))]
    ])
    await message.answer("Нажми кнопку, чтобы запустить мини-апп:", reply_markup=keyboard)

# Обработка данных из веб-аппа
@dp.message(lambda msg: msg.web_app_data is not None)
async def web_app_data_handler(message: types.Message):
    data = json.loads(message.web_app_data.data)
    action = data.get('action')
    user_id = data.get('userId')
    username = data.get('username', 'Без имени')

    if action == 'new_user':
        # Уведомление о новом игроке
        await bot.send_message(ADMIN_ID, f"Новый игрок: {username} (ID {user_id})")

    elif action == 'withdraw':
        # Заявка на вывод – получаем номер заявки
        requests = await firebase_get('withdrawRequests')
        count = len(requests) if requests else 0
        number = count + 1

        if data.get('type') == 'stars':
            amount = data.get('amount')
            commission = data.get('commission')
            text = f"Заявка #{number}: {username} (ID {user_id})\nЗвёзды: {amount}⭐ (комиссия {commission}⭐)"
        else:
            gift_name = data.get('giftName')
            text = f"Заявка #{number}: {username} (ID {user_id})\nПодарок: {gift_name}"

        # Кнопки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{number}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{number}")
            ]
        ])
        await bot.send_message(ADMIN_ID, text, reply_markup=keyboard)

# Обработка нажатий на кнопки
@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    data = callback.data
    if data.startswith('confirm_') or data.startswith('reject_'):
        parts = data.split('_')
        if len(parts) != 2:
            await callback.answer("Неверный формат")
            return
        action_type = parts[0]
        try:
            number = int(parts[1])
        except:
            await callback.answer("Ошибка номера")
            return

        requests = await firebase_get('withdrawRequests')
        if not requests:
            await callback.answer("Заявка не найдена")
            return

        keys = list(requests.keys())
        if number > len(keys):
            await callback.answer("Заявка не найдена")
            return

        idx = number - 1
        key = keys[idx]
        status = 'completed' if action_type == 'confirm' else 'rejected'
        await firebase_update(f'withdrawRequests/{key}', {'status': status})

        await callback.answer(f"Заявка #{number} {'подтверждена' if action_type == 'confirm' else 'отклонена'}")
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(ADMIN_ID, f"Заявка #{number} {status}")

# ===== ЗАПУСК =====
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
