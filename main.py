import telebot
import schedule
import time
import threading
from datetime import datetime, timedelta
import pytz
import os

# Настройки из переменных окружения
TOKEN = os.getenv('TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

bot = telebot.TeleBot(TOKEN)

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

def send_reminder():
    day_of_week = datetime.now().weekday()
    message_text = reminders[day_of_week]
    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton("✅ Выпила", callback_data="took_pill")
    keyboard.add(button)

    sent_message = bot.send_message(CHANNEL_ID, message_text, reply_markup=keyboard)
    last_pill_time[sent_message.message_id] = {"sent_time": datetime.now(), "taken_time": None}

def check_reminder():
    current_time = datetime.now()
    for message_id, times in list(last_pill_time.items()):
        sent_time = times["sent_time"]
        taken_time = times["taken_time"]
        if taken_time is None and current_time > (sent_time + timedelta(minutes=5)):
            bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку, а то по жопе получишь!")
            last_pill_time[message_id]["taken_time"] = current_time

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "took_pill":
        bot.answer_callback_query(call.id, "Отлично!")
        praise_text = "Молодец!"
        bot.send_message(CHANNEL_ID, praise_text)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        last_pill_time[call.message.message_id]["taken_time"] = datetime.now()

def run_bot():
    bot.polling(none_stop=True)

schedule.every().day.at("11:33", tz=pytz.timezone('Asia/Vladivostok')).do(send_reminder)
schedule.every(1).minutes.do(check_reminder)

if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    while True:
        schedule.run_pending()
        time.sleep(1)
