import requests
import json
from timeit import default_timer as timer

url = "https://temptaking.ado.sg/group/540cb0a94ff617666b8041c364b8ca98"
req = requests.get(url)
req_text = str(req.content)


def urlParse(text):
    return text[text.find('{'):text.rfind('}') + 1]


parsed_url = json.loads(urlParse(req_text))
print(parsed_url["groupName"])
print(parsed_url["groupCode"])
print(json.dumps(parsed_url["members"]))

group_members = json.loads(json.dumps(parsed_url["members"]))

print('Please choose your name from the following list:\n' + '\n'.join([str(i+1) + '. ' + group_members[i]["identifier"] for i in range(len(group_members))]))

print([[item["identifier"]] for item in group_members])

# msg = 'Please choose your name from the following list:\n' + '\n'.join([str(i + 1) + '.' + group_members[i].split(',')[1] for i in range(len(group_members))]
