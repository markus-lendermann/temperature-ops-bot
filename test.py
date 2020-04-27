import requests
import json
import re
from timeit import default_timer as timer
from datetime import datetime, timedelta

status = "endgame 2"
status = "offline,{}".format(status)

print(status.startswith("offline"))
print(status)

if status.startswith("offline"):
    status = status.split(",")[1]

print(status)



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
# msg = strings["remind_delayed"] + strftime(now, strings["window_open_AM"])
# # msg = strftime(now, strings["remind_offline"])
# # msg = strftime(now, strings["status_online"])
# print(sendBroadcast(msg))

hour = now.hour
minute = now.minute
print(round(2 * (hour + minute / 60) % 24))