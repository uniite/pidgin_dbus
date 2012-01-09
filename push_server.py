#!/usr/bin/env python
import Queue
import threading
import json
import struct
import sys
import SocketServer
import random
import purple_tube



def buddyStatusChanged (i, old_status, new_status):
    print "State changed"
    buddy = purple_tube.getBuddyInfo(i)
    # A fun glitch in AIM
    s1 = purple_tube.purple.PurpleStatusGetName(old_status)
    s2 = purple_tube.purple.PurpleStatusGetName(new_status)
    if s1 == s2 == "Offline":
        buddy.state = "Invisible"
    print "Buddy %s changed state from %s to %s, logged in %s" % (buddy.alias, s1, s2, buddy.loginTime)
    push([buddy])
    


def buddySignedOn (i):
    buddy = purple_tube.getBuddyInfo(i)
    # Ignore certain groups
    if buddy.group in purple_tube.ignore_groups:
        return
    print "Buddy %s signed on at %s" % (buddy.alias, buddy.loginTime)
    push([buddy])


def buddySignedOff (i):
    buddy = purple_tube.getBuddyInfo(i)
    # Ignore certain groups
    if buddy.group in purple_tube.ignore_groups:
        return
    print "Buddy %s signed off" % buddy.alias
    push([buddy])


def conversationUpdated (i, updateType):
    c = purple_tube.getConversationInfo(i)
    print "Conversation %s updated" % c.title
    push([c])


def setupSignals (proxy):
    # Set up the signals for push notification
    proxy.connect_to_signal("BuddyStatusChanged", buddyStatusChanged)
    proxy.connect_to_signal("BuddySignedOn", buddySignedOn)
    proxy.connect_to_signal("BuddySignedOff", buddySignedOff)
    proxy.connect_to_signal("ConversationUpdated", conversationUpdated)


push_server = None
def push (item):
    # Try to push this notification to all the connected clients
    if push_server and hasattr(push_server, "push_handlers"):
        for handler in push_server.push_handlers["handlers"]:
            # Never know when there's a weird connection issue,
            # and we don't want that ruining the notifications.
            try:
                handler.sendData(item)
            except:
                pass


class KeepAliveException (Exception):
    pass


class SimpleJSONHandler(SocketServer.BaseRequestHandler):
    def sendData (self, obj):
        # Grab a type from the object
        # Handle some odd types that lack _type attribute
        if type(obj) == type([]):
            t = obj[0]._type
            if t == "bddy":
                t = "blst"
            elif t == "conv":
                t = "clst"
        else:
            t = obj._type
            del obj._type
        if len(t) != 4 or type(t) != type(""):
            raise ValueError("Invalid '_type' for object.")
        # Convert the object o json
        data = json.dumps(obj)
        # Get the size of the type and data
        n = struct.pack("!i", len(data))
        # Send the type of the data (always 4 bytes)
        # (Send it all at one to avoid threading issues)
        # TODO: Check if this actually works reliably for threading
        return self.request.send(n + t + data)


class ThreadedPushHandler(SimpleJSONHandler):
    
    def handle(self):
        # Let everyone know we're accepting notifications
        self.server.addPushHandler(self)
        print "Handler: %s" % self.server.push_handlers
        # Should always be careful about connection issues
        try:
            # Set up the Push connection
            if self.request.recv(5) == "READY":
                print "Push client connected (%s)" % (self.client_address[0])
            else:
                print "Push connection failed (%s)" % (self.client_address[0])
                raise Exception("Client not ready.")
            
            # We're connected!
            # Push down a current copy of the buddy list to get the client started
            self.sendData(purple_tube.getOnlineBuddies())
            # and a current list of conversations
            self.sendData(purple_tube.getConversations())
            
            # Just chill here, while the DBUS signals take care of the pushing
            while True:
                # Check for keep-alives
                if self.request.recv(9) != "KEEPALIVE":
                    raise KeepAliveException("Keep-alive invalid.")
        # TODO: Actual error handling
        except KeepAliveException:
            pass
        # Clean up
        finally:
            # Stop getting notifications (since the connection is dead)
            self.server.removePushHandler(self)


class ThreadedPullHandler(SimpleJSONHandler):
    
    def handle(self):
        print "Pull client connected (%s)" % (self.client_address[0])
        
        while True:
            # Parse an RPC call
            n = self.request.recv(4)
            n = struct.unpack("!i", n)[0]
            print "Len: %s" % n
            if n > 32768:
                continue
            data = self.request.recv(n)
            print "Data: %s" % data
            data = json.loads(data)
            # Validate the data
            try:
                if not (data.has_key("method") and data.has_key("args")):
                    # TODO: Replace with error
                    raise ValueError("Invalid RPC Call")
                if type(data["args"]) != type([]):
                    raise TypeError("Invalid value for 'args'")
                if not hasattr(purple_tube, data["method"]):
                    ValueError("Method not found")
                method = getattr(purple_tube, data["method"])
                if not hasattr(method, "published"):
                    ValueError("Invalid method")
            except Exception, e:
                print e
                # Send back an error
                msg = "null"
                self.request.send(struct.pack("!i", len(msg)))
                self.request.send(msg)
                continue
            # Execute the call
            args = data["args"]
            result = method(*args)
            # Send back the result
            result = json.dumps(result)
            print "Result: %s" % result
            n = struct.pack("!i", len(result))
            self.request.send(n)
            self.request.send(result)
            

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    def __init__(self, (host, port), Handler):
        SocketServer.TCPServer.__init__(self, (host, port), Handler, bind_and_activate=False)
        self.allow_reuse_address = True
        self.daemon_threads = True
        self.server_bind()
        self.server_activate()
        self.push_handlers = {"handlers": []}
    
    def addPushHandler (self, handler):
        self.push_handlers["handlers"].append(handler)
    
    def removePushHandler (self, handler):
        self.push_handlers["handlers"].remove(handler)
    
    def finish_request(self, request, client_address):
        """Finish one request by instantiating RequestHandlerClass."""
        self.RequestHandlerClass(request, client_address, self)


def startPushServer ():
    global push_server
    # Set up the TCP Server
    HOST, PORT = "0.0.0.0", 35421
    push_server = ThreadedTCPServer((HOST, PORT), ThreadedPushHandler)
    ip, port = push_server.server_address

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=push_server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.setDaemon(True)
    server_thread.start()
    print "Push server running in thread:", server_thread.getName()

    return push_server


def startPullServer ():
    global pull_server
    # Set up the TCP Server
    HOST, PORT = "0.0.0.0", 35422
    pull_server = ThreadedTCPServer((HOST, PORT), ThreadedPullHandler)
    ip, port = pull_server.server_address

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=pull_server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.setDaemon(True)
    server_thread.start()
    print "Pull server running in thread:", server_thread.getName()

    return pull_server


def main ():    
    import dbus
    import gobject
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)
    gobject.threads_init()
    bus = dbus.SessionBus()
    proxy = bus.get_object("im.pidgin.purple.PurpleService", "/im/pidgin/purple/PurpleObject")
    setupSignals(proxy)
    dbus.mainloop.glib.threads_init()    
    DBUSMAINLOOP = gobject.MainLoop()

    print 'Creating DBus Thread'
    DBUSLOOPTHREAD = threading.Thread(name='glib_mainloop', target=DBUSMAINLOOP.run)
    DBUSLOOPTHREAD.setDaemon(True)
    DBUSLOOPTHREAD.start()
    
    # TODO: Watch out for DBUS signal handlers doing things before the
    # push server is ready.
    print 'Starting TCP Servers'
    # Start the push server (for pushing data to the client)
    startPushServer()
    # Start the pull server (for the client to request data)
    startPullServer()
    while True:
        pass


if __name__ == "__main__":
    main()


