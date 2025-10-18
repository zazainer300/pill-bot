import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask, request
import pytz
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

# =================== НАСТРОЙКА ===================
# Переменные окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003095096004"))
PUBLIC_URL = os.getenv("PUBLIC_URL")  # например: https://your-app.onrender.com

if not TOKEN:
    raise SystemExit("❌ TELEGRAM_TOKEN не найден. Укажите его в переменных окружения Render.")

# Telegram bot
bot = telebot.TeleBot(TOKEN, threaded=True)
app = Flask(__name__)

# Часовой пояс Владивостока
tz = pytz.timezone("Asia/Vladivostok")

# =================== ЛОГИ ===================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

# =================== ДАННЫЕ ===================
last_pill_time = {}
last_pill_lock = threading.Lock()

reminders = [
    "Жопа, выпей таблетку.",
    "Жопа, время таблеток.",
    "Наглая, выпей, пожалуйста, таблеточку.",
    "Сказочница, таблеточка зовёт!",
    "Жопа, не забудь выпить.",
    "Наглая, твоя таблеточка ждёт.",
    "Софа, выпей таблеточку."
]

# =================== ФУНКЦИИ ===================
def save_last_pill_time():
    with last_pill_lock:
        try:
            data = {
                k: {
                    'sent_time': v['sent_time'].isoformat(),
                    'taken_time': v['taken_time'].isoformat() if v['taken_time'] else None
                } for k, v in last_pill_time.items()
            }
            with open('last_pill_time.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logging.debug("✅ last_pill_time сохранён.")
        except Exception as e:
            logging.error(f"Ошибка при сохранении last_pill_time: {e}")

def load_last_pill_time():
    global last_pill_time
    try:
        with open('last_pill_time.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            last_pill_time = {
                int(k): {
                    'sent_time': datetime.fromisoformat(v['sent_time']),
                    'taken_time': datetime.fromisoformat(v['taken_time']) if v['taken_time'] else None
                } for k, v in data.items()
            }
        logging.info("✅ last_pill_time загружен.")
    except FileNotFoundError:
        logging.info("Файл last_pill_time.json не найден. Создан пустой словарь.")
        last_pill_time = {}
    except Exception as e:
        logging.error(f"Ошибка при загрузке last_pill_time: {e}")
        last_pill_time = {}

# =================== ФУНКЦИИ БОТА ===================
def send_reminder():
    current_time = datetime.now(tz)
    day_of_week = current_time.weekday()
    message_text = reminders[day_of_week]

    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton("✅ Выпила", callback_data="took_pill")
    keyboard.add(button)

    try:
        sent_message = bot.send_message(CHANNEL_ID, message_text, reply_markup=keyboard)
        with last_pill_lock:
            last_pill_time[sent_message.message_id] = {"sent_time": current_time, "taken_time": None}
        save_last_pill_time()
        logging.info(f"[{current_time}] Напоминание отправлено (message_id={sent_message.message_id})")
    except Exception as e:
        logging.error(f"Ошибка при отправке напоминания: {e}")

def check_reminder():
    current_time = datetime.now(tz)
    logging.debug("Проверка напоминаний...")
    with last_pill_lock:
        for message_id, times in list(last_pill_time.items()):
            sent_time = times["sent_time"]
            taken_time = times["taken_time"]
            if taken_time is None and current_time - sent_time > timedelta(minutes=5):
                try:
                    bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку 😠")
                    last_pill_time[message_id]["taken_time"] = current_time
                    save_last_pill_time()
                    logging.info(f"Отправлено повторное напоминание для message_id={message_id}")
                except Exception as e:
                    logging.error(f"Ошибка при повторном напоминании: {e}")

def log_bot_status():
    current_time = datetime.now(tz)
    logging.info(f"Статус: {len(last_pill_time)} напоминаний сохранено.")
    with last_pill_lock:
        for message_id, times in last_pill_time.items():
            logging.info(f"→ {message_id}: отправлено в {times['sent_time']}, нажата: {bool(times['taken_time'])}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    current_time = datetime.now(tz)
    if call.data == "took_pill":
        try:
            bot.answer_callback_query(call.id, "Отлично!")
            bot.send_message(CHANNEL_ID, "Молодец ❤️")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            with last_pill_lock:
                if call.message.message_id in last_pill_time:
                    last_pill_time[call.message.message_id]["taken_time"] = current_time
                    save_last_pill_time()
            logging.info(f"[{current_time}] Кнопка нажата (message_id={call.message.message_id})")
        except Exception as e:
            logging.error(f"Ошибка при обработке кнопки: {e}")

# =================== APSCHEDULER ===================
scheduler = BackgroundScheduler(timezone=tz)

def setup_scheduler():
    scheduler.remove_all_jobs()
    scheduler.add_job(send_reminder, 'cron', hour=15, minute=0, id='send_reminder')
    scheduler.add_job(check_reminder, 'interval', minutes=10, id='check_reminder')
    scheduler.add_job(log_bot_status, 'interval', minutes=2, id='log_status')
    logging.info("✅ Расписание задач настроено.")
    for job in scheduler.get_jobs():
        logging.info(f"→ {job}")

def job_listener(event):
    if event.exception:
        logging.error(f"Ошибка в задаче {event.job_id}: {event.exception}")
    else:
        logging.debug(f"Задача {event.job_id} выполнена успешно.")

scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

# =================== FLASK ROUTES ===================
@app.route('/')
def home():
    return "✅ Бот работает (Render Flask Webhook).", 200

@app.route(f"/webhook/{TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

def set_webhook():
    if not PUBLIC_URL:
        logging.error("❌ PUBLIC_URL не задан в окружении! Webhook не будет установлен.")
        return
    webhook_url = f"{PUBLIC_URL}/webhook/{TOKEN}"
    bot.remove_webhook()
    success = bot.set_webhook(url=webhook_url)
    logging.info(f"🔗 Установка webhook: {webhook_url} — {'успешно' if success else 'ошибка'}")

# =================== MAIN ===================
if __name__ == "__main__":
    logging.info("🚀 Запуск бота на Render...")
    load_last_pill_time()
    setup_scheduler()
    scheduler.start()
    set_webhook()
    try:
        bot.get_me()
        bot.send_message(CHANNEL_ID, "✅ Бот запущен на Render!")
        logging.info("Бот успешно инициализирован через Telegram API.")
    except Exception as e:
        logging.error(f"Ошибка при проверке Telegram API: {e}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
