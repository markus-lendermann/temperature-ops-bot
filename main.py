from __future__ import division
from api_wrapper import TelegramApiWrapper
import json
import logging
import urllib
import urllib2
import re
from datetime import datetime, timedelta
# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
import webapp2
import requests
import requests_toolbelt.adapters.appengine
import Queue as queue

requests_toolbelt.adapters.appengine.monkeypatch()


def loadTokens():
    with open("tokens.json") as tf:
        tokens = json.load(tf)

    return tokens


def loadStrings():
    with open("strings.json") as tf:
        strings = json.load(tf)

    return strings


class WebsiteStatus(ndb.Model):
    status = ndb.BooleanProperty(default=True)


class Client(ndb.Model):
    firstName = ndb.StringProperty()
    status = ndb.StringProperty(default='0')
    groupId = ndb.StringProperty()
    groupName = ndb.StringProperty()
    groupMembers = ndb.StringProperty()
    memberName = ndb.StringProperty()
    memberId = ndb.StringProperty()
    pin = ndb.StringProperty()
    temp = ndb.StringProperty()


tokens = loadTokens()
strings = loadStrings()
test = queue.Queue()

telegramApi = TelegramApiWrapper(tokens["telegram-bot"])
BASE_URL = 'https://api.telegram.org/bot' + tokens["telegram-bot"] + '/'


class MeHandler(webapp2.RequestHandler):
    def get(self):
        resp = telegramApi.getMe()
        self.response.write(resp["result"])


class SetWebhookHandler(webapp2.RequestHandler):
    def get(self):
        url = tokens["project-url"] + "webhook"
        resp = telegramApi.setWebhook(url)
        if resp["ok"]:
            self.response.write("webhook has been set to " + url)
        else:
            self.response.write("webhook failed to set. DEBUG: ")
            self.response.write(str(resp))


class WebsiteStatusHandler(webapp2.RequestHandler):
    def get(self):
        wstatus = WebsiteStatus.query().fetch()
        if len(wstatus) == 0:
            wstatus = WebsiteStatus.get_or_insert('status')
            wstatus.status = True  # if status object doesn't exist yet, initialize as true
            wstatus.put()
        else:
            wstatus = wstatus[0]
        try:
            requests.get("https://temptaking.ado.sg")
            if not wstatus.status:
                wstatus.status = True
                wstatus.put()
                all_clients = Client.query().fetch(keys_only=True)
                for client in all_clients:
                    key_id = client.id()
                    payload = {
                        'chat_id': str(key_id),
                        'text': strings["status _online"]
                    }
                    telegramApi.sendMessage(payload)
        except:
            if wstatus.status:
                wstatus.status = False
                wstatus.put()
                all_clients = Client.query().fetch(keys_only=True)
                for client in all_clients:
                    key_id = client.id()
                    payload = {
                        'chat_id': str(key_id),
                        'text': strings["status_offline"]
                    }
                    telegramApi.sendMessage(payload)
        self.response.write('ok')


class ReminderHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        if len(WebsiteStatus.query().fetch()) == 0:
            wstatus = WebsiteStatus.get_or_insert('status')
            wstatus.status = True  # if status object doesn't exist yet, initialize as true
            wstatus.put()
        else:
            wstatus = WebsiteStatus.query().fetch()
            wstatus = wstatus[0]
        all_clients = Client.query().fetch(keys_only=True)
        for i in range(len(all_clients)):
            client = all_clients[i]
            key_id = client.id()
            client = client.get()
            now = datetime.now() + timedelta(hours=8)
            if now.hour == 0 or now.hour == 12:
                if client.status == 'endgame 1' or client.status == 'endgame 2':
                    if client.temp != 'error':
                        client.temp = 'none'
            if client.temp == 'none':
                if wstatus.status:
                    temperatures = [[str(x / 10), str((x + 1) / 10)] for x in range(355, 375, 2)]
                    if now.hour < 12:
                        text = now.strftime(strings["window_open_AM"])
                    else:
                        text = now.strftime(strings["window_open_PM"])
                    payload = {
                        'chat_id': str(key_id),
                        'text': text,
                        'reply_markup': {
                            "keyboard": temperatures,
                            "one_time_keyboard": True
                        }
                    }
                    telegramApi.sendMessage(payload)
                    client.status = 'endgame 2'
            client.put()
        self.response.write('ok')


class BroadcastHandler(webapp2.RequestHandler):
    def get(self):
        if self.request.get('password') == tokens["broadcast_password"]:
            all_clients = Client.query().fetch(keys_only=True)
            for client in all_clients:
                key_id = client.id()
                payload = {
                    'chat_id': str(key_id),
                    'text': self.request.get('msg'),
                }
                telegramApi.sendMessage(payload)
            self.response.write('broadcast sent to ' + str(len(all_clients)) + ' clients')
        else:
            self.response.write('wrong password')


def setGroupId(client, group_url):
    group_string = 'temptaking.ado.sg/group'
    if group_url.startswith(group_string):
        group_url = 'https://' + group_url
    if group_url.startswith('https://' + group_string) or group_url.startswith('http://' + group_string):
        try:
            req_text = str(requests.get(group_url).content)
        except:
            return 0
        if 'Invalid code' in req_text:
            return -1

        def urlParse(text):
            return text[text.find('{'):text.rfind('}') + 1]

        parsed_url = json.loads(urlParse(req_text))
        client.groupName = parsed_url["groupName"]
        client.groupId = parsed_url["groupCode"]
        client.groupMembers = json.dumps(parsed_url["members"])
        client.put()
        return 1
    else:
        return -1


def submitTemp(client, temp):
    now = datetime.now() + timedelta(hours=8)
    if now.hour < 12:
        meridies = 'AM'
    else:
        meridies = 'PM'
    try:
        url = 'https://temptaking.ado.sg/group/MemberSubmitTemperature'
        payload = {
            'groupCode': client.groupId,
            'date': now.strftime('%d/%m/%Y'),
            'meridies': meridies,
            'memberId': client.memberId,
            'temperature': temp,
            'pin': client.pin
        }
        r = requests.post(url, data=payload)
    except:
        return 'error'
    return r.json()


class WebhookHandler(webapp2.RequestHandler):
    def post(self):
        urlfetch.set_default_fetch_deadline(60)
        body = json.loads(self.request.body)
        logging.info('request body:')
        logging.info(body)
        self.response.write(json.dumps(body))

        update_id = body['update_id']
        try:
            message = body['message']
        except:
            message = body['edited_message']
        message_id = message.get('message_id')
        date = message.get('date')
        text = message.get('text')
        fr = message.get('from')
        chat = message['chat']
        chat_id = chat['id']
        client = Client.get_or_insert(str(chat_id))

        # reply function used in context of this response only
        def reply(msg=None, markup=None):
            if msg:
                if markup:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg,
                        'reply_to_message_id': str(message_id),
                        'reply_markup': markup
                    }
                else:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg,
                        'reply_to_message_id': str(message_id)
                    }
                resp = telegramApi.sendMessage(payload)
            else:
                logging.error('no msg specified')
                resp = None
            logging.info('send response:')
            logging.info(resp)

        # message function used in context of this response only
        def message(msg=None, markup=None):
            if msg:
                if markup:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg,
                        'reply_markup': markup
                    }
                else:
                    payload = {
                        'chat_id': str(chat_id),
                        'text': msg
                    }
                resp = telegramApi.sendMessage(payload)
            else:
                logging.error('no msg specified')
                resp = None
            logging.info('send response:')
            logging.info(resp)

        if text is None:
            reply(strings["no_text_error"])
            return

        # force check website status before proceeding
        wstatus = WebsiteStatus.query().fetch()
        if len(wstatus) == 0:
            # initialize wstatus object if not already done previously
            wstatus = WebsiteStatus.get_or_insert('status')
            wstatus.status = True
            wstatus.put()
        else:
            wstatus = wstatus[0]
        if not wstatus.status:
            message(strings["status_offline_response"])
            return

        def endgame2():
            client.status = 'endgame 2'
            client.put()
            now = datetime.now() + timedelta(hours=8)
            if now.hour < 12:
                meridies = 'AM'
            else:
                meridies = 'PM'
            temperatures = [[str(x / 10), str((x + 1) / 10)] for x in range(355, 375, 2)]
            form_fields = {
                'chat_id': str(chat_id),
                'text': now.strftime("It's now %H:%M on %A, %d/%m/%y. You are eligible for " + meridies +
                                     " submission.\n\n") + strings["select_temp"],
                'reply_markup': {
                    "keyboard": temperatures,
                    "one_time_keyboard": True
                }
            }
            requests.post(BASE_URL + 'sendMessage', json=form_fields)

        if text.startswith('/'):
            if text == '/start':
                message(strings["SAF100"])
                client.status = '1'
                client.temp = 'init'
                client.put()
                return
            elif text == '/forcesubmit':
                if client.status == 'endgame 1':
                    endgame2()
                    return
            reply(strings["invalid_input"])

        elif client.status == '1':
            group_url = text
            groupFlag = setGroupId(client, group_url)
            if groupFlag == 1:
                msg = strings["group_msg"] + client.groupName
                markup = {
                    "keyboard": [
                        [
                            strings["group_keyboard_yes"],
                            strings["group_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = '2'
                client.put()
            elif groupFlag == 0:
                reply(strings["status_offline_response"])
            else:
                reply(strings["invalid_url"])
            return

        elif client.status == '2':
            if text == strings["group_keyboard_yes"]:
                gm = json.loads(client.groupMembers)
                name_list = '\n'.join([str(i + 1) + '. ' + gm[i]["identifier"] for i in range(len(gm))])
                msg = strings["member_msg_1"] + name_list
                markup = {
                    "keyboard": [[item["identifier"]] for item in gm],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = '3'
                client.put()
                return
            elif text == strings["group_keyboard_no"]:
                message(strings["SAF100_2"])
                client.status = '1'
                client.put()
                return
            else:
                msg = strings["use_keyboard"]
                markup = {
                    "keyboard": [
                        [
                            strings["group_keyboard_yes"],
                            strings["group_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                return

        elif client.status == '3':
            gm = json.loads(client.groupMembers)
            try:
                index = [obj["identifier"] for obj in gm].index(text)
                client.memberId = gm[index]["id"]
                client.memberName = gm[index]["identifier"]
                client.pin = gm[index]["hasPin"]

                msg = strings["member_msg_2"].format(client.memberName)
                markup = {
                    "keyboard": [
                        [
                            strings["member_keyboard_yes"],
                            strings["member_keyboard_no"]
                        ]
                    ],
                    "one_time_keyboard": True
                }
                message(msg, markup)
                client.status = '4'
            except ValueError:
                # user input does not match any identifier
                msg = strings["use keyboard"]
                markup = {
                    "keyboard": [[item["identifier"]] for item in gm],
                    "one_time_keyboard": True
                }
                message(msg, markup)
            client.put()
            return

        elif client.status == '4':
            if text == strings["member keyboard yes"]:
                message('Your member ID is ' + client.memberId + '.')
                if client.pin == 'false':
                    # TODO: actually re-check if the pin is now true on the website (only possible if user sets pin
                    #  between having entered group url and now so realistically this isn't needed)
                    form_fields = {
                        'chat_id': str(chat_id),
                        'text': strings["set pin"] + client.groupId + '.',
                        'reply_markup': {
                            "keyboard": [
                                [
                                    strings["pin keyboard"]
                                ]
                            ],
                            "one_time_keyboard": True
                        }
                    }
                    requests.post(BASE_URL + 'sendMessage', json=form_fields)
                else:
                    message('Please enter your pin:')
                    client.status = '5'
                    client.put()
                return
            elif text == strings["member keyboard no"]:
                group_members = client.groupMembers
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': 'Please choose your name again from the following list:\n' + '\n'.join(
                        [str(i + 1) + '.' + group_members[i].split(',')[1] for i in range(len(group_members))]),
                    'reply_markup': {
                        "keyboard": [[item.split(',')[1][1:]] for item in group_members],
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
                client.status = '3'
                client.put()
                return
            elif text == strings["pin keyboard"]:  # triggered if user set pin after prompted to by bot
                groupFlag = setGroupId(client, 'https://temptaking.ado.sg/group/' + client.groupId)
                if groupFlag == 0:
                    form_fields = {
                        'chat_id': str(chat_id),
                        'text': strings["status offline response"],
                        'reply_markup': {
                            "keyboard": [
                                [
                                    strings["pin keyboard"]
                                ]
                            ],
                            "one_time_keyboard": True
                        }
                    }
                    requests.post(BASE_URL + 'sendMessage', json=form_fields)
                else:
                    group_members = client.groupMembers
                    for item in group_members:
                        member_id = item.split(',')[0]
                        member_name = item.split(',')[1][1:]
                        pin = item.split(',')[2][1:]
                        if member_name == client.memberName:
                            client.memberId = member_id
                            client.memberName = member_name
                            client.pin = pin
                    if client.pin == 'false':
                        # TODO: actually re-check if the pin is now true on the website
                        form_fields = {
                            'chat_id': str(chat_id),
                            'text': 'Wake up your idea. ' + strings["set pin"] + client.groupId + '.',
                            'reply_markup': {
                                "keyboard": [
                                    [
                                        strings["pin keyboard"]
                                    ]
                                ],
                                "one_time_keyboard": True
                            }
                        }
                        requests.post(BASE_URL + 'sendMessage', json=form_fields)
                    else:
                        message('Please enter your pin:')
                        client.status = '5'
                        client.put()
                    return
            else:
                if client.pin == 'false':
                    form_fields = {
                        'chat_id': str(chat_id),
                        'text': strings["use keyboard"],
                        'reply_markup': {
                            "keyboard": [
                                [
                                    strings["pin keyboard"]
                                ]
                            ],
                            "one_time_keyboard": True
                        }
                    }
                    requests.post(BASE_URL + 'sendMessage', json=form_fields)
                else:
                    form_fields = {
                        'chat_id': str(chat_id),
                        'text': 'Wake up your idea. Use the keyboard I gave you.',
                        'reply_markup': {
                            "keyboard": [
                                [
                                    strings["member keyboard yes"],
                                    strings["member keyboard no"]
                                ]
                            ],
                            "one_time_keyboard": True
                        }
                    }
                    requests.post(BASE_URL + 'sendMessage', json=form_fields)
                return

        elif client.status == '5':
            p = re.compile(r'\d{4}$').match(text)
            if p is None:
                reply(strings["invalid pin"])
            else:
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': 'You entered ' + text + ' as your pin.',
                    'reply_markup': {
                        "keyboard": [
                            [
                                strings["pin keyboard yes"],
                                strings["pin keyboard no"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
                client.status = '6'
                client.pin = text
                client.put()
            return

        elif client.status == '6':
            if text == strings["pin keyboard yes"]:
                message('Your confirmed pin is ' + client.pin + '.')
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': strings[
                                "setup summary"] + '\n\nGroup name: ' + client.groupName + '\nMember name: ' + client.memberName + '\nMember ID: '
                            + client.memberId + '\nPin: ' + client.pin,
                    'reply_markup': {
                        "keyboard": [
                            [
                                strings["summary keyboard yes"],
                                strings["summary keyboard no"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
                client.status = 'endgame 1'
                client.put()
                return
            elif text == strings["pin keyboard no"]:
                message('Please enter your pin again:')
                client.status = '5'
                client.put()
                return
            else:
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': strings["use keyboard"],
                    'reply_markup': {
                        "keyboard": [
                            [
                                strings["pin keyboard yes"],
                                strings["pin keyboard no"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
                return

        elif client.status == 'endgame 1':
            now = datetime.now() + timedelta(hours=8)
            if text == strings["summary keyboard no"]:
                message(strings["SAF100"])
                client.status = '1'
                client.temp = 'init'
                client.put()
                return
            if client.temp == 'init':
                if now.hour < 12:
                    message(now.strftime("It's now %H:%M on %A, %d/%m/%y. ") + strings["new user AM"])
                else:
                    message(now.strftime("It's now %H:%M on %A, %d/%m/%y. ") + strings["new user PM"])
                return
            else:
                if now.hour < 12:
                    message('You have already submitted a temperature of ' + client.temp + u'\u00b0' + now.strftime(
                        'C for %A, %d/%m/%y, AM window. ') + strings["old user AM"])
                else:
                    message('You have already submitted a temperature of ' + client.temp + u'\u00b0' + now.strftime(
                        'C for %A, %d/%m/%y, PM window. ') + strings["old user PM"])
            return

        elif client.status == 'endgame 2':
            p = re.compile(r'\d{2}[.]\d{1}$').match(text)
            if p is None:
                temperatures = [[str(x / 10), str((x + 1) / 10)] for x in range(355, 375, 2)]
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': strings["invalid temp"] + '\n\n' + strings["select temp"],
                    'reply_markup': {
                        "keyboard": temperatures,
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
            else:
                temp = float(text)
                if temp >= 40.05 or temp <= 34.95:
                    temperatures = [[str(x / 10), str((x + 1) / 10)] for x in range(355, 375, 2)]
                    form_fields = {
                        'chat_id': str(chat_id),
                        'text': (
                                'The website only accepts temperatures between 35' + u'\u00b0' + 'C and 40' + u'\u00b0' + 'C. Please re-select your current temperature below, or type it in if it is not shown.').encode(
                            'utf-8'),
                        'reply_markup': {
                            "keyboard": temperatures,
                            "one_time_keyboard": True
                        }
                    }
                    requests.post(BASE_URL + 'sendMessage', json=form_fields)
                else:
                    resp = submitTemp(client, text)
                    if resp == 'OK':
                        client.temp = text
                        now = datetime.now() + timedelta(hours=8)
                        if now.hour < 12:
                            message('I have submitted a temperature of ' + client.temp + u'\u00b0' + 'C' + now.strftime(
                                ' at %H:%M under the AM window for %A, %d/%m/%y.\n\n') + strings["old user AM"])
                        else:
                            message('I have submitted a temperature of ' + client.temp + u'\u00b0' + 'C' + now.strftime(
                                ' at %H:%M under the PM window for %A, %d/%m/%y.\n\n') + strings["old user PM"])
                        client.status = 'endgame 1'
                        client.put()
                    elif resp == 'Wrong pin.':
                        message(strings["wrong pin"])
                        client.status = 'wrong pin'
                        client.temp = 'error'
                        client.put()
                    else:
                        message(strings["temp submit error"])
                return
        elif client.status == 'wrong pin':
            p = re.compile(r'\d{4}$').match(text)
            if p is None:
                reply(strings["invalid pin"])
            else:
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': 'You entered ' + text + ' as your pin.',
                    'reply_markup': {
                        "keyboard": [
                            [
                                "Re-submit my temperature now",
                                strings["pin keyboard no"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
                client.status = 'resubmit temp'
                client.pin = text
                client.put()
            return
        elif client.status == 'resubmit temp':
            if text == 'Re-submit my temperature now':
                temperatures = [[str(x / 10), str((x + 1) / 10)] for x in range(355, 375, 2)]
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': strings["select temp"],
                    'reply_markup': {
                        "keyboard": temperatures,
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
                client.status = 'endgame 2'
                client.put()
                return
            elif text == strings["pin keyboard no"]:
                message('Please enter your pin again:')
                client.status = 'wrong pin'
                client.put()
                return
            else:
                form_fields = {
                    'chat_id': str(chat_id),
                    'text': strings["use keyboard"],
                    'reply_markup': {
                        "keyboard": [
                            [
                                strings["pin keyboard yes"],
                                strings["pin keyboard no"]
                            ]
                        ],
                        "one_time_keyboard": True
                    }
                }
                requests.post(BASE_URL + 'sendMessage', json=form_fields)
                return
        else:
            reply(strings["invalid input"])
            return


app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/webhook', WebhookHandler),
    ('/remind', ReminderHandler),
    ('/broadcast', BroadcastHandler),
    ('/website_status', WebsiteStatusHandler),
], debug=True)
