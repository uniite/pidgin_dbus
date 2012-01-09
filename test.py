#!/usr/bin/env python

def my_func(buddy, old_status, new_status):
    print buddy, old_status, new_status

import dbus, gobject
from dbus.mainloop.glib import DBusGMainLoop
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()

bus.add_signal_receiver(my_func,
                        dbus_interface="im.pidgin.purple.PurpleInterface",
                        signal_name="BuddyStatusChanged")

loop = gobject.MainLoop()
loop.run()
