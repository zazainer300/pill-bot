import telebot
import schedule
import time
import threading
from datetime import datetime, timedelta
import pytz
from flask import Flask

# === НАСТРОЙКИ ===
TOKEN = "6000570380:AAGUjahW0W9iahEKW1o7d_bo4poeswofeAc"
CHANNEL_ID = -1003095096004  # ID твоего канала

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


# === ФУНКЦИИ ===
def send_reminder():
    day_of_week = datetime.now().weekday()
    message_text = reminders[day_of_week]

    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton("✅ Выпила", callback_data="took_pill")
    keyboard.add(button)

    sent_message = bot.send_message(CHANNEL_ID, message_text, reply_markup=keyboard)
    last_pill_time[sent_message.message_id] = {"sent_time": datetime.now(), "taken_time": None}
    print(f"[{datetime.now()}] Отправлено напоминание.")


def check_reminder():
    current_time = datetime.now()
    for message_id, times in list(last_pill_time.items()):
        sent_time = times["sent_time"]
        taken_time = times["taken_time"]
        if taken_time is None and current_time > (sent_time + timedelta(minutes=5)):
            bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку, а то по жопе получишь!")
            last_pill_time[message_id]["taken_time"] = current_time
            print(f"[{datetime.now()}] Отправлено повторное напоминание.")


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "took_pill":
        bot.answer_callback_query(call.id, "Отлично!")
        bot.send_message(CHANNEL_ID, "Молодец ❤️")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        last_pill_time[call.message.message_id]["taken_time"] = datetime.now()
        print(f"[{datetime.now()}] Кнопка нажата.")


# === ФОНОВЫЕ ПОТОКИ ===
def schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)


def run_bot():
    """Запускает бота с защитой от ошибки 409."""
    import telebot.apihelper
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except telebot.apihelper.ApiTelegramException as e:
            if "Conflict" in str(e):
                print("⚠️ Обнаружен дубликат бота — завершаем этот экземпляр.")
                time.sleep(10)
            else:
                print(f"Ошибка polling: {e}")
                time.sleep(10)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(10)


# === ПОДДЕРЖКА РЕНДЕРА (порт-заглушка) ===
@app.route('/')
def home():
    return "✅ Бот работает", 200


# === РАСПИСАНИЕ ===
schedule.every().day.at("15:30", tz=pytz.timezone('Asia/Vladivostok')).do(send_reminder)
schedule.every(1).minutes.do(check_reminder)


# === ЗАПУСК ===
if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=schedule_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)




