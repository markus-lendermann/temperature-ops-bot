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
# msg = strings["reminder_existing_config"].format("00:01", "12:01") + strings["reminder_change_config"].format("AM")
#
msg = ""
print(sendBroadcast(msg))

#
# print(f'{0:02}')
#
# print([[f'{2*x:02}:01', f'{2*x+1:02}:01'] for x in range(6)])
# print([[f'{2*x:02}:01', f'{2*x+1:02}:01'] for x in range(6, 12)])
# print(now.hour < 12)

p = re.compile(r'\d{2}:01$').match("13:0")
print(p)

print([[str(x / 10), str((x + 1) / 10)] for x in range(350, 400, 2)])