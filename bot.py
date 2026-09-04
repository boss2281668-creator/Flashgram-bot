import asyncio
import aiohttp
import ssl

BOT_TOKEN = "1780244435:7jxPw_XahYYBhjhLd_Z2dkCosT6C59xVq2J"
MINIAPP_URL = "https://starlit-nougat-e91801.netlify.app"

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def send_message(chat_id, text, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, ssl=ssl_context) as resp:
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

async def poll_updates():
    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                url = f"{API_URL}/getUpdates"
                params = {"offset": offset, "timeout": 30}
                async with session.get(url, params=params, ssl=ssl_context) as resp:
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
    print("Бот запущен.")
    asyncio.run(poll_updates())
