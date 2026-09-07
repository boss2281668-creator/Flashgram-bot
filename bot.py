import asyncio
import aiohttp
import json
import random
import re
from datetime import datetime

# ===== КОНФИГ =====
TOKEN = "1780244966:X-2yDGvIo695duDq3Ppr6eIP4kuCL2GntKv"
API_BASE = "http://31.76.29.36:8081"
ADMIN_ID = 1780243448  # главный админ
FIREBASE_URL = "https://nft-app-8eda5-default-rtdb.firebaseio.com"

# ===== КЛАВИАТУРА =====
MAIN_KEYBOARD = {
    "keyboard": [
        ["🎯 Создать конкурс", "📋 Мои конкурсы"],
        ["📢 Мои каналы/чаты", "🆘 Служба поддержки"]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False
}

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
async def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    url = f"{API_BASE}/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

async def send_photo(chat_id, photo, caption=None, reply_markup=None):
    url = f"{API_BASE}/bot{TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

async def firebase_get(path):
    async with aiohttp.ClientSession() as sess:
        url = f"{FIREBASE_URL}/{path}.json"
        async with sess.get(url) as resp:
            return await resp.json()

async def firebase_set(path, data):
    async with aiohttp.ClientSession() as sess:
        url = f"{FIREBASE_URL}/{path}.json"
        async with sess.put(url, json=data) as resp:
            return await resp.json()

async def firebase_push(path, data):
    async with aiohttp.ClientSession() as sess:
        url = f"{FIREBASE_URL}/{path}.json"
        async with sess.post(url, json=data) as resp:
            return await resp.json()

async def firebase_delete(path):
    async with aiohttp.ClientSession() as sess:
        url = f"{FIREBASE_URL}/{path}.json"
        async with sess.delete(url) as resp:
            return await resp.json()

# ===== ПРОВЕРКА ДОСТУПА =====
async def is_admin(user_id):
    if user_id == str(ADMIN_ID):
        return True
    allowed = await firebase_get("allowed_users")
    if allowed and user_id in allowed:
        return True
    return False

# ===== ПАРСИНГ ДАТЫ =====
def parse_date(text):
    text = text.strip()
    formats = [
        "%d.%m.%Y %H:%M", "%d.%m.%Y",
        "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt
        except ValueError:
            continue
    return None

def format_date(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M")
    return str(dt)

# ===== ЛИСТ КАНАЛОВ =====
async def show_channels(chat_id, user_id):
    channels_data = await firebase_get(f"channels/{user_id}/list")
    if not channels_data:
        text = "📢 У вас пока нет добавленных каналов/чатов.\n\n"
        text += "💡 Инструкция:\n"
        text += "1. Добавьте бота в канал/чат как администратора с правом публикации.\n"
        text += "2. Нажмите «➕ Добавить канал» и отправьте боту @channelname\n"
        text += "   или перешлите любое сообщение из приватного канала.\n\n"
        text += "⚠️ Для групп (чатов) выдайте боту право писать в них."
    else:
        text = "📢 Ваши каналы/чаты:\n\n"
        sorted_items = sorted(channels_data.items(), key=lambda x: x[1].get("added_at", ""))
        for idx, (cid, cdata) in enumerate(sorted_items, 1):
            name = cdata.get("name", "Без названия")
            ctype = cdata.get("type", "канал")
            text += f"{idx}. {name} ({ctype})\n"

    keyboard = {
        "inline_keyboard": [
            [{"text": "➕ Добавить канал", "callback_data": "add_channel"}],
            [{"text": "➕ Добавить группу", "callback_data": "add_group"}]
        ]
    }
    if channels_data:
        row = []
        for cid, cdata in channels_data.items():
            row.append({"text": f"✖️ {cdata.get('name', '')}", "callback_data": f"del_channel_{cid}"})
        if row:
            keyboard["inline_keyboard"].append(row[:3])
            if len(row) > 3:
                keyboard["inline_keyboard"].append(row[3:6])

    await send_message(chat_id, text, reply_markup=keyboard)

# ===== ПУБЛИКАЦИЯ КОНКУРСА =====
async def publish_contest(chat_id, user_id, contest_data):
    result = await firebase_push("contests", contest_data)
    contest_id = result["name"]

    text = f"🎯 **Новый конкурс!**\n\n"
    text += f"{contest_data['text']}\n\n"
    if contest_data.get('date_start'):
        text += f"📅 Начало: {format_date(contest_data['date_start'])}\n"
    if contest_data.get('date_end'):
        text += f"⏳ Окончание: {format_date(contest_data['date_end'])}\n"
    text += f"🏆 Победителей: {contest_data['winners_count']}\n"
    text += f"🎁 Призы: {contest_data['prize']}\n\n"
    text += f"ID: `{contest_id}`\n"
    text += f"Участвовать: напишите боту `/join {contest_id}` или нажмите кнопку ниже."

    button_text = contest_data.get('button_text', 'Участвовать')
    keyboard = {
        "inline_keyboard": [
            [{"text": f"🎯 {button_text}", "callback_data": f"join_{contest_id}"}]
        ]
    }

    channel_id = contest_data.get('channel_id')
    if channel_id:
        channels = await firebase_get(f"channels/{user_id}/list")
        if channels and channel_id in channels:
            channel_name = channels[channel_id].get("name")
            if not channel_name.startswith('@'):
                channel_name = '@' + channel_name
            try:
                if contest_data.get('media_type') == "photo":
                    await send_photo(channel_name, contest_data['media_id'], caption=text, reply_markup=keyboard)
                else:
                    await send_message(channel_name, text, parse_mode="Markdown", reply_markup=keyboard)
                await send_message(chat_id, f"✅ Конкурс опубликован в канале {channel_name}!")
                return contest_id
            except Exception as e:
                await send_message(chat_id, f"❌ Ошибка публикации в канал: {e}\nПубликую в личку.")
                # публикуем в личку
                if contest_data.get('media_type') == "photo":
                    await send_photo(chat_id, contest_data['media_id'], caption=text, reply_markup=keyboard)
                else:
                    await send_message(chat_id, text, parse_mode="Markdown", reply_markup=keyboard)
                await send_message(chat_id, "✅ Конкурс опубликован здесь, в личных сообщениях.")
                return contest_id

    # Публикуем в личку
    if contest_data.get('media_type') == "photo":
        await send_photo(chat_id, contest_data['media_id'], caption=text, reply_markup=keyboard)
    else:
        await send_message(chat_id, text, parse_mode="Markdown", reply_markup=keyboard)
    await send_message(chat_id, "✅ Конкурс опубликован здесь, в личных сообщениях.")
    return contest_id

# ===== ОБРАБОТЧИК ОБНОВЛЕНИЙ =====
user_states = {}

async def handle_update(update):
    global user_states

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = str(msg["from"]["id"])
        text = msg.get("text", "")
        username = msg["from"].get("username", "Без имени")
        photo = msg.get("photo")
        video = msg.get("video")
        document = msg.get("document")
        caption = msg.get("caption", "")

        # ---- /start ----
        if text == "/start":
            await send_message(chat_id, "👋 Добро пожаловать в конкурс-бот!\n"
                                        "Выберите действие в меню ниже:",
                              reply_markup=MAIN_KEYBOARD)
            return

        # ---- Управление доступом (только для главного админа) ----
        if user_id == str(ADMIN_ID):
            # Добавить админа
            if text.startswith("/add_admin"):
                parts = text.split()
                if len(parts) < 2:
                    await send_message(chat_id, "❌ Укажите ID: `/add_admin 123456789`")
                    return
                new_admin = parts[1].strip()
                allowed = await firebase_get("allowed_users") or {}
                allowed[new_admin] = True
                await firebase_set("allowed_users", allowed)
                await send_message(chat_id, f"✅ Пользователь {new_admin} теперь имеет доступ к админ-командам.")
                return

            # Удалить админа
            if text.startswith("/remove_admin"):
                parts = text.split()
                if len(parts) < 2:
                    await send_message(chat_id, "❌ Укажите ID: `/remove_admin 123456789`")
                    return
                rm_admin = parts[1].strip()
                allowed = await firebase_get("allowed_users") or {}
                if rm_admin in allowed:
                    del allowed[rm_admin]
                    await firebase_set("allowed_users", allowed)
                    await send_message(chat_id, f"✅ Пользователь {rm_admin} удалён из списка админов.")
                else:
                    await send_message(chat_id, f"❌ Пользователь {rm_admin} не найден в списке.")
                return

            # Список админов
            if text == "/list_admins":
                allowed = await firebase_get("allowed_users") or {}
                if not allowed:
                    await send_message(chat_id, "📋 Список разрешённых пользователей пуст.")
                else:
                    ids = list(allowed.keys())
                    out = "📋 Разрешённые пользователи:\n" + "\n".join(ids)
                    await send_message(chat_id, out)
                return

        # ---- Проверка доступа для остальных команд ----
        is_admin_user = await is_admin(user_id)

        # ---- /join contest_id ----
        if text.startswith("/join"):
            parts = text.split()
            if len(parts) < 2:
                await send_message(chat_id, "❌ Укажите ID конкурса: `/join contest_id`")
                return
            contest_id = parts[1]
            contest = await firebase_get(f"contests/{contest_id}")
            if not contest:
                await send_message(chat_id, "❌ Конкурс не найден.")
                return
            if contest.get("status") != "active":
                await send_message(chat_id, "❌ Конкурс уже завершён.")
                return
            participants = contest.get("participants", {})
            if user_id not in participants:
                participants[user_id] = username
                await firebase_set(f"contests/{contest_id}/participants", participants)
                await send_message(chat_id, f"✅ Вы участвуете в конкурсе {contest_id}!")
            else:
                await send_message(chat_id, "Вы уже участвуете в этом конкурсе.")
            return

        # ---- /clear_contests (админ) ----
        if text == "/clear_contests" and is_admin_user:
            await firebase_delete("contests")
            await send_message(chat_id, "🗑 Все конкурсы удалены.")
            return

        # ---- /results (админ) ----
        if text.startswith("/results") and is_admin_user:
            parts = text.split()
            if len(parts) < 2:
                await send_message(chat_id, "❌ Укажите ID конкурса: `/results contest_id`")
                return
            contest_id = parts[1]
            contest = await firebase_get(f"contests/{contest_id}")
            if not contest:
                await send_message(chat_id, "❌ Конкурс не найден.")
                return
            if contest.get("status") != "active":
                await send_message(chat_id, "❌ Конкурс уже завершён.")
                return
            participants = contest.get("participants", {})
            if not participants:
                await send_message(chat_id, "❌ Нет участников.")
                return
            winners_count = contest.get("winners_count", 1)
            winner_ids = random.sample(list(participants.keys()), min(winners_count, len(participants)))
            winners = {uid: participants[uid] for uid in winner_ids}
            await firebase_set(f"contests/{contest_id}/status", "finished")
            await firebase_set(f"contests/{contest_id}/winner", winners)

            result_text = f"🏁 **Итоги конкурса {contest_id}**\n\n"
            result_text += f"Участников: {len(participants)}\n"
            result_text += "Победители:\n"
            for uid, uname in winners.items():
                result_text += f"@{uname} (ID {uid})\n"
            await send_message(chat_id, result_text)
            for uid in winner_ids:
                try:
                    await send_message(uid, f"🎉 Поздравляем! Вы выиграли конкурс {contest_id}!")
                except:
                    pass
            return

        # ---- Добавление канала (ожидание названия) ----
        if user_id in user_states and user_states.get(user_id, {}).get("mode") == "add_channel":
            channel_data = {
                "name": text,
                "type": "channel",
                "added_at": datetime.now().isoformat()
            }
            await firebase_push(f"channels/{user_id}/list", channel_data)
            del user_states[user_id]
            await send_message(chat_id, f"✅ Канал {text} добавлен!",
                              reply_markup=MAIN_KEYBOARD)
            await show_channels(chat_id, user_id)
            return

        # ---- Создание конкурса (пошаговое, доступно только админам) ----
        if is_admin_user and user_id in user_states and user_states.get(user_id, {}).get("mode") == "create_contest":
            state = user_states[user_id]
            step = state.get("step")
            data = state.get("data", {})

            if step == "text":
                if photo:
                    media_type = "photo"
                    media_id = photo[-1]["file_id"]
                    data["text"] = caption or text
                elif video:
                    media_type = "video"
                    media_id = video["file_id"]
                    data["text"] = caption or text
                elif document and document.get("mime_type", "").startswith("image/"):
                    media_type = "document"
                    media_id = document["file_id"]
                    data["text"] = caption or text
                else:
                    media_type = None
                    media_id = None
                    if text:
                        data["text"] = text
                    else:
                        await send_message(chat_id, "❌ Отправьте текст конкурса (или подпись к медиа).")
                        return

                data["media_type"] = media_type
                data["media_id"] = media_id
                state["step"] = "date_start"
                user_states[user_id] = state
                await send_message(chat_id, "📅 Введите дату начала конкурса.\n"
                                            "Форматы: `ДД.ММ.ГГГГ ЧЧ:ММ` или `ДД.ММ.ГГГГ`\n"
                                            "Если дата не нужна, отправьте `-`")
                return

            if step == "date_start":
                if text == "-":
                    data["date_start"] = None
                    data["date_end"] = None
                    state["step"] = "winners"
                    user_states[user_id] = state
                    await send_message(chat_id, "🏆 Введите количество победителей (число):")
                else:
                    dt = parse_date(text)
                    if dt:
                        data["date_start"] = dt
                        state["step"] = "date_end"
                        user_states[user_id] = state
                        await send_message(chat_id, "📅 Введите дату окончания конкурса.\n"
                                                    "Форматы: `ДД.ММ.ГГГГ ЧЧ:ММ` или `ДД.ММ.ГГГГ`\n"
                                                    "Если не нужно, отправьте `-`")
                    else:
                        await send_message(chat_id, "❌ Неверный формат. Используйте `ДД.ММ.ГГГГ ЧЧ:ММ` или `ДД.ММ.ГГГГ`.")
                return

            if step == "date_end":
                if text == "-":
                    data["date_end"] = None
                    state["step"] = "winners"
                    user_states[user_id] = state
                    await send_message(chat_id, "🏆 Введите количество победителей (число):")
                else:
                    dt = parse_date(text)
                    if dt:
                        data["date_end"] = dt
                        state["step"] = "winners"
                        user_states[user_id] = state
                        await send_message(chat_id, "🏆 Введите количество победителей (число):")
                    else:
                        await send_message(chat_id, "❌ Неверный формат. Используйте `ДД.ММ.ГГГГ ЧЧ:ММ` или `ДД.ММ.ГГГГ`.")
                return

            if step == "winners":
                try:
                    winners_count = int(text)
                    if winners_count < 1:
                        raise ValueError
                    data["winners_count"] = winners_count
                    state["step"] = "prize"
                    user_states[user_id] = state
                    await send_message(chat_id, "🎁 Опишите призы (текст):")
                except:
                    await send_message(chat_id, "❌ Введите целое число больше 0.")
                return

            if step == "prize":
                data["prize"] = text
                channels = await firebase_get(f"channels/{user_id}/list")
                if channels:
                    keyboard = {"inline_keyboard": []}
                    for cid, cdata in channels.items():
                        name = cdata.get("name", "Без названия")
                        keyboard["inline_keyboard"].append([{"text": f"📢 {name}", "callback_data": f"publish_channel_{cid}"}])
                    keyboard["inline_keyboard"].append([{"text": "💬 Опубликовать здесь (в личку)", "callback_data": "publish_here"}])
                    state["step"] = "choose_channel"
                    user_states[user_id] = state
                    await send_message(chat_id, "📢 Выберите канал для публикации конкурса:", reply_markup=keyboard)
                else:
                    state["step"] = "button_text"
                    user_states[user_id] = state
                    await send_message(chat_id, "📢 У вас нет добавленных каналов.\n"
                                                "Конкурс будет опубликован здесь, в личных сообщениях.\n\n"
                                                "🎉 Введите текст, который будет отображаться на кнопке.\n"
                                                "По умолчанию: `Участвовать`",
                                  reply_markup={
                                      "inline_keyboard": [
                                          [{"text": "🔹 Участвовать", "callback_data": "btn_text_Участвовать"}],
                                          [{"text": "🔹 Участвую!", "callback_data": "btn_text_Участвую!"}],
                                          [{"text": "🔹 Принять участие", "callback_data": "btn_text_Принять участие"}]
                                      ]
                                  })
                return

            if step == "choose_channel":
                # обрабатывается в callback
                pass

            if step == "button_text":
                data["button_text"] = text
                state["step"] = "color"
                user_states[user_id] = state
                color_keyboard = {
                    "inline_keyboard": [
                        [{"text": "🟣 Фиолетовый", "callback_data": "btn_color_#6c5ce7"},
                         {"text": "🟢 Зелёный", "callback_data": "btn_color_#4ade80"}],
                        [{"text": "🔴 Красный", "callback_data": "btn_color_#f87171"},
                         {"text": "🟡 Жёлтый", "callback_data": "btn_color_#fbbf24"}],
                        [{"text": "🔵 Синий", "callback_data": "btn_color_#3b82f6"},
                         {"text": "🟣 Пурпурный", "callback_data": "btn_color_#a855f7"}]
                    ]
                }
                await send_message(chat_id, "🎨 Выберите цвет кнопки из вариантов ниже:",
                                  reply_markup=color_keyboard)
                return

        # ===== КНОПКИ МЕНЮ =====
        if text == "🎯 Создать конкурс":
            if not await is_admin(user_id):
                await send_message(chat_id, "❌ У вас нет прав для создания конкурсов.")
                return
            user_states[user_id] = {"mode": "create_contest", "step": "text", "data": {}}
            await send_message(chat_id, "✍️ Отправьте текст конкурса.\n"
                                        "Вы можете также отправить картинку, видео или GIF.\n"
                                        "❗ Используйте только один медиафайл.\n\n"
                                        "Если отправляете медиа, текст должен быть в подписи.",
                              reply_markup={"inline_keyboard": [[{"text": "❌ Отмена", "callback_data": "cancel_contest"}]]})
            return

        if text == "📋 Мои конкурсы":
            contests = await firebase_get("contests")
            if not contests:
                await send_message(chat_id, "❌ Конкурсов пока нет.")
                return
            # Получаем список разрешённых пользователей для проверки
            allowed_users = await firebase_get("allowed_users") or {}
            user_contests = {}
            for cid, cdata in contests.items():
                if user_id == str(ADMIN_ID) or user_id in allowed_users:
                    user_contests[cid] = cdata
                elif user_id in cdata.get("participants", {}):
                    user_contests[cid] = cdata
            if not user_contests:
                await send_message(chat_id, "❌ Вы не участвуете ни в одном конкурсе.")
                return
            out = "📋 Ваши конкурсы:\n"
            for cid, cdata in user_contests.items():
                status = "✅ Активен" if cdata.get("status") == "active" else "🏁 Завершён"
                participants_count = len(cdata.get("participants", {}))
                date_end = cdata.get("date_end")
                date_str = f", окончание: {format_date(date_end)}" if date_end else ""
                out += f"ID: `{cid}` – {status}, участников: {participants_count}{date_str}\n"
            await send_message(chat_id, out)
            return

        if text == "📢 Мои каналы/чаты":
            await show_channels(chat_id, user_id)
            return

        if text == "🆘 Служба поддержки":
            await send_message(chat_id, "🆘 По всем вопросам обращайтесь в поддержку:\n"
                                        "📩 @RandomSupport")
            return

        if text and not text.startswith("/"):
            await send_message(chat_id, "⚠️ Неизвестная команда. Используйте кнопки меню.",
                              reply_markup=MAIN_KEYBOARD)

    # ---- ОБРАБОТКА CALLBACK ----
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_data = cb["data"]
        user_id = str(cb["from"]["id"])
        username = cb["from"].get("username", "Без имени")
        chat_id = cb["message"]["chat"]["id"]

        if cb_data == "cancel_contest":
            if user_id in user_states:
                del user_states[user_id]
            await send_message(chat_id, "❌ Создание конкурса отменено.",
                              reply_markup=MAIN_KEYBOARD)
            return

        if cb_data.startswith("publish_channel_"):
            channel_id = cb_data[17:]
            if user_id in user_states and user_states.get(user_id, {}).get("mode") == "create_contest":
                state = user_states[user_id]
                if state.get("step") == "choose_channel":
                    state["data"]["channel_id"] = channel_id
                    state["step"] = "button_text"
                    user_states[user_id] = state
                    await send_message(chat_id, "🎉 Введите текст, который будет отображаться на кнопке.\n"
                                                "По умолчанию: `Участвовать`\n"
                                                "Вы также можете добавить премиум эмодзи в начале текста.",
                                      reply_markup={
                                          "inline_keyboard": [
                                              [{"text": "🔹 Участвовать", "callback_data": "btn_text_Участвовать"}],
                                              [{"text": "🔹 Участвую!", "callback_data": "btn_text_Участвую!"}],
                                              [{"text": "🔹 Принять участие", "callback_data": "btn_text_Принять участие"}]
                                          ]
                                      })
            return

        if cb_data == "publish_here":
            if user_id in user_states and user_states.get(user_id, {}).get("mode") == "create_contest":
                state = user_states[user_id]
                if state.get("step") == "choose_channel":
                    state["data"]["channel_id"] = None
                    state["step"] = "button_text"
                    user_states[user_id] = state
                    await send_message(chat_id, "🎉 Введите текст, который будет отображаться на кнопке.\n"
                                                "По умолчанию: `Участвовать`\n"
                                                "Вы также можете добавить премиум эмодзи в начале текста.",
                                      reply_markup={
                                          "inline_keyboard": [
                                              [{"text": "🔹 Участвовать", "callback_data": "btn_text_Участвовать"}],
                                              [{"text": "🔹 Участвую!", "callback_data": "btn_text_Участвую!"}],
                                              [{"text": "🔹 Принять участие", "callback_data": "btn_text_Принять участие"}]
                                          ]
                                      })
            return

        if cb_data.startswith("btn_text_"):
            text = cb_data[9:]
            if user_id in user_states and user_states.get(user_id, {}).get("mode") == "create_contest":
                state = user_states[user_id]
                if state.get("step") == "button_text":
                    state["data"]["button_text"] = text
                    state["step"] = "color"
                    user_states[user_id] = state
                    color_keyboard = {
                        "inline_keyboard": [
                            [{"text": "🟣 Фиолетовый", "callback_data": "btn_color_#6c5ce7"},
                             {"text": "🟢 Зелёный", "callback_data": "btn_color_#4ade80"}],
                            [{"text": "🔴 Красный", "callback_data": "btn_color_#f87171"},
                             {"text": "🟡 Жёлтый", "callback_data": "btn_color_#fbbf24"}],
                            [{"text": "🔵 Синий", "callback_data": "btn_color_#3b82f6"},
                             {"text": "🟣 Пурпурный", "callback_data": "btn_color_#a855f7"}]
                        ]
                    }
                    await send_message(chat_id, f"✅ Текст кнопки: `{text}`\n\n🎨 Выберите цвет кнопки:",
                                      reply_markup=color_keyboard)
            return

        if cb_data.startswith("btn_color_"):
            color_hex = cb_data[10:]
            if user_id in user_states and user_states.get(user_id, {}).get("mode") == "create_contest":
                state = user_states[user_id]
                data = state.get("data", {})
                if state.get("step") == "color":
                    data["button_color"] = color_hex
                    contest_data = {
                        "text": data.get("text", ""),
                        "media_type": data.get("media_type"),
                        "media_id": data.get("media_id"),
                        "date_start": data.get("date_start").isoformat() if data.get("date_start") else None,
                        "date_end": data.get("date_end").isoformat() if data.get("date_end") else None,
                        "winners_count": data.get("winners_count", 1),
                        "prize": data.get("prize", ""),
                        "button_text": data.get("button_text", "Участвовать"),
                        "button_color": color_hex,
                        "channel_id": data.get("channel_id"),
                        "status": "active",
                        "participants": {},
                        "winner": None,
                        "created_at": datetime.now().isoformat(),
                        "created_by": user_id
                    }
                    await publish_contest(chat_id, user_id, contest_data)
                    del user_states[user_id]
                    await send_message(chat_id, "✅ Конкурс создан и опубликован!",
                                      reply_markup=MAIN_KEYBOARD)
            return

        if cb_data.startswith("join_"):
            contest_id = cb_data[5:]
            contest = await firebase_get(f"contests/{contest_id}")
            if not contest:
                await send_message(chat_id, "❌ Конкурс не найден.")
                return
            if contest.get("status") != "active":
                await send_message(chat_id, "❌ Конкурс уже завершён.")
                return
            participants = contest.get("participants", {})
            if user_id not in participants:
                participants[user_id] = username
                await firebase_set(f"contests/{contest_id}/participants", participants)
                await send_message(chat_id, f"✅ Вы участвуете в конкурсе {contest_id}!")
            else:
                await send_message(chat_id, "Вы уже участвуете в этом конкурсе.")
            return

        if cb_data == "add_channel":
            user_states[user_id] = {"mode": "add_channel"}
            await send_message(chat_id, "📢 Введите название канала в формате @channelname\n"
                                        "Или перешлите сообщение из приватного канала.",
                              reply_markup=MAIN_KEYBOARD)
            return

        if cb_data == "add_group":
            user_states[user_id] = {"mode": "add_channel"}
            await send_message(chat_id, "📢 Введите название группы в формате @groupname\n"
                                        "Или перешлите сообщение из группы.",
                              reply_markup=MAIN_KEYBOARD)
            return

        if cb_data.startswith("del_channel_"):
            channel_id = cb_data[12:]
            await firebase_delete(f"channels/{user_id}/list/{channel_id}")
            await send_message(chat_id, "🗑 Канал удалён.")
            await show_channels(chat_id, user_id)
            return

# ===== ПОЛЛИНГ =====
async def poll_updates():
    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                url = f"{API_BASE}/bot{TOKEN}/getUpdates"
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
    print("🎯 Конкурс-бот (финальная версия) запущен (FlashGram).")
    asyncio.run(poll_updates())
