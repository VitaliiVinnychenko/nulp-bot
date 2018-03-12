import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from constants import token, db_conn, updateMessage, messages


if __name__ == '__main__':
    bot = telebot.TeleBot(token)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text=messages['menu'], callback_data='menu'))
    counter = 0

    with db_conn.cursor() as cur:
        sql_query = 'SELECT user_id, first_name FROM user_settings WHERE created_at >= \'2018-03-11 21:02:00\';'
        cur.execute(sql_query)

        for i in cur:
            try:
                bot.send_message(chat_id=i[0], text=updateMessage.format(i[1]), parse_mode='Markdown',
                                 reply_markup=markup)

                print(i)
            except:
                print(i, 'PASS')
                counter += 1
                continue

        print(counter)
