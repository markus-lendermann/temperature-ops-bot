import requests
import json
from timeit import default_timer as timer
from datetime import datetime, timedelta


def loadStrings():
    with open("strings.json", encoding="utf-8") as tf:
        strings = json.load(tf)

    return strings
strings = loadStrings()

now = datetime.now()

msg = "<i>Setup Summary</i>\nGroup name: <b>{}</b>\nMember name: <b>{}</b>\nMember ID: <b>{}</b>\nPin: <b>{}</b>".format("TCRM Temperature OPS", "Markus", "123456", "0000")

msg = strings["SAF100"]


url = 'https://tempbotv2.ey.r.appspot.com/broadcast'
payload = {
    "msg": msg
}


r = requests.post(url, json=payload)
print(r.text)
