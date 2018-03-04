import datetime
import json
import logging
import collections
import atexit
from constants import *
from handlers import *
from html_parser import get_schedule
from job import JobQueue, Days


logger = telebot.logger
telebot.logger.setLevel(logging.DEBUG)
jq = JobQueue(bot=bot)


def get_format_data(key, value, i):
    return emoji_digits[key], value[i]['name'], value[i]['lecturer'], value[i]['room'], time_schedule[key]


def show_week_schedule(message, week='thisWeek', d=0):
    bot.send_chat_action(message.chat.id, 'typing')

    with db_conn.cursor() as cur:
        sql_query = 'SELECT institute_id, group_id, subgroup FROM user_settings WHERE user_id = {}'
        cur.execute(sql_query.format(message.chat.id))
        response = list(cur)

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text=messages['menu'], callback_data='menu'))

        if len(response) == 0:
            bot.send_message(message.chat.id, messages['noUser'], reply_markup=keyboard, parse_mode='Markdown')
        else:
            response = response[0]
            data = redis_db.get(str(response[0]) + '-' + str(response[1]))

            if data is None:
                data = get_schedule(response[0], response[1])
            else:
                data = json.loads(data.decode('utf-8'))['schedule']

            start_date, end_date = week_range(datetime.datetime.today() + datetime.timedelta(days=d))
            response_message = messages[week + 'Schedule'].format(
                (start_date + datetime.timedelta(days=1)).strftime("%d.%m") + ' - '
                + (end_date + datetime.timedelta(days=1)).strftime("%d.%m")
            )

            index = 0
            for i in data:
                i = collections.OrderedDict(sorted(i.items()))

                response_message += '\n\n\n' + days[index].upper() + ' ' + \
                                    (start_date + datetime.timedelta(days=index + 1)).strftime("(%d.%m)")
                response_message += generate_schedule_message(i, response[2], week)
                index += 1

            delete_message(message)
            bot.send_message(
                chat_id=message.chat.id,
                text=response_message,
                reply_markup=keyboard
            )


def week_range(date):
    year, week, dow = date.isocalendar()

    if dow == 7:
        start_date = date
    else:
        start_date = date - datetime.timedelta(dow)

    end_date = start_date + datetime.timedelta(6)

    return start_date, end_date


def render_subgroup(subgroup, key, value):
    response = ''

    if subgroup is None:
        for i in [0, 1]:
            if value[i] is not None:
                format_data = get_format_data(int(key) - 1, value, i)
                response += subgroup_undefined_schedule_template.format(*format_data, emoji_digits[i])
    else:
        if value[subgroup - 1] is not None:
            format_data = get_format_data(int(key) - 1, value, subgroup - 1)
            response += subgroup_defined_schedule_template.format(*format_data)

    return response


def generate_schedule_message(data, subgroup, week='thisWeek'):
    response = ''

    for key, value in data.items():
        if type(value) is list:
            response += render_subgroup(subgroup, key, value)
        elif type(value) is dict and week in value:
            value = value[week]

            if type(value) is list:
                response += render_subgroup(subgroup, key, value)
            elif value is not None:
                response += subgroup_defined_schedule_template.format(
                    emoji_digits[int(key) - 1],
                    value['name'],
                    value['lecturer'],
                    value['room'],
                    time_schedule[int(key) - 1]
                )
        else:
            response += subgroup_defined_schedule_template.format(
                emoji_digits[int(key) - 1],
                value['name'],
                value['lecturer'],
                value['room'],
                time_schedule[int(key) - 1]
            )

    return response


@bot.message_handler(commands=['today'])
def show_today_schedule(message):
    bot.send_chat_action(message.chat.id, 'typing')

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text=messages['menu'], callback_data='menu'))

    with db_conn.cursor() as cur:
        sql_query = 'SELECT institute_id, group_id, subgroup FROM user_settings WHERE user_id = {}'
        cur.execute(sql_query.format(message.chat.id))
        response = list(cur)

    if len(response) == 0:
        bot.send_message(message.chat.id, messages['noUser'], reply_markup=keyboard, parse_mode='Markdown')
    else:
        response = response[0]
        weekday = datetime.datetime.today().weekday()

        keyboard = InlineKeyboardMarkup()

        for item in main_menu:
            keyboard.add(InlineKeyboardButton(text=item['name'], callback_data=item['value']))

        if weekday == 5 or weekday == 6:
            delete_message(message)
            bot.send_message(
                chat_id=message.chat.id,
                text=messages['todayIsWeekend'],
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            data = redis_db.get(str(response[0]) + '-' + str(response[1]))

            if data is None:
                data = get_schedule(response[0], response[1])[weekday]
            else:
                data = json.loads(data.decode('utf-8'))['schedule'][weekday]

            data = collections.OrderedDict(sorted(data.items()))

            response_message = messages['todaySchedule'].format(datetime.datetime.today().strftime("%d.%m"))
            response_message += generate_schedule_message(data, response[2])

            delete_message(message)
            bot.send_message(
                chat_id=message.chat.id,
                text=response_message,
                reply_markup=keyboard
            )


@bot.message_handler(commands=['tomorrow'])
def show_tomorrow_schedule(message, local_bot=bot):
    if type(message) == int:
        user_id = message
    else:
        user_id = message.chat.id

    local_bot.send_chat_action(user_id, 'typing')

    with db_conn.cursor() as cur:
        sql_query = 'SELECT institute_id, group_id, subgroup FROM user_settings WHERE user_id = {}'
        cur.execute(sql_query.format(user_id))
        response = list(cur)

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text=messages['menu'], callback_data='menu'))

        if len(response) == 0:
            local_bot.send_message(user_id, messages['noUser'], reply_markup=keyboard, parse_mode='Markdown')
        else:
            response = response[0]
            weekday = (datetime.datetime.today() + datetime.timedelta(days=1)).weekday()

            keyboard = InlineKeyboardMarkup()

            for item in main_menu:
                keyboard.add(InlineKeyboardButton(text=item['name'], callback_data=item['value']))

            if weekday == 5 or weekday == 6:
                if type(message) != int:
                    delete_message(message)

                local_bot.send_message(
                    chat_id=user_id,
                    text=messages['tomorrowIsWeekend'],
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                data = redis_db.get(str(response[0]) + '-' + str(response[1]))

                if data is None:
                    data = get_schedule(response[0], response[1])[weekday]
                else:
                    data = json.loads(data.decode('utf-8'))['schedule'][weekday]

                data = collections.OrderedDict(sorted(data.items()))

                response_message = messages['tomorrowSchedule'].format(
                    (datetime.datetime.today() + datetime.timedelta(days=1)).strftime("%d.%m")
                )
                response_message += generate_schedule_message(data, response[2])

                if type(message) != int:
                    delete_message(message)

                local_bot.send_message(
                    chat_id=user_id,
                    text=response_message,
                    reply_markup=keyboard
                )


@bot.message_handler(commands=['week'])
def show_this_week_schedule(message):
    show_week_schedule(message)


@bot.message_handler(commands=['nextweek'])
def show_next_week_schedule(message):
    show_week_schedule(message, 'nextWeek', 7)


@bot.message_handler(commands=['settings'])
def handle_settings(message):
    keyboard = InlineKeyboardMarkup()

    for item in settings_menu:
        keyboard.add(InlineKeyboardButton(text=item, callback_data=item))

    bot.send_chat_action(message.chat.id, 'typing')

    bot.send_message(
        chat_id=message.chat.id,
        text=messages['mainMenu'],
        reply_markup=keyboard
    )


@bot.message_handler(commands=['start'])
def handle_menu_command(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text=messages['go'], callback_data=messages['go']))

    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(
        message.chat.id,
        messages['greeting'].format(message.from_user.first_name),
        parse_mode='Markdown',
        reply_markup=keyboard
    )


@bot.message_handler(commands=['menu'])
def handle_menu_command(message):
    show_menu(message)


@bot.message_handler(content_types=['text'])
def handle_text_content(message):
    building = [item for item in buildings if item['name'].lower() == message.text.lower().strip()]

    if message.text == notification_buttons[0]:
        bot.send_chat_action(message.chat.id, 'typing')

        keyboard = ReplyKeyboardRemove()

        with db_conn.cursor() as cur:
            sql_query = 'UPDATE user_settings SET send_schedule = TRUE WHERE user_id = {};'
            cur.execute(sql_query.format(message.chat.id))

        db_conn.commit()
        bot.send_message(message.chat.id, messages['saveNotifications'], reply_markup=keyboard, parse_mode='Markdown')

    elif message.text == notification_buttons[1]:
        bot.send_chat_action(message.chat.id, 'typing')

        keyboard = ReplyKeyboardRemove()

        with db_conn.cursor() as cur:
            sql_query = 'UPDATE user_settings SET send_schedule = FALSE WHERE user_id = {};'
            cur.execute(sql_query.format(message.chat.id))

        db_conn.commit()
        bot.send_message(message.chat.id, messages['saveNotifications'], reply_markup=keyboard, parse_mode='Markdown')

    elif message.text == messages['back']:
        keyboard = InlineKeyboardMarkup()

        for item in main_menu:
            keyboard.add(InlineKeyboardButton(text=item['name'], callback_data=item['value']))

        bot.send_chat_action(message.chat.id, 'typing')
        bot.send_message(message.chat.id, messages['mainMenu'], reply_markup=keyboard)

    elif len(building) > 0 and building[0]['lat'] is not None:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text=messages['menu'], callback_data='menu'))

        bot.send_chat_action(message.chat.id, 'typing')
        bot.send_message(
            message.chat.id,
            message.text + ' знаходиться за адресою:\n*' + building[0]['address'] + '*',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )

        bot.send_chat_action(message.chat.id, 'find_location')
        bot.send_location(
            chat_id=message.chat.id,
            latitude=building[0]['lat'],
            longitude=building[0]['lng'],
            reply_markup=keyboard
        )
    else:
        bot.send_chat_action(message.chat.id, 'typing')
        bot.send_message(
            message.chat.id,
            text='Шо ти з мене хочеш??? ',
            reply_markup=ReplyKeyboardRemove()
        )


@bot.message_handler(content_types=['photo'])
def handle_text_content(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['photoAnswer'], reply_markup=ReplyKeyboardRemove())


@bot.message_handler(content_types=['video', 'video_note'])
def handle_text_content(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['videoAnswer'], reply_markup=ReplyKeyboardRemove())


@bot.message_handler(content_types=['contact'])
def handle_text_content(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['contactAnswer'], reply_markup=ReplyKeyboardRemove())


@bot.message_handler(content_types=['location'])
def handle_text_content(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['locationAnswer'], reply_markup=ReplyKeyboardRemove())


@bot.message_handler(content_types=['audio', 'document', 'voice'])
def handle_text_content(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['otherAnswer'], reply_markup=ReplyKeyboardRemove())


@bot.message_handler(content_types=['sticker'])
def handle_text_content(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['stickerAnswer'], reply_markup=ReplyKeyboardRemove())


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        if call.data == 'buildings':
            show_buildings_list(call)

        elif call.data == 'today':
            show_today_schedule(call.message)

        elif call.data == 'tomorrow':
            show_tomorrow_schedule(call.message)

        elif call.data == 'week':
            show_this_week_schedule(call.message)

        elif call.data == 'nextweek':
            show_next_week_schedule(call.message)

        elif call.data == 'schedule':
            show_schedule_menu(call.message)

        elif call.data == 'settings':
            show_settings(call.message)

        elif call.data == settings_menu[1]:
            delete_message(call.message)
            set_institute(call.message)

        elif call.data == settings_menu[2]:
            delete_message(call.message)
            change_subgroup_number(call.message)

        elif call.data == settings_menu[3]:
            delete_message(call.message)
            toggle_notifications(call.message)

        elif call.data == messages['back'] or call.data == 'back':
            delete_message(call.message)
            show_menu(call.message)

        elif call.data == messages['go']:
            set_institute(call.message)

        elif call.data == 'menu':
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=InlineKeyboardMarkup([]))
            show_menu(call.message)

    elif call.inline_message_id:
        if call.data == 'buildings':
            show_buildings_list(call)

        elif call.data == 'today':
            show_today_schedule(call.message)

        elif call.data == 'tomorrow':
            show_tomorrow_schedule(call.message)

        elif call.data == 'week':
            show_this_week_schedule(call.message)

        elif call.data == 'nextweek':
            show_next_week_schedule(call.message)

        elif call.data == 'schedule':
            show_schedule_menu(call.message)

        elif call.data == 'settings':
            show_settings(call.message)

        elif call.data == settings_menu[1]:
            delete_message(call.message)
            set_institute(call.message)

        elif call.data == settings_menu[2]:
            delete_message(call.message)
            change_subgroup_number(call.message)

        elif call.data == settings_menu[3]:
            delete_message(call.message)
            toggle_notifications(call.message)

        elif call.data == messages['back'] or call.data == 'back':
            delete_message(call.message)
            show_menu(call.message)

        elif call.data == messages['go']:
            set_institute(call.message)

        elif call.data == 'menu':
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=InlineKeyboardMarkup([]))
            show_menu(call.message)


def send_schedule(local_bot):
    weekday = (datetime.datetime.today() + datetime.timedelta(days=1)).weekday()

    if weekday != 5 and weekday != 6:
        with db_conn.cursor() as cur:
            sql_query = 'SELECT user_id FROM user_settings WHERE send_schedule = TRUE;'
            cur.execute(sql_query)

            for i in cur:
                show_tomorrow_schedule(i[0], local_bot)


def exit_handler():
    jq.stop()


if __name__ == "__main__":
    atexit.register(exit_handler)

    jq.run_daily(
        callback=send_schedule,
        days=(Days.MON, Days.TUE, Days.WED, Days.THU, Days.SUN),
        time=datetime.time(16, 30, 00)
    )

    jq.start()

    bot.polling(none_stop=True)
