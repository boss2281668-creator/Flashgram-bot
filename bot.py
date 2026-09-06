import asyncio
import aiohttp

FLASHGRAM_BOT_TOKEN = "1780244829:fi5IEFAljHni0Iy7NlVrXLnz5LFxglS7TPn"
API_BASE = "http://31.76.29.36:8081"
MINIAPP_URL = "https://fastidious-froyo-488a06.netlify.app"  # или другая старая ссылка

async def send_message(chat_id, text, reply_markup=None):
    url = f"{API_BASE}/bot{FLASHGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
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
        else:
            await send_message(chat_id, f"Ты написал: {text}")

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
