import requests
import json
from timeit import default_timer as timer
from datetime import datetime, timedelta


def loadStrings():
    with open("strings.json") as tf:
        strings = json.load(tf)

    return strings
strings = loadStrings()

now = datetime.now()

msg = "<i>Setup Summary</i>\nGroup name: <b>{}</b>\nMember name: <b>{}</b>\nMember ID: <b>{}</b>\nPin: <b>{}</b>".format("TCRM Temperature OPS", "Markus", "123456", "0000")

msg = now.strftime(strings["SAF100"]).format()


url = 'https://tempbotv2.ey.r.appspot.com/broadcast?msg=' + msg


r = requests.get(url)
print(r.text)

print("°".encode("utf-8"))
