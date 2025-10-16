import telebot
import schedule
import time
import threading
from datetime import datetime, timedelta
import pytz

# Замени на свой токен и ID канала
TOKEN = '6000570380:AAGUjahW0W9iahEKW1o7d_bo4poeswofeAc'  # Токен от BotFather
CHANNEL_ID = -1003095096004  # ID канала (получи от @myidbot)

bot = telebot.TeleBot(TOKEN)

# Словарь для хранения времени последнего нажатия и времени отправки
last_pill_time = {}

# Список уникальных напоминаний для каждого дня
reminders = [
    "Жопа, выпей таблетку.",
    "Жопа, время таблеток.",
    "Наглая, выпей, пожалуйста, таблеточку.",
    "Сказочница, таблеточка зовёт!",
    "Жопа, не забудь выпить.",
    "Наглая, твоя таблеточка ждёт.",
    "Софа, выпей таблеточку."
]


# Функция для отправки напоминания
def send_reminder():
    day_of_week = datetime.now().weekday()
    message_text = reminders[day_of_week]
    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton("✅ Выпила", callback_data="took_pill")
    keyboard.add(button)

    sent_message = bot.send_message(CHANNEL_ID, message_text, reply_markup=keyboard)
    last_pill_time[sent_message.message_id] = {"sent_time": datetime.now(), "taken_time": None}


# Функция проверки и отправки напоминания при просрочке
def check_reminder():
    current_time = datetime.now()
    for message_id, times in list(last_pill_time.items()):
        sent_time = times["sent_time"]
        taken_time = times["taken_time"]
        if taken_time is None and current_time > (sent_time + timedelta(minutes=5)):
            bot.send_message(CHANNEL_ID, "Наглая, ты не нажала кнопку! Выпей таблетку,а то по жопе получишь!")
            last_pill_time[message_id]["taken_time"] = current_time


# Обработчик нажатия кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "took_pill":
        bot.answer_callback_query(call.id, "Отлично!")
        praise_text = "Молодец"
        bot.send_message(CHANNEL_ID, praise_text)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      reply_markup=None)
        last_pill_time[call.message.message_id]["taken_time"] = datetime.now()


# Запуск polling в отдельном потоке
def run_bot():
    bot.polling(none_stop=True)


# Тестовый запуск сразу
schedule.every().day.at("11:30", tz=pytz.timezone('Asia/Vladivostok')).do(send_reminder)
schedule.every(1).minutes.do(check_reminder)

# Основной цикл
if __name__ == '__main__':
    threading.Thread(target=run_bot).start()
    while True:
        schedule.run_pending()
        time.sleep(1)