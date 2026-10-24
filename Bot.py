import telebot
import os
import sqlite3
from telebot import types
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# --- 1. Мини-сервер для Render (чтобы не было ошибки порта) ---
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# --- 2. Настройки бота ---
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Контакт для связи
CONTACT_USERNAME = "@Moscow_1488"

# --- 3. База данных для заказов ---
def init_db():
    conn = sqlite3.connect('stars_shop.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  username TEXT,
                  stars_count INTEGER, 
                  price_rub INTEGER, 
                  status TEXT DEFAULT 'new')''')
    conn.commit()
    conn.close()

init_db()

def save_order(user_id, username, stars_count, price_rub):
    conn = sqlite3.connect('stars_shop.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, username, stars_count, price_rub) VALUES (?, ?, ?, ?)",
              (user_id, username, stars_count, price_rub))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id

# --- 4. Клавиатуры ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🌟 Купить звёзды", "ℹ️ О магазине")
    kb.add("📞 Связаться с продавцом")
    return kb

def stars_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    # Оставлен только один пакет: 13 звёзд за 25 рублей
    btn1 = types.InlineKeyboardButton("🌟 13 звёзд — 25 ₽", callback_data="buy_13_25")
    kb.add(btn1)
    return kb

# --- 5. Хендлеры ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Красивое приветствие с эмодзи
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
        "⚠️ *Пакеты на 21 и 43 звезды временно недоступны.*\n\n"
        "Оплата производится в рублях. Нажмите на нужный пакет ниже:"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=stars_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_buy(call):
    # Извлекаем данные из callback_data (например, buy_13_25)
    parts = call.data.split("_")
    stars = int(parts[1])
    price = int(parts[2])

    msg = bot.send_message(
        call.message.chat.id,
        f"📝 Вы выбрали: {stars} звёзд за {price} ₽.\n\n"
        f"Пожалуйста, введите ваш юзернейм в Telegram (например, @username), "
        f"на который вы хотите получить звёзды:"
    )
    bot.register_next_step_handler(msg, receive_username, stars, price)

def receive_username(message, stars, price):
    username = message.text.strip()
    if not username.startswith('@'):
        bot.reply_to(message, "❌ Ошибка: юзернейм должен начинаться с @. Попробуйте снова.")
        return

    user_id = message.from_user.id
    
    # Сохраняем заказ в базу
    order_id = save_order(user_id, username, stars, price)

    # Формируем сообщение с инструкцией
    text = (
        f"✅ Заказ №{order_id} успешно создан!\n\n"
        f"🌟 Количество звёзд: {stars}\n"
        f"💰 Сумма к оплате: {price} ₽\n"
        f"👤 Получатель: {username}\n\n"
        f"💳 **Для оплаты и получения звёзд**, пожалуйста, напишите нашему менеджеру:\n"
        f"👉 {CONTACT_USERNAME}\n\n"
        f"В сообщении укажите номер вашего заказа и юзернейм. После оплаты звёзды будут зачислены в течение 5 минут! ⏱️"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "ℹ️ О магазине")
def about_shop(message):
    text = (
        "🏪 **О нашем магазине**\n\n"
        "Мы занимаемся продажей звёзд Telegram с 2023 года.\n"
        "✅ Работаем быстро и надёжно.\n"
        "✅ Цены ниже официальных.\n"
        "✅ Поддержка 24/7.\n\n"
        f"По всем вопросам: {CONTACT_USERNAME}"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "📞 Связаться с продавцом")
def contact_seller(message):
    text = (
        "📞 **Связь с продавцом**\n\n"
        f"Напишите нам в Telegram: {CONTACT_USERNAME}\n\n"
        "Мы всегда рады помочь! 😊"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

# --- 6. Запуск бота ---
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
