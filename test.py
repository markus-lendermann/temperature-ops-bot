import requests
import json
from timeit import default_timer as timer

url = "https://temptaking.ado.sg/group/2c151e8ed996c62450f92383838af8a7"
req = requests.get(url)
req_text = str(req.content)


def urlParse(text):
    return text[text.find('{'):text.rfind('}') + 1]


parsed_url = json.loads(urlParse(req_text))
# print(parsed_url["groupName"])
# print(parsed_url["groupCode"])
# print(json.dumps(parsed_url["members"]))

group_members = json.loads(json.dumps(parsed_url["members"]))

print(group_members)

text = "Mr Teow"

try:
    index = [obj["identifier"] for obj in group_members].index(text)
    print(group_members[index]["id"])
    print(group_members[index]["identifier"])
    print(group_members[index]["hasPin"])
except ValueError:
    print("no")

# print('Please choose your name from the following list:\n' + '\n'.join([str(i+1) + '. ' + group_members[i]["identifier"] for i in range(len(group_members))]))

# print([[item["identifier"]] for item in group_members])

# msg = 'Please choose your name from the following list:\n' + '\n'.join([str(i + 1) + '.' + group_members[i].split(',')[1] for i in range(len(group_members))]
