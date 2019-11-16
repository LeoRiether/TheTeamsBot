from google.cloud import firestore
import google.cloud.exceptions
from functools import reduce
from os import environ as env

db = firestore.Client()

bot_name = 'theteamsbot'

def pipe(*fns):
    return lambda x: reduce(lambda acc, f: f(acc), fns, x)

def filtering(pred):
    return lambda arr: filter(pred, arr)

def mapping(fn):
    return lambda arr: map(fn, arr)

def reducing(fn, initial=None):
    return lambda arr: reduce(fn, arr, initial)

def erase_at_symbol(s):
    if s.startswith('@'):
        return s[1:]
    return s

is_mention = lambda s: s.startswith('@')
split_whitespace = lambda s: s.split()

get_mentions = pipe(
    split_whitespace,
    filtering(is_mention),
    mapping(erase_at_symbol),
    list
)

def create_team(chat_id, name, people):
    db.collection(f'teams::{chat_id}').add({
        'name': name,
        'people': people
    })

def teams_on_chat(chat_id):
    return db.collection(f'teams::{chat_id}').stream()

def send_message(chat_id, text):
    import requests
    requests.post(f'https://api.telegram.org/bot{env["TOKEN"]}/sendMessage', data={
        'chat_id': chat_id,
        'text': text
    })
    return "ok" # not even sure if it's really ok

def command(chat_id, text):
    args = split_whitespace(text)

    # Remove @theteamsbot from the command
    if args[0].endswith('@' + bot_name):
        args[0] = args[0][: -(len(bot_name) + 1)]

    if args[0] == '/addteam':
        if len(args) < 3:
            return send_message(chat_id, "/addteam usage: /addteam teamName @mention1 @mention2 ...")

        names = list(map(erase_at_symbol, args[1:]))
        create_team(chat_id, names[0], names[1:])
        send_message(chat_id, f"Team {names[0]} was added!")
        return "ok"
    
    return "not ok"

def api_post(req):
    """
    api_post receives a POST request from the Telegram webhook
    and responds accordingly
    """

    data = req.get_json()

    message = data['message']
    is_bot = message['from']['is_bot']
    text = message['text']
    chat_id = message['chat']['id']

    if is_bot:
        return "bot messages not allowed to prevent recursion"

    # We got a command
    if text.startswith('/'):
        return command(chat_id, text)
    
    # Text received might have a mention
    mentions = get_mentions(text)
    if len(mentions) == 0:
        return "ok"

    # <imperative>
    people = []
    for team in teams_on_chat(chat_id):
        t = team.to_dict()
        if t['name'] in mentions:
            people += t['people']
    # </imperative>

    if len(people) == 0:
        return "ok"

    res = str.join(' ', [ '@' + name for name in people ])
    send_message(chat_id, res)
    return "ok"

