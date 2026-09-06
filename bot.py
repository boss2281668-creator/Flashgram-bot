import asyncio
import aiohttp
import json

FLASHGRAM_BOT_TOKEN = "1780244829:fi5IEFAljHni0Iy7NlVrXLnz5LFxglS7TPn"
API_BASE = "http://31.76.29.36:8081"
ADMIN_ID = 1780243448
MINIAPP_URL = "https://harmonious-fudge-de7464.netlify.app"  # НОВАЯ ССЫЛКА
FIREBASE_URL = "https://nft-app-8eda5-default-rtdb.firebaseio.com"

async def send_message(chat_id, text, reply_markup=None):
    url = f"{API_BASE}/bot{FLASHGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

async def answer_callback(callback_id, text, show_alert=False):
    url = f"{API_BASE}/bot{FLASHGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id, "text": text, "show_alert": show_alert}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

async def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    url = f"{API_BASE}/bot{FLASHGRAM_BOT_TOKEN}/editMessageReplyMarkup"
    payload = {"chat_id": chat_id, "message_id": message_id}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

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

async def handle_update(update):
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text == "/start":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🚀 Открыть апгрейдер", "web_app": {"url": MINIAPP_URL}}]
                ]
            }
            await send_message(chat_id, "Нажми кнопку, чтобы запустить мини-апп:", reply_markup=keyboard)
            return

        if "web_app_data" in msg:
            data = json.loads(msg["web_app_data"]["data"])
            action = data.get("action")
            user_id = data.get("userId")
            username = data.get("username", "Без имени")

            if action == "new_user":
                await send_message(ADMIN_ID, f"Новый игрок: {username} (ID {user_id})")

            elif action == "withdraw":
                requests = await firebase_get("withdrawRequests")
                count = len(requests) if requests else 0
                number = count + 1

                if data.get("type") == "stars":
                    amount = data.get("amount")
                    commission = data.get("commission")
                    text_msg = f"Заявка #{number}: {username} (ID {user_id})\nЗвёзды: {amount}⭐ (комиссия {commission}⭐)"
                else:
                    gift_name = data.get("giftName")
                    text_msg = f"Заявка #{number}: {username} (ID {user_id})\nПодарок: {gift_name}"

                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Подтвердить", "callback_data": f"confirm_{number}"},
                            {"text": "❌ Отклонить", "callback_data": f"reject_{number}"}
                        ]
                    ]
                }
                await send_message(ADMIN_ID, text_msg, reply_markup=keyboard)

    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]
        data = cb["data"]

        if data.startswith("confirm_") or data.startswith("reject_"):
            parts = data.split("_")
            if len(parts) != 2:
                await answer_callback(cb_id, "Неверный формат")
                return
            action_type = parts[0]
            try:
                number = int(parts[1])
            except:
                await answer_callback(cb_id, "Ошибка номера")
                return

            requests = await firebase_get("withdrawRequests")
            if not requests:
                await answer_callback(cb_id, "Заявка не найдена")
                return

            keys = list(requests.keys())
            if number > len(keys):
                await answer_callback(cb_id, "Заявка не найдена")
                return

            idx = number - 1
            key = keys[idx]
            status = "completed" if action_type == "confirm" else "rejected"
            await firebase_update(f"withdrawRequests/{key}", {"status": status})

            await answer_callback(cb_id, f"Заявка #{number} {'подтверждена' if action_type == 'confirm' else 'отклонена'}")
            await edit_message_reply_markup(chat_id, message_id, reply_markup={"inline_keyboard": []})
            await send_message(ADMIN_ID, f"Заявка #{number} {status}")

async def poll_updates():
    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                url = f"{API_BASE}/bot{FLASHGRAM_BOT_TOKEN}/getUpdates"
                params = {"offset": offset, "timeout": 30}
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        for update in data["result"]:
                            offset = update["update_id"] + 1
                            await handle_update(update)
                    else:
                        print("Ошибка:", data)
                        await asyncio.sleep(2)
            except Exception as e:
                print("Ошибка:", e)
                await asyncio.sleep(2)

if __name__ == "__main__":
    print("Бот запущен (FlashGram).")
    asyncio.run(poll_updates())
