#!/usr/bin/python3


import json
import requests
import time
import zpipe


class Andromeda(object):
    def __init__(self, options):
        self.name = options.get('name', 'andromeda')
        self.zsig = options.get('zsig', 'a galaxy of stars within me')
        self.blocklist = options.get('blocklist', [])
        self.room = options['room']
        self.largeroom = options.get('largeroom', None)
        self.user = options['user']
        self.realm = options.get('realm', 'ATHENA.MIT.EDU')
        self.pushover_token = options['pushover_token']
        self.pushover_user = options['pushover_user']

        self.last_time = time.time()

        self.zp = zpipe.ZPipe(["zpipe"], self.check_zgram)
        self.zp.subscribe(self.room)
        if self.largeroom:
            self.zp.subscribe(self.largeroom)

    def info(self, cls, instance, message):
        nn = zpipe.Zephyrgram(self.name, cls, instance, None, 'auto', False,
                              [self.zsig, message])
        self.zp.zwrite(nn)

    def check_zgram(self, _, zgram):
        cls = zgram.cls.lower()
        instance = zgram.instance.lower()
        try:
            sender, foundrealm = zgram.sender.split("@")
            _, message = zgram.fields
        except ValueError:
            return

        if foundrealm != self.realm or not zgram.auth:
            return
        if 'auto' in zgram.opcode.lower():
            return

        self.handle(cls, instance, sender, message)

    def check_rate(self):
        if self.last_time + 5 <= time.time():
            self.last_time = time.time()
            return True
        else:
            return False

    def handle(self, cls, instance, sender, message):
        if ((cls == self.room and instance == self.name) or
            cls == self.largeroom):
            if sender in self.blocklist:
                self.info(cls, instance,
                     '{}: you are blocked from sending notifications '
                     'to {}'. format(sender, self.user))
                return
            if not self.check_rate():
                self.info(cls, instance,
                     "{} could not be notified; try again later".format(self.user))
                return

            if cls == self.largeroom and sender == self.user:
                send = '{}: {}'.format(instance, message)
            else:
                send = '{}-{}: {}'.format(sender, instance, message)
            resp = requests.post("https://api.pushover.net/1/messages.json",
                                 data={"token": self.pushover_token,
                                       "user": self.pushover_user,
                                       "message": send})
            if resp.status_code == 200:
                self.info(cls, instance, "notification sent to {}".format(self.user))
            elif resp.status_code >= 400 and resp.status_code <= 499:
                self.info( cls, instance,
                     "{} could not be notified; do not try again".format(self.user))
            else:
                self.info(cls, instance,
                     "{} could not be notified; try again later".format(self.user))
            return


def main():
    with open('andromeda.json') as f:
        options = json.load(f)
    Andromeda(options)


if __name__ == '__main__':
    main()
