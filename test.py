import requests
import json
import re
from timeit import default_timer as timer
from datetime import datetime, timedelta


def loadTokens():
    with open("tokensv2.json", encoding="utf-8") as tf:
        tokens = json.load(tf)

    return tokens



def loadStrings():
    with open("strings.json", encoding="utf-8") as tf:
        strings = json.load(tf)

    return strings


def sendBroadcast(msg):
    print(msg)
    r = requests.post('{}{}/broadcast'.format(tokens["project-url"], tokens["telegram-bot"]), json={"msg": msg})
    return r.text


def strftime(datetimeobject, formatstring):
    formatstring = formatstring.replace("%%", "percent_placeholder")
    ps = list(set(re.findall("(%.)", formatstring)))
    format2 = "|".join(ps)
    vs = datetimeobject.strftime(format2).split("|")
    for p, v in zip(ps, vs):
        formatstring = formatstring.replace(p, v)
    return formatstring.replace("percent_placeholder", "%")


tokens = loadTokens()
strings = loadStrings()

now = datetime.now()


# groupName = "BMTC SCH 1"
# memberName = "Shawn"
# memberId = "298347"
# pin = "1234"
#
# print(strftime(now, "%H:%M"))
# print(str(datetime.now()))
#
# msg = strings["reminder_existing_config"].format("00:01", "12:01") + strings["reminder_change_config"].format("AM")
#
# msg = ""
# print(sendBroadcast(msg))


def test(c):
    [a, b] = c
    print("a is {}, b is {}".format(a, b))
    return "ok"

test(["a", "b"])


print([None]*10)

#
# print(f'{0:02}')
#
# print([[f'{2*x:02}:01', f'{2*x+1:02}:01'] for x in range(6)])
# print([[f'{2*x:02}:01', f'{2*x+1:02}:01'] for x in range(6, 12)])
# print(now.hour < 12)

# valid_states = ['endgame 1', 'endgame 2', 'remind wizard 1', 'remind wizard 2']
# print('endgame 1' in valid_states)