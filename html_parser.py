import json
import re
import requests
from bs4 import BeautifulSoup, element

from constants import base_url, redis_db, db_conn


def schedule_url(institute_id, group_id):
    return base_url + '?inst={}&group={}'.format(institute_id, group_id)


def get_text(item):
    return str(re.sub(r'<.*?>', '', str(item)))


def get_subject_object(name, lecturer, room):
    return {
        'name': name,
        'lecturer': lecturer,
        'room': room
    }


def get_institutes_list():
    response = requests.get(base_url)
    soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), 'html.parser')

    institutes_list = soup.find('select', {'name': 'inst'}).find_all('option')[1:]

    return [{'name': x.string, 'id': x['value']} for x in institutes_list]


def get_groups_list(institute_id):
    response = requests.get(schedule_url(institute_id, ''))
    soup = BeautifulSoup(response.content, 'html.parser')
    groups_list = soup.find('select', {'name': 'group'}).find_all('option')[1:]

    return [{'name': x.string, 'id': x['value'], 'inst': institute_id} for x in groups_list]


def get_data_from_html(root):
    if len(root) == 1:
        return get_subject_object(
            root[0].select('b')[0].string,
            root[0].select('i')[0].string,
            re.search(r'<br\/>(.*)\n<\/div>', str(root[0])).group(1)
        )

    return None


def one_more_parser(root):
    children = root.findAll('td')

    if len(children) == 1:
        result = get_data_from_html(children[0].select('.vidst'))
    else:
        result = [get_data_from_html(x.select('.vidst')) for x in children]

        if result[1:] == result[:-1]:
            result = None

    return result


def get_object(item):
    global thisWeek, nextWeek

    if len(item) == 1:
        subgroups = item[0].select('td')

        if len(subgroups) == 1:
            return get_data_from_html(item[0].select('.vidst'))
        else:
            return [get_data_from_html(i.select('.vidst')) for i in subgroups]
    elif type(item[0]) is element.Tag:
        for x in item:
            if x.has_attr('class'):
                thisWeek = one_more_parser(x)
            else:
                nextWeek = one_more_parser(x)

        return {
            'thisWeek': thisWeek,
            'nextWeek': nextWeek
        }


def get_schedule(institute_id, group_id):
    response = requests.get(schedule_url(institute_id, group_id))
    soup = BeautifulSoup(response.content, 'html.parser')

    schedule_items = soup.select('#stud > table.outer > tr')[1:]
    res = soup.select('#stud')[0].find_all('td', {'rowspan': re.compile(r".*"), 'class': 'leftcell'})

    day = -1
    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт']
    schedule = []

    if len(res) == 5:
        for i in range(5):
            schedule.append({})
    else:
        i = 0; j = 0

        while j != 5:
            if i == j and len(res) == i + 1:
                schedule += [{}] + [None] * (5 - i - 1)
                break
            elif weekdays[j] == res[i].text:
                schedule.append({})
                i += 1
                j += 1
            else:
                schedule.append(None)
                j += 1

    for item in schedule_items:

        if len(item.select('td')) > 1:
            root = item.select('td.maincell')[0]

            if item.has_attr('style'):
                day += 1

            line_number = root.find_previous_sibling('td').text

            if schedule[day] is not None:
                schedule[day][get_text(line_number)] = get_object(root.select('table tr'))
            else:
                day += 1

    return schedule
