#!/usr/bin/env python
'''
Implement the JEOL protocol for storing beam parameters. Errors are written to STDERR (not logged).
'''

# The default serial port is /dev/ttyS0 (the first on-board RS232 port)

# If you are using a USB to serial dongle, you'll need the correct device
# name. To list all available ports on your system, try:

#   $ python -m serial.tools.list_ports

# Common serial names include:
#  * /dev/ttyUSB*
#  * /dev/cu.PL2303-*
#  * /dev/cu.UC-232AC
#  * /dev/ttyAMA0 (Raspberry Pi)

from __future__ import print_function
import serial
import sys
import os
import re
import json
import datetime
import argparse
from time import sleep

opts = {
	'port': 		{ 'value': '/dev/ttyS0', 'help': 'serial port', 'type': str },
	'baudrate':		{ 'value': 2400, 'help': 'serial baud rate', 'type': int },
	'databits':		{ 'value': 8, 'help': 'data bits', 'type': int },
	'parity':		{ 'value': 'N', 'help': 'parity', 'type': str },
	'stopbits':		{ 'value': 1, 'help': 'stop bits', 'type': int },
	'timeout':		{ 'value': 5, 'help': 'serial timeout', 'type': int },
	'softflow':		{ 'value': False, 'help': 'software flow control', 'type': bool },
	'hardflow':		{ 'value': True, 'help': 'hardware flow control', 'type': bool },
	'interactive':	{ 'value': True, 'help': 'Interactive mode. Prompts for JEOL commands and returns any reply.', 'type': bool },
	'log':			{ 'value': 'STDOUT', 'help': 'Log file to append to. STDOUT writes to the console.', 'type': str },
	'config':		{ 'value': 'scope.json', 'help': 'File to store SEM settings.', 'type': str },
}

def get_terminal_width(margin=5):
	'''
	Return the current terminal width minus a nice margin.

	In python 3.3+, use shutil.get_terminal_size() instead.
	'''
	if not sys.stdout.isatty():
		return 80

	import struct
	from fcntl import ioctl
	from termios import TIOCGWINSZ
	reply = ioctl(sys.stdout, TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
	return struct.unpack("HHHH", reply)[0:2][1] - margin

class sem:
	def __init__(self, port, config):
		self.port = port
		self.config = config
		self.load_params()
		self.send('', safe=False)

	def readline(self):
		''' Use CR instead of LF for serial readline '''
		eol = b'\r'
		leneol = len(eol)
		line = bytearray()
		while True:
			c = self.port.read(1)
			if c:
				line += c
				if line[-leneol:] == eol:
					break
			else:
				break
		return bytes(line)

	def send(self, cmd, safe=True):
		''' 
			Send a single line. Return the response (always a single line).

			Note that some commands (eg. INTG) can take a while to run, and the
			default timeout may not be sufficient.		

			serial.SerialTimeoutException is raised on tx or rx timeout.
			
			Raises a RuntimeError if safe is True and the command response
			doesn't start with !0. SEM return codes may include !3 (bad
			command), !4 (invalid parameter), or !5 (cannot comply, eg.
			running 'SD SEI' when beam is off).

		'''
		self.port.write(str(cmd) + '\r')
		resp = self.readline()
		if safe and resp[0:2] != "!0":
			raise RuntimeError("Command '{0}' failed ({1})".format(cmd, resp))

		return resp

	def get(self, cmd, safe=True):
		'''
			send() a command, and return the results without the leading !0 [CMD] or trailing \r 
		'''
		resp = self.send(cmd, safe)[3:]
		if resp[0:len(cmd)] != cmd:
			raise RuntimeError("Sent {0} but got response {1}??".format(cmd, resp))
		return resp[len(cmd)+1:-1]

	def get_current_state(self):
		st = {}

		cmds = [
			"ACC",		# Acceleration voltage
			"GA",		# Gun alignment
			"OLAP",		# OL selection
			"ST",		# OL astig
			"STC",		# CL astig
			"CC",		# Probe current (coarse)
			"CF",		# Probe current (fine)
			"WD",		# Working distance
			"OC",		# OL focus (coarse)
			"OF",		# OL focus (fine)
		]

		for cmd in cmds:
			st[cmd] = self.get(cmd)

		return st

	def update_current_state(self):
		st = self.get_current_state()	
			
		# Save params for every combination of:
		#   Acceleration voltage > Probe current (coarse) > WD > OL select

		if st["ACC"] not in self.state:
			self.state[st["ACC"]] = {}
		if st["CC"] not in self.state[st["ACC"]]:
			self.state[st["ACC"]][st["CC"]] = {}
		if st["WD"] not in self.state[st["ACC"]][st["CC"]]:
			self.state[st["ACC"]][st["CC"]][st["WD"]] = {}
		if st["OLAP"] not in self.state[st["ACC"]][st["CC"]][st["WD"]]:
			self.state[st["ACC"]][st["CC"]][st["WD"]][st["OLAP"]] = {}

		for param in [ "GA", "ST", "STC", "OC", "OF" ]:
			self.state[st["ACC"]][st["CC"]][st["WD"]][st["OLAP"]][param] = st[param]

	def save_params(self):
		''' Save gun alignment, astig, focus, etc. '''
		print("Saving parameters.")
		self.update_current_state()
		# for param in self.state:
		# 	print(param, ">", self.state[param])

		with open(self.config, "w") as cfg:
			cfg.write(
				json.dumps(self.state,
					sort_keys=True,
					separators=(',', ':')
				)
			)

	def load_params(self):
		''' Load parameters from disk. Does not change SEM state. '''
		print("Loading parameters from {0}".format(self.config))
		try:
			with open(self.config, "r") as cfg:
				try:
					self.state = json.loads(cfg.read())
				except ValueError:
					print('Broken config, starting a new one.')
					self.state = {}
		except IOError:
			print('Could not open config, starting a new one.')
			self.state = {}

	def set_params(self):
		''' Update SEM to use saved microscope state, if available. '''
		st = self.get_current_state()

		#   Acceleration voltage > Probe current (coarse) > WD > OL select
		if st["ACC"] in self.state:
			if st["CC"] in self.state[st["ACC"]]:
				if st["WD"] in self.state[st["ACC"]][st["CC"]]:
					if st["OLAP"] in self.state[st["ACC"]][st["CC"]][st["WD"]]:
						print("Updating SEM with saved parameters.")
						for param in [ "GA", "ST", "STC", "OC", "OF" ]:
							# print(param, ">", self.state[st["ACC"]][st["CC"]][st["WD"]][st["OLAP"]][param])
							self.send(param + " " + self.state[st["ACC"]][st["CC"]][st["WD"]][st["OLAP"]][param])
						return True

		print("No saved settings available.")
		return False

	def safe_mode(self):
		''' Reset the SEM to a known state. '''
		cmds = [
			"SS TV",		# Fast scan rate
			"MONI I64", 	# 64 integrations for CRT #2
			"FREZ OFF",		# Unfreeze
			"WBL OFF",		# Turn off the wobbler
			"INST ON",		# Enable instant mag
			"MG 25",		# ...and set minimum zoom
			"INST OFF",		# Disable instant mag
			"MG 25",		# ...and set minimum zoom
			"SM PIC",		# Picture capture mode
			"VIDO ON",		# NTSC compat mode
			"DMG OFF",		# D-MAG off
			"PMT ON",		# PMT link
			"IMS1 SEI",		# Upper SEI (IMS)
			"EM SHR",		# Upper SEI (EM)
			"AEC CNST",		# Constant emission mode
			"IS X0 Y0", 	# Reset image shift to 0,0
			"YZM OFF",		# Disable YZ modulation
			"IA1 ANA",		# Analog IMS input
			"DFIS OFF", 	# No menus on CRT #1
			"DA 0",			# Minimum dynamic focus
			"WFM OFF",		# Waveform mode off
			"PNU2 STAT",	# CRT2 standard display
		]

		print("Setting safe mode", end="")
		for cmd in cmds:
			print(".", end="")
			sys.stdout.flush()
			self.send(cmd)
		print("")

		# if beam is on:
		# "SD SEI",		# SEI detector enabled

		# Pick a "safe" known entry for this accel voltage
		# Reload focus, gun alignment, stig etc.

if __name__ == '__main__':

	# argparse foolishly relies on the COLUMNS environment variable to determine the terminal width.
	# This is only used in Bash-like shells, and even then it isn't exported by default, so argparse
	# defaults to a paltry 80 columns.
	#
	# This gets the real terminal width if COLUMNS isn't already available.
	if not 'COLUMNS' in os.environ:
		os.environ['COLUMNS'] = str(get_terminal_width())

	# Build out a dynamic argument list based on opts
	PARSER = argparse.ArgumentParser(description=__doc__)
	for opt in opts:
		this_type = opts[opt]['type']
		this_val = this_type(opts[opt]['value'])

		if this_type == bool:
			action = 'store_false' if this_val == True else 'store_true'
			PARSER.add_argument(
				'--' + opt,
				default=this_val,
				action=action,
				help='%s (default: %s)' % (opts[opt]['help'], str(this_val))
			)
		else:
			PARSER.add_argument(
				'--' + opt,
				default=this_val,
				type=this_type,
				action='store',
				help='%s (default: %s)' % (opts[opt]['help'], str(this_val))
			)

	ARGS = PARSER.parse_args()

	# Write to STDOUT, or append to the specified log.
	if ARGS.log == 'STDOUT':
		log = sys.stdout
	else:
		log = open(ARGS.log, 'a', 0)

	ser = serial.Serial(
		port=ARGS.port,
		baudrate=ARGS.baudrate,
		bytesize=ARGS.databits,
		parity=ARGS.parity,
		stopbits=ARGS.stopbits,
		timeout=ARGS.timeout,
		xonxoff=ARGS.softflow,
		rtscts=ARGS.hardflow,
		# dsrdtr follows rtscts
		dsrdtr=None,
		# CR, no LF
	)

	jeol = sem(ser, ARGS.config)

	# Until ^C
	while True:
		try:
			if ARGS.interactive:
				cmd = raw_input('> ').rstrip()
				if cmd == "safemode":
					jeol.safe_mode()
				elif cmd == "status":
					print(jeol.get_current_state())
				elif cmd == "save":
					jeol.save_params()
				elif cmd == "load":
					jeol.load_params()
				elif cmd == "set":
					jeol.set_params()
				else:
					print(jeol.send(cmd, safe=False))

			else:
				print("One-shot command mode HERE.")

		except (KeyboardInterrupt, EOFError):
			print()
			sys.exit(0)
