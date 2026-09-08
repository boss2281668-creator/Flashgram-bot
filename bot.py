import asyncio
import aiohttp
import json
import random
import sys
from datetime import datetime, timedelta

# ---------- ТВОЙ НОВЫЙ ТОКЕН (ВРЕМЕННО) ----------
TOKEN = "1780244992:JTLJRwQM5F_dUbEG4WauZBYznNqSFNzmnE5"
API_BASE = "https://api.telegram.org"
FIREBASE_URL = "https://nft-app-8eda5-default-rtdb.firebaseio.com"

ADMIN_IDS = ["1780243448", "1780243287"]

BONUS_AMOUNT_GRAM = 5000
BONUS_INTERVAL_HOURS = 12
EARN_AMOUNT_GRAM = 2500
CRON_TO_GRAM = 10000
VIP_DURATION_DAYS = 7

VIP_PRICES = {
    "Gold": 100,
    "Diamond": 250,
    "Rich": 500
}

VIP_BONUSES = {
    "Gold": {"cron": 5, "gram": 10000, "luck": 0.05, "cooldown": 8},
    "Diamond": {"cron": 15, "gram": 25000, "luck": 0.10, "cooldown": 4},
    "Rich": {"cron": 25, "gram": 50000, "luck": 0.15, "cooldown": 2}
}

GAMES = {
    "basketball": {
        "name": "🏀 Баскетбол",
        "keywords": ["бас", "баскетбол"],
        "success_stickers": ["🏀🔥", "🏀💥", "🏀⭐"],
        "fail_stickers": ["🏀💔", "🏀❌", "🏀😢"]
    },
    "football": {
        "name": "⚽ Футбол",
        "keywords": ["фут", "футбол"],
        "success_stickers": ["⚽🔥", "⚽💥", "⚽⭐"],
        "fail_stickers": ["⚽💔", "⚽❌", "⚽😢"]
    },
    "tennis": {
        "name": "🎾 Теннис",
        "keywords": ["тенис", "теннис"],
        "success_stickers": ["🎾🔥", "🎾💥", "🎾⭐"],
        "fail_stickers": ["🎾💔", "🎾❌", "🎾😢"]
    },
    "darts": {
        "name": "🎯 Дартс",
        "keywords": ["дартс", "дарц"],
        "success_stickers": ["🎯🔥", "🎯💥", "🎯⭐"],
        "fail_stickers": ["🎯💔", "🎯❌", "🎯😢"]
    }
}

CHANNELS = [
    {"name": "CronChannel", "id": "-1001234567890"}
]

CHAT_LINK = "https://t.me/CronChat"

def get_main_keyboard(user_id):
    keyboard = [
        ["👤 Профиль", "📋 Команды", "🏆 Топ"],
        ["💎 Донат", "💸 Перевести", "🎮 Игры"],
        ["🎁 Бонус", "💬 Чаты", "💰 Заработать"]
    ]
    if is_admin(user_id):
        keyboard.insert(2, ["⚙️ Админ панель"])
    return {"keyboard": keyboard, "resize_keyboard": True, "one_time_keyboard": False}

# ---------- БЕЗОПАСНЫЕ ЗАПРОСЫ К API ----------
async def send_message(chat_id, text, reply_markup=None):
    url = f"{API_BASE}/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                return await resp.json()
    except Exception as e:
        print(f"[ERROR] send_message failed: {e}")
        return None

async def firebase_get(path):
    try:
        async with aiohttp.ClientSession() as sess:
            url = f"{FIREBASE_URL}/{path}.json"
            async with sess.get(url, timeout=10) as resp:
                return await resp.json()
    except Exception as e:
        print(f"[ERROR] firebase_get({path}) failed: {e}")
        return None

async def firebase_set(path, data):
    try:
        async with aiohttp.ClientSession() as sess:
            url = f"{FIREBASE_URL}/{path}.json"
            async with sess.put(url, json=data, timeout=10) as resp:
                return await resp.json()
    except Exception as e:
        print(f"[ERROR] firebase_set({path}) failed: {e}")
        return None

async def firebase_delete(path):
    try:
        async with aiohttp.ClientSession() as sess:
            url = f"{FIREBASE_URL}/{path}.json"
            async with sess.delete(url, timeout=10) as resp:
                return await resp.json()
    except Exception as e:
        print(f"[ERROR] firebase_delete({path}) failed: {e}")
        return None

# ---------- ОСТАЛЬНЫЕ ФУНКЦИИ ----------
async def check_vip_expiry(user_data):
    vip_until = user_data.get("vip_until")
    if vip_until:
        try:
            until = datetime.fromisoformat(vip_until)
            if datetime.now() > until:
                user_data["vip"] = None
                user_data["vip_until"] = None
                user_data["last_vip_claim"] = None
        except:
            user_data["vip"] = None
            user_data["vip_until"] = None
            user_data["last_vip_claim"] = None
    return user_data

async def get_user_data(user_id, username=None):
    data = await firebase_get(f"users/{user_id}")
    if not data:
        data = {
            "balance_cron": 0,
            "balance_gram": 100,
            "vip": None,
            "vip_until": None,
            "last_vip_claim": None,
            "last_bonus": None,
            "earned_channels": {},
            "username": username or "Без имени"
        }
        await firebase_set(f"users/{user_id}", data)
    else:
        data = await check_vip_expiry(data)
        if username and data.get("username") != username:
            data["username"] = username
            await firebase_set(f"users/{user_id}", data)
    return data

async def update_user_data(user_id, data):
    await firebase_set(f"users/{user_id}", data)

async def check_subscription(user_id, channel_id):
    url = f"{API_BASE}/bot{TOKEN}/getChatMember"
    payload = {"chat_id": channel_id, "user_id": user_id}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                data = await resp.json()
                if data.get("ok"):
                    status = data["result"].get("status")
                    return status in ("member", "administrator", "creator")
                return False
    except Exception as e:
        print(f"[ERROR] check_subscription: {e}")
        return False

async def apply_vip_bonuses(user_id, user_data):
    user_data = await check_vip_expiry(user_data)
    vip = user_data.get("vip")
    if not vip:
        return user_data, None
    vip_info = VIP_BONUSES.get(vip)
    if not vip_info:
        return user_data, None
    last_claim = user_data.get("last_vip_claim")
    now = datetime.now()
    if last_claim:
        try:
            last_time = datetime.fromisoformat(last_claim)
        except:
            last_time = now - timedelta(hours=vip_info["cooldown"])
    else:
        last_time = now - timedelta(hours=vip_info["cooldown"])
    if (now - last_time) >= timedelta(hours=vip_info["cooldown"]):
        user_data["balance_cron"] = user_data.get("balance_cron", 0) + vip_info["cron"]
        user_data["balance_gram"] = user_data.get("balance_gram", 0) + vip_info["gram"]
        user_data["last_vip_claim"] = now.isoformat()
        return user_data, {"cron": vip_info["cron"], "gram": vip_info["gram"], "vip": vip}
    return user_data, None

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def get_top_users(limit=10):
    users = await firebase_get("users")
    if not users:
        return []
    filtered = []
    for uid, data in users.items():
        if uid in ADMIN_IDS:
            continue
        cron = data.get("balance_cron", 0)
        gram = data.get("balance_gram", 0)
        username = data.get("username", uid)
        filtered.append({"id": uid, "username": username, "cron": cron, "gram": gram})
    sorted_users = sorted(filtered, key=lambda x: x["gram"], reverse=True)
    return sorted_users[:limit]

ADMIN_PANEL = {
    "inline_keyboard": [
        [{"text": "💰 Выдать cron", "callback_data": "admin_give_cron"}],
        [{"text": "💰 Забрать cron", "callback_data": "admin_take_cron"}],
        [{"text": "💰 Выдать gram", "callback_data": "admin_give_gram"}],
        [{"text": "💰 Забрать gram", "callback_data": "admin_take_gram"}],
        [{"text": "📋 Список пользователей", "callback_data": "admin_users"}],
        [{"text": "🔥 Снести БД", "callback_data": "admin_delete_db"}],
        [{"text": "❌ Закрыть", "callback_data": "admin_close"}]
    ]
}

async def play_game(chat_id, user_id, game_key, bet):
    game = GAMES.get(game_key)
    if not game:
        await send_message(chat_id, "❌ Игра не найдена.")
        return

    if bet <= 0:
        await send_message(chat_id, "❌ Ставка должна быть положительным числом.")
        return

    user_data = await get_user_data(user_id)
    bal_gram = user_data.get("balance_gram", 0)
    if bal_gram < bet:
        await send_message(chat_id, f"❌ Недостаточно gram для ставки (нужно {bet}).")
        return

    user_data["balance_gram"] = bal_gram - bet
    await update_user_data(user_id, user_data)

    vip = user_data.get("vip")
    luck_bonus = VIP_BONUSES[vip]["luck"] if vip in VIP_BONUSES else 0
    base_chance = 0.5
    total_chance = min(base_chance + luck_bonus, 0.95)
    win = random.random() < total_chance

    if win:
        sticker = random.choice(game["success_stickers"])
        win_amount = bet * 2
        user_data["balance_gram"] = user_data.get("balance_gram", 0) + win_amount
        await update_user_data(user_id, user_data)
        result_text = f"🏆 Ты победил!\n💰 Выигрыш: +{win_amount} gram\n🍀 VIP-бонус: +{int(luck_bonus*100)}%"
    else:
        sticker = random.choice(game["fail_stickers"])
        result_text = f"❌ Ты проиграл.\n💰 Потеряно: {bet} gram\n🍀 VIP-бонус: +{int(luck_bonus*100)}%"

    await send_message(chat_id, sticker)
    await send_message(chat_id, f"{game['name']}\n\n{result_text}")

async def transfer_funds(sender_id, receiver_id, currency, amount):
    if sender_id == receiver_id:
        return False, "❌ Нельзя перевести самому себе."

    if amount <= 0:
        return False, "❌ Сумма должна быть положительной."

    sender_data = await get_user_data(sender_id)
    receiver_data = await get_user_data(receiver_id)

    if currency == "cron":
        bal = sender_data.get("balance_cron", 0)
        if bal < amount:
            return False, f"❌ Недостаточно cron. У тебя {bal} cron."
        sender_data["balance_cron"] = bal - amount
        receiver_data["balance_cron"] = receiver_data.get("balance_cron", 0) + amount
    elif currency == "gram":
        bal = sender_data.get("balance_gram", 0)
        if bal < amount:
            return False, f"❌ Недостаточно gram. У тебя {bal} gram."
        sender_data["balance_gram"] = bal - amount
        receiver_data["balance_gram"] = receiver_data.get("balance_gram", 0) + amount
    else:
        return False, "❌ Допустимые валюты: cron, gram."

    await update_user_data(sender_id, sender_data)
    await update_user_data(receiver_id, receiver_data)
    return True, f"✅ Переведено {amount} {currency} пользователю {receiver_id}."

# ---------- ГЛАВНЫЙ ОБРАБОТЧИК (ЗАЩИЩЁН ОТ ОШИБОК) ----------
async def handle_update(update):
    try:
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = str(msg["from"]["id"])
            username = msg["from"].get("username", msg["from"].get("first_name", "Гость"))
            text = msg.get("text", "")
            chat_type = msg["chat"]["type"]

            user_data = await get_user_data(user_id, username)
            user_data, vip_bonus = await apply_vip_bonuses(user_id, user_data)
            await update_user_data(user_id, user_data)

            if vip_bonus:
                await send_message(
                    chat_id,
                    f"👑 VIP-бонус ({vip_bonus['vip']})!\n"
                    f"💰 +{vip_bonus['cron']} cron и +{vip_bonus['gram']} gram\n"
                    f"⏳ Следующий VIP-бонус через {VIP_BONUSES[vip_bonus['vip']]['cooldown']} часов."
                )

            # ===== ИГРЫ =====
            game_played = False
            lower_text = text.lower().strip()
            words = lower_text.split()
            if words:
                cmd = words[0]
                game_key = None
                for key, game_data in GAMES.items():
                    if cmd in game_data["keywords"]:
                        game_key = key
                        break
                if game_key:
                    bet = 100
                    if len(words) > 1:
                        try:
                            bet = int(words[1])
                        except ValueError:
                            bet = 100
                    await play_game(chat_id, user_id, game_key, bet)
                    game_played = True
            if game_played:
                return

            # ===== АДМИН-КОМАНДЫ =====
            if is_admin(user_id):
                if text.startswith("/give_cron"):
                    parts = text.split()
                    if len(parts) < 3:
                        await send_message(chat_id, "❌ Используйте: /give_cron ID количество")
                        return
                    target_id = parts[1].strip()
                    try:
                        amount = int(parts[2])
                    except:
                        await send_message(chat_id, "❌ Сумма должна быть числом")
                        return
                    target_data = await get_user_data(target_id)
                    target_data["balance_cron"] = target_data.get("balance_cron", 0) + amount
                    await update_user_data(target_id, target_data)
                    await send_message(chat_id, f"✅ Выдано {amount} cron пользователю {target_id}")
                    return

                if text.startswith("/take_cron"):
                    parts = text.split()
                    if len(parts) < 3:
                        await send_message(chat_id, "❌ Используйте: /take_cron ID количество")
                        return
                    target_id = parts[1].strip()
                    try:
                        amount = int(parts[2])
                    except:
                        await send_message(chat_id, "❌ Сумма должна быть числом")
                        return
                    target_data = await get_user_data(target_id)
                    current = target_data.get("balance_cron", 0)
                    if current < amount:
                        await send_message(chat_id, f"❌ У пользователя {target_id} недостаточно cron (есть {current})")
                        return
                    target_data["balance_cron"] = current - amount
                    await update_user_data(target_id, target_data)
                    await send_message(chat_id, f"✅ Забрано {amount} cron у пользователя {target_id}")
                    return

                if text.startswith("/give_gram"):
                    parts = text.split()
                    if len(parts) < 3:
                        await send_message(chat_id, "❌ Используйте: /give_gram ID количество")
                        return
                    target_id = parts[1].strip()
                    try:
                        amount = int(parts[2])
                    except:
                        await send_message(chat_id, "❌ Сумма должна быть числом")
                        return
                    target_data = await get_user_data(target_id)
                    target_data["balance_gram"] = target_data.get("balance_gram", 0) + amount
                    await update_user_data(target_id, target_data)
                    await send_message(chat_id, f"✅ Выдано {amount} gram пользователю {target_id}")
                    return

                if text.startswith("/take_gram"):
                    parts = text.split()
                    if len(parts) < 3:
                        await send_message(chat_id, "❌ Используйте: /take_gram ID количество")
                        return
                    target_id = parts[1].strip()
                    try:
                        amount = int(parts[2])
                    except:
                        await send_message(chat_id, "❌ Сумма должна быть числом")
                        return
                    target_data = await get_user_data(target_id)
                    current = target_data.get("balance_gram", 0)
                    if current < amount:
                        await send_message(chat_id, f"❌ У пользователя {target_id} недостаточно gram (есть {current})")
                        return
                    target_data["balance_gram"] = current - amount
                    await update_user_data(target_id, target_data)
                    await send_message(chat_id, f"✅ Забрано {amount} gram у пользователя {target_id}")
                    return

                if text == "/users":
                    users = await firebase_get("users")
                    if not users:
                        await send_message(chat_id, "❌ Нет пользователей")
                        return
                    out = "📋 Список пользователей:\n"
                    for uid, data in users.items():
                        cron = data.get("balance_cron", 0)
                        gram = data.get("balance_gram", 0)
                        username_db = data.get("username", uid)
                        out += f"{username_db} (ID: {uid}) | cron: {cron} | gram: {gram}\n"
                    await send_message(chat_id, out)
                    return

            # ===== ПЕРЕВОД =====
            if text.startswith("/transfer"):
                parts = text.split()
                if len(parts) != 4:
                    await send_message(chat_id, "❌ Используйте: /transfer ID валюта сумма (валюта: cron или gram)")
                    return
                target_id = parts[1].strip()
                currency = parts[2].lower()
                try:
                    amount = int(parts[3])
                except:
                    await send_message(chat_id, "❌ Сумма должна быть числом")
                    return

                receiver_data = await firebase_get(f"users/{target_id}")
                if not receiver_data:
                    await get_user_data(target_id, "Неизвестный")
                success, message = await transfer_funds(user_id, target_id, currency, amount)
                await send_message(chat_id, message)
                return

            # ===== ОБЫЧНЫЕ КОМАНДЫ =====
            if text == "/start":
                bal_cron = user_data.get("balance_cron", 0)
                bal_gram = user_data.get("balance_gram", 0)
                vip = user_data.get("vip", "Нет")
                reply = get_main_keyboard(user_id) if chat_type == "private" else None
                await send_message(
                    chat_id,
                    f"👋 Привет, @{username}!\n"
                    f"💰 Баланс: {bal_cron} cron | {bal_gram} gram\n"
                    f"👑 VIP: {vip}\n\n"
                    "Выбери действие в меню:",
                    reply_markup=reply
                )
                return

            if text == "👤 Профиль":
                bal_cron = user_data.get("balance_cron", 0)
                bal_gram = user_data.get("balance_gram", 0)
                vip = user_data.get("vip", "Нет")
                if is_admin(user_id):
                    vip_status = "Admin"
                else:
                    vip_status = vip
                vip_until = user_data.get("vip_until")
                vip_active = False
                if vip_until:
                    try:
                        end_date = datetime.fromisoformat(vip_until)
                        if datetime.now() < end_date:
                            vip_active = True
                    except:
                        pass
                vip_active_text = "Вип активен" if vip_active else "Нет"
                until_str = vip_until[:16] if vip_until else "—"
                reply = get_main_keyboard(user_id) if chat_type == "private" else None
                await send_message(
                    chat_id,
                    f"👤 Профиль @{username}\n"
                    f"🆔 ID: {user_id}\n"
                    f"💰 Баланс: {bal_cron} cron | {bal_gram} gram\n"
                    f"👑 Статус: {vip_status}\n"
                    f"📅 Окончание VIP: {until_str}\n"
                    f"📅 Вип активен: {vip_active_text}",
                    reply_markup=reply
                )
                return

            if text == "📋 Команды":
                reply = get_main_keyboard(user_id) if chat_type == "private" else None
                await send_message(
                    chat_id,
                    "📋 Доступные команды:\n"
                    "/start – главное меню\n"
                    "/transfer ID валюта сумма – перевести cron или gram\n"
                    "В любом чате: бас 100, фут 50, дартс 200, тенис 150\n"
                    "Любое сообщение – показать баланс\n"
                    "Кнопки меню – для быстрых действий",
                    reply_markup=reply
                )
                return

            if text == "🏆 Топ":
                top_users = await get_top_users(limit=10)
                if not top_users:
                    await send_message(chat_id, "❌ Нет пользователей для топа.")
                    return
                out = "🏆 **Топ пользователей по gram**\n\n"
                for idx, user in enumerate(top_users, 1):
                    out += f"{idx}. {user['username']} | gram: {user['gram']} | cron: {user['cron']}\n"
                reply = get_main_keyboard(user_id) if chat_type == "private" else None
                await send_message(chat_id, out, reply_markup=reply)
                return

            if text == "💎 Донат":
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🪙 Купить cron (1 = 10000 gram)", "callback_data": "buy_cron"}],
                        [{"text": "👑 Купить VIP Gold (100 cron)", "callback_data": "buy_vip_Gold"}],
                        [{"text": "👑 Купить VIP Diamond (250 cron)", "callback_data": "buy_vip_Diamond"}],
                        [{"text": "👑 Купить VIP Rich (500 cron)", "callback_data": "buy_vip_Rich"}]
                    ]
                }
                await send_message(
                    chat_id,
                    "💎 Донат:\n"
                    "1 cron = 10000 gram\n"
                    "Пополнить баланс можно через @CronSupport (1 cron = 25 ⭐)\n\n"
                    "👑 VIP-статусы (дают бонусы каждый час, действуют 7 дней):\n"
                    "• Gold (100 cron) – 5 cron/час + 10k gram/час, шанс +5%\n"
                    "• Diamond (250 cron) – 15 cron/час + 25k gram/час, шанс +10%\n"
                    "• Rich (500 cron) – 25 cron/час + 50k gram/час, шанс +15%",
                    reply_markup=keyboard
                )
                return

            if text == "💸 Перевести":
                await send_message(
                    chat_id,
                    "💸 **Перевод средств**\n\n"
                    "Используй команду:\n"
                    "`/transfer ID валюта сумма`\n\n"
                    "Примеры:\n"
                    "`/transfer 123456789 cron 50` – перевести 50 cron\n"
                    "`/transfer 987654321 gram 100` – перевести 100 gram\n\n"
                    "Валюта может быть `cron` или `gram`.\n"
                    "ID получателя можно узнать в его профиле.",
                    reply_markup=get_main_keyboard(user_id) if chat_type == "private" else None
                )
                return

            if text == "🎮 Игры":
                reply = get_main_keyboard(user_id) if chat_type == "private" else None
                await send_message(
                    chat_id,
                    "🎮 Игры доступны в любом чате!\n"
                    "Используйте команды:\n"
                    "бас 100 – баскетбол\n"
                    "фут 50 – футбол\n"
                    "дартс 200 – дартс\n"
                    "тенис 150 – теннис\n\n"
                    "Ставка указывается числом после команды.\n"
                    "Если не указать – ставка 100 gram.",
                    reply_markup=reply
                )
                return

            if text == "⚙️ Админ панель" and is_admin(user_id):
                await send_message(
                    chat_id,
                    "⚙️ Админ-панель:\n"
                    "Выберите действие:",
                    reply_markup=ADMIN_PANEL
                )
                return

            if text == "🎁 Бонус":
                bal_gram = user_data.get("balance_gram", 0)
                if is_admin(user_id):
                    new_bal = bal_gram + BONUS_AMOUNT_GRAM
                    user_data["balance_gram"] = new_bal
                    await update_user_data(user_id, user_data)
                    reply = get_main_keyboard(user_id) if chat_type == "private" else None
                    await send_message(
                        chat_id,
                        f"🎁 Админ-бонус! Ты получил {BONUS_AMOUNT_GRAM} gram!\n"
                        f"💰 Новый баланс: {new_bal} gram",
                        reply_markup=reply
                    )
                    return

                last_bonus = user_data.get("last_bonus")
                if last_bonus:
                    try:
                        last_time = datetime.fromisoformat(last_bonus)
                    except:
                        last_time = datetime.now() - timedelta(hours=BONUS_INTERVAL_HOURS)
                    next_time = last_time + timedelta(hours=BONUS_INTERVAL_HOURS)
                    now = datetime.now()
                    if now >= next_time:
                        new_bal = bal_gram + BONUS_AMOUNT_GRAM
                        user_data["balance_gram"] = new_bal
                        user_data["last_bonus"] = now.isoformat()
                        await update_user_data(user_id, user_data)
                        reply = get_main_keyboard(user_id) if chat_type == "private" else None
                        await send_message(
                            chat_id,
                            f"🎁 Ты получил бонус {BONUS_AMOUNT_GRAM} gram!\n"
                            f"💰 Новый баланс: {new_bal} gram\n"
                            f"⏳ Следующий бонус через 12 часов.",
                            reply_markup=reply
                        )
                    else:
                        remaining = next_time - now
                        hours = remaining.seconds // 3600
                        minutes = (remaining.seconds % 3600) // 60
                        reply = get_main_keyboard(user_id) if chat_type == "private" else None
                        await send_message(
                            chat_id,
                            f"⏳ Следующий бонус через {hours}ч {minutes}мин.\n"
                            f"💰 Баланс: {bal_gram} gram",
                            reply_markup=reply
                        )
                else:
                    new_bal = bal_gram + BONUS_AMOUNT_GRAM
                    user_data["balance_gram"] = new_bal
                    user_data["last_bonus"] = datetime.now().isoformat()
                    await update_user_data(user_id, user_data)
                    reply = get_main_keyboard(user_id) if chat_type == "private" else None
                    await send_message(
                        chat_id,
                        f"🎁 Ты получил первый бонус {BONUS_AMOUNT_GRAM} gram!\n"
                        f"💰 Новый баланс: {new_bal} gram\n"
                        f"⏳ Следующий бонус через 12 часов.",
                        reply_markup=reply
                    )
                return

            if text == "💬 Чаты":
                reply = get_main_keyboard(user_id) if chat_type == "private" else None
                await send_message(
                    chat_id,
                    "💬 Наш чат: @CronChat\n"
                    "Присоединяйся к общению!",
                    reply_markup=reply
                )
                return

            if text == "💰 Заработать":
                earned = user_data.get("earned_channels", {})
                keyboard = {"inline_keyboard": []}
                for channel in CHANNELS:
                    name = channel["name"]
                    if earned.get(name):
                        status = "✅ уже получено"
                    else:
                        status = "➕ получить 2500 gram"
                    keyboard["inline_keyboard"].append([
                        {"text": f"{name} – {status}", "callback_data": f"earn_{name}"}
                    ])
                    keyboard["inline_keyboard"].append([
                        {"text": f"✅ Я подписался на {name} (вручную)", "callback_data": f"earn_manual_{name}"}
                    ])
                await send_message(
                    chat_id,
                    "💰 Заработай 2500 gram за подписку на каналы!",
                    reply_markup=keyboard
                )
                return

            if not text.startswith("/"):
                bal_cron = user_data.get("balance_cron", 0)
                bal_gram = user_data.get("balance_gram", 0)
                reply = get_main_keyboard(user_id) if chat_type == "private" else None
                await send_message(
                    chat_id,
                    f"@{username}: {bal_cron} cron | {bal_gram} gram",
                    reply_markup=reply
                )
                return

            await send_message(
                chat_id,
                "⚠️ Неизвестная команда. Используйте кнопки меню."
            )

        # ---- CALLBACK ----
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_data = cb["data"]
            user_id = str(cb["from"]["id"])
            chat_id = cb["message"]["chat"]["id"]

            if cb_data == "admin_give_cron" and is_admin(user_id):
                await send_message(chat_id, "Введите: `/give_cron ID количество`")
                return
            if cb_data == "admin_take_cron" and is_admin(user_id):
                await send_message(chat_id, "Введите: `/take_cron ID количество`")
                return
            if cb_data == "admin_give_gram" and is_admin(user_id):
                await send_message(chat_id, "Введите: `/give_gram ID количество`")
                return
            if cb_data == "admin_take_gram" and is_admin(user_id):
                await send_message(chat_id, "Введите: `/take_gram ID количество`")
                return
            if cb_data == "admin_users" and is_admin(user_id):
                users = await firebase_get("users")
                if not users:
                    await send_message(chat_id, "❌ Нет пользователей")
                    return
                out = "📋 Список пользователей:\n"
                for uid, data in users.items():
                    cron = data.get("balance_cron", 0)
                    gram = data.get("balance_gram", 0)
                    username_db = data.get("username", uid)
                    out += f"{username_db} (ID: {uid}) | cron: {cron} | gram: {gram}\n"
                await send_message(chat_id, out)
                return
            if cb_data == "admin_delete_db" and is_admin(user_id):
                confirm_keyboard = {
                    "inline_keyboard": [
                        [{"text": "✅ Да, снести всё", "callback_data": "admin_confirm_delete"}],
                        [{"text": "❌ Отмена", "callback_data": "admin_close"}]
                    ]
                }
                await send_message(chat_id, "⚠️ Вы уверены, что хотите удалить ВСЕ данные пользователей? Это действие необратимо!", reply_markup=confirm_keyboard)
                return
            if cb_data == "admin_confirm_delete" and is_admin(user_id):
                await firebase_delete("users")
                await send_message(chat_id, "✅ База данных полностью очищена.")
                await send_message(chat_id, "Админ-панель закрыта.")
                return
            if cb_data == "admin_close":
                await send_message(chat_id, "✅ Админ-панель закрыта.")
                return

            if cb_data == "buy_cron":
                user_data = await get_user_data(user_id)
                bal_gram = user_data.get("balance_gram", 0)
                if bal_gram >= CRON_TO_GRAM:
                    user_data["balance_gram"] = bal_gram - CRON_TO_GRAM
                    user_data["balance_cron"] = user_data.get("balance_cron", 0) + 1
                    await update_user_data(user_id, user_data)
                    await send_message(chat_id, f"✅ Ты купил 1 cron за {CRON_TO_GRAM} gram!")
                else:
                    await send_message(chat_id, f"❌ Недостаточно gram. Нужно {CRON_TO_GRAM} gram.")
                return

            if cb_data.startswith("buy_vip_"):
                vip_type = cb_data[8:]
                price = VIP_PRICES[vip_type]
                user_data = await get_user_data(user_id)
                bal_cron = user_data.get("balance_cron", 0)
                if bal_cron < price:
                    await send_message(chat_id, f"❌ Недостаточно cron. Нужно {price} cron.")
                    return
                user_data["balance_cron"] = bal_cron - price
                user_data["vip"] = vip_type
                user_data["vip_until"] = (datetime.now() + timedelta(days=VIP_DURATION_DAYS)).isoformat()
                user_data["last_vip_claim"] = datetime.now().isoformat()
                user_data["last_bonus"] = datetime.now().isoformat()
                vip_info = VIP_BONUSES[vip_type]
                user_data["balance_cron"] = user_data.get("balance_cron", 0) + vip_info["cron"]
                user_data["balance_gram"] = user_data.get("balance_gram", 0) + vip_info["gram"]
                await update_user_data(user_id, user_data)
                await send_message(
                    chat_id,
                    f"👑 Поздравляем! Ты купил VIP {vip_type} на {VIP_DURATION_DAYS} дней!\n\n"
                    f"📋 Привилегии:\n"
                    f"• {vip_info['cron']} cron и {vip_info['gram']} gram каждые {vip_info['cooldown']} часов\n"
                    f"• Шанс в играх +{int(vip_info['luck']*100)}%\n\n"
                    f"💰 Ты получил первый VIP-бонус: +{vip_info['cron']} cron и +{vip_info['gram']} gram\n"
                    f"⏳ Следующий VIP-бонус через {vip_info['cooldown']} часов.\n"
                    f"⏳ Таймер обычного бонуса сброшен."
                )
                return

            if cb_data.startswith("game_"):
                game_key = cb_data[5:]
                await play_game(chat_id, user_id, game_key, 100)
                return

            if cb_data.startswith("earn_"):
                channel_name = cb_data[5:]
                channel_id = None
                for ch in CHANNELS:
                    if ch["name"] == channel_name:
                        channel_id = ch["id"]
                        break
                if not channel_id:
                    await send_message(chat_id, "❌ Канал не найден.")
                    return
                is_sub = await check_subscription(user_id, channel_id)
                if is_sub:
                    user_data = await get_user_data(user_id)
                    earned = user_data.get("earned_channels", {})
                    if earned.get(channel_name):
                        await send_message(chat_id, f"✅ Ты уже получил бонус за {channel_name}.")
                        return
                    bal_gram = user_data.get("balance_gram", 0)
                    new_bal = bal_gram + EARN_AMOUNT_GRAM
                    user_data["balance_gram"] = new_bal
                    earned[channel_name] = True
                    user_data["earned_channels"] = earned
                    await update_user_data(user_id, user_data)
                    await send_message(
                        chat_id,
                        f"✅ Ты получил {EARN_AMOUNT_GRAM} gram за подписку на {channel_name}!\n"
                        f"💰 Новый баланс gram: {new_bal}"
                    )
                else:
                    await send_message(
                        chat_id,
                        f"❌ Ты не подписан на {channel_name}. Подпишись и нажми снова.\n"
                        f"Ссылка: https://t.me/{channel_name}"
                    )
                return

            if cb_data.startswith("earn_manual_"):
                channel_name = cb_data[12:]
                user_data = await get_user_data(user_id)
                earned = user_data.get("earned_channels", {})
                if earned.get(channel_name):
                    await send_message(chat_id, f"✅ Ты уже получил бонус за {channel_name}.")
                    return
                bal_gram = user_data.get("balance_gram", 0)
                new_bal = bal_gram + EARN_AMOUNT_GRAM
                user_data["balance_gram"] = new_bal
                earned[channel_name] = True
                user_data["earned_channels"] = earned
                await update_user_data(user_id, user_data)
                await send_message(
                    chat_id,
                    f"✅ Ты получил {EARN_AMOUNT_GRAM} gram за {channel_name} (ручное подтверждение)!\n"
                    f"💰 Новый баланс gram: {new_bal}"
                )
                return

    except Exception as e:
        print(f"[CRITICAL] Ошибка в handle_update: {type(e).__name__}: {e}")
        try:
            for admin in ADMIN_IDS:
                await send_message(admin, f"⚠️ Ошибка в боте: {e}")
        except:
            pass

# ---------- ГЛАВНЫЙ ЦИКЛ ----------
async def poll_updates():
    offset = 0
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{API_BASE}/bot{TOKEN}/getUpdates"
                params = {"offset": offset, "timeout": 30}
                async with session.get(url, params=params, timeout=35) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        for update in data["result"]:
                            offset = update["update_id"] + 1
                            await handle_update(update)
                    else:
                        print(f"[ERROR] Ошибка получения обновлений: {data}")
                        await asyncio.sleep(5)
        except asyncio.TimeoutError:
            print("[WARN] Таймаут при получении обновлений, продолжаем...")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[CRITICAL] Ошибка в poll_updates: {type(e).__name__}: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    print("[LOG] Бот запускается...")
    asyncio.run(poll_updates())
