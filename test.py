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
# msg = '<i>[Sent by Admin]</i>\n\n<b>CHANGELOG: V1.5</b>\n\n<b>1. Groups containing members with special characters in their names (including emojis) are now valid.</b> Previously, the bot would respond with "This isn\'t a valid temptaking url". It is unclear how many people were affected by this issue previously, but those who know any previously affected can inform them of this fix.'
# print(sendBroadcast(msg))

print(sendBroadcast('<i>[Sent by Admin]</i>\n\nDear users,\n\n<b>The bot is back online.</b> Fixed a crash caused by users using other bots to message this one.\n\nThis bot now ignores other bots. Will fix in future update.'))



#
# print(f'{0:02}')
#
# print([[f'{2*x:02}:01', f'{2*x+1:02}:01'] for x in range(6)])
# print([[f'{2*x:02}:01', f'{2*x+1:02}:01'] for x in range(6, 12)])
# print(now.hour < 12)

# valid_states = ['endgame 1', 'endgame 2', 'remind wizard 1', 'remind wizard 2']
# print('endgame 1' in valid_states)