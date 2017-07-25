#!/usr/bin/python3


import argparse
import contextlib
import json
import requests
import sys
import threading
import time
import zpipe


@contextlib.contextmanager
def nonblocking(lock):
    if not lock.acquire(blocking=False):
        yield False
        return
    try:
        yield lock
    finally:
        lock.release()


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
        self.page_lock = threading.Lock()

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

        if cls == self.largeroom and sender == self.user:
            notification = '{}: {}'.format(instance, message)
        else:
            notification = '{}-{}: {}'.format(sender, instance, message)

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

        if priority == 2:
            self.page(cls, instance, notification)
            return

        request = {'token': self.pushover_token,
                   'user': self.pushover_user,
                   'message': notification,
                   'priority': priority}
        resp = requests.post(
            'https://api.pushover.net/1/messages.json',
            data=request)
        if resp.status_code == 200:
            self.success_info(cls, instance, note_type)
        elif resp.status_code >= 400 and resp.status_code <= 499:
            print(resp.text, file=sys.stderr)
            self.reject_info(cls, instance, False)
        else:
            self.reject_info(cls, instance, True)

    def page(self, cls, instance, notification):
        with nonblocking(self.page_lock) as locked:
            if not locked:
                self.info(cls, instance,
                          '{} is already being paged'.format(self.user))
                return
            request = {'token': self.pushover_token,
                       'user': self.pushover_user,
                       'message': notification,
                       'priority': 2,
                       'retry': self.retry,
                       'expire': self.expire}
            resp = requests.post(
                'https://api.pushover.net/1/messages.json',
                data=request)
            if resp.status_code == 200:
                self.success_info(cls, instance, 'page')
                try:
                    receipt = resp.json()['receipt']
                except (ValueError, KeyError):
                    print(resp.text, file=sys.stderr)
                    return
            elif resp.status_code >= 400 and resp.status_code <= 499:
                print(resp.text, file=sys.stderr)
                self.reject_info(cls, instance, False)
                return
            else:
                self.reject_info(cls, instance, True)
                return

            start_time = time.time()
            while time.time() < start_time + self.expire:
                time.sleep(6)
                resp = requests.get(
                    'https://api.pushover.net/1/receipts/'
                    '{}.json?token={}'.format(receipt, self.pushover_token))
                if resp.status_code == 200:
                    try:
                        j = resp.json()
                        if j['acknowledged']:
                            self.info(cls, instance,
                                      'page acknowledged by {}'.format(
                                    self.user))
                            return
                    except (ValueError, KeyError):
                        print(resp.text, file=sys.stderr)
                        return
                elif resp.status_code >= 400 and resp.status_code <= 499:
                    print(resp.text, file=sys.stderr)
                    return
            self.info(cls, inst, 'page expired unacknowledged')


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-c', '--config-file', default='andromeda.json')
    args = argparser.parse_args()
    with open(args.config_file) as f:
        options = json.load(f)
    Andromeda(options)


if __name__ == '__main__':
    main()
