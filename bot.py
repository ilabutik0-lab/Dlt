import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart

# ==============================================================================
# ⚠️ ОБЯЗАТЕЛЬНО УКАЖИ СВОИ ДАННЫЕ ЗДЕСЬ:
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8906681827:AAH5j1XXcDP_3xcNNPqK98D3XALcMHMpsPE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1827818074"))  # Твой Telegram ID
PORT = int(os.environ.get("PORT", 8080))
# ==============================================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настройки работы бота
bot_settings = {
    "is_active": True,           # Включен ли бот вообще
    "delete_mode": "all",        # "all" - удалять все, "only_me" - только мои
    "delay_seconds": 1800        # По умолчанию 30 минут (1800 секунд)
}


# Генерация кнопок меню управления
def get_control_keyboard():
    status_btn = "🟢 Работает (Поставить на паузу)" if bot_settings["is_active"] else "🔴 НА ПАУЗЕ (Включить)"
    
    if bot_settings["delete_mode"] == "all":
        mode_btn = "🔄 Режим: ВСЕ сообщения"
    else:
        mode_btn = "👤 Режим: ТОЛЬКО МОИ"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status_btn, callback_data="toggle_active")],
        [InlineKeyboardButton(text=mode_btn, callback_data="toggle_mode")],
        [
            InlineKeyboardButton(text="⏱ 5 мин", callback_data="time_5"),
            InlineKeyboardButton(text="⏱ 15 мин", callback_data="time_15"),
            InlineKeyboardButton(text="⏱ 30 мин", callback_data="time_30"),
            InlineKeyboardButton(text="⏱ 1 час", callback_data="time_60")
        ],
        [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_menu")]
    ])
    return kb


def get_status_text():
    status = "🟢 <b>АКТИВЕН</b>" if bot_settings["is_active"] else "🔴 <b>НА ПАУЗЕ</b>"
    mode = "Удалять <b>ВСЕ</b> (мои и собеседника)" if bot_settings["delete_mode"] == "all" else "Удалять <b>ТОЛЬКО МОИ</b> сообщения"
    mins = bot_settings["delay_seconds"] // 60

    return (
        f"⚙️ <b>Панель управления Telegram Business Cleaner:</b>\n\n"
        f"• Статус бота: {status}\n"
        f"• Режим очистки: {mode}\n"
        f"• Время жизни сообщений: <b>{mins} мин.</b>\n\n"
        f"<i>Нажимай на кнопки ниже для настройки:</i>"
    )


# Фоновая задача на удаление конкретного сообщения
async def schedule_delete(chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)

    # Если во время ожидания бота выключили — отменяем удаление
    if not bot_settings["is_active"]:
        return

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


# ==============================================================================
# ОБРАБОТКА СООБЩЕНИЙ В ЛИЧНЫХ ЧАТАХ (TELEGRAM BUSINESS)
# ==============================================================================
@dp.business_message()
async def on_business_message(message: Message):
    # Если бот выключен — ничего не делаем
    if not bot_settings["is_active"]:
        return

    # Проверяем, кто отправил сообщение
    is_my_message = (message.from_user.id == ADMIN_ID)

    # Если включен режим "ТОЛЬКО МОИ", а пишет собеседник — пропускаем
    if bot_settings["delete_mode"] == "only_me" and not is_my_message:
        return

    # Отправляем сообщение в очередь на удаление
    asyncio.create_task(
        schedule_delete(
            chat_id=message.chat.id,
            message_id=message.message_id,
            delay=bot_settings["delay_seconds"]
        )
    )


# ==============================================================================
# УПРАВЛЕНИЕ БОТОМ (КНОПКИ И КОМАНДЫ)
# ==============================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("👋 Это приватный бот автоудаления для Telegram Business.")
        return

    await message.answer(
        get_status_text(),
        reply_markup=get_control_keyboard(),
        parse_mode="HTML"
    )


# Включение / Выключение паузы по кнопке
@dp.callback_query(F.data == "toggle_active")
async def cb_toggle_active(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Доступ запрещен!", show_alert=True)

    bot_settings["is_active"] = not bot_settings["is_active"]
    await call.answer("Статус изменен!")
    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")


# Переключение режима (Все сообщения <-> Только мои)
@dp.callback_query(F.data == "toggle_mode")
async def cb_toggle_mode(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Доступ запрещен!", show_alert=True)

    if bot_settings["delete_mode"] == "all":
        bot_settings["delete_mode"] = "only_me"
        await call.answer("Теперь удаляются ТОЛЬКО ТВОИ сообщения!")
    else:
        bot_settings["delete_mode"] = "all"
        await call.answer("Теперь удаляются ВСЕ сообщения в диалоге!")

    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")


# Выбор времени по кнопкам
@dp.callback_query(F.data.startswith("time_"))
async def cb_set_time(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Доступ запрещен!", show_alert=True)

    mins = int(call.data.split("_")[1])
    bot_settings["delay_seconds"] = mins * 60
    await call.answer(f"Таймер установлен на {mins} мин.")
    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")


# Обновить меню
@dp.callback_query(F.data == "refresh_menu")
async def cb_refresh(call: CallbackQuery):
    await call.answer("Обновлено!")
    await call.message.edit_text(get_status_text(), reply_markup=get_control_keyboard(), parse_mode="HTML")


# Ручная команда для любого времени (например, /timer 45)
@dp.message(Command("timer"))
async def cmd_timer(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Формат: <code>/timer 20</code> (укажи число минут)", parse_mode="HTML")
        return

    mins = int(parts[1])
    if mins <= 0:
        await message.answer("⚠️ Число должно быть больше 0 минут!")
        return

    bot_settings["delay_seconds"] = mins * 60
    await message.answer(f"⏱ <b>Установлен таймер: {mins} мин.!</b>", parse_mode="HTML")


# ==============================================================================
# ВЕБ-СЕРВЕР ДЛЯ НЕПРЕРЫВНОЙ РАБОТЫ (RENDER + UPTIMEROBOT 24/7)
# ==============================================================================
async def handle_ping(request):
    return web.Response(text="Telegram Business Cleaner Bot is Online 24/7!", status=200)

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/ping", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()


# Точка входа
async def main():
    print(f">>> Запуск встроенного веб-сервера на порту {PORT}...")
    await start_webserver()
    print(">>> Бот запущен и готов к работе в Telegram Business!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
