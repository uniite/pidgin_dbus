#!/usr/bin/env python

import dbus, gobject
from dbus.mainloop.glib import DBusGMainLoop
import json


# Set up a dbus connection for retrieving data
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
obj = bus.get_object("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")
purple = dbus.Interface(obj, "im.pidgin.purple.PurpleInterface")


# Groups to ignore
ignore_groups = []
try:
    me = purple.PurpleFindGroup("Me")
    ignore_groups.append(me)
except:
    pass


def published (x):
    x.published = True
    return x

    
# The base object for all returned data (except lists)
class ObjDict (dict):
	"""
	An object whos attributes are items in a dictionary.
	This allows for objects based on this class to be JSON-serializable.
	"""
	
	def __getattr__ (self, name):
		return self[name]

	def __setattr__ (self, name, value):
		self[name] = value

## PurpleMessageFlags
PURPLE_MESSAGE_SEND = 0x0001
PURPLE_MESSAGE_RECV = 0x0002
PURPLE_MESSAGE_SYSTEM = 0x0004
PURPLE_MESSAGE_AUTO_RESP = 0x0008
PURPLE_MESSAGE_ACTIVE_ONLY = 0x0010
PURPLE_MESSAGE_NICK = 0x0020
PURPLE_MESSAGE_NO_LOG = 0x0040
PURPLE_MESSAGE_WHISPER = 0x0080
PURPLE_MESSAGE_ERROR = 0x0200
PURPLE_MESSAGE_DELAYED = 0x0400
PURPLE_MESSAGE_RAW = 0x0800
PURPLE_MESSAGE_IMAGES = 0x1000
PURPLE_MESSAGE_NOTIFY = 0x2000
PURPLE_MESSAGE_NO_LINKIFY = 0x4000
PURPLE_MESSAGE_INVISIBLE = 0x8000


@published
def getBuddyList ():
	return purple.PurpleBlistGetBuddies()


@published
def getOnlineBuddies ():
    # Get the full buddy list
    b = [getBuddyInfo(x) for x in getBuddyList()]
    # Filter out Offline or irellevant buddies
    b = [x for x in b if (x.state != "Offline" and not x.group in ignore_groups)]
    # Sort the list by buddy alias
    b.sort(lambda x, y: cmp(x.alias, y.alias))
    return b


@published
def getBuddyInfo (i):
    buddy = ObjDict()
    buddy._type = "bddy"
    buddy.id = i
    buddy.alias = purple.PurpleBuddyGetContactAlias(i)
    buddy.name = purple.PurpleBuddyGetName(i)
    buddy.account = purple.PurpleBuddyGetAccount(i)
    buddy.group = purple.PurpleBuddyGetGroup(i)
    presence = purple.PurpleBuddyGetPresence(i)
    buddy.loginTime = purple.PurplePresenceGetLoginTime(presence)
    buddy.idleTime = purple.PurplePresenceGetIdleTime(presence)
    status = purple.PurplePresenceGetActiveStatus(presence)
    if status:
        buddy.state = purple.PurpleStatusGetName(status)
        buddy.status = purple.PurpleStatusGetAttrString(status, "message")
    return buddy


@published
def getConversationList ():
    return purple.PurpleGetConversations()


@published
def getConversations ():
    c = getConversationList()
    c = [getConversationInfo(x) for x in c]
    c = [x for x in c if x.type in ("im", "chat")]
    return c


@published
def getMessage (i, c=0):
    msg = ObjDict()
    msg.id = i
    msg.who = purple.PurpleConversationMessageGetSender(i)
    msg.what = purple.PurpleConversationMessageGetMessage(i)
    msg.when = purple.PurpleConversationMessageGetTimestamp(i)
    msg.flags = purple.PurpleConversationMessageGetFlags(i)
    msg.conv = c
    return msg
    

@published
def getConversationInfo (i):
    conv = ObjDict()
    conv._type = "conv"
    conv.id = i
    conv.type = purple.PurpleConversationGetType(i)
    conv.title = purple.PurpleConversationGetTitle(i)
    conv.im = purple.PurpleConversationGetImData(i)
    conv.chat = purple.PurpleConversationGetChatData(i)
    conv.name = purple.PurpleConversationGetName(i)
    conv.account = purple.PurpleConversationGetAccount(i)
    conv.messages = [] #purple.PurpleConversationGetMessageHistory(i)
    # These dbus data types are tricky
    if len(conv.messages) > 2:
        c = []
        for i in range(2):
            c.append(conv.messages[i])
        conv.messages = c
    conv.messages = [getMessage(x, i) for x in conv.messages]
    # This method has a tendency to backfire
    try:
        conv.unread = purple.PurpleConversationGetData(i, "unseen-count")
    except:
        conv.unread = 0
    # Figure out the conversation type
    if conv.type == 1:
            conv.type = "im"
    elif conv.type == 2:
            conv.type = "chat"
    else:
        print "Unknown conversation type for %s" % i
    # Figure out if there are any important unread messages
    conv.important = False
    if conv.unread > 0:
        if conv.type == "chat":
            nick = purple.PurpleConvChatGetNick(conv.chat)
            for msg in conv.messages:
                if msg.flags & PURPLE_MESSAGE_NICK:
                    conv.important = True
                    break
        else:
            conv.important = True
    
    # TODO: Fix this
    del conv["messages"]

    return conv
        
    

    


