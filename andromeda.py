#!/usr/bin/python


import zephyr
import re
import requests
import time


name = "andromeda"
blocklist = []
room = "ROOM"
largeroom = "LARGEROOM"
user = "USER"
realm = "ATHENA.MIT.EDU"

def info(cls, instance, message):
    nn = zephyr.ZNotice()
    nn.cls = cls
    nn.instance = instance
    nn.sender = name
    nn.fields.append(message)
    nn.send()

def mainloop(cb):
    subs = zephyr.Subscriptions()
    subs.add((room,"*","*"))
    subs.add(("SANDBOX","*","*"))
    subs.add((largeroom,"*","*"))
    while True:
		notice = zephyr.receive(True)
		if "@" not in notice.sender: continue
		sender, foundrealm = notice.sender.split("@")
		if realm == foundrealm and notice.auth:
			cb(notice.cls, notice.instance, sender, notice.fields[-1])

last_time = time.time()
def check_rate():
	global last_time
	if last_time + 5 <= time.time():
		last_time = time.time()
		return True
	else:
		return False

def handle(cls, instance, sender, message):
	if (cls == room and instance == name) or cls == largeroom:
		if sender in blocklist:
			info(cls, instance, sender + ": you are blocked from sending notifications to " + user)
		elif check_rate():
			if cls == largeroom and sender == user:
				send = "%s: %s" % (instance, message)
			else:
				send = "%s-%s: %s" % (sender, instance, message)
			resp = requests.post("https://api.pushover.net/1/messages.json", data={"token": "<TOKEN>", "user": "<USER>", "message": send})
			if resp.status_code == 200:
				info(cls, instance, "notification sent to " + user)
			elif resp.status_code >= 400 and resp.status_code <= 499:
				info(cls, instance, user + " could not be notified; do not try again")
			else:
				info(cls, instance, user + " could not be notified; try again later")
		else:
			info(cls, instance, user + " could not be notified; try again later")
	elif (cls == room or cls == "SANDBOX") and sender == user:
		message = message.replace("\n", " ").replace("\t", " ").strip()
		while "  " in message:
			message = message.replace("  ", " ")
		match = re.match("^(i,i )?\"([^\"]+)\"$", message)
		if match:
			message = match.group(2)
		match = re.match("^[(]([^()]+)[)]$", message)
		if match:
			message = match.group(1)
		if message.startswith("I suppose "):
			message = message.split(" ",2)[2]
		if message.startswith("I think "):
			message = message.split(" ",2)[2]
		if message.lower().startswith("okay ") or message.startswith("okay, "):
			message = message.split(" ",1)[1]
		match = re.match("^[Oo]+(h|ps) ([a-zA-Z0-9 :]+)$", message)
		if match:
			message = match.group(2)
		if message.lower().startswith("maybe "):
			message = message.split(" ",1)[1]
		if message.lower().startswith("speaking of which "):
			message = message.split(" ",3)[3]
		match = re.match("^I should (really|probably) ([a-z A-Z0-9:]+)( tbh| at some point)?[.]*$", message)
		if match:
			time.sleep(2)
			info(cls, instance, match.group(2)[0].upper() + match.group(2)[1:] + "!")
		else:
			match = re.match("^I should be doing ([a-z A-Z0-9:]+)( tbh| at some point)?[.]*$", message)
			if match:
				time.sleep(2)
				info(cls, instance, "Do " + match.group(1) + "!")

mainloop(handle)
