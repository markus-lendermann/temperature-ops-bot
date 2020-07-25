from api_wrapper import TelegramApiWrapper
from flask import Flask, request
import json
import logging
import lib.requests as requests
import re
from datetime import datetime, timedelta
from google.cloud import ndb
from multiprocessing.pool import ThreadPool
from time import time as timer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s :: (%(name)s) > %(message)s'
)


# load private API tokens from file
def loadTokens():
    with open("tokens.json") as tf:
        tokens = json.load(tf)

    return tokens


# load strings from file
def loadStrings():
    with open("strings.json") as tf:
        strings = json.load(tf)

    return strings


class WebsiteStatus(ndb.Model):
    status = ndb.BooleanProperty(default=True)
    url = ndb.StringProperty(default="https://temptaking.ado.sg")  # for debugging purposes
    skippedReminder = ndb.BooleanProperty(default=False)


class Client(ndb.Model):
    firstName = ndb.StringProperty()
    status = ndb.StringProperty(default='0')
    groupId = ndb.StringProperty()
    groupName = ndb.StringProperty()
    groupMembers = ndb.TextProperty()
    memberName = ndb.StringProperty()
    memberId = ndb.StringProperty()
    pin = ndb.StringProperty()
    temp = ndb.StringProperty()
    remindAM = ndb.IntegerProperty(default=-1)
    remindPM = ndb.IntegerProperty(default=-1)
    blocked = ndb.BooleanProperty(default=False)

    def reset(self):
        self.status = '1'
        self.temp = 'init'
        self.remindAM = -1
        self.remindPM = -1


app = Flask(__name__)
logger = logging.getLogger(__name__)

tokens = loadTokens()
strings = loadStrings()
telegramApi = TelegramApiWrapper(tokens["telegram-bot"])
valid_command_states = ['endgame 1', 'endgame 2', 'remind wizard 1', 'remind wizard 2', 'offline,endgame 1',
                        'offline,endgame 2', 'offline,remind wizard 1', 'offline,remind wizard 2']
THREAD_NUMBER = 20  # number of threads to create in /remind and /broadcast thread pools

#  this context will be used for the entire app instance
ndb_client = ndb.Client()

#  check website status when initializing
with ndb_client.context():
    wstatus = WebsiteStatus.get_or_insert('status')


def getRouteUrl(url):
    return '/{}/{}'.format(tokens["telegram-bot"], url)


def generateTemperatures():
    return [[str(x / 10), str((x + 1) / 10)] for x in range(350, 375, 2)]


def generateHours(hour):
    if hour < 12:
        return [[f'{2 * x:02}:01', f'{2 * x + 1:02}:01'] for x in range(6)]
    else:
        return [[f'{2 * x:02}:01', f'{2 * x + 1:02}:01'] for x in range(6, 12)]


def emojiTime(now):
    hour = now.hour
    minute = now.minute
    clocks = strings["clocks"]

    return clocks[round(2 * (hour + minute / 60) % 24)]


def strftime(datetimeobject, formatstring):
    formatstring = formatstring.replace("%%", "percent_placeholder")
    ps = list(set(re.findall("(%.)", formatstring)))
    format2 = "|".join(ps)
    vs = datetimeobject.strftime(format2).split("|")
    for p, v in zip(ps, vs):
        formatstring = formatstring.replace(p, v)
    return formatstring.replace("percent_placeholder", "%")


def submitTemp(client, temp):
    now = datetime.now() + timedelta(hours=8)
    if now.hour < 12:
        meridies = 'AM'
    else:
        meridies = 'PM'
    try:
        url = '{}/group/MemberSubmitTemperature'.format(wstatus.url)
        payload = {
            'groupCode': client.groupId,
            'date': strftime(now, '%d/%m/%Y'),
            'meridies': meridies,
            'memberId': client.memberId,
            'temperature': temp,
            'pin': client.pin
        }
        r = requests.post(url, data=payload)
        logging.info('submit temp response: {}'.format(r.text))
    except Exception as e:
        # TODO: proper exception handling has to be done tbh
        logging.error(e)
        return 'error'
    return r.text


@app.route(getRouteUrl("me"))
def getMe():
    resp = telegramApi.getMe()
    return resp["result"]


@app.route(getRouteUrl("setWebhook"))
def getWebhook():
    url = tokens["project-url"] + "{}/webhook".format(tokens["telegram-bot"])
    resp = telegramApi.setWebhook(url)
    if resp["ok"]:
        return "webhook has been set to " + url
    else:
        return "webhook failed to set. DEBUG: " + str(resp)


# for debugging purposes
@app.route(getRouteUrl("flipSwitch"))
def flipSwitch():
    with ndb_client.context():
        wstatus = WebsiteStatus.get_or_insert('status')
        if wstatus.url == "https://temptaking.ado.sg":
            wstatus.url = "https://temptaking.ado.sgs"  # force website to appear offline
        else:
            wstatus.url = "https://temptaking.ado.sg"
        wstatus.put()
        return wstatus.url


@app.route(getRouteUrl("websiteStatus"))
def websiteStatus(context=None):
    def websiteStatus():
        wstatus = WebsiteStatus.get_or_insert('status')
        try:
            requests.get(wstatus.url)
            if not wstatus.status:
                def fetch_remind_response(client):
                    with ndb_client.context():
                        try:
                            resp = "not sent"
                            key_id = client.id()
                            client = client.get()
                            if client.status.startswith("offline"):
                                client.status = client.status.split(",")[1]
                                payload = {
                                    'chat_id': str(key_id),
                                    'text': strings["status_online"],
                                    'parse_mode': 'HTML'
                                }
                                resp = telegramApi.sendMessage(payload)
                                client.put()
                            return client, str(key_id), resp, None
                        except Exception as e:
                            return client, str(client.id()), None, e

                # update wstatus
                wstatus.status = True
                wstatus.put()

                all_clients = Client.query().fetch(keys_only=True)
                start = timer()
                remind_results = ThreadPool(THREAD_NUMBER).imap_unordered(fetch_remind_response, all_clients)
                i = 0
                p = 0
                f = 0
                b = 0

                for client, key_id, resp, e in remind_results:
                    if e is None:
                        if resp != "not sent":
                            i += 1
                            if resp["ok"]:
                                logging.info('websiteStatus response for {}: {}'.format(key_id, resp["result"]))
                                p += 1
                            else:
                                logging.info('websiteStatus response for {}: {}'.format(key_id, resp["description"]))
                                if resp["error_code"] == 403:
                                    b += 1
                                else:
                                    f += 1
                    else:
                        logging.error(e)
                        f += 1

                if wstatus.skippedReminder:
                    remind(True)
                    wstatus.skippedReminder = False  # only update this after calling remind()
                wstatus.put()

                logging.info(
                    'online notification sent to {} clients. '
                    'successes: {} blocked: {} failures: {} elapsed time: {} rate: {}'.format(
                        str(i), str(p), str(b), str(f), str(timer() - start), str(i/(timer() - start))))
                return 'online notification sent to {} clients. ' \
                       'successes: {} blocked: {} failures: {} elapsed time: {} rate: {}'.format(
                    str(i), str(p), str(b), str(f), str(timer() - start), str(i/(timer() - start)))
        except Exception as e:
            logging.error(e)
            if wstatus.status:
                wstatus.status = False
                wstatus.put()
            return "offline"
        else:
            return "online"

    if context:
        resp = websiteStatus()
    else:
        with ndb_client.context():
            resp = websiteStatus()
    return resp


@app.route(getRouteUrl("remind"))
def remind(context=None):
    def remind():
        wstatus = WebsiteStatus.get_or_insert('status')
        if wstatus.status:
            def fetch_remind_response(client):
                with ndb_client.context():
                    try:
                        resp = "not sent"
                        key_id = client.id()
                        client = client.get()
                        now = datetime.now() + timedelta(hours=8)
                        if now.hour == 0 or now.hour == 12:
                            if client.status in valid_command_states:
                                if client.temp != 'error':
                                    client.temp = 'none'
                                    client.status = 'endgame 2'
                        if client.temp == 'none':
                            if (12 > now.hour >= client.remindAM) or (now.hour >= 12 and now.hour >= client.remindPM):
                                temperatures = generateTemperatures()
                                if now.hour < 12:
                                    if wstatus.skippedReminder:
                                        text = strings["remind_delayed"] + strftime(now, strings["window_open_AM"])
                                    else:
                                        text = strftime(now, strings["window_open_AM"])
                                else:
                                    if wstatus.skippedReminder:
                                        text = strings["remind_delayed"] + strftime(now, strings["window_open_PM"])
                                    else:
                                        text = strftime(now, strings["window_open_PM"])
                                payload = {
                                    'chat_id': str(key_id),
                                    'text': text,
                                    "parse_mode": "HTML",
                                    'reply_markup': {
                                        "keyboard": temperatures,
                                        "one_time_keyboard": True
                                    }
                                }
                                resp = telegramApi.sendMessage(payload)
                                if not resp['ok']:
                                    if resp['description'] == 'Forbidden: bot was blocked by the user':
                                        client.blocked = True
                                client.status = 'endgame 2'
                        client.put()
                        return client, str(key_id), resp, None
                    except Exception as e:
                        return client, str(client.id()), None, e

            all_clients = Client.query().fetch(keys_only=True)
            start = timer()
            remind_results = ThreadPool(THREAD_NUMBER).imap_unordered(fetch_remind_response, all_clients)
            i = 0
            p = 0
            f = 0
            b = 0

            for client, key_id, resp, e in remind_results:
                if e is None:
                    if resp != "not sent":
                        i += 1
                        if resp["ok"]:
                            logging.info('remind response for {}: {}'.format(key_id, resp["result"]))
                            p += 1
                        else:
                            logging.info('remind response for {}: {}'.format(key_id, resp["description"]))
                            if resp["error_code"] == 403:
                                b += 1
                            else:
                                f += 1
                else:
                    logging.error(e)
                    f += 1

            logging.info('reminder sent to {} clients. successes: {} blocked: {} failures: {} elapsed time: {} rate: {}'.format(
                str(i), str(p), str(b), str(f), str(timer() - start), str(i/(timer() - start))))
            return 'reminder sent to {} clients. successes: {} blocked: {} failures: {} elapsed time: {} rate: {}'.format(
                str(i), str(p), str(b), str(f), str(timer() - start), str(i/(timer() - start)))
        else:
            if not wstatus.skippedReminder:
                def fetch_remind_response(client):
                    with ndb_client.context():
                        try:
                            resp = "not sent"
                            key_id = client.id()
                            client = client.get()
                            now = datetime.now() + timedelta(hours=8)
                            if now.hour == 0 or now.hour == 12:
                                if client.status in valid_command_states:
                                    if client.temp != 'error':
                                        client.temp = 'none'
                                        client.status = 'offline,endgame 2'
                            if client.temp == 'none':
                                if (12 > now.hour >= client.remindAM) or (
                                        now.hour >= 12 and now.hour >= client.remindPM):
                                    temperatures = generateTemperatures()
                                    text = strftime(now, strings["remind_offline"])
                                    payload = {
                                        'chat_id': str(key_id),
                                        'text': text,
                                        "parse_mode": "HTML",
                                        'reply_markup': {
                                            "keyboard": temperatures,
                                            "one_time_keyboard": True
                                        }
                                    }
                                    resp = telegramApi.sendMessage(payload)
                                    if not resp['ok']:
                                        if resp['description'] == 'Forbidden: bot was blocked by the user':
                                            client.blocked = True
                                    client.status = 'endgame 2'
                            client.put()
                            return client, str(key_id), resp, None
                        except Exception as e:
                            return client, str(client.id()), None, e

                all_clients = Client.query().fetch(keys_only=True)
                start = timer()
                remind_results = ThreadPool(THREAD_NUMBER).imap_unordered(fetch_remind_response, all_clients)
                i = 0
                p = 0
                f = 0
                b = 0

                for client, key_id, resp, e in remind_results:
                    if e is None:
                        if resp != "not sent":
                            i += 1
                            if resp["ok"]:
                                logging.info('remind response for {}: {}'.format(key_id, resp["result"]))
                                p += 1
                            else:
                                logging.info('remind response for {}: {}'.format(key_id, resp["description"]))
                                if resp["error_code"] == 403:
                                    b += 1
                                else:
                                    f += 1
                    else:
                        logging.error(e)
                        f += 1

                wstatus.skippedReminder = True
                wstatus.put()

                logging.info('website offline. notification sent to {} clients. '
                             'successes: {} blocked: {} failures: {} elapsed time: {} rate: {}'.format(
                    str(i), str(p), str(b), str(f), str(timer() - start), str(i/(timer() - start))))
                return 'website offline. notification sent to {} clients. ' \
                       'successes: {} blocked: {} failures: {} elapsed time: {} rate: {}'.format(
                    str(i), str(p), str(b), str(f), str(timer() - start), str(i/(timer() - start)))
            return "website offline"

    if context:
        resp = remind()
    else:
        with ndb_client.context():
            resp = remind()
    return resp


@app.route(getRouteUrl("broadcast"), methods=["POST"])
def broadcast():
    with ndb_client.context():
        # try:
        #     id_list = request.get_json()['ids']
        #     for key_id in id_list:
        #         payload = {
        #             'chat_id': str(key_id),
        #             'text': request.get_json()['msg'],
        #             'parse_mode': 'HTML'
        #         }
        #         resp = telegramApi.sendMessage(payload)
        #         logging.info('broadcast response for {}:'.format(str(key_id)))
        #         logging.info(resp)
        #     return 'broadcast sent to {} clients'.format(str(len(id_list)))
        # except:
        def fetch_broadcast_response(params):
            [key_id, payload] = params
            try:
                resp = telegramApi.sendMessage(payload)
                return key_id, resp, None
            except Exception as e:
                return key_id, None, e

        all_clients = Client.query().fetch(keys_only=True)

        text = request.get_json()['msg']
        param_list = [None] * len(all_clients)

        for i in range(len(all_clients)):
            key_id = str(all_clients[i].id())
            payload = {
                'chat_id': key_id,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            param_list[i] = [key_id, payload]

        start = timer()
        broadcast_results = ThreadPool(THREAD_NUMBER).imap_unordered(fetch_broadcast_response, param_list)
        p = 0
        f = 0
        b = 0
        for key_id, resp, e in broadcast_results:
            if e is None:
                if resp["ok"]:
                    logging.info('broadcast response for {}: {}'.format(key_id, resp["result"]))
                    p += 1
                else:
                    logging.info('broadcast response for {}: {}'.format(key_id, resp["description"]))
                    if resp["error_code"] == 403:
                        b += 1
                    else:
                        f += 1
            else:
                logging.error(e)
                f += 1

        return 'broadcast sent to {} clients. successes: {} blocked: {} failures: {} elapsed time: {} rate: {}'.format(
            str(len(all_clients)), str(p), str(b), str(f), str(timer() - start), str(len(all_clients)/(timer() - start)))


@app.route(getRouteUrl("webhook"), methods=["POST"])
def webhook():
    with ndb_client.context():
        body = request.get_json()
        logging.info('request body: {}'.format(body))
        response = json.dumps(body)

        update_id = body['update_id']
        if 'message' in body:
            message = body['message']
        elif 'edited_message' in body:
            message = body['edited_message']
        else:
            logging.info("no message or edited message found")
            return response
        message_id = message.get('message_id')
        date = message.get('date')
        text = message.get('text')
        fr = message.get('from')
        chat = message['chat']
        chat_id = chat['id']
        client = Client.get_or_insert(str(chat_id))

        if client.firstName != fr:
            client.firstName = fr["first_name"]
            client.put()

        # reply function used in context of this response only
        def reply(msg=None, markup=None):
            if msg:
                if markup:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg,
                        'reply_to_message_id': str(message_id),
                        'reply_markup': markup,
                        'parse_mode': 'HTML'
                    }
                else:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg,
                        'reply_to_message_id': str(message_id),
                        'parse_mode': 'HTML'
                    }
                resp = telegramApi.sendMessage(payload)
            else:
                logging.error('no msg specified')
                resp = None
            logging.info('send response: {}'.format(resp))

        # message function used in context of this response only
        def message(msg=None, markup=None):
            if msg:
                if markup:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg,
                        'reply_markup': markup,
                        'parse_mode': 'HTML'
                    }
                else:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg,
                        'parse_mode': 'HTML'
                    }
                resp = telegramApi.sendMessage(payload)
            else:
                logging.error('no msg specified')
                resp = None
            logging.info('send response: {}'.format(resp))

        # message specific person only
        def messageMe(chat_id_list, msg=None, markup=None):
            for id in chat_id_list:
                if msg:
                    if markup:
                        payload = {
                            'chat_id': id,
                            'text': msg,
                            'reply_markup': markup,
                            'parse_mode': 'HTML'
                        }
                    else:
                        payload = {
                            'chat_id': id,
                            'text': msg,
                            'parse_mode': 'HTML'
                        }
                    resp = telegramApi.sendMessage(payload)
                else:
                    logging.error('no msg specified')
                    resp = None
                logging.info('messageMe() send response: {}'.format(resp))

        def setGroupId(client, group_url):
            group_string = 'temptaking.ado.sg/group/'
            if group_url.startswith(group_string):
                group_url = 'https://' + group_url
            if group_url.startswith('https://' + group_string) or group_url.startswith('http://' + group_string):
                try:
                    req_text = str(requests.get(group_url).content.decode('utf-8'))
                except:
                    return 0
                if 'Invalid code' in req_text:
                    return -1

                def urlParse(text):
                    return text[text.find('{'):text.rfind('}') + 1]

                try:
                    parsed_url = json.loads(urlParse(req_text))
                except:
                    return -1
                client.groupName = parsed_url["groupName"]
                client.groupId = parsed_url["groupCode"]
                client.groupMembers = json.dumps(parsed_url["members"])
                client.put()
                return 1
            else:
                return -1

        if text is None:
            reply(strings["no_text_error"])
            return response

        # force check website status before proceeding
        wstatus = WebsiteStatus.get_or_insert('status')
        if not wstatus.status:
            message(strings["status_offline_response"])
            # remember the client's previous status
            if not client.status.startswith("offline"):
                client.status = "offline,{}".format(client.status)
                client.put()
            return response

        if text.startswith('/'):
            if text == '/start':
                message(strings["SAF100"])
                client.reset()
                client.put()
                return response
            elif text == '/forcesubmit':
                if client.status in valid_command_states:
                    now = datetime.now() + timedelta(hours=8)
                    temperatures = generateTemperatures()
                    if now.hour < 12:
                        msg = strftime(now, strings["window_open_AM"])
                    else:
                        msg = strftime(now, strings["window_open_PM"])
                    markup = {
                        "keyboard": temperatures,
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
                    client.status = 'endgame 2'
                    client.put()
                    return response
            elif text == '/remind':
                if client.status in valid_command_states:
                    hours = generateHours(0)
                    if client.remindAM == -1 or client.remindPM == -1:
                        msg = strings["reminder_not_configured"] + strings["reminder_change_config"].format("AM")
                    else:
                        msg = strings["reminder_existing_config"].format(
                            f'{client.remindAM:02}:01', f'{client.remindPM:02}:01'
                        ) + strings["reminder_change_config"].format("AM")
                    markup = {
                        "keyboard": hours,
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
                    client.status = 'remind wizard 1'
                    client.put()
                    return response
            reply(strings["invalid_input"])
            return response

        elif client.status == '1':
            group_url = text
            groupFlag = setGroupId(client, group_url)
            if groupFlag == 1:
                msg = strings["group_msg"].format(client.groupName)
                markup = {
                    "keyboard": [
                        [
                            strings["group_keyboard_yes"]
                        ],
                        [
                            strings["group_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = '2'
                client.put()
            elif groupFlag == 0:
                websiteStatus(True)
                if not wstatus.status:
                    message(strings["status_offline_response"])
                    if not client.status.startswith("offline"):
                        client.status = "offline,{}".format(client.status)
                        client.put()
                else:
                    message(strings["website_error"])
            else:
                reply(strings["invalid_url"])
            return response

        elif client.status == '2':
            if text == strings["group_keyboard_yes"]:
                gm = json.loads(client.groupMembers)
                name_list = '\n'.join(
                    [str(i + 1) + '. ' + "<b>{}</b>".format(gm[i]["identifier"]) for i in range(len(gm))])
                if len(gm) > 300 or len(strings["member_msg_1"] + name_list) > 4096:
                    message(strings["member_overflow"].format(str(len(gm))))
                else:
                    msg = strings["member_msg_1"] + name_list
                    markup = {
                        "keyboard": [[item["identifier"]] for item in gm][0:300],
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
                client.status = '3'
                client.put()
                return response
            elif text == strings["group_keyboard_no"]:
                message(strings["SAF100_2"])
                client.status = '1'
                client.put()
                return response
            else:
                msg = strings["use_keyboard"]
                # TODO: put all these markups in a markups.json
                markup = {
                    "keyboard": [
                        [
                            strings["group_keyboard_yes"]
                        ],
                        [
                            strings["group_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                return response

        elif client.status == '3':
            gm = json.loads(client.groupMembers)
            try:
                index = [obj["identifier"] for obj in gm].index(text)
                client.memberId = gm[index]["id"]
                client.memberName = gm[index]["identifier"]
                client.pin = str(gm[index]["hasPin"])  # if this is False, ask the user to set a pin later

                msg = strings["member_msg_2"].format(client.memberName)
                markup = {
                    "keyboard": [
                        [
                            strings["member_keyboard_yes"]
                        ],
                        [
                            strings["member_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = '4'
            except ValueError:
                # user input does not match any identifier
                name_list = '\n'.join(
                    [str(i + 1) + '. ' + "<b>{}</b>".format(gm[i]["identifier"]) for i in range(len(gm))])
                if len(gm) > 300 or len(strings["member_msg_1"] + name_list) > 4096:
                    reply(strings["member_overflow_wrong"].format(text))
                else:
                    msg = strings["member_msg_1"] + name_list
                    markup = {
                        "keyboard": [[item["identifier"]] for item in gm],
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
            client.put()
            return response

        elif client.status == '4':
            if text == strings["member_keyboard_yes"]:
                if client.pin == 'False':
                    msg = strings["set_pin_1"].format(client.groupId)
                    markup = {
                        "keyboard": [
                            [
                                strings["pin_keyboard"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
                    client.pin = 'no pin'
                else:
                    message(strings["pin_msg_1"])
                    client.status = '5'
                client.put()
                return response
            elif text == strings["member_keyboard_no"]:
                gm = json.loads(client.groupMembers)
                name_list = '\n'.join(
                    [str(i + 1) + '. ' + "<b>{}</b>".format(gm[i]["identifier"]) for i in range(len(gm))])
                if len(gm) > 300 or len(strings["member_msg_1"] + name_list) > 4096:
                    message(strings["member_overflow"].format(str(len(gm))))
                else:
                    msg = strings["member_msg_3"] + name_list
                    markup = {
                        "keyboard": [[item["identifier"]] for item in gm],
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
                client.status = '3'
                client.put()
                return response
            elif text == strings["pin_keyboard"]:  # triggered if user set pin after prompted to by bot
                groupFlag = setGroupId(client, '{}/group/{}'.format(wstatus.url, client.groupId))
                if groupFlag == 0:
                    websiteStatus(True)
                    if not wstatus.status:
                        message(strings["status_offline_response"])
                        if not client.status.startswith("offline"):
                            client.status = "offline,{}".format(client.status)
                            client.put()
                    else:
                        msg = strings["website_error"]
                        markup = {
                            "keyboard": [
                                [
                                    strings["pin_keyboard"]
                                ]
                            ],
                            "one_time_keyboard": True
                        }
                        message(msg, markup)
                else:
                    # check that hasPin is now True
                    gm = json.loads(client.groupMembers)
                    try:
                        index = [obj["identifier"] for obj in gm].index(client.memberName)  # if this throws an
                        # exception, it means the user has changed their name and is probably trying to break the bot
                        client.memberId = gm[index]["id"]
                        client.memberName = gm[index]["identifier"]
                        client.pin = str(gm[index]["hasPin"])  # this should be true now

                        if client.pin == 'False':
                            msg = strings["set_pin_2"].format(client.groupId)
                            markup = {
                                "keyboard": [
                                    [
                                        strings["pin_keyboard"]
                                    ]
                                ],
                                "one_time_keyboard": True
                            }
                            message(msg, markup)
                            client.pin = 'no pin'
                        else:
                            message(strings["pin_msg_1"])
                            client.status = '5'
                        client.put()
                    except ValueError:
                        # user is probably trying to break the bot
                        message(strings["fatal_error"])
                        client.reset()
                        client.put()
                return response
            else:
                msg = strings["use_keyboard"]
                if client.pin == 'no pin':
                    markup = {
                        "keyboard": [
                            [
                                strings["pin_keyboard"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                else:
                    markup = {
                        "keyboard": [
                            [
                                strings["member_keyboard_yes"]
                            ],
                            [
                                strings["member_keyboard_no"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                message(msg, markup)
                return response

        elif client.status == '5':
            p = re.compile(r'\d{4}$').match(text)
            if p is None:
                reply(strings["invalid_pin"])
            else:
                msg = strings["pin_msg_2"].format(text)
                markup = {
                    "keyboard": [
                        [
                            strings["pin_keyboard_yes"]
                        ],
                        [
                            strings["pin_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = '6'
                client.pin = text
                client.put()
            return response

        elif client.status == '6':
            if text == strings["pin_keyboard_yes"]:
                msg = strings["setup_summary"].format(client.groupName, client.memberName, client.pin)
                markup = {
                    "keyboard": [
                        [
                            strings["summary_keyboard_yes"]
                        ],
                        [
                            strings["summary_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = '7'
                client.groupMembers = ''  # flush datastore
                client.put()
                # inform myself of new user
                messageMe(tokens["admin-id"], strings["setup_summary"].format(
                    client.groupName, client.memberName, "XXXX"))
                return response
            elif text == strings["pin_keyboard_no"]:
                message(strings["pin_msg_3"])
                client.status = '5'
                client.put()
                return response
            else:
                msg = strings["use_keyboard"]
                markup = {
                    "keyboard": [
                        [
                            strings["pin_keyboard_yes"]
                        ],
                        [
                            strings["pin_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                return response

        elif client.status == '7':
            if text == strings["summary_keyboard_no"]:
                message(strings["SAF100"])
                client.reset()
                client.put()
                return response
            elif text == strings["summary_keyboard_yes"]:
                hours = generateHours(0)
                msg = strings["reminder_not_configured"] + strings["reminder_change_config"].format("AM")
                markup = {
                    "keyboard": hours,
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = 'remind wizard 1'
                client.put()
                return response
            else:
                msg = strings["use_keyboard"]
                markup = {
                    "keyboard": [
                        [
                            strings["summary_keyboard_yes"]
                        ],
                        [
                            strings["summary_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                return response

        elif client.status == 'endgame 1':
            now = datetime.now() + timedelta(hours=8)
            if client.temp == 'none':
                temperatures = generateTemperatures()
                if now.hour < 12:
                    msg = strftime(now, strings["window_open_AM"])
                else:
                    msg = strftime(now, strings["window_open_PM"])
                markup = {
                    "keyboard": temperatures,
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = 'endgame 2'
                client.put()
            else:
                if now.hour < 12:
                    message((strftime(now,
                                      strings["already_submitted_AM"]).format(client.temp)
                             + strings["old_user_AM"]))
                else:
                    message((strftime(now,
                                      strings["already_submitted_PM"]).format(client.temp)
                             + strings["old_user_PM"]))
            return response

        elif client.status == 'endgame 2':
            p = re.compile(r'\d{2}[.]\d$').match(text)
            if p is None:
                temperatures = generateTemperatures()
                msg = strings["invalid_temp"]
                markup = {
                    "keyboard": temperatures,
                    "one_time_keyboard": True
                }
                message(msg, markup)
            else:
                temp = float(text)
                if temp >= 40.05 or temp <= 34.95:
                    temperatures = generateTemperatures()
                    msg = strings["temp_outside_range"]
                    markup = {
                        "keyboard": temperatures,
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
                else:
                    resp = submitTemp(client, text)
                    if resp == 'OK':
                        client.temp = text
                        now = datetime.now() + timedelta(hours=8)
                        if now.hour < 12:
                            message((strftime(now,
                                              strings["just_submitted_AM"]).format(emojiTime(now), client.temp)
                                     + strings["old_user_AM"]))
                        else:
                            message((strftime(now,
                                              strings["just_submitted_PM"]).format(emojiTime(now), client.temp)
                                     + strings["old_user_PM"]))
                        client.status = 'endgame 1'
                        client.groupMembers = ''  # flush datastore
                        client.put()
                    elif resp == 'Wrong pin.':
                        message(strings["wrong_pin"])
                        client.status = 'wrong pin'
                        client.temp = 'error'
                        client.put()
                    else:
                        websiteStatus(True)
                        if not wstatus.status:
                            message(strings["status_offline_response"])
                            if not client.status.startswith("offline"):
                                client.status = "offline,{}".format(client.status)
                                client.put()
                        else:
                            message(strings["temp_submit_error"].format(client.groupId))
                            client.status = "endgame 1"
                            client.put()
                return response
        elif client.status == 'wrong pin':
            p = re.compile(r'\d{4}$').match(text)
            if p is None:
                reply(strings["invalid_pin"])
            else:
                msg = strings["pin_msg_2"].format(text)
                markup = {
                    "keyboard": [
                        [
                            strings["pin_resubmit_temp"]
                        ],
                        [
                            strings["pin_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = 'resubmit temp'
                client.pin = text
                client.put()
            return response
        elif client.status == 'resubmit temp':
            if text == strings["pin_resubmit_temp"]:
                temperatures = generateTemperatures()
                msg = strings["select_temp"]
                markup = {
                    "keyboard": temperatures,
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = 'endgame 2'
                client.put()
                return response
            elif text == strings["pin_keyboard_no"]:
                message(strings["pin_msg_3"])
                client.status = 'wrong pin'
                client.put()
                return response
            else:
                msg = strings["use_keyboard"]
                markup = {
                    "keyboard": [
                        [
                            strings["pin_resubmit_temp"]
                        ],
                        [
                            strings["pin_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                return response
        elif client.status == 'remind wizard 1':
            if text not in [f'{x:02}:01' for x in range(12)]:
                hours = generateHours(0)
                msg = strings["invalid_reminder_time"]
                markup = {
                    "keyboard": hours,
                    "one_time_keyboard": True
                }
                reply(msg, markup)
            else:
                client.remindAM = int(text[:2])
                msg = strings["reminder_change_config"].format("PM")
                hours = generateHours(12)
                markup = {
                    "keyboard": hours,
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = 'remind wizard 2'
                client.put()
            return response

        elif client.status == 'remind wizard 2':
            if text not in [f'{x:02}:01' for x in range(12, 24)]:
                hours = generateHours(12)
                msg = strings["invalid_reminder_time"]
                markup = {
                    "keyboard": hours,
                    "one_time_keyboard": True
                }
                reply(msg, markup)
            else:
                client.remindPM = int(text[:2])
                msg = strings["reminder_successful_change"].format(
                    f'{client.remindAM:02}:01', f'{client.remindPM:02}:01')
                message(msg)
                client.status = 'endgame 1'
                if client.temp == 'init':
                    client.temp = 'none'
                    now = datetime.now() + timedelta(hours=8)
                    temperatures = generateTemperatures()
                    if now.hour < 12:
                        msg = strftime(now, strings["window_open_AM"])
                    else:
                        msg = strftime(now, strings["window_open_PM"])
                    markup = {
                        "keyboard": temperatures,
                        "one_time_keyboard": True
                    }
                    message(msg, markup)
                    client.status = 'endgame 2'
                client.put()
            return response

        else:
            reply(strings["invalid_input"])
        return response
