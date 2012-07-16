#!/usr/bin/python2.4
#
# Copyright 2011 Google Inc. All Rights Reserved.

# pylint: disable-msg=C6310

"""WebRTC Demo

This module demonstrates the WebRTC API by implementing a simple video chat app.
"""

import datetime
import logging
import os
import random
import re
import wsgiref.handlers
from google.appengine.api import channel
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

MAX_NR_USERS = 2

def generate_random(len):
    word = ''
    for i in range(len):
        word += random.choice('0123456789')
    return word

def sanitize(key):
    return re.sub("[^a-zA-Z0-9\-]", "-", key);

def make_token(room, user):
    return room.key().id_or_name() + '/' + user

def make_pc_config(stun_server):
    if stun_server:
        return "STUN " + stun_server
    else:
        return "STUN stun.l.google.com:19302"

class Room(db.Model):
	
    users = db.StringListProperty()

    def __str__(self):
        str = "["
        if len(self.users) > 0:
        	for u in self.users:
        		str += ", " + u
        str += "]"
        return str

    def get_occupancy(self):
        return len(self.users)

	#Check how this is used
    def get_other_user(self, user):
        if user == self.users[0]:
            return self.users[1]
        elif user == self.users[1]:
            return self.users[0]
        else:
            return None

    def has_user(self, user):
        return self.index_of(user) >= 0
        
    def index_of(self, user):
    	index = -1
    	if not user:
    		return index
    		
    	for i in range(len(self.users)):
    		if self.users[i] == user:
    			index = i
    			break
        return index

    def add_user(self, user):
    
    	#Check if the user is already in the list
    	if self.has_user(user):
    		return
    
    	#Add new user if there is capacity
    	if len(self.users) <= MAX_NR_USERS:
    		self.users.append(user)
    	else:
    		raise RuntimeError('room is full')
    	
        self.put()

    def remove_user(self, user):
    	index = self.index_of(user)
    	if index >= 0:
    		self.users.remove(index)
    		
        if len(self.users > 0):
            self.put()
        else:
            self.delete()

class ConnectPage(webapp.RequestHandler):
    def post(self):
        key = self.request.get('from')
        room_key, user = key.split('/');
        logging.info('User ' + user + ' connected to room ' + room_key)


class DisconnectPage(webapp.RequestHandler):
    def post(self):
        key = self.request.get('from')
        room_key, user = key.split('/');
        logging.info('Removing user ' + user + ' from room ' + room_key)
        room = Room.get_by_key_name(room_key)
        if room and room.has_user(user):
            other_user = room.get_other_user(user)
            room.remove_user(user)
            logging.info('Room ' + room_key + ' has state ' + str(room))
            if other_user:
                channel.send_message(make_token(room, other_user), 'BYE')
                logging.info('Sent BYE to ' + other_user)
        else:
            logging.warning('Unknown room ' + room_key)


class MessagePage(webapp.RequestHandler):
    def post(self):
        message = self.request.body
        room_key = self.request.get('r')
        room = Room.get_by_key_name(room_key)
        if room:
            user = self.request.get('u')
            other_user = room.get_other_user(user)
            if other_user:
                # special case the loopback scenario
                if other_user == user:
                    message = message.replace("\"OFFER\"",
                        "\"ANSWER\",\n   \"answererSessionId\" : \"1\"")
                    message = message.replace("a=crypto:0 AES_CM_128_HMAC_SHA1_32",
                        "a=xrypto:0 AES_CM_128_HMAC_SHA1_32")
                channel.send_message(make_token(room, other_user), message)
                logging.info('Delivered message to user ' + other_user);
        else:
            logging.warning('Unknown room ' + room_key)


class MainPage(webapp.RequestHandler):
    """The main UI page, renders the 'index.html' template."""

    def get(self):
        """Renders the main page. When this page is shown, we create a new
 channel to push asynchronous updates to the client."""
        room_key = sanitize(self.request.get('r'));
        debug = self.request.get('debug')
        stun_server = self.request.get('ss');
        if not room_key:
            room_key = generate_random(8)
            redirect = '/?r=' + room_key
            if debug:
                redirect += ('&debug=' + debug)
            if stun_server:
                redirect += ('&ss=' + stun_server)
            self.redirect(redirect)
            logging.info('Redirecting visitor to base URL to ' + redirect)
            return

        user = None
        initiator = 0
        room = Room.get_by_key_name(room_key)
        if not room and debug != "full":
            # New room.
            user = generate_random(8)
            room = Room(key_name = room_key)
            room.add_user(user)
            if debug != "loopback":
                initiator = 0
            else:
                room.add_user(user)
                initiator = 1
        elif room and room.get_occupancy() == 1 and debug != "full":
            # 1 occupant.
            user = generate_random(8)
            room.add_user(user)
            initiator = 1
        else:
            # 2 occupants (full).
            path = os.path.join(os.path.dirname(__file__), 'full.html')
            self.response.out.write(template.render(path, { 'room_key': room_key }));
            logging.info('Room ' + room_key + ' is full');
            return

        room_link = 'http://localhost:8080/?r=' + room_key
        if debug:
            room_link += ('&debug=' + debug)
        if stun_server:
            room_link += ('&ss=' + stun_server)

        token = channel.create_channel(room_key + '/' + user)
        pc_config = make_pc_config(stun_server)
        template_values = {'token': token,
                           'me': user,
                           'room_key': room_key,
                           'room_link': room_link,
                           'initiator': initiator,
                           'pc_config': pc_config
        }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))
        logging.info('User ' + user + ' added to room ' + room_key);
        logging.info('Room ' + room_key + ' has state ' + str(room))

"""
application = webapp.WSGIApplication([
    ('/', MainPage),
    ('/message', MessagePage),
    ('/_ah/channel/connected/', ConnectPage),
    ('/_ah/channel/disconnected/', DisconnectPage)
], debug=True)


def main():
    run_wsgi_app(application)
"""

def main():
    application = webapp.WSGIApplication(
        [('/', MainPage),
            ('/message', MessagePage),
            ('/_ah/channel/connected/', ConnectPage),
            ('/_ah/channel/disconnected/', DisconnectPage)],
        debug=True)

    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()