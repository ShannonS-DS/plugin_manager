import time, serial, sys, datetime, pprint, logging, socket
sys.path.append('../waggle_protocol/')
from utilities import packetmaker
from multiprocessing import Queue



LOG_FORMAT='%(asctime)s - %(name)s - %(levelname)s - line=%(lineno)d - %(message)s'
formatter = logging.Formatter(LOG_FORMAT)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)


logger = logging.getLogger(__name__)
logger.handlers = []
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


HOST = NCIP #sets to NodeController IP
PORT = 9090 #port for push_server

    
    

class register(object):
    def __init__(self, name, man, mailbox_outgoing):
    	man[name] = 1
        
        ss = system_send(mailbox_outgoing)
        ss.read_mailbox()
        

class system_send(object):
    
    def __init__(self,mailbox_outgoing):
        self.mailbox_outgoing = mailbox_outgoing
        self.socket = None
    
    
    def send(msg):
        if not self.socket:
            try: 
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            except Exception as e: 
                logger.error("Could not create socket to %s:%d : %s" % (HOST, PORT, str(e)))
                raise

        try: 
            self.socket.connect((HOST,PORT))
        except Exception as e: 
            logger.error("Could not connect to %s:%d : %s" % (HOST, PORT, str(e)))
            raise

        try:
            self.socket.send(msg)
        except Exception as e: 
            logger.error("Could not send message to %s:%d : %s" % (HOST, PORT, str(e)))
            raise
            

    def read_mailbox(mailbox_outgoing):

    
    
    
        packet = packetmaker.make_GN_reg(1)
    
        while 1:
            print 'Registration packet made. Sending to 1.'
            try:
                for pack in packet:
                    self.send(pack)
            except Exception as e:
                logger.error("Could not send guest node registration: %s" % (str(e)))
                time.sleep(2)
                continue
    
    
        
        while 1:
         
            msg = mailbox_outgoing.get() # a blocking call.
         
            while 1:
            
                try:
                    self.send(msg)
                except Exception as e: 
                    logger.error("Could not send message to %s:%d : %s" % (HOST, PORT, str(e)))
                    
                    time.sleep(2)
                    continue
                    
                #TODO get ack
            
                logger.debug("Did send message to nodecontroller.")
                if self.socket:
                    self.socket.close()
                
            
                # once message msg has been delivered, the inner loop can be left.    
                break
         
         