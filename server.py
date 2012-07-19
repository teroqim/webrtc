#!/usr/bin/python2.7

import datetime
import logging
import os
import random
import re
import webapp2
import sys

from google.appengine.api import channel
from google.appengine.ext import db
from google.appengine.ext.webapp import template

MAX_NR_USERS = 2

def generate_random(len):
    word = ''
    for i in range(len):
        word += random.choice('0123456789')
    return word

def sanitize(key):
    return re.sub("[^a-zA-Z0-9\-]", "-", key);

def make_client_id(room, user):
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
    	if len(self.users) <= 1:
    		return None
    		
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
    	if not user:
    		return
    	try:
    		logging.info('Removing user: ' + str(user))
    		self.users.remove(user)
    		if len(self.users) > 0:
    			self.put()
    		else:
    			self.delete()
    	except:
    		logging.info("Silent error trying to delete user from room. " + str(sys.exc_info()))

class ConnectPage(webapp2.RequestHandler):
    def post(self):
        key = self.request.get('from')
        room_id, user = key.split('/');
        logging.info('User ' + user + ' connected to room ' + room_id)


class DisconnectPage(webapp2.RequestHandler):
    def post(self):
        key = self.request.get('from') #contains clientId
        room_id, user = key.split('/');
        logging.info('Removing user ' + user + ' from room ' + room_id)
        room = Room.get_by_key_name(room_id)
        if room and room.has_user(user):
            other_user = room.get_other_user(user)
            room.remove_user(user)
            logging.info('Room ' + room_id + ' has state ' + str(room))
            if other_user:
                channel.send_message(make_client_id(room, other_user), 'BYE')
                logging.info('Sent BYE to ' + other_user)
        else:
            logging.warning('Unknown room ' + room_id)


class MessagePage(webapp2.RequestHandler):
    def post(self):
        message = self.request.body
        room_id = self.request.get('r')
        room = Room.get_by_key_name(room_id)
        if room:
            user = self.request.get('u')
            other_user = room.get_other_user(user)
            if other_user:
                channel.send_message(make_client_id(room, other_user), message)
                logging.info('Delivered message to user ' + other_user);
        else:
            logging.warning('Unknown room ' + room_id)


class MainPage(webapp2.RequestHandler):
    """The main UI page, renders the 'index.html' template."""

    def get(self):
        """Renders the main page. When this page is shown, we create a new
 channel to push asynchronous updates to the client."""
        room_id = sanitize(self.request.get('r'));
        if not room_id:
        	#Redirect visitor to new room with random id
            room_id = generate_random(8)
            redirect = '/?r=' + room_id
            self.redirect(redirect)
            logging.info('Redirecting visitor to base URL to ' + redirect)
            return

        user = None
        initiator = 0
        #Get room from datastore
        room = Room.get_by_key_name(room_id)
        if not room: 
            # New room.
            user = generate_random(8)
            room = Room(key_name = room_id)
            room.add_user(user)
            initiator = 0
        elif room and room.get_occupancy() == 1: 
            # 1 occupant.
            user = generate_random(8)
            room.add_user(user)
            initiator = 1
        else:
            # 2 occupants (full).
            path = os.path.join(os.path.dirname(__file__), 'full.html')
            self.response.out.write(template.render(path, { 'room_id': room_id }));
            logging.info('Room ' + room_id + ' is full');
            return

        token = channel.create_channel(make_client_id(room, user))
        pc_config = make_pc_config('')
        logging.info('Room id: ' + str(room_id))
        template_values = {'token': token,
                           'me': user,
                           'room_id': room_id,
                           'initiator': initiator,
                           'pc_config': pc_config
        }
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))
        logging.info('User ' + user + ' added to room ' + room_id);
        logging.info('Room ' + room_id + ' has state ' + str(room))


app = webapp2.WSGIApplication(
        [('/', MainPage),
            ('/message', MessagePage),
            ('/_ah/channel/connected/', ConnectPage),
            ('/_ah/channel/disconnected/', DisconnectPage)],
        debug=True)
