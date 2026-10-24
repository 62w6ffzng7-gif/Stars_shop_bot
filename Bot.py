import telebot
import os
import sqlite3
import random
import string
from telebot import types
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- 1. Мини-сервер для Render ---
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# --- 2. Настройки ---
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")  # ВАШ ЛИЧНЫЙ ID (узнать у @userinfobot)
CONTACT_USERNAME = "@Moscow1488" # ИСПРАВЛЕНО: убрано подчеркивание, как у вас в профиле

bot = telebot.TeleBot(TOKEN)

# --- 3. База данных ---
def init_db():
    conn = sqlite3.connect('stars_shop.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  username TEXT,
                  stars_count INTEGER, 
                  price_rub INTEGER, 
                  secret_code TEXT,
                  status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

init_db()

# --- 4. Генератор секретного кода ---
def generate_secret_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# --- 5. Клавиатуры ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🌟 Купить звёзды", "ℹ️ О магазине")
    kb.add("📞 Связаться с продавцом")
    return kb

def stars_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton("🌟 13 звёзд — 25 ₽", callback_data="buy_13_25")
    kb.add(btn1)
    return kb

# --- 6. Хендлеры ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        "👋 Добро пожаловать в наш магазин звёзд Telegram!\n\n"
        "Здесь вы можете быстро и выгодно приобрести звёзды для себя или друзей. 🌟\n"
        "Мы работаем без посредников, цены ниже официальных!\n\n"
        "👇 Выберите действие из меню ниже:"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "🌟 Купить звёзды")
def buy_menu(message):
    text = (
        "💎 Выберите пакет звёзд:\n\n"
        "🔹 13 звёзд — 25 рублей\n\n"
        "⚠️ Пакеты на 21 и 43 звезды временно недоступны.\n\n"
        "Нажмите на нужный пакет ниже:"
    )
    bot.send_message(message.chat.id, text, reply_markup=stars_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_buy(call):
    parts = call.data.split("_")
    stars = int(parts[1])
    price = int(parts[2])

    msg = bot.send_message(
        call.message.chat.id,
        f"📝 Вы выбрали: {stars} звёзд за {price} ₽.\n\n"
        f"Введите ваш юзернейм в Telegram (например, @username), на который вы хотите получить звёзды:"
    )
    bot.register_next_step_handler(msg, receive_username, stars, price)

def receive_username(message, stars, price):
    username = message.text.strip()
    if not username.startswith('@'):
        bot.reply_to(message, "❌ Ошибка: юзернейм должен начинаться с @. Попробуйте снова.")
        return

    user_id = message.from_user.id
    secret = generate_secret_code()
    
    # Создаем заказ в базе
    conn = sqlite3.connect('stars_shop.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, username, stars_count, price_rub, secret_code) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, stars, price, secret))
    order_id = c.lastrowid
    conn.commit()
    conn.close()

    # 1. Сообщение ПОКУПАТЕЛЮ (без Markdown, чтобы ничего не ломалось)
    buyer_text = (
        f"✅ Заказ №{order_id} создан!\n\n"
        f"🌟 Количество звёзд: {stars}\n"
        f"💰 Сумма к оплате: {price} ₽\n"
        f"👤 Получатель: {username}\n\n"
        f"🔑 Ваш секретный код: {secret}\n\n"
        f"💳 Что делать дальше:\n"
        f"1. Напишите нашему менеджеру: {CONTACT_USERNAME}\n"
        f"2. В сообщении укажите номер заказа ({order_id}) и секретный код ({secret}).\n"
        f"3. Менеджер пришлет вам реквизиты для оплаты (карта/СБП).\n\n"
        f"После оплаты звёзды будут зачислены в течение 5 минут! ⏱️"
    )
    bot.send_message(message.chat.id, buyer_text, reply_markup=main_menu())

    # 2. Уведомление АДМИНУ (Вам)
    if ADMIN_ID:
        admin_text = (
            f"🚨 НОВЫЙ ЗАКАЗ!\n\n"
            f"🆔 Номер заказа: {order_id}\n"
            f"👤 Покупатель: {message.from_user.first_name} (@{message.from_user.username})\n"
            f"🎯 Получатель звёзд: {username}\n"
            f"🌟 Количество: {stars} шт.\n"
            f"💰 Сумма: {price} ₽\n\n"
            f"🔑 Секретный код: {secret}\n\n"
            f"⚠️ Ожидайте сообщения от покупателя для выставления реквизитов."
        )
        try:
            bot.send_message(int(ADMIN_ID), admin_text)
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")

@bot.message_handler(func=lambda message: message.text == "ℹ️ О магазине")
def about_shop(message):
    # Убран parse_mode, чтобы кнопка гарантированно работала
    text = (
        "🏪 О нашем магазине\n\n"
        "Мы занимаемся продажей звёзд Telegram с 2023 года.\n"
        "✅ Работаем быстро и надёжно.\n"
        "✅ Цены ниже официальных.\n"
        "✅ Поддержка 24/7.\n\n"
        f"По всем вопросам: {CONTACT_USERNAME}"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "📞 Связаться с продавцом")
def contact_seller(message):
    text = (
        "📞 Связь с продавцом\n\n"
        f"Напишите нам в Telegram: {CONTACT_USERNAME}\n\n"
        "Мы всегда рады помочь! 😊"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

# --- 7. Запуск ---
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
