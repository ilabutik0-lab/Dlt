import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8906681827:AAH5j1XXcDP_3xcNNPqK98D3XALcMHMpsPE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7314968751"))
PORT = int(os.environ.get("PORT", 10000))
# =============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

bot_settings = {
    "is_active": True,
    "delete_mode": "all",
    "delay_seconds": 15
}

def get_control_keyboard():
    status_btn = "🟢 Работает (Пауза)" if bot_settings["is_active"] else "🔴 НА ПАУЗЕ (Включить)"
    mode_btn = "🔄 Режим: ВСЕ" if bot_settings["delete_mode"] == "all" else "👤 Режим: ТОЛЬКО МОИ"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status_btn, callback_data="toggle_active")],
        [InlineKeyboardButton(text=mode_btn, callback_data="toggle_mode")],
        [
            InlineKeyboardButton(text="⏱ 10 сек", callback_data="time_10s"),
            InlineKeyboardButton(text="⏱ 1 мин", callback_data="time_1m"),
            InlineKeyboardButton(text="⏱ 15 мин", callback_data="time_15m"),
            InlineKeyboardButton(text="⏱ 30 мин", callback_data="time_30m")
        ],
        [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_menu")]
    ])

def get_status_text():
    status = "🟢 <b>АКТИВЕН</b>" if bot_settings["is_active"] else "🔴 <b>НА ПАУЗЕ</b>"
    mode = "Удалять <b>ВСЕ</b> сообщения" if bot_settings["delete_mode"] == "all" else "Удалять <b>ТОЛЬКО МОИ</b>"
    sec = bot_settings["delay_seconds"]
    time_str = f"{sec // 60} мин." if sec >= 60 else f"{sec} сек."

    return (
        f"⚙️ <b>Telegram Business Cleaner:</b>\n\n"
        f"• Статус: {status}\n"
        f"• Режим: {mode}\n"
        f"• Таймер: <b>{time_str}</b>\n\n"
        f"<i>Команда для быстрой смены таймера: <code>/timer 10s</code></i>"
    )

async def schedule_delete(chat_id: int, message_id: int, delay: int, business_connection_id: str):
    print(f"[ЛОГ] Сообщение {message_id} запланировано к удалению через {delay} сек. (conn={business_connection_id})", flush=True)
    await asyncio.sleep(delay)

    if not bot_settings["is_active"]:
        print("[ЛОГ] Удаление отменено: бот на паузе.", flush=True)
        return

    # Прямой запрос к Telegram API (обход ограничений aiogram)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "business_connection_id": business_connection_id
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get("ok"):
                    print(f"[УСПЕХ] Сообщение {message_id} успешно удалено!", flush=True)
                else:
                    print(f"[ОШИБКА] Telegram вернул: {result}", flush=True)
    except Exception as e:
        print(f"[ОШИБКА] Не удалось удалить сообщение {message_id}: {e}", flush=True)

# ============ ОТЛАДКА ============
@dp.update()
async def debug_updates(update):
    try:
        conn = getattr(update, 'business_connection_id', None)
        print(f"[DEBUG] type={update.event_type} | conn={conn}", flush=True)
    except Exception as e:
        print(f"[DEBUG] ошибка вывода: {e}", flush=True)

@dp.business_connection()
async def on_conn(connection):
    print(f"[CONN] id={connection.id} user={connection.user.id} can_reply={connection.can_reply}", flush=True)

# ============ ОСНОВНАЯ ЛОГИКА ============
@dp.business_message()
async def on_business_message(message: Message):
    print(f"[ЛОГ] Получено бизнес-сообщение от user_id={message.from_user.id}, conn={message.business_connection_id}", flush=True)

    if not bot_settings["is_active"]:
        print("[ЛОГ] Бот на паузе, пропускаем.", flush=True)
        return

    is_my_msg = (message.from_user.id == ADMIN_ID)
    if bot_settings["delete_mode"] == "only_me" and not is_my_msg:
        print("[ЛОГ] Режим 'только мои', сообщение не наше — пропуск.", flush=True)
        return

    asyncio.create_task(
        schedule_delete(
            chat_id=message.chat.id,
            message_id=message.message_id,
            delay=bot_settings["delay_seconds"],
            business_connection_id=message.business_connection_id
        )
    )

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "toggle_active")
async def cb_toggle_active(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    bot_settings["is_active"] = not bot_settings["is_active"]
    await call.answer()
    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "toggle_mode")
async def cb_toggle_mode(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    bot_settings["delete_mode"] = "only_me" if bot_settings["delete_mode"] == "all" else "all"
    await call.answer()
    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("time_"))
async def cb_set_time(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    val = call.data.split("_")[1]
    if val == "10s":
        bot_settings["delay_seconds"] = 10
    elif val == "1m":
        bot_settings["delay_seconds"] = 60
    elif val == "15m":
        bot_settings["delay_seconds"] = 900
    elif val == "30m":
        bot_settings["delay_seconds"] = 1800
    await call.answer("Время обновлено!")
    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "refresh_menu")
async def cb_refresh(call: CallbackQuery):
    await call.answer("Обновлено")
    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")

@dp.message(Command("timer"))
async def cmd_timer(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return
    arg = parts[1].lower()

    if arg.endswith("s"):
        bot_settings["delay_seconds"] = int(arg[:-1])
    elif arg.endswith("m"):
        bot_settings["delay_seconds"] = int(arg[:-1]) * 60
    elif arg.isdigit():
        bot_settings["delay_seconds"] = int(arg) * 60

    await message.answer(f"⏱ Таймер установлен: <b>{bot_settings['delay_seconds']} сек.</b>", parse_mode="HTML")

# ============ ВЕБ-СЕРВЕР ============
async def handle_ping(request):
    return web.Response(text="OK", status=200)

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[BOOT] Web server started on port {PORT}", flush=True)

# ============ ГЛАВНАЯ ============
async def main():
    print("[BOOT] Bot is starting...", flush=True)
    print(f"[BOOT] PORT={PORT}", flush=True)

    await asyncio.gather(
        start_webserver(),
        dp.start_polling(
            bot,
            drop_pending_updates=True,
            allowed_updates=[
                "message",
                "business_message",
                "edited_business_message",
                "business_connection",
                "callback_query"
            ]
        )
    )

if __name__ == "__main__":
    asyncio.run(main())