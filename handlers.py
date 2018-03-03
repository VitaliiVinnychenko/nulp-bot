import requests, telebot
from telebot.types import *
from constants import *


bot = telebot.TeleBot(token)
institutes_list, groups_list = [], []
new_settings = {}


def delete_message(message):
    s = requests.Session()
    s.get('https://api.telegram.org/bot{0}/deletemessage?message_id={1}&chat_id={2}'
          .format(token, message.message_id, message.chat.id))


def show_menu(message):
    global new_settings
    keyboard = InlineKeyboardMarkup()
    new_settings[str(message.chat.id)] = initial_settings

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
    global institutes_list, new_settings
    keyboard = ReplyKeyboardMarkup()

    new_settings[str(message.chat.id)] = initial_settings

    with db_conn.cursor() as cur:
        sql_query = 'SELECT name FROM institutes ORDER BY name'
        cur.execute(sql_query)

        for item in cur:
            institutes_list.append(item[0])
            keyboard.row(item[0])

        bot.send_chat_action(message.chat.id, 'typing')
        send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
        bot.register_next_step_handler(send, set_faculty)


def set_faculty(message, response=messages['changeFaculty']):
    global institutes_list, new_settings
    value = message.text.strip().upper()

    if len([item for item in institutes_list if item == value]) != 0 \
            or new_settings[str(message.chat.id)]['institute'] is not None:

        with db_conn.cursor() as cur:
            keyboard = ReplyKeyboardMarkup()
            sql_query = 'SELECT name FROM group_names WHERE institute_id = ' \
                        '(SELECT id FROM institutes WHERE name = \'{}\') ORDER BY name;'

            bot.send_chat_action(message.chat.id, 'typing')
            cur.execute(sql_query.format(value))
            new_settings[str(message.chat.id)]['institute'] = value
            new_settings[str(message.chat.id)]['faculty'] = None

            for item in cur:
                groups_list.append(item[0])
                keyboard.row(item[0])

            send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
            bot.register_next_step_handler(send, set_group_number)
    else:
        wrong_institute(message)


def set_group_number(message, response=messages['changeGroupNumber']):
    global groups_list, new_settings
    value = message.text.strip().upper()

    if len([item for item in groups_list if item == value]) != 0 \
            and new_settings[str(message.chat.id)]['faculty'] is None:
        new_settings[str(message.chat.id)]['faculty'] = value

    if len([item for item in groups_list if item == value]) != 0 \
            or new_settings[str(message.chat.id)]['faculty'] is not None:

        bot.send_chat_action(message.chat.id, 'typing')
        new_settings[str(message.chat.id)]['group'] = new_settings[str(message.chat.id)]['groupID'] = None
        send = bot.send_message(message.chat.id, response, reply_markup=ReplyKeyboardHide())
        bot.register_next_step_handler(send, set_subgroup_number)
    else:
        wrong_faculty(message)


def set_subgroup_number(message, response=messages['changeSubgroupNumber']):
    global new_settings

    bot.send_chat_action(message.chat.id, 'typing')
    value = message.text.strip()

    if new_settings[str(message.chat.id)]['faculty'] is None:
        set_faculty(message, messages['wrongFaculty'])

    with db_conn.cursor() as cur:
        sql_query = 'SELECT id FROM groups WHERE name = \'{}\''
        cur.execute(sql_query.format(new_settings[str(message.chat.id)]['faculty'] + '-' + value))
        results = list(cur)

        keyboard = ReplyKeyboardMarkup(True, True)
        keyboard.row('1', '2')
        keyboard.row(messages['bothSubgroups'])

        if len(results) != 0 and new_settings[str(message.chat.id)]['group'] is None:
            new_settings[str(message.chat.id)]['group'] = value
            new_settings[str(message.chat.id)]['groupID'] = results[0][0]
            send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
            bot.register_next_step_handler(send, save_changes)
        elif new_settings[str(message.chat.id)]['group'] is not None:
            send = bot.send_message(message.chat.id, response, reply_markup=keyboard)
            bot.register_next_step_handler(send, save_changes)
        else:
            wrong_group_number(message)


def save_changes(message):
    global new_settings
    value = message.text.strip()

    def save(subgroup):
        global new_settings
        update = False
        bot.send_chat_action(message.chat.id, 'typing')

        with db_conn.cursor() as cur:
            cur.execute('select * from user_settings where user_id = {}'.format(message.chat.id))

            if len(list(cur)) == 1:
                update = True

        with db_conn.cursor() as cur:
            if update:
                sql_query = 'UPDATE user_settings SET institute_id = (SELECT id FROM institutes WHERE name = \'{1}\'),'\
                            'group_id = {2}, subgroup = {3} WHERE user_id = {0}'
            else:
                sql_query = 'INSERT INTO user_settings(user_id, institute_id, group_id, subgroup, first_name, ' \
                            'last_name, username) VALUES ' \
                            '({}, (SELECT id FROM institutes WHERE name = \'{}\'), {}, {}, \'{}\', \'{}\', {})'

            if message.chat.username is None:
                username = 'NULL'
            else:
                username = '\'' + message.chat.username + '\''

            cur.execute(sql_query.format(
                message.chat.id,
                new_settings[str(message.chat.id)]['institute'],
                new_settings[str(message.chat.id)]['groupID'],
                subgroup,
                message.chat.first_name,
                message.chat.last_name,
                username
            ))

        db_conn.commit()
        bot.send_message(
            message.chat.id,
            messages['saveChanges'],
            reply_markup=ReplyKeyboardHide(),
            parse_mode='Markdown'
        )
        show_menu(message)

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
            reply_markup=ReplyKeyboardHide(),
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
