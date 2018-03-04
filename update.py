import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from constants import token, db_conn, updateMessage, messages


if __name__ == '__main__':
    bot = telebot.TeleBot(token)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text=messages['menu'], callback_data='menu'))

    with db_conn.cursor() as cur:
        sql_query = 'SELECT user_id, first_name FROM user_settings'
        cur.execute(sql_query)

        for i in cur:
            try:
                bot.send_message(chat_id=i[0], text=updateMessage.format(i[1]), parse_mode='Markdown',
                                 reply_markup=markup)
            except:
                continue
