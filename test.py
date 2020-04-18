import requests
import json
import re
from timeit import default_timer as timer
from datetime import datetime, timedelta


def loadStrings():
    with open("strings.json", encoding="utf-8") as tf:
        strings = json.load(tf)

    return strings


def sendBroadcast(msg):
    print(msg)
    r = requests.post('https://tempbotv2.ey.r.appspot.com/broadcast', json={"msg": msg})
    return r.text


def strftime(datetimeobject, formatstring):
    formatstring = formatstring.replace("%%", "percent_placeholder")
    ps = list(set(re.findall("(%.)", formatstring)))
    format2 = "|".join(ps)
    vs = datetimeobject.strftime(format2).split("|")
    for p, v in zip(ps, vs):
        formatstring = formatstring.replace(p, v)
    return formatstring.replace("percent_placeholder", "%")

strings = loadStrings()

now = datetime.now()

groupName = "BMTC SCH 1"
memberName = "Shawn"
memberId = "298347"
pin = "1234"

msg = strings["temp_submit_error"]
print(sendBroadcast(msg))
