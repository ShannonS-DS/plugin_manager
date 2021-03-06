#!/usr/bin/env python3
import multiprocessing
import time
import sys
import re
import os
import socket
import json
import argparse
import select
import datetime
import logging
import logging.handlers
from multiprocessing import Queue
import plugins
import lib.run_plugins_multi
from waggle.protocol.utils.pidfile import PidFile, AlreadyRunning


loglevel = logging.DEBUG
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - line=%(lineno)d - %(message)s'
LOG_FILENAME = "/var/log/waggle/plugin_manager.log"
pid_file = "/var/run/waggle/plugin_manager.pid"

formatter = logging.Formatter(LOG_FORMAT)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(loglevel)
root_logger.handlers = []
root_logger.addHandler(handler)

logger = logging.getLogger(__name__)
logger.handlers = []


class PluginManagerAPI:
    def __init__(self):
        self.plug = lib.run_plugins_multi.plugin_runner()
        self.system_plugins={'system_receive': 1, 'system_send': 1 ,'system_router': 1 }

        self.command_functions = {
            "list" : {  'function' : self.command_list_plugins_full,
                        'description' : 'list plugins'
            },
            "log" : {   'function' : None,
                        'description' : 'get message stream'
            },
            "help" : {  'function' : self.command_help,
                        'description' : ''
            },
            "start" : { 'function' : self.command_start_plugin,
                        'arguments' : '<plugin>',
                        'description' : 'start plugin'
            },
            "stop" : {  'function' : self.command_stop_plugin,
                        'arguments' : '<plugin>',
                        'description' : 'stop plugin'
            },
            "kill" : {  'function' : self.command_kill_plugin,
                        'arguments' : '<plugin>',
                        'description' : 'kill plugin'
            },
            "pause" : { 'function' : self.command_pause_plugin,
                        'arguments' : '<plugin>',
                        'description' : 'pause plugin'
            },
            "unpause" : {
                        'function' : self.command_unpause_plugin,
                        'arguments' : '<plugin>',
                        'description' : 'unpause plugin'
            },
            "get_pid" : {
                        'function' : self.command_plugin_pid,
                        'arguments' : '<plugin>',
                        'description' : 'get PID of plugin'
            },
            "info" : {  'function' : self.command_plugin_info,
                        'arguments' : '<plugin>',
                        'description' : 'get info about plugin'
            },
            "startall" : {  'function' : self.command_start_all,
                        'description' : 'start all plugins'
            },
            "stopall" : {  'function' : self.command_stop_all,
                        'description' : 'stop all plugins'
            },
            "killall" : {  'function' : self.command_kill_all,
                        'description' : 'kill all plugins'
            }

        }
        self.blacklist = self.get_list('plugins/blacklist.txt')
        self.whitelist = self.get_list('plugins/whitelist.txt')

        logger.info('Automatically starting whitelisted plugins...')
        self.command_start_whitelist()
        logger.info('whitelisted plugins started.')



    def manip_list(self, plugin, listtype, manipulation):
        """
        Takes a plugin name and adds or removes it from the blacklist or whitelist, as specified by caller
        """
        if (listtype == "whitelist"):
            file = open('plugins/whitelist.txt','r+')
            if (self.on_blacklist(plugin)):
                logger.error('Error: Plugin %s on blacklist. Cannot be on both lists.' % (plugin))
        elif (listtype == "blacklist"):
            file = open('plugins/blacklist.txt','r+')
            if (on_whitelist(plugin)):
                logger.error( 'Error: Plugin %s on whitelist. Cannot be on both lists.' % (plugin))
        li = file.read()
        li = re.split('\n', li)
        if (manipulation == "rm"):
            if (plugin in li):
                li.remove(plugin)
                li = "\n".join(li)
                file.seek(0)
                file.truncate()
                file.write(li)
                return 1
            else:
                return 0
        if (manipulation == "add"):
            if (not (plugin in li)):
                li.insert(0,plugin)
                li = "\n".join(li)
                file.seek(0)
                file.write(li)
                return 1
            else:
                return 0

    def get_list(self, filename):
        mylist = open(filename).read().strip()
        mylist = re.split('\n', mylist)
        mylist = [f for f in mylist if f]
        mylist = [x for x in mylist if not x.startswith("#")]
        return mylist

    def get_blacklist(self):
        return self.blacklist

    def get_whitelist(self):
        return self.whitelist


    #Checks if the plugin is on the blacklist
    def on_blacklist(self, name):
        return (name in self.get_blacklist())

    #Checks if the plugin is on the whitelist
    def on_whitelist(self, name):
        return (name in self.get_whitelist())

    #### commands ####


    def command_list_plugins_full(self):
        """
        Lists available plugins, if they are active, and whether they are present on the whitelist and blacklist
        """
        headers                                                       = ["plugin", "instance", "active", "whitelist", "blacklist"]
        system_table                                                  = []
        user_table                                                    = []

        #example: tabulate(table, headers, tablefmt = "fancy_grid")


        for name in plugins.__all__:
            if name in self.system_plugins:
                table                                                 = system_table
            else:
                table                                                 = user_table
            plugin                                                    = getattr(plugins, name)
            active                                                    = 0
            for j in self.plug.jobs:
                if (j.name == name):
                    #print 'Plugin', name, 'is active. Whitelist:', on_whitelist(name), '  |  Blacklist:', on_blacklist(name)
                    table.append([name, "", True, self.on_whitelist(name), self.on_blacklist(name)])
                    active                                            = 1
                    break
            if (not active):
                #print 'Plugin', name, 'is inactive. Whitelist:', on_whitelist(name), '  |  Blacklist:', on_blacklist(name)
                table.append([name, "", False, self.on_whitelist(name), self.on_blacklist(name)])



        results                                                       = {}
        results['objects']                                            = []

        system_obj                                                    = {}
        system_obj['type']                                            = 'table'
        system_obj['title']                                           = 'System plugins'
        system_obj['header']                                          = headers
        system_obj['data']                                            = system_table


        user_obj                                                      = {}
        user_obj['type']                                              = 'table'
        user_obj['title']                                             = 'User plugins'
        user_obj['header']                                            = headers
        user_obj['data']                                              = user_table

        results['objects'].append(system_obj)
        results['objects'].append(user_obj)

        results['status']                                             = 'success'
        return json.dumps(results)


        #client_sock.sendall(tabulate(user_table, headers, tablefmt   = "fancy_grid"))

    def create_status_message(self, status, message):
        result = {}
        result['status'] = self.status_code_to_text(status)
        result['message'] = message

        return json.dumps(result)

    def status_code_to_text(self, code):
        if code==1:
            return 'success'
        return 'error'

    def command_start_plugin(self, plugin):

        if (self.on_blacklist(plugin)):
            message = 'Cannot start plugin %s because it is blacklisted.' % (plugin)

            return self.create_status_message(0, message)

        status, message = self.plug.start_plugin(plugin)

        return self.create_status_message(status, message)



    def command_stop_plugin(self, plugin):
        status, message =  self.plug.stop_plugin(plugin)
        return self.create_status_message(status, message)


    def command_kill_plugin(self, plugin):
        status, message =  self.plug.kill_plugin(plugin)
        return self.create_status_message(status, message)



    def command_pause_plugin(self, plugin):
        status, message = self.plug.pause_plugin(plugin)
        return self.create_status_message(status, message)

    def command_unpause_plugin(self, plugin):
        status, message =  self.plug.unpause_plugin(plugin)
        return self.create_status_message(status, message)


    def command_plugin_pid(self, plugin):
        status, message = self.plug.plugin_pid(plugin)
        return self.create_status_message(status, message)


    def command_plugin_info(self, plugin):
        status, message =  self.plug.plugin_info(plugin)
        return self.create_status_message(status, message)



    def command_start_all(self):

        blacklist = self.get_blacklist()
        fail = 0
        for plugin in plugins.__all__:
            if (not (plugin in blacklist)):
                start, msg = self.plug.start_plugin(plugin)
                logger.info("Starting plugin %s" % (plugin))
                if not start:
                    logger.error( 'Failed to start plugin %s ' % (plugin))
                    fail = fail + 1
        if (fail == 0):
            return self.create_status_message(1, "Started all non-blacklisted plugins.")


        return self.create_status_message(0, "Attempted to start all non-blacklisted plugins, failed to start " + fail)



    def command_kill_all(self):
        status, message =  self.plug.kill_all()
        return self.create_status_message(status, message)


    def command_stop_all(self):
        status, message =  self.plug.stop_all()
        return self.create_status_message(status, message)

    def command_start_whitelist(self):
        #status, message =  self.start_whitelist()

        whitelist = self.get_whitelist()
        fail = 0
        for name in whitelist:
            logger.info("Starting plugin %s" % (name))
            start = self.plug.start_plugin(name)
            if (not start) and (not name == ""):
                logger.error('Failed to start plugin %s' % (name))
                fail = fail + 1
            else:
                logger.debug('Started plugin %s' % (name))
        if (fail == 0):

            return self.create_status_message(1, "Started all %d whitelisted plugins." % (len(whitelist)))

        return self.create_status_message(0,  "Attempted to start all whitelisted plugins, failed to start %d plugins" % (fail))

    def command_pause_all(self):
        status, message =  self.plug.pause_all()
        return self.create_status_message(status, message)


    def command_unpause_all(self):
        status, message =  self.plug.unpause_all()
        return self.create_status_message(status, message)


    def command_info_all(self):
        status, message =  self.plug.info_all()
        return self.create_status_message(status, message)


    def command_help(self):

        headers = ['command', 'arguments', 'description']

        help_table_data=[]

        for i in self.command_functions:
            args = ''
            if 'arguments' in self.command_functions[i]:
                args = self.command_functions[i]['arguments']
            help_table_data.append([i, args, self.command_functions[i]['description'] ] )
        result = {}
        result['objects']=[]

        help_table                                                      = {}
        help_table['type']                                              = 'table'
        help_table['title']                                             = 'help overview'
        help_table['header']                                            = headers
        help_table['data']                                              = help_table_data
        result['objects'].append(help_table)

        result['status']    = 'success'

        return json.dumps(result)


    def message_log_process(self, client_sock, queue):
        """
        Process to send data to remote listeners.
        """

        client_sock.setblocking(0)

        logger.debug('process for listener is running')
        counter=0
        while 1:
            try:
                msg = queue.get()
            except Queue.Empty:
                msg = None
                time.sleep(1)

            if msg:
                counter=0
                logger.info("message for listener: %s" % (str(msg)))
                try:
                    client_sock.sendall(str(msg))
                except Exception as e:
                    logger.warning("Could not send message to listener, closing. %s" % (str(e)) )
                    break
            else:
                # this will check connection every 5 seconds if no data comes in.
                counter=counter+1
                if counter >= 5:
                    try:
                        data = client_sock.recv(128)
                    except Exception as e:
                        logger.info("connection seems to be closed: %s" % (str(e)))
                        break
                    counter = 0
        logger.info("Closing listener process: %d" % (os.getpid()))
        sys.exit(0)


    def do_command(self, command_line):

        command = command_line[0]

        try:
            command_function = self.command_functions[command]['function']
        except KeyError:
            loggr.debug("Command %s unknown." % (command))
            return '{"error":"command %s is unknown"}' % (command)
            sys.exit(1)

        arguments = command_line[1:]
        if len(arguments) > 0:
            logger.debug("with %d arguments" % (len(arguments)))
            try:
                results = command_function(*arguments)
            except Exception as e:
                logger.error("error in command_function: %s" % (str(e)))
                return
            return results
        else:
            logger.debug("no arguments")
            try:
                results = command_function()
            except Exception as e:
                logger.error("error in command_function: %s" % (str(e)))
                return

            return results


    def listen_to_socket(self):

        socket_file = '/tmp/plugin_manager'

        if os.path.exists(socket_file): #checking for the file
            os.remove(socket_file)


        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)


        server_sock.bind(socket_file)

        # listen for clients
        server_sock.listen(5)

        read_list = [server_sock]

        timeout_reading = 10
        while True:

            logger.debug("waiting for data")

            readable, writable, errored = select.select(read_list, [], [], timeout_reading)



            if len(readable) == 0:
                logger.debug("no command after 10 seconds")
                # this will join all children and thus remove zombies
                multiprocessing.active_children()
                continue


            try:
                client_sock, address = server_sock.accept()
            except KeyboardInterrupt:
                logger.info("Shutdown requested...exiting")
                #self.stop()
                sys.exit(0)
            except Exception as e:
                logger.info("server_sock.accept: "+str(e))
                #self.stop()
                sys.exit(1)




            try:
                data = client_sock.recv(8192).decode('iso-8859-15') #arbitrary

            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt")
                break
            except Exception as a:
                logger.error("client_sock.recv failed: %s" % (str(e) ))
                break




            command = str(data).rstrip()



            if command == 'log':
                logger.debug("received command \"log\"" )
                myq  = Queue()

                listener_name = 'client'
                #listener_e = self.plug.listener_exists(listener_name)
                #if listener_e[0]:
                #    result_json = self.create_status_message(0, 'listener already exists')
                #else:

                logger.debug('spawning process for listener')
                j = multiprocessing.Process(name=listener_name, target=self.message_log_process, args=(client_sock, myq))

                j.start()

                add_listener_result = self.plug.add_listener(listener_name, myq, j.pid)

                if add_listener_result[0] == 0:
                    result_json = self.create_status_message(add_listener_result[0], add_listener_result[1])
                    j.terminate()
                else:
                    logger.info("Registered listener with uuid %s" % (add_listener_result[1]))
                    self.plug.restart_plugin('system_router')
                    continue;

            else:

                logger.debug("received command \"%s\"" % (command))
                try:
                    result_json = self.do_command(command.split())
                except Exception as e:
                    logger.error("command execution failed: %s" % (str(e)) )
                    continue

            if not 'status' in result_json:
                logger.error("result_json has not status")
                continue

            try:
                client_sock.sendall(result_json.encode('iso-8859-15')+"\n".encode('iso-8859-15'))
            except Exception as e:
                logger.warning("Could not reply to client: %s" % (str(e)) )
                continue

            logger.debug("got data: \"%s\"" % (str(data)))

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--logging', dest='enable_logging', help='write to log files instead of stdout', action='store_true')
    parser.add_argument('--force', dest='force', help='kill other processes and start', action='store_true')
    args = parser.parse_args()


    if args.enable_logging:
        # 5 times 10MB
        sys.stdout.write('logging to '+LOG_FILENAME+'\n')
        log_dir = os.path.dirname(LOG_FILENAME)
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=1485760, backupCount=5)

        handler.setFormatter(formatter)
        root_logger.handlers = []
        root_logger.addHandler(handler)




    try:
        with PidFile(pid_file, force=args.force, name=os.path.basename(__file__)):


            while (datetime.datetime.now().year < 2016):
                logger.warning("We are in the wrong year. Waiting for the correct time.")
                time.sleep(10)


            pmAPI = PluginManagerAPI()

            time.sleep(2)

            pmAPI.listen_to_socket()

    except AlreadyRunning as e:
        logger.error(str(e))
        logger.error("Please use supervisorctl to start and stop the Waggle Plugin Manager.")
    except KeyboardInterrupt:
        logger.error("exiting...")
    except Exception as e:
        logger.error("Error (%s): %s" % ( str(type(e)), str(e)))
