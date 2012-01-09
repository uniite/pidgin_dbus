#!/usr/bin/env python

from threading import Thread
import SocketServer


class PushTCPHandler(SocketServer.BaseRequestHandler):    
    def handle(self):
        print "New connection..."
	while True:
		pass


class ServerThread (Thread):
    def run (self):
        HOST, PORT = "192.168.100.120", 35420

        # Create the server, binding to port 35420
        server = SocketServer.TCPServer((HOST, PORT), PushTCPHandler)

        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        print "Waiting for connections..."
        server.serve_forever()


def main ():
    # Start the push TCP server
    server = ServerThread()
    server.start()


if __name__ == "__main__":
    main()
