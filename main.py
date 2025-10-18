import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime, timedelta
import pytz
from flask import Flask
import threading
import os
import logging
import time  # Добавляем импорт модуля time

# Настройка логирования для диагностики
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
# Настройка хранилища задач в SQLite
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
    day_of_week = datetime.now(tz).weekday()
    message_text = reminders[day_of_week]

    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton("✅ Выпила", callback_data="took_pill")
    keyboard.add(button)

    try:
        sent_message = bot.send_message(CHANNEL_ID, message_text, reply_markup=keyboard)
        last_pill_time[sent_message.message_id] = {"sent_time": datetime.now(tz), "taken_time": None}
        logging.info(f"[{datetime.now(tz)}] Отправлено напоминание.")
    except Exception as e:
        logging.error(f"[{datetime.now(tz)}] Ошибка при отправке напоминания: {e}")

def check_reminder():
    tz = pytz.timezone('Asia/Vladivostok')
    current_time = datetime.now(tz)
    for message_id, times in list(last_pill_time.items()):
        sent_time = times["sent_time"]
        taken_time = times["taken_time"]
        if taken_time is None and current_time > (sent_time + timedelta(minutes=5)):
            try:
                bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку, а то по жопе получишь!")
                last_pill_time[message_id]["taken_time"] = current_time
                logging.info(f"[{datetime.now(tz)}] Отправлено повторное напоминание.")
            except Exception as e:
                logging.error(f"[{datetime.now(tz)}] Ошибка при отправке повторного напоминания: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "took_pill":
        try:
            bot.answer_callback_query(call.id, "Отлично!")
            bot.send_message(CHANNEL_ID, "Молодец ❤️")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            last_pill_time[call.message.message_id]["taken_time"] = datetime.now(pytz.timezone('Asia/Vladivostok'))
            logging.info(f"[{datetime.now(tz)}] Кнопка нажата.")
        except Exception as e:
            logging.error(f"[{datetime.now(tz)}] Ошибка при обработке кнопки: {e}")

# === ФОНОВЫЕ ПОТОКИ ===
def run_bot():
    import telebot.apihelper
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except telebot.apihelper.ApiTelegramException as e:
            if "Conflict" in str(e):
                logging.warning(f"[{datetime.now(pytz.timezone('Asia/Vladivostok'))}] Обнаружен дубликат бота — завершаем этот экземпляр.")
                time.sleep(10)
            else:
                logging.error(f"[{datetime.now(pytz.timezone('Asia/Vladivostok'))}] Ошибка polling: {e}")
                time.sleep(10)
        except Exception as e:
            logging.error(f"[{datetime.now(pytz.timezone('Asia/Vladivostok'))}] Ошибка: {e}")
            time.sleep(10)

# === ПОДДЕРЖКА РЕНДЕРА (порт-заглушка) ===
@app.route('/')
def home():
    return "✅ Бот работает", 200

# === НАСТРОЙКА РАСПИСАНИЯ ===
def setup_scheduler():
    logging.info(f"[{datetime.now(pytz.timezone('Asia/Vladivostok'))}] Инициализация расписания...")
    # Удаляем старые задачи
    scheduler.remove_all_jobs()
    # Ежедневное напоминание в 15:40
    scheduler.add_job(
        send_reminder,
        'cron',
        hour=15,
        minute=40,
        timezone=pytz.timezone('Asia/Vladivostok'),
        id='send_reminder'
    )
    # Проверка каждую минуту
    scheduler.add_job(
        check_reminder,
        'interval',
        minutes=1,
        timezone=pytz.timezone('Asia/Vladivostok'),
        id='check_reminder'
    )

# === ЗАПУСК ===
if __name__ == "__main__":
    # Запускаем планировщик
    setup_scheduler()
    scheduler.start()
    logging.info(f"[{datetime.now(pytz.timezone('Asia/Vladivostok'))}] Планировщик запущен.")

    # Запускаем бота и Flask в отдельных потоках
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
