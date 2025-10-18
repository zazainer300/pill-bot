import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from datetime import datetime, timedelta
import pytz
from flask import Flask, request
import threading
import os
import logging
import time
import json

# ================= ЛОГИРОВАНИЕ =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

# ================= ВРЕМЯ =================
os.environ["TZ"] = "Asia/Vladivostok"
if hasattr(time, 'tzset'):
    time.tzset()
tz = pytz.timezone('Asia/Vladivostok')

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv("TOKEN")  # Токен из переменной окружения
PUBLIC_URL = os.getenv("PUBLIC_URL")  # URL Render
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003095096004"))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= ДАННЫЕ =================
last_pill_time = {}

def save_last_pill_time():
    try:
        with open('last_pill_time.json', 'w') as f:
            json.dump({k: {'sent_time': v['sent_time'].isoformat(), 
                            'taken_time': v['taken_time'].isoformat() if v['taken_time'] else None} 
                       for k, v in last_pill_time.items()}, f)
        logging.debug("last_pill_time сохранён.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении: {e}")

def load_last_pill_time():
    global last_pill_time
    try:
        with open('last_pill_time.json', 'r') as f:
            data = json.load(f)
            last_pill_time = {
                int(k): {
                    'sent_time': datetime.fromisoformat(v['sent_time']),
                    'taken_time': datetime.fromisoformat(v['taken_time']) if v['taken_time'] else None
                } for k, v in data.items()
            }
        logging.info("last_pill_time загружен.")
    except FileNotFoundError:
        logging.info("Файл last_pill_time.json не найден, создаём новый словарь.")
        last_pill_time = {}
    except Exception as e:
        logging.error(f"Ошибка при загрузке: {e}")
        last_pill_time = {}

# ================= НАПОМИНАНИЯ =================
reminders = [
    "Жопа, выпей таблетку.",
    "Жопа, время таблеток.",
    "Наглая, выпей, пожалуйста, таблеточку.",
    "Сказочница, таблеточка зовёт!",
    "Жопа, не забудь выпить.",
    "Наглая, твоя таблеточка ждёт.",
    "Софа, выпей таблеточку."
]

# ================= APSCHEDULER =================
scheduler = BackgroundScheduler(timezone=tz)

def send_reminder():
    current_time = datetime.now(tz)
    day_of_week = current_time.weekday()
    message_text = reminders[day_of_week % len(reminders)]
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("✅ Выпила", callback_data="took_pill"))
    try:
        sent_message = bot.send_message(CHANNEL_ID, message_text, reply_markup=keyboard)
        last_pill_time[sent_message.message_id] = {"sent_time": current_time, "taken_time": None}
        save_last_pill_time()
        logging.info(f"Отправлено напоминание message_id={sent_message.message_id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке напоминания: {e}")

def check_reminder():
    current_time = datetime.now(tz)
    for message_id, times in list(last_pill_time.items()):
        sent_time = times["sent_time"]
        taken_time = times["taken_time"]
        if taken_time is None and (current_time - sent_time) > timedelta(minutes=5):
            try:
                bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку!")
                last_pill_time[message_id]["taken_time"] = current_time
                save_last_pill_time()
                logging.info(f"Повторное напоминание для message_id={message_id}")
            except Exception as e:
                logging.error(f"Ошибка при повторном напоминании: {e}")

def log_bot_status():
    current_time = datetime.now(tz)
    logging.info(f"Статус: {len(last_pill_time)} напоминаний сохранено.")

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
    scheduler.add_job(log_bot_status, 'interval', minutes=2, id='log_status')
    scheduler.start()
    logging.info("Планировщик запущен.")

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    current_time = datetime.now(tz)
    if call.data == "took_pill":
        try:
            bot.answer_callback_query(call.id, "Отлично!")
            bot.send_message(CHANNEL_ID, "Молодец ❤️")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            if call.message.message_id in last_pill_time:
                last_pill_time[call.message.message_id]["taken_time"] = current_time
                save_last_pill_time()
                logging.info(f"Кнопка нажата для message_id={call.message.message_id}")
        except Exception as e:
            logging.error(f"Ошибка при обработке кнопки: {e}")

# ================= FLASK =================
@app.route('/')
def home():
    return "✅ Бот работает", 200

@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    json_data = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "!", 200

def run_bot():
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logging.error(f"Ошибка polling: {e}")
            time.sleep(5)

# ================= ЗАПУСК =================
if __name__ == "__main__":
    load_last_pill_time()
    setup_scheduler()
    try:
        bot.remove_webhook()
        result = bot.set_webhook(url=f"{PUBLIC_URL}/webhook/{TOKEN}")
        logging.info(f"Webhook установлен: {PUBLIC_URL}/webhook/{TOKEN}, result={result}")
    except Exception as e:
        logging.error(f"Ошибка установки webhook: {e}")
