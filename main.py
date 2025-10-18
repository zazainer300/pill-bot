import os
import time
import json
import logging
from datetime import datetime, timedelta

import pytz
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

# === ЛОГИ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Не задана переменная окружения TELEGRAM_TOKEN")

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003095096004"))
PUBLIC_URL = os.getenv("PUBLIC_URL")
if not PUBLIC_URL:
    raise ValueError("Не задана переменная окружения PUBLIC_URL")

# === TELEGRAM BOT & FLASK ===
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === ВРЕМЕННАЯ ЗОНА ===
os.environ["TZ"] = "Asia/Vladivostok"
if hasattr(time, "tzset"):
    time.tzset()
tz = pytz.timezone("Asia/Vladivostok")

# === ДАННЫЕ ===
last_pill_time = {}

def save_last_pill_time():
    try:
        with open('last_pill_time.json', 'w') as f:
            json.dump({k: {
                'sent_time': v['sent_time'].isoformat(),
                'taken_time': v['taken_time'].isoformat() if v['taken_time'] else None
            } for k, v in last_pill_time.items()}, f)
        logging.info("last_pill_time сохранён.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении last_pill_time: {e}")

def load_last_pill_time():
    global last_pill_time
    try:
        with open('last_pill_time.json', 'r') as f:
            data = json.load(f)
            last_pill_time = {int(k): {
                'sent_time': datetime.fromisoformat(v['sent_time']),
                'taken_time': datetime.fromisoformat(v['taken_time']) if v['taken_time'] else None
            } for k, v in data.items()}
        logging.info("last_pill_time загружен.")
    except FileNotFoundError:
        logging.info("Файл last_pill_time.json не найден — создаём новый.")
        last_pill_time = {}
    except Exception as e:
        logging.error(f"Ошибка при загрузке last_pill_time: {e}")
        last_pill_time = {}

reminders = [
    "Жопа, выпей таблетку.",
    "Жопа, время таблеток.",
    "Наглая, выпей, пожалуйста, таблеточку.",
    "Сказочница, таблеточка зовёт!",
    "Жопа, не забудь выпить.",
    "Наглая, твоя таблеточка ждёт.",
    "Софа, выпей таблеточку."
]

# === APSCHEDULER ===
scheduler = BackgroundScheduler(timezone=tz)

def send_reminder():
    current_time = datetime.now(tz)
    day_of_week = current_time.weekday()
    message_text = reminders[day_of_week]

    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton("✅ Выпила", callback_data="took_pill")
    keyboard.add(button)

    try:
        sent_message = bot.send_message(CHANNEL_ID, message_text, reply_markup=keyboard)
        last_pill_time[sent_message.message_id] = {"sent_time": current_time, "taken_time": None}
        save_last_pill_time()
        logging.info(f"Отправлено напоминание ({sent_message.message_id}) в {current_time}.")
    except Exception as e:
        logging.error(f"Ошибка при отправке напоминания: {e}")

def check_reminder():
    current_time = datetime.now(tz)
    for message_id, times in list(last_pill_time.items()):
        sent_time = times["sent_time"]
        taken_time = times["taken_time"]
        if taken_time is None and current_time - sent_time > timedelta(minutes=5):
            try:
                bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку 😠")
                last_pill_time[message_id]["taken_time"] = current_time
                save_last_pill_time()
                logging.info(f"Отправлено повторное напоминание ({message_id})")
            except Exception as e:
                logging.error(f"Ошибка при повторном напоминании: {e}")

def log_status():
    current_time = datetime.now(tz)
    logging.info(f"[{current_time}] Статус: {len(last_pill_time)} напоминаний сохранено.")

def job_listener(event):
    if event.exception:
        logging.error(f"Ошибка в задаче {event.job_id}: {event.exception}")
    else:
        logging.debug(f"Задача {event.job_id} выполнена успешно.")

scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

def setup_scheduler():
    scheduler.remove_all_jobs()
    scheduler.add_job(send_reminder, 'cron', hour=15, minute=0, id='send_reminder')
    scheduler.add_job(check_reminder, 'interval', minutes=10, id='check_reminder')
    scheduler.add_job(log_status, 'interval', minutes=2, id='log_status')
    scheduler.start()
    logging.info("Планировщик запущен.")

# === CALLBACK ===
@bot.callback_query_handler(func=lambda call: call.data == "took_pill")
def handle_pill_button(call):
    current_time = datetime.now(tz)
    try:
        bot.answer_callback_query(call.id, "Отлично!")
        bot.send_message(CHANNEL_ID, "Молодец ❤️")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        if call.message.message_id in last_pill_time:
            last_pill_time[call.message.message_id]["taken_time"] = current_time
            save_last_pill_time()
        logging.info(f"Кнопка нажата для {call.message.message_id}")
    except Exception as e:
        logging.error(f"Ошибка при обработке кнопки: {e}")

# === FLASK ===
@app.route('/')
def home():
    logging.info(f"[{datetime.now(tz)}] Проверка /")
    return "✅ Бот работает", 200

@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.data.decode('utf-8'))
        bot.process_new_updates([update])
    except Exception as e:
        logging.error(f"Ошибка обработки webhook: {e}")
    return '', 200

# === ЗАПУСК ===
if __name__ == "__main__":
    load_last_pill_time()
    setup_scheduler()

    # Устанавливаем webhook
    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{PUBLIC_URL}/webhook/{TOKEN}")
        logging.info(f"🔗 Webhook установлен: {PUBLIC_URL}/webhook/{TOKEN}")
    except Exception as e:
        logging.error(f"Ошибка при установке webhook: {e}")
