#!/usr/bin/python3


import argparse
import json
import requests
import sys
import time
import zpipe


class Andromeda(object):
    def __init__(self, options):
        self.user = options['user']
        self.realm = options.get('realm', 'ATHENA.MIT.EDU')
        self.pushover_token = options['pushover_token']
        self.pushover_user = options['pushover_user']
        self.blocklist = options.get('blocklist', [])
        self.priority = options.get('priority')
        self.retry = options.get('retry', 30)
        self.expire = options.get('expire', 600)
        self.name = options.get('name', 'andromeda')
        self.zsig = options.get('zsig', 'a galaxy of stars within me')
        self.room = options.get('room', self.user)
        self.largeroom = options.get('largeroom', None)

        self.last_time = time.time()

        self.zp = zpipe.ZPipe(['zpipe'], self.handle)
        self.zp.subscribe(self.room)
        if self.largeroom:
            self.zp.subscribe(self.largeroom)

    def info(self, cls, instance, message):
        time.sleep(1)
        nn = zpipe.Zephyrgram(self.name, cls, instance, None, 'auto', False,
                              [self.zsig, message])
        self.zp.zwrite(nn)

    def reject_info(self, cls, instance, again):
        self.info(cls, instance,
                  '{} could not be notified; {}'.format(
                self.user,
                'try again later' if again else 'do not try again'))

    def success_info(self, cls, instance, note_type):
        self.info(cls, instance,
                  '{} sent to {}'.format(note_type, self.user))

    def check_rate(self):
        if self.last_time + 5 <= time.time():
            self.last_time = time.time()
            return True
        else:
            return False

    def handle(self, _, zgram):
        cls = zgram.cls.lower()
        instance = zgram.instance.lower()
        opcode = zgram.opcode.lower()

        if 'auto' in opcode:
            return
        if not ((cls == self.room and instance == self.name) or
                cls == self.largeroom):
            return

        try:
            sender, foundrealm = zgram.sender.split('@')
            _, message = zgram.fields
        except ValueError:
            return
        if foundrealm != self.realm or not zgram.auth:
            return

        if sender in self.blocklist:
            self.info(cls, instance,
                      '{}: you are blocked from sending notifications '
                      'to {}'.format(sender, self.user))
            return

        priority = 2 if 'page' in opcode else 1 if 'urgent' in opcode else 0
        note_type = {0: 'notification',
                     1: 'urgent notification',
                     2: 'page'}[priority]
        if priority > 0 and not self.priority:
            self.info(cls, instance,
                      '{} has disabled {}s'.format(self.user, note_type))
            return

        if not self.check_rate():
            self.reject_info(cls, instance, True)
            return

        if cls == self.largeroom and sender == self.user:
            notification = '{}: {}'.format(instance, message)
        else:
            notification = '{}-{}: {}'.format(sender, instance, message)

        request = {'token': self.pushover_token,
                   'user': self.pushover_user,
                   'message': notification,
                   'priority': priority}
        if priority == 2:
            request.update({'retry': self.retry,
                            'expire': self.expire})

        resp = requests.post(
            'https://api.pushover.net/1/messages.json',
            data=request)

        if resp.status_code == 200:
            self.success_info(cls, instance, note_type)
        elif resp.status_code >= 400 and resp.status_code <= 499:
            print(resp.json(), file=sys.stderr)
            self.reject_info(cls, instance, False)
        else:
            self.reject_info(cls, instance, True)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-c', '--config-file', default='andromeda.json')
    args = argparser.parse_args()
    with open(args.config_file) as f:
        options = json.load(f)
    Andromeda(options)


if __name__ == '__main__':
    main()
