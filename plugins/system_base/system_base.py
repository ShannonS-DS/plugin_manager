#!/usr/bin/env python3

import os, psutil, subprocess, datetime, time, logging, socket
from collections import namedtuple

"""
	This plugin is to monitor and report systematic information and activities vary from temperature, disk space, and system information to status of plugins.
	This plugin also detects USB devices to launch corresponding plugin.
"""

#TODO: when exceptions happen it could send an error code corresponding to the error, not sending the heavy error message, to reduce payload of the message. 

logger = logging.getLogger(__name__)

class register(object):
	def __init__(self, name, man, mailbox_outgoing):
		man[name] = 1
		base = base_plugin(name, man, mailbox_outgoing)
		base.run()

epoch = datetime.datetime.utcfromtimestamp(0)

def epoch_time(dt):
	return (dt - epoch).total_seconds() * 1000.0

def get_host_name():
	"""
		Returns host name containing which device (from uSD and eMMC) is used to boot 
	"""
	ret = ""
	try:
		ret = subprocess.getoutput(["uname -n"])
	except Exception as e:
		ret = "error on getting host name: %s" % (str(e))
	return ret

def get_boot_info(history_count):
	"""
		Returns history of reboot and shutdown.
	"""
	ret = ""
	try:
		ret = subprocess.getoutput(["last -x reboot | head -n %d" % (history_count)])
	except Exception as e:
		ret = "error on getting boot messages: %s" % (str(e))
	return ret

def get_shutdown_info(history_count):
	"""
		Returns history of reboot and shutdown.
	"""
	ret = ""
	try:
		ret = subprocess.getoutput(["last -x shutdown | head -n %d" % (history_count)])
	except Exception as e:
		ret = "error on getting shutdown messages: %s" % (str(e))
	return ret

def disk_usage(path):
	"""Return disk usage statistics about the given path.

	Returned valus is a named tuple with attributes 'total', 'used' and
	'free', which are the amount of total, used and free space, in bytes.
	"""
	total = used = free = 0
	ret = ""
	try:
		st = os.statvfs(path)
		free = st.f_bavail * st.f_frsize
		total = st.f_blocks * st.f_frsize
		used = (st.f_blocks - st.f_bfree) * st.f_frsize
		ret = "(total=%d, used=%d, free=%d)" % (total, used, free)
	except Exception as e:
		pass
	return ret

def get_current_cpu_temp():
	temperature_file = '/sys/class/thermal/thermal_zone0/temp'
	tempC = 0
	if os.path.isfile(temperature_file):
		tempC = int(open(temperature_file).read()) / 1e3
	else:
		tempC = -1000
	return tempC

def get_white_list():
	whitelist_file = '/usr/lib/waggle/plugin_manager/plugins/whitelist.txt'
	list = []
	if os.path.isfile(whitelist_file):
		try:
			with open(whitelist_file, 'r') as f:
				for line in f:
					if line.strip():
						list.append(line)
		except Exception as e:
			list = "error: %s" % (str(e))
	else:
		list = "error: does not exist"

	return list

def get_service_list():
	ret = ""
	try:
		raw = subprocess.getoutput(["waggle-service list"])
		splits = raw.split('\n')
		for line in splits:
			if 'waggle' in line:
				entities = line.split('|')
				for entity in entities:
					if not entity.strip() == '':
						ret += entity.strip() + ","
				ret += "|"
	except Exception as e:
		ret = "error on getting waggle-service list: %s" % (str(e))
	return ret

class base_plugin(object):
	plugin_name = 'base plugin'
	plugin_version = "1"
	def __init__(self, name, man, mailbox_outgoing):
		self.name = name
		self.man = man
		self.outqueue = mailbox_outgoing

	def get_boot_info(self):
		ret = ""

	def send(self, category, msg):
		timestamp_epoch = epoch_time(datetime.datetime.utcnow())

		self.outqueue.put([
			str(datetime.datetime.utcnow().date()).encode('iso-8859-1'),
			self.plugin_name.encode('iso-8859-1'),
			self.plugin_version.encode('iso-8859-1'),
			'default'.encode('iso-8859-1'),
			'%d' % (timestamp_epoch),
			category.encode('iso-8859-1'),
			'meta.txt'.encode('iso-8859-1'),
			msg
			])

	def send_command(self, command, timeout=3):
		socket_file = '/tmp/plugin_manager'
		client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		#client_sock.setblocking(0)

		client_sock.settimeout(timeout)
		try:
			client_sock.connect(socket_file)
		except Exception as e:
			print(("Error connecting to socket: %s" % (str(e))))
			client_sock.close()
			return None

		try:
			client_sock.sendall(command.encode('iso-8859-15'))
		except Exception as e:
			print(("Error talking to socket: %s" % (str(e))))
			client_sock.close()
			return None   

		#ready = select.select([mysocket], [], [], timeout_in_seconds)
		try:
			data = client_sock.recv(2048).decode('iso-8859-15') #TODO need better solution
		except Exception as e:
			print(("Error reading socket: %s" % (str(e))))
			client_sock.close()
			return None

		client_sock.close()

		try:
			results = json.loads(data.rstrip())
		except Exception as e:
			return {'status' : 'error', 'message':'Could not parse JSON: '+str(e)}

		return results

	def get_autostart_dict(self, base_path):
		autostart_file = '/usr/lib/waggle/plugin_manager/plugins/autostartlist.txt'
		dict = {}

		if os.path.isfile(autostart_file):
			try:
				with open(autostart_file, 'r') as file:
					for line in file:
						entity = line.split(':')
						dict[base_path + entity[0]] = entity[1].strip()
			except Exception as e:
				logger.debug("Failed to retreive autostart plugin list")
				pass
		return dict

	def collect_system_info(self):
		data = {}
		data['disk'] = disk_usage("/")
		data['host name'] = get_host_name()
		data['reboots'] = get_boot_info(3)
		data['shutdowns'] = get_shutdown_info(4)
		data['temperature'] = get_current_cpu_temp()

		return ['{}:{}'.format(keys, data[keys]).encode('iso-8859-1') for keys in data]

	def collect_service_info(self):
		data = {}
		data['whitelist'] = get_white_list()
		data['services'] = get_service_list()

		return ['{}:{}'.format(keys, data[keys]).encode('iso-8859-1') for keys in data]

	def collect_plugin_info(self):
		data = {}

		return ['{}:{}'.format(keys, data[keys]).encode('iso-8859-1') for keys in data]

	def run(self):
		# Wait 40 seconds for other services preparing to run
		# TODO: need to know when all system/services are green so this report can send right information of the current system status.
		time.sleep(40)
		data = self.collect_system_info()
		self.send('system info', data)
		data = self.collect_service_info()
		self.send('service info', data)
		
		# Get whitelist
		whitelist = get_white_list()
		if 'error:' in whitelist:
			whitelist = []

		# Get auto start plugin list
		autoplugins = self.get_autostart_dict("/dev/")
		delete_plugins = []
		while self.man[self.name]:

			# Check if predefined serial port is recognizable (sensor attached)
			for device in autoplugins:
				plugin = autoplugins[device]
				# Check if the device is attached or not, based on device_rules in waggle_image
				if os.path.islink(device) or os.path.isfile(device):
					if plugin in whitelist:
						continue
					elif plugin == '':
						continue
					else:
						# Check if plugin alive
						cmd = "info %s" % (plugin)
						ret = self.send_command(cmd)
						if 'status' in ret and ret['status'] == 'success':
							continue
						else:
							# Start the plugin
							logger.debug("Try to start %s" % (plugin))
							cmd = "start %s" % (plugin)
							ret = self.sendcommand(cmd)
							if 'status' in ret and ret['status'] == 'success':
								logger.debug("%s is up and running" % (plugin))
								delete_plugins.append(device)
							else:
								logger.debug("%s failed to start" % (plugin))

			if delete_plugins:
				for device in delete_plugins:
					del autoplugins[device]
				delete_plugins = []


			time.sleep(3)
