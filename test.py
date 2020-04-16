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
url = 'https://temptaking.ado.sg/group/MemberSubmitTemperature'
payload = {
    'groupCode': "2c151e8ed996c62450f92383838af8a7",
    'date': now.strftime('%d/%m/%Y'),
    'meridies': 'PM',
    'memberId': "2067669",
    'temperature': "35.9",
    'pin': "0000"
}
r = requests.post(url, data=payload)
#
# print(r.text)
#
# temp = "36.0"
# print(str(now.strftime(strings["already_submitted_PM"]).format(temp, u'\u00b0') + strings["old_user_PM"]))


print(("35" + u'\u00b0' + "C"))
print((u"35{}C".format(u'\u00b0')))
print(("35{}C".format(u'\u00b0')) == ("35" + u'\u00b0' + "C"))
print(u"")
# url = "https://temptaking.ado.sg/group/2424241947e5a26be7a9c10d6720c84b"
# req = requests.get(url)
# req_text = str(req.content)
#
#
# def urlParse(text):
#     return text[text.find('{'):text.rfind('}') + 1]
#
#
# parsed_url = json.loads(urlParse(req_text))
# # print(parsed_url["groupName"])
# # print(parsed_url["groupCode"])
# # print(json.dumps(parsed_url["members"]))
#
#
# # print(json.dumps(parsed_url["members"]))
#
# group_members = json.loads(json.dumps(parsed_url["members"]))[0:323]
# name_list = "Please choose your name from the following list:" + '\n'.join([str(i + 1) + '. ' + group_members[i]["identifier"] for i in range(len(group_members))])
# print(group_members)
# print(len(name_list) > 4096)
# print(len(name_list))
#
# text = "E 3SG WONG MING HIN"
#
# try:
#     index = [obj["identifier"] for obj in group_members].index(text)
#     print(group_members[index]["id"])
#     print(group_members[index]["identifier"])
#     print(group_members[index]["hasPin"])
# except ValueError:
#     print("no")



# print('Please choose your name from the following list:\n' + '\n'.join([str(i+1) + '. ' + group_members[i]["identifier"] for i in range(len(group_members))]))
# print(len(json.dumps(parsed_url)))


# print([[item["identifier"]] for item in group_members])

# msg = 'Please choose your name from the following list:\n' + '\n'.join([str(i + 1) + '.' + group_members[i].split(',')[1] for i in range(len(group_members))]