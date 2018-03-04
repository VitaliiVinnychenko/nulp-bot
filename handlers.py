import re
import requests
import telebot
from telebot.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup

from constants import *


bot = telebot.TeleBot(token)
institutes_list, groups_list, group_numbers = [], [], []


def delete_message(message):
    s = requests.Session()
    s.get('https://api.telegram.org/bot{0}/deletemessage?message_id={1}&chat_id={2}'
          .format(token, message.message_id, message.chat.id))


def show_menu(message):
    keyboard = InlineKeyboardMarkup()

    for item in main_menu:
        keyboard.add(InlineKeyboardButton(text=item['name'], callback_data=item['value']))

    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['mainMenu'], reply_markup=keyboard)


def show_schedule_menu(message):
    keyboard = InlineKeyboardMarkup()

    bot.send_chat_action(message.chat.id, 'typing')

    for item in schedule_menu:
        keyboard.add(InlineKeyboardButton(text=item['name'], callback_data=item['value']))

    delete_message(message)
    bot.send_message(message.chat.id, messages['schedule'], reply_markup=keyboard)


def set_institute(message, response=messages['changeInstitute']):
    global institutes_list
    keyboard = ReplyKeyboardMarkup()

    with db_conn.cursor() as cur:
        sql_query = 'SELECT name FROM institutes ORDER BY name'
        cur.execute(sql_query)

        for item in cur:
            institutes_list.append(item[0])
            keyboard.row(item[0])

        bot.send_chat_action(message.chat.id, 'typing')

        if response == messages['changeInstitute'] and message.text != messages['mainMenu']:
            bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=InlineKeyboardMarkup([])
            )

        send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
        bot.register_next_step_handler(send, set_faculty)


def set_faculty(message, response=messages['changeFaculty']):
    global institutes_list
    value = message.text.strip().upper()

    if len([item for item in institutes_list if item == value]) != 0 \
            or redis_db.get('setup-' + str(message.chat.id) + '-i') is not None:

        with db_conn.cursor() as cur:
            keyboard = ReplyKeyboardMarkup()
            sql_query = 'SELECT name FROM group_names WHERE institute_id = ' \
                        '(SELECT id FROM institutes WHERE name = \'{}\') ORDER BY name;'

            bot.send_chat_action(message.chat.id, 'typing')
            cur.execute(sql_query.format(value))
            redis_db.setex('setup-' + str(message.chat.id) + '-i', 64800, value)

            for item in cur:
                groups_list.append(item[0])
                keyboard.row(item[0])

            send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
            bot.register_next_step_handler(send, set_group_number)
    else:
        wrong_institute(message)


def set_group_number(message, response=messages['changeGroupNumber']):
    global groups_list, group_numbers

    value = message.text.strip().upper()

    if len([item for item in groups_list if item == value]) != 0 \
            and redis_db.get('setup-' + str(message.chat.id) + '-f') is None:
        redis_db.setex('setup-' + str(message.chat.id) + '-f', 64800, value)

    if len([item for item in groups_list if item == value]) != 0 \
            or redis_db.get('setup-' + str(message.chat.id) + '-f') is not None:

        keyboard = ReplyKeyboardMarkup()
        sql_query = """SELECT name FROM groups WHERE name LIKE \'{}%\'
                        AND institute_id = (SELECT id FROM institutes WHERE name = \'{}\')
                    """

        with db_conn.cursor() as cur:
            cur.execute(sql_query.format(
                redis_db.get('setup-' + str(message.chat.id) + '-f').decode('utf-8'),
                redis_db.get('setup-' + str(message.chat.id) + '-i').decode('utf-8')
            ))

            group_numbers = list(cur)

        bot.send_chat_action(message.chat.id, 'typing')

        for i in group_numbers:
            keyboard.add(re.search(r'^.*-(\d*)$', i[0]).group(1))

        send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
        bot.register_next_step_handler(send, set_subgroup_number)
    else:
        wrong_faculty(message)


def set_subgroup_number(message, response=messages['changeSubgroupNumber']):
    bot.send_chat_action(message.chat.id, 'typing')
    value = message.text.strip()
    faculty = redis_db.get('setup-' + str(message.chat.id) + '-f').decode('utf-8')

    if len([item for item in group_numbers if item[0] == faculty + '-' + value]) != 0 \
            and redis_db.get('setup-' + str(message.chat.id) + '-g') is None:
        redis_db.setex('setup-' + str(message.chat.id) + '-g', 64800, value)

    if len([item for item in group_numbers if item[0] == faculty + '-' + value]) != 0 \
            or redis_db.get('setup-' + str(message.chat.id) + '-g') is not None:

        with db_conn.cursor() as cur:
            sql_query = 'SELECT id FROM groups WHERE name = \'{}\''
            cur.execute(sql_query.format(faculty + '-' + value))
            results = list(cur)

            keyboard = ReplyKeyboardMarkup(True, True)
            keyboard.row('1', '2')
            keyboard.row(messages['bothSubgroups'])

            if len(results) != 0 and (redis_db.get('setup-' + str(message.chat.id) + '-g') is None or
                                      redis_db.get('setup-' + str(message.chat.id) + '-g-id') is None):

                redis_db.setex('setup-' + str(message.chat.id) + '-g', 64800, value)
                redis_db.setex('setup-' + str(message.chat.id) + '-g-id', 64800, results[0][0])

                send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
                bot.register_next_step_handler(send, save_changes)

            elif redis_db.get('setup-' + str(message.chat.id) + '-g') is not None and \
                    redis_db.get('setup-' + str(message.chat.id) + '-g-id') is not None:
                send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
                bot.register_next_step_handler(send, save_changes)
            else:
                wrong_group_number(message)


def save_changes(message):
    value = message.text.strip()

    def save(subgroup):
        update = False
        bot.send_chat_action(message.chat.id, 'typing')

        with db_conn.cursor() as cur:
            cur.execute('select * from user_settings where user_id = {}'.format(message.chat.id))

            if len(list(cur)) == 1:
                update = True

        if redis_db.get('setup-' + str(message.chat.id) + '-g-id') is None:
            redis_db.delete('setup-' + str(message.chat.id) + '-g')
        else:
            with db_conn.cursor() as cur:
                if update:
                    sql_query = 'UPDATE user_settings SET institute_id = (SELECT id FROM institutes ' \
                                'WHERE name = \'{1}\'),' \
                                'group_id = {2}, subgroup = {3} WHERE user_id = {0}'
                else:
                    sql_query = 'INSERT INTO user_settings(user_id, institute_id, group_id, subgroup, first_name, ' \
                                'last_name, username) VALUES ' \
                                '({}, (SELECT id FROM institutes WHERE name = \'{}\'), {}, {}, \'{}\', {}, {})'

                if message.chat.username is None:
                    username = 'NULL'
                else:
                    username = '\'' + message.chat.username + '\''

                if message.chat.last_name is None:
                    last_name = 'NULL'
                else:
                    last_name = '\'' + re.sub(r'\'', "\'\'", message.chat.last_name) + '\''

                cur.execute(sql_query.format(
                    message.chat.id,
                    redis_db.get('setup-' + str(message.chat.id) + '-i').decode('utf-8'),
                    redis_db.get('setup-' + str(message.chat.id) + '-g-id').decode('utf-8'),
                    subgroup,
                    re.sub(r'\'', "\'\'", message.chat.first_name),
                    last_name,
                    username
                ))

            db_conn.commit()
            bot.send_message(
                message.chat.id,
                messages['saveChanges'],
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='Markdown'
            )
            show_menu(message)

            redis_db.delete('setup-' + str(message.chat.id) + '-i')
            redis_db.delete('setup-' + str(message.chat.id) + '-f')
            redis_db.delete('setup-' + str(message.chat.id) + '-g')
            redis_db.delete('setup-' + str(message.chat.id) + '-g-id')

    if value == '1' or value == '2':
        save(int(value))

    elif value == messages['bothSubgroups']:
        save('NULL')
    else:
        wrong_subgroup_number(message)


def change_subgroup_number(message, response=messages['changeSubgroupNumber']):
    keyboard = ReplyKeyboardMarkup(True, True)
    keyboard.row('1', '2')
    keyboard.row(messages['bothSubgroups'])

    send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
    bot.register_next_step_handler(send, save_new_subgroup)


def wrong_new_subgroup_number(message):
    change_subgroup_number(message, messages['wrongSubgroupNumber'])


def save_new_subgroup(message):
    value = message.text.strip()

    def save(subgroup):
        bot.send_chat_action(message.chat.id, 'typing')
        with db_conn.cursor() as cur:
            sql_query = 'UPDATE user_settings SET subgroup = {} WHERE user_id = {}'

            cur.execute(sql_query.format(subgroup, message.chat.id))

        db_conn.commit()

        bot.send_message(
            message.chat.id,
            messages['successfullyUpdatedSubgroup'],
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        show_menu(message)

    if value == '1' or value == '2':
        save(int(value))

    elif value == messages['bothSubgroups']:
        save('NULL')
    else:
        wrong_new_subgroup_number(message)


def wrong_institute(message):
    set_institute(message, messages['wrongInstitute'])


def wrong_faculty(message):
    set_faculty(message, messages['wrongFaculty'])


def wrong_group_number(message):
    set_group_number(message, messages['wrongGroupNumber'])


def wrong_subgroup_number(message):
    set_subgroup_number(message, messages['wrongSubgroupNumber'])


def show_settings(message, decline=False):
    keyboard = InlineKeyboardMarkup()

    for item in settings_menu:
        keyboard.add(InlineKeyboardButton(text=item, callback_data=item))

    bot.send_chat_action(message.chat.id, 'typing')

    if not decline:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=messages['mainMenu']
        )
        bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=keyboard
        )
    else:
        bot.send_message(message.chat.id, messages['mainMenu'], reply_markup=keyboard)


def show_buildings_list(call):
    keyboard = ReplyKeyboardMarkup(True, True)
    keyboard.row(messages['back'])

    for item in buildings:
        keyboard.row(item['name'])

    bot.send_chat_action(call.message.chat.id, 'typing')
    delete_message(call.message)
    bot.send_message(
        chat_id=call.message.chat.id,
        text=messages['buildingsMenu'],
        reply_markup=keyboard,
    )


def toggle_notifications(message):
    keyboard = ReplyKeyboardMarkup(True, True)

    keyboard.row(*notification_buttons)

    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, messages['toggleNotifications'], reply_markup=keyboard)
