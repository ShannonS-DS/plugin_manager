#!/usr/bin/env python3

# -*- coding: utf-8 -*-
import logging
from . import coresense
import datetime
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class register(object):

    def __init__(self, name, man, mailbox_outgoing):
        
        env = envsense(name, man, mailbox_outgoing)
        
        env.run()
    


epoch = datetime.datetime.utcfromtimestamp(0)

def epoch_time(dt):
    return (dt - epoch).total_seconds() * 1000.0



class envsense(object):

    plugin_name = 'envsense'
    plugin_version = '2'

    def __init__(self, name, man, mailbox_outgoing):
        self.name = name
        self.man = man
        self.outqueue = mailbox_outgoing
        

    def run(self):
        self.running = True
        while self.running:
            device = '/dev/waggle_coresense'
            logger.debug("try to connect to device "+device)
            
            try:
                with coresense.create_connection(device) as conn:
                    while self.running:
                
                        try:
                            msg = conn.recv()
                        except Exception as e:
                            logger.error("(Inner loop) Error of type %s: %s" % (str(type(e)), str(e)))
                            msg = None
                            time.sleep(1)
                            break
                    
                        if msg:    
                            self.handle_message(msg)
            except Exception as e:
                logger.error("(Outer loop) Error of type %s: %s" % (str(type(e)), str(e)))
            
            time.sleep(10)

    def stop(self):
        self.running = False

    def handle_message(self, message):
        logger.info(message)
        for entry in message.entries:
            self.handle_message_entry(message, entry)

    def handle_message_entry(self, message, entry):
        
        
        timestamp_epoch =  epoch_time(message.timestamp)
        
        
        self.outqueue.put([
            str(message.timestamp.date()).encode('iso-8859-1'),
            self.plugin_name.encode('iso-8859-1'),
            self.plugin_version.encode('iso-8859-1'),
            'default'.encode('iso-8859-1'),
            '%d' % (timestamp_epoch),
            entry.sensor.encode('iso-8859-1'),
            'meta.txt'.encode('iso-8859-1'),
            format_entry_values(entry),
        ])

    @property
    def running(self):
        return self.man[self.name] != 0

    @running.setter
    def running(self, state):
        self.man[self.name] = 1 if state else 0



def format_entry_values(entry):
    return ['{}:{}'.format(key, value).encode('iso-8859-1') for key, value in entry.values]
