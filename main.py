import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime, timedelta
import pytz
from flask import Flask
import threading
import os
import logging
import time
import json

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Установка временной зоны
os.environ["TZ"] = "Asia/Vladivostok"
if hasattr(time, 'tzset'):
    time.tzset()

# === НАСТРОЙКИ ===
TOKEN = "6000570380:AAGLK37oLf3b1W5P9kNYnsigEXSUVt7Ua0I"
CHANNEL_ID = -1003095096004  # ID канала

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# === ДАННЫЕ ===
last_pill_time = {}

# Функции для сохранения и загрузки last_pill_time
def save_last_pill_time():
    try:
        with open('last_pill_time.json', 'w') as f:
            json.dump({k: {'sent_time': v['sent_time'].isoformat(), 'taken_time': v['taken_time'].isoformat() if v['taken_time'] else None} for k, v in last_pill_time.items()}, f)
        logging.debug("last_pill_time сохранён в файл.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении last_pill_time: {e}")

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
        logging.debug("last_pill_time загружен из файла.")
    except FileNotFoundError:
        logging.info("Файл last_pill_time.json не найден, инициализация пустого словаря.")
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

# === ИНИЦИАЛИЗАЦИЯ APSCHEDULER ===
job_stores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
}
scheduler = BackgroundScheduler(
    jobstores=job_stores,
    timezone=pytz.timezone('Asia/Vladivostok')
)

# === ФУНКЦИИ ===
def send_reminder():
    tz = pytz.timezone('Asia/Vladivostok')
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
        logging.info(f"[{current_time}] Отправлено напоминание для message_id={sent_message.message_id}")
    except Exception as e:
        logging.error(f"[{current_time}] Ошибка при отправке напоминания: {e}")

def check_reminder():
    tz = pytz.timezone('Asia/Vladivostok')
    current_time = datetime.now(tz)
    logging.debug(f"[{current_time}] Выполняется check_reminder, last_pill_time: {last_pill_time}")
    for message_id, times in list(last_pill_time.items()):
        sent_time = times["sent_time"]
        taken_time = times["taken_time"]
        time_diff = current_time - sent_time
        logging.debug(f"[{current_time}] Проверка message_id={message_id}, sent_time={sent_time}, taken_time={taken_time}, time_diff={time_diff}")
        if taken_time is None and time_diff > timedelta(minutes=10):
            try:
                bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку, а то по жопе получишь!")
                last_pill_time[message_id]["taken_time"] = current_time
                save_last_pill_time()
                logging.info(f"[{current_time}] Отправлено повторное напоминание для message_id={message_id}")
            except Exception as e:
                logging.error(f"[{current_time}] Ошибка при отправке повторного напоминания: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    tz = pytz.timezone('Asia/Vladivostok')
    current_time = datetime.now(tz)
    if call.data == "took_pill":
        try:
            bot.answer_callback_query(call.id, "Отлично!")
            bot.send_message(CHANNEL_ID, "Молодец ❤️")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            if call.message.message_id in last_pill_time:
                last_pill_time[call.message.message_id]["taken_time"] = current_time
                save_last_pill_time()
                logging.info(f"[{current_time}] Кнопка нажата для message_id={call.message.message_id}")
            else:
                logging.warning(f"[{current_time}] message_id={call.message.message_id} не найден в last_pill_time")
        except Exception as e:
            logging.error(f"[{current_time}] Ошибка при обработке кнопки: {e}")

# === ФОНОВЫЕ ПОТОКИ ===
def run_bot():
    import telebot.apihelper
    tz = pytz.timezone('Asia/Vladivostok')
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except telebot.apihelper.ApiTelegramException as e:
            if "Conflict" in str(e):
                logging.warning(f"[{datetime.now(tz)}] Обнаружен дубликат бота — завершаем этот экземпляр.")
                time.sleep(10)
            else:
                logging.error(f"[{datetime.now(tz)}] Ошибка polling: {e}")
                time.sleep(10)
        except Exception as e:
            logging.error(f"[{datetime.now(tz)}] Ошибка: {e}")
            time.sleep(10)

# === ПОДДЕРЖКА РЕНДЕРА (порт-заглушка) ===
@app.route('/')
def home():
    return "✅ Бот работает", 200

# === НАСТРОЙКА РАСПИСАНИЯ ===
def setup_scheduler():
    tz = pytz.timezone('Asia/Vladivostok')
    logging.info(f"[{datetime.now(tz)}] Инициализация расписания...")
    scheduler.remove_all_jobs()
    scheduler.add_job(
        send_reminder,
        'cron',
        hour=16,
        minute=05,
        timezone=pytz.timezone('Asia/Vladivostok'),
        id='send_reminder'
    )
    scheduler.add_job(
        check_reminder,
        'interval',
        minutes=1,
        timezone=pytz.timezone('Asia/Vladivostok'),
        id='check_reminder'
    )

# === ЗАПУСК ===
if __name__ == "__main__":
    tz = pytz.timezone('Asia/Vladivostok')
    # Загружаем last_pill_time
    load_last_pill_time()
    # Запускаем планировщик
    setup_scheduler()
    try:
        scheduler.start()
        logging.info(f"[{datetime.now(tz)}] Планировщик запущен.")
    except Exception as e:
        logging.error(f"[{datetime.now(tz)}] Ошибка при запуске планировщика: {e}")
    # Запускаем бота и Flask
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)

