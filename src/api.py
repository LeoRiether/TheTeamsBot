from google.cloud import firestore
import google.cloud.exceptions
from functools import reduce
from os import environ as env

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
    db = firestore.Client()
    db.collection(f'teams::{chat_id}').add({
        'name': name,
        'people': people
    })

def delete_team(chat_id, name):
    db = firestore.Client()
    for team in db.collection(f'teams::{chat_id}').where(u'name', u'==', name).stream():
        team.reference.delete()

def teams_on_chat(chat_id):
    db = firestore.Client()
    return db.collection(f'teams::{chat_id}').stream()

def send_message(chat_id, text):
    from requests import post
    post(f'https://api.telegram.org/bot{env["TOKEN"]}/sendMessage', data={
        'chat_id': chat_id,
        'text': text
    })
    return "ok" # not even sure if it's really ok

def command(chat_id, text):
    """
    Handles a command (string prefixed by '/')
    lots of side-effects: calls send_message, create_team and delete_team
    """
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
    
    if args[0] == '/rmteam':
        if len(args) < 2:
            return send_message(chat_id, "/rmteam usage: /rmteam @team_name or /rmteam team_name")
        
        team_name = erase_at_symbol(args[1])
        delete_team(chat_id, team_name)
        send_message(chat_id, f"Goodbye, {team_name}")
        return "ok"
    
    return "not ok"

def api_post(req):
    """
    api_post receives a POST request from the Telegram webhook
    and responds accordingly
    """

    data = req.get_json()

    if not 'message' in data:
        return "wtf"
    message = data['message']
    if not 'text' in message:
        return "not ok"
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

