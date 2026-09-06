import asyncio
import aiohttp
import json
import ssl

# ===== НАСТРОЙКИ =====
FLASHGRAM_BOT_TOKEN = "1780244829:fi5IEFAljHni0Iy7NlVrXLnz5LFxglS7TPn"
API_BASE = "http://31.76.29.36:8081"
MINIAPP_URL = "https://harmonious-fudge-de7464.netlify.app"
ADMIN_CHAT_ID = 1780243448  # твой Telegram ID (туда будут уведомления)

# ===== ОТПРАВКА СООБЩЕНИЙ =====
async def send_message(chat_id, text, reply_markup=None):
    url = f"{API_BASE}/bot{FLASHGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

# ===== ОБРАБОТЧИК ОБНОВЛЕНИЙ =====
async def handle_update(update):
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        # Команда /start – кнопка с мини-аппом
        if text == "/start":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🚀 Открыть апгрейдер", "web_app": {"url": MINIAPP_URL}}]
                ]
            }
            await send_message(chat_id, "Нажми кнопку, чтобы запустить мини-апп:", reply_markup=keyboard)
            return

        # Данные из веб-аппа
        if "web_app_data" in msg:
            data = json.loads(msg["web_app_data"]["data"])
            action = data.get("action")
            user_id = data.get("userId")
            username = data.get("username", "Без имени")

            if action == "new_user":
                await send_message(ADMIN_CHAT_ID, f"Новый игрок: {username} (ID {user_id})")

            elif action == "withdraw":
                # Отправляем админу уведомление о заявке
                if data.get("type") == "stars":
                    amount = data.get("amount")
                    commission = data.get("commission")
                    text_msg = f"Заявка на вывод: {username} (ID {user_id})\nЗвёзды: {amount}⭐ (комиссия {commission}⭐)"
                else:
                    gift_name = data.get("giftName")
                    text_msg = f"Заявка на вывод: {username} (ID {user_id})\nПодарок: {gift_name}"
                await send_message(ADMIN_CHAT_ID, text_msg)

# ===== ПОЛЛИНГ ОБНОВЛЕНИЙ =====
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

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("Бот запущен (FlashGram).")
    asyncio.run(poll_updates())
