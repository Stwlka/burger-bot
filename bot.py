import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

logging.basicConfig(level=logging.INFO)

# ==========================================
# ВСТАВЬ СЮДА СВОЙ НОВЫЙ ТОКЕН (ПОСЛЕ REVOKE)
BOT_TOKEN = '8993291116:AAFIIIhfkOCR7u8Tsqxe6lFufT8vEWHZOLM'
# ВСТАВЬ СЮДА СВОЙ ID (узнать у @userinfobot)
ADMIN_ID = 6994399653
# ==========================================

# ВСТАВЬ АДРЕС СВОЕГО CLOUDFLARE WORKER'А
WORKER_URL = "https://wild-credit-6d87.kzvania4.workers.dev"
# ==========================================

# Секретный путь для вебхука (придумай любой набор букв)
WEBHOOK_PATH = "/webhook"
# Твой будущий адрес на Render (мы узнаем его после деплоя)
BASE_WEBHOOK_URL = "https://burger-bot-9t1p.onrender.com"

session = AiohttpSession(api=TelegramAPIServer.from_base(WORKER_URL))
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

# Имитация базы данных
cart_db = {}

# Меню бургеров
BURGERS = {
    "gladiator": {"name": "Гладиатор", "price": 450},
    "cheeseburger": {"name": "Чизбургер", "price": 370},
    "barbekyu": {"name": "Барбекю", "price": 490},
    "vkus_haus": {"name": "Вкус Хаус", "price": 550},
    "chiz_master": {"name": "Чиз Мастер", "price": 600}
}

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    cart_db[message.from_user.id] = []
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🍔 Меню")], [types.KeyboardButton(text="🛒 Корзина")]],
        resize_keyboard=True
    )
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Добро пожаловать в Burger Haus. Выбирай бургеры, а я посчитаю сумму.",
        reply_markup=keyboard
    )

@dp.message(lambda message: message.text == "🍔 Меню")
async def show_menu(message: types.Message):
    builder = InlineKeyboardBuilder()
    for key, item in BURGERS.items():
        builder.button(text=f"{item['name']} - {item['price']} ₽", callback_data=f"add_{key}")
    builder.adjust(1)
    await message.answer("Выбери бургер, чтобы добавить в корзину:", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data.startswith('add_'))
async def process_add(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    burger_key = callback.data.split('_')[1]
    if user_id not in cart_db:
        cart_db[user_id] = []
    cart_db[user_id].append(BURGERS[burger_key])
    await callback.answer(f"{BURGERS[burger_key]['name']} добавлен в корзину!")
    await callback.message.edit_text(f"✅ {BURGERS[burger_key]['name']} добавлен!\n\nВыбирай дальше или переходи в корзину.")

@dp.message(lambda message: message.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    cart = cart_db.get(user_id, [])
    if not cart:
        await message.answer("Твоя корзина пуста. Загляни в меню! 🍔")
        return
    total = sum(item['price'] for item in cart)
    text = "🛒 <b>Твоя корзина:</b>\n\n"
    for item in cart:
        text += f"• {item['name']} — {item['price']} ₽\n"
    text += f"\n<b>Итого: {total} ₽</b>"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оформить заказ", callback_data="checkout")
    builder.button(text="🗑 Очистить", callback_data="clear_cart")
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    cart_db[callback.from_user.id] = []
    await callback.message.edit_text("Корзина очищена. Ждем вас снова! 👋")

@dp.callback_query(lambda c: c.data == "checkout")
async def process_checkout(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cart = cart_db.get(user_id, [])
    if not cart:
        await callback.answer("Корзина пуста!", show_alert=True)
        return
    total = sum(item['price'] for item in cart)
    username = callback.from_user.username or "Без юзернейма"
    name = callback.from_user.first_name
    
    order_text = f"🔔 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
    order_text += f"👤 Клиент: {name} (@{username})\n"
    order_text += f"🆔 ID: {user_id}\n\n"
    order_text += f"<b>Состав:</b>\n"
    for item in cart:
        order_text += f"• {item['name']} — {item['price']} ₽\n"
    order_text += f"\n<b>Сумма к оплате: {total} ₽</b>"
    
    try:
        await bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")
        await callback.message.edit_text(f"✅ Заказ на {total} ₽ оформлен! Владелец скоро свяжется с вами.")
        cart_db[user_id] = []
    except Exception as e:
        await callback.message.edit_text("Ошибка при отправке заказа. Попробуйте позже.")
        print(f"Ошибка отправки админу: {e}")

# ==========================================
# НАСТРОЙКА ВЕБ-СЕРВЕРА ДЛЯ RENDER
# ==========================================
async def on_startup(bot: Bot):
    webhook_url = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    print(f"Вебхук установлен: {webhook_url}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()

def main():
    app = web.Application()

    async def health_check(request):
    return web.Response(text="OK")

app.router.add_get('/', health_check)
    
    # Обработчик вебхука
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Добавляем обработчики старта/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Настраиваем приложение
    setup_application(app, dp, bot=bot)
    
    # Render сам выдает порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
