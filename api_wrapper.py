import json
import lib.requests as requests


class TelegramApiWrapper():

    def __init__(self, token):
        self.token = token

    # Sends a POST request with a JSON payload to the specified URL
    # Returns the JSON response
    def _postJson(self, json, url):
        r = requests.post(url, json=json)
        return r.json()

    # Sends a message represented in JSON
    def sendMessage(self, json):
        return self._postJson(json, self.getUrl("sendMessage"))

    def getUrl(self, method):
        return "https://api.telegram.org/bot{}/{}".format(self.token, method)

    def getMe(self):
        return self._postJson({}, self.getUrl("getMe"))

    def setWebhook(self, webhookUrl):
        return self._postJson({"url": webhookUrl}, self.getUrl("setWebhook"))

    def clearWebhook(self):
        return self.setWebhook("")
