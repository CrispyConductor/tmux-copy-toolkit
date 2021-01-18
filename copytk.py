# Tmux Copy Toolkit
# (C) Chris Breneman 2021

import os
import os.path
import sys
import re
import argparse
import traceback
import curses
import itertools
import math
import subprocess
import shutil
from datetime import datetime
import time
import platform

#logdir = '/tmp/copytklog'
logdir = None

python_command = 'python3'
# Find full path to tmux command so it can be invoked without a shell
def find_command_path(c):
	cmd = 'command -V ' + c
	f = os.popen(cmd)
	result = f.read()
	estatus = f.close()
	if estatus:
		raise Exception('Error finding tmux: ' + cmd)
	r = ' '.join(result.split('\n')[0].split(' ')[2:])
	if r[0] != '/':
		raise Exception('Got unexpected result from tmux path finding: ' + cmd)
	return r
tmux_command = find_command_path('tmux')

# strings that can be used to map to regexes in the quickcopy matches
match_expr_presets = {
	# matches common types of urls and things that look like urls
	'urls': r'(?:^|[][\s:=,#"{}()'+"'"+r'])([a-zA-Z][a-zA-Z0-9]{1,5}://(?:[a-zA-Z0-9_]+(?::[a-zA-Z0-9_-]+)?@)?(?:(?:[a-zA-Z0-9][\w-]*\.)*[a-zA-Z][\w-]*|(?:[0-2]?[0-9]{1,2}\.){3}[0-2]?[0-9]{1,2})(?::[0-9]{1,5})?(?:/(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)?/?)?(?:\?(?:(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)+(?:=(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)?)?&)*(?:(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)+(?:=(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)?)?)?)?(?:#(?:(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)+(?:=(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)?)?&)*(?:(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)+(?:=(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)?)?)?)?)(?:$|[][\s:=,#"{}()'+"'"+r'])',
	# Unix and window style absolute paths
	'abspaths': r'(?:^|[][\s:=,#$"{}<>()'+"'"+r'])((?:/|~/|[A-Z]:[\\/])(?:(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)|[a-zA-Z0-9_-]{1,25}\\? [a-zA-Z0-9_-]{1,25})[\\/])*(?:(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)|[a-zA-Z0-9_-]{1,25}\\? [a-zA-Z0-9_-]{1,25})\.[a-zA-Z0-9]{1,6}|(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)[\\/]?))(?:$|[][\s:=,#$"{}<>()'+"'"+r'])',
	# Absolute or relative paths
	'paths': r'(?:^|[][\s:=,#$"{}<>()'+"'"+r'])((?:(?:/|~/|[A-Z]:[\\/])(?:(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)|[a-zA-Z0-9_-]{1,25}\\? [a-zA-Z0-9_-]{1,25})[\\/])*(?:(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)|[a-zA-Z0-9_-]{1,25}\\? [a-zA-Z0-9_-]{1,25})\.[a-zA-Z0-9]{1,6}|(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)[\\/]?)|(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)[\\/](?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)[\\/]?|(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)|[a-zA-Z0-9_-]{1,25}\\? [a-zA-Z0-9_-]{1,25})\.[a-zA-Z0-9]{1,6})|(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)[\\/](?:(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)|[a-zA-Z0-9_-]{1,25}\\? [a-zA-Z0-9_-]{1,25})[\\/])+(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)[\\/]?|(?:(?:[a-zA-Z0-9_-]{1,30}|\.|\.\.)|[a-zA-Z0-9_-]{1,25}\\? [a-zA-Z0-9_-]{1,25})\.[a-zA-Z0-9]{1,6})))(?:$|[][\s:=,#$"{}<>()'+"'"+r'])',
	# Isolated filenames without paths
	'filenames': r'(?:^|[][\s:=,#$"{}<>()/'+"'"+r'])([a-zA-Z0-9_-]{1,30}\.[a-zA-Z][a-zA-Z0-9]{0,5})(?:$|[][\s:=,#$"{}<>()'+"'"+r'])'
}



def log_clear():
	if not logdir: return
	shutil.rmtree(logdir, ignore_errors=True)
	os.makedirs(logdir)

def log(message, fn=None, time=False):
	if not logdir: return
	if fn == None: fn = 'main.log'
	if time:
		message = str(datetime.now()) + ': ' + message
	with open(os.path.join(logdir, fn), 'a') as f:
		f.write(message + '\n')

# We need to replace the current pane with a pane running the plugin script.
# Ideally this would be done without messing with any application currently running within the pane.
# So, create a new window and pane for that application.  If the created window/pane
# is larger than the current pane, divide it into sections and set the pane to the proper size.


def runcmd(command, one=False, lines=False, noblanklines=False):
	# runs command in shell via popen
	f = os.popen(command)
	data = f.read()
	estatus = f.close()
	if estatus:
		raise Exception(f'Command "{command}" exited with status {estatus}')
	if one or lines: # return list of lines
		dlines = data.split('\n')
		if not one and noblanklines:
			dlines = [ l for l in dlines if len(l) > 0 ]
	if one: # single-line
		return dlines[0] if len(dlines) > 0 else ''
	return dlines if lines else data

def runtmux(args, one=False, lines=False, noblanklines=False, sendstdin=None):
	args = [ str(a) for a in args ]
	log('run tmux: ' + ' '.join(args), time=True)
	with subprocess.Popen(
		[ tmux_command ] + args,
		shell=False,
		stdin=subprocess.PIPE if sendstdin != None else subprocess.DEVNULL,
		stdout=subprocess.PIPE
	) as proc:
		if sendstdin != None and isinstance(sendstdin, str):
			sendstdin = bytearray(sendstdin, 'utf8')
		recvstdout, _ = proc.communicate(input=sendstdin)
		if proc.returncode != 0:
			raise Exception(f'tmux {" ".join(args)} exited with status {proc.returncode}')
	log('tmux returned', time=True)
	data = recvstdout.decode('utf8')
	if one or lines: # return list of lines
		dlines = data.split('\n')
		if not one and noblanklines:
			dlines = [ l for l in dlines if len(l) > 0 ]
	if one: # single-line
		return dlines[0] if len(dlines) > 0 else ''
	return dlines if lines else data

def runshellcommand(command, one=False, lines=False, noblanklines=False, sendstdin=None, raisenonzero=True):
	log('run shell command: ' + command, time=True)
	with subprocess.Popen(
		command,
		shell=True,
		executable='/bin/bash',
		stdin=subprocess.PIPE if sendstdin != None else subprocess.DEVNULL,
		stdout=subprocess.PIPE
	) as proc:
		if sendstdin != None and isinstance(sendstdin, str):
			sendstdin = bytearray(sendstdin, 'utf8')
		recvstdout, _ = proc.communicate(input=sendstdin)
		if proc.returncode != 0 and raisenonzero:
			raise Exception(f'Command {command} returned exit code {proc.returncode}')
	data = recvstdout.decode('utf8')
	if one or lines: # return list of lines
		dlines = data.split('\n')
		if not one and noblanklines:
			dlines = [ l for l in dlines if len(l) > 0 ]
	if one: # single-line
		return dlines[0] if len(dlines) > 0 else ''
	return dlines if lines else data


def runtmuxmulti(argsets):
	if len(argsets) < 1: return
	allargs = []
	for argset in argsets:
		if len(allargs) > 0:
			allargs.append(';')
		allargs.extend(argset)
	runtmux(allargs)

tmux_options_cache = {}
def fetch_tmux_options(optmode='g'):
	if optmode in tmux_options_cache:
		return tmux_options_cache[optmode]
	tmuxargs = [ 'show-options' ]
	if optmode:
		tmuxargs += [ '-' + optmode ]
	rows = runtmux(tmuxargs, lines=True, noblanklines=True)
	opts = {}
	for row in rows:
		i = row.find(' ')
		if i == -1:
			opts[row] = 'on'
			continue
		name = row[:i]
		val = row[i+1:]
		# need to process val for quoting and backslash-escapes
		if len(val) > 1 and val[0] == '"':
			assert(val[-1] == '"')
			val = val[1:-1]
		elif len(val) > 1 and val[0] == "'":
			assert(val[-1] == "'")
			val = val[1:-1]
		if val.find('\\') != -1:
			rval = ''
			esc = False
			for c in val:
				if esc:
					rval += c
					esc = False
				elif c == '\\':
					esc = True
				else:
					rval += c
			val = rval
		opts[name] = val
	tmux_options_cache[optmode] = opts
	return opts

def get_tmux_option(name, default=None, optmode='g', aslist=False, userlist=False):
	opts = fetch_tmux_options(optmode)
	if aslist:
		ret = []
		if name in opts:
			ret.append(opts[name])
		i = 0
		while True:
			if userlist:
				lname = name + '-' + str(i)
			else:
				lname = name + '[' + str(i) + ']'
			if lname not in opts: break
			ret.append(opts[lname])
			i += 1
		if len(ret) == 0 and default != None:
			if isinstance(default, list):
				return default
			else:
				return [ default ]
		return ret
	else:
		return opts.get(name, default)

def str2bool(s):
	return str(s).lower() not in ( '', 'off', 'no', 'false', '0' )

def get_tmux_option_key_curses(name, default=None, optmode='g', aslist=False):
	remap = {
		'Escape': '\x1b',
		'Enter': '\n',
		'Space': ' '
	}
	v = get_tmux_option(name, default=default, optmode=optmode, aslist=aslist)
	if aslist:
		# also allow space-separated list
		return [ remap.get(s, s) for k in v for s in k.split(' ') ]
	else:
		return remap.get(v, v)

def capture_pane_contents(target=None, opts=None):
	args = [ 'capture-pane', '-p' ]
	if opts:
		args += [ '-' + opts ]
	if target != None:
		args += [ '-t', target ]
	return runtmux(args)[:-1]

def get_pane_info(target=None, capture=False, capturej=False):
	args = [ 'display-message', '-p' ]
	if target != None:
		args += [ '-t', target ]
	args += [ '#{session_id} #{window_id} #{pane_id} #{pane_width} #{pane_height} #{window_zoomed_flag} #{cursor_x} #{cursor_y} #{copy_cursor_x} #{copy_cursor_y} #{pane_mode}' ]
	r = runtmux(args, one=True).split(' ')
	try:
		cursorpos = (int(r[6]), int(r[7]))
	except:
		cursorpos = (0, 0)
	try:
		copycursorpos = (int(r[8]), int(r[9]))
	except:
		copycursorpos = (0, 0)
	mode = r[10]
	rdict = {
		'session_id': r[0],
		'window_id': r[1],
		'window_id_full': r[0] + ':' + r[1],
		'pane_id': r[2],
		'pane_id_full': r[0] + ':' + r[1] + '.' + r[2],
		'pane_size': (int(r[3]), int(r[4])),
		'zoomed': bool(int(r[5])),
		'cursor': copycursorpos if mode == 'copy-mode' else cursorpos
	}
	if capture:
		rdict['contents'] = capture_pane_contents(rdict['pane_id_full'])
	if capturej:
		rdict['contentsj'] = capture_pane_contents(rdict['pane_id_full'], 'J')
	return rdict

def create_window_pane_of_size(size):
	# Create a new window in the background
	window_id_full = runtmux([ 'new-window', '-dP', '-F', '#{session_id}:#{window_id}', '/bin/cat' ], one=True)
	# Get the information about the new pane just created
	pane = get_pane_info(window_id_full)
	# If the width is greater than the target width, do a vertical split.
	# Note that splitting reduces width by at least 2 due to the separator
	tmuxcmds = []
	resize = False
	if pane['pane_size'][0] > size[0] + 1:
		tmuxcmds.append([ 'split-window', '-t', pane['pane_id_full'], '-hd', '/bin/cat' ])
		resize = True
	# If too tall, do a horizontal split
	if pane['pane_size'][1] > size[1] + 1:
		tmuxcmds.append([ 'split-window', '-t', pane['pane_id_full'], '-vd', '/bin/cat' ])
		resize = True
	# Resize the pane to desired size
	if resize:
		tmuxcmds.append([ 'resize-pane', '-t', pane['pane_id_full'], '-x', size[0], '-y', size[1] ])
	if len(tmuxcmds) > 0:
		runtmuxmulti(tmuxcmds)
	# Return info
	pane['pane_size'] = size
	return pane

swap_count = 0
def swap_hidden_pane(show_hidden=None):
	global swap_count
	if show_hidden == True and swap_count % 2 == 1:
		return
	if show_hidden == False and swap_count % 2 == 0:
		return

	if args.swap_mode == 'pane-swap':
		# Swap target pane and hidden pane
		t1 = args.t
		t2 = args.hidden_t
		runtmux([ 'swap-pane', '-Z', '-s', t2, '-t', t1 ])
	else:
		# Switch to either the hidden window or the orig window
		if swap_count % 2 == 0:
			selectwin = args.hidden_window
		else:
			selectwin = args.orig_window
		runtmux([ 'select-window', '-t', selectwin ])
	swap_count += 1

def move_tmux_cursor(pos, target, gotocopy=True): # (x, y)
	log('move cursor to: ' + str(pos), time=True)
	tmuxcmds = []
	if gotocopy:
		tmuxcmds.append([ 'copy-mode', '-t', target ])
	tmuxcmds.append([ 'send-keys', '-X', '-t', target, 'top-line' ])
	if pos[1] > 0:
		tmuxcmds.append([ 'send-keys', '-X', '-t', target, '-N', str(pos[1]), 'cursor-down' ])
	#tmuxcmds.append([ 'send-keys', '-X', '-t', target, 'start-of-line' ]) # Was breaking when on a wrapped line
	if pos[0] > 0:
		tmuxcmds.append([ 'send-keys', '-X', '-t', target, '-N', str(pos[0]), 'cursor-right' ])
	runtmuxmulti(tmuxcmds)

def cleanup_internal_process():
	if swap_count % 2 == 1:
		swap_hidden_pane()
	runtmux([ 'kill-window', '-t', args.hidden_window ])

def gen_em_labels(n, chars=None, min_nchars=1, max_nchars=None):
	# Generates easy-motion letter abbreviation sequences
	all_chars = chars or 'asdghklqwertyuiopzxcvbnmfj;'
	# Determine how many chars per label are needed
	need_label_len = max(math.ceil(math.log(n, len(all_chars))), 1)
	if min_nchars > need_label_len:
		need_label_len = min_nchars
	if max_nchars and need_label_len > max_nchars:
		need_label_len = max_nchars
	# Determine how many letters are actually needed at such a length
	at_len_need_chars = math.ceil(n ** (1 / need_label_len))
	# If there are free letters, then there are some available lower on the stack.  Evenly divide the
	# remaininder among the lower tiers.
	n_remaining_chars = len(all_chars) - at_len_need_chars
	nchars_per_tier = [ at_len_need_chars ]
	for i in range(need_label_len - 1):
		nc = n_remaining_chars // (need_label_len - 1 - i)
		if i+1 < min_nchars:
			nc = 0
		nchars_per_tier.append(nc)
		n_remaining_chars -= nc
	nchars_per_tier.reverse()

	# Construct the labels
	remaining_chars = all_chars
	for tier in range(need_label_len):
		tierchars = remaining_chars[:nchars_per_tier[tier]]
		remaining_chars = remaining_chars[nchars_per_tier[tier]:]
		for label in itertools.product(*[tierchars for i in range(tier + 1)]):
			yield ''.join(label)

def process_pane_capture_lines(data, nlines=None):
	# processes pane capture data into an array of lines
	# also handles nonprintables
	lines = [
		''.join([
			'        ' if c == '\t' else (
				c if c.isprintable() else ''
			)
			for c in line
		])
		for line in data.split('\n')
	]
	if nlines != None:
		lines = lines[:nlines]
	return lines

def process_pane_capture_line(line):
	return ''.join([
		'        ' if c == '\t' else (
			c if c.isprintable() else ''
		)
		for c in line
	])



# Aligns display capture data to actual data that doesn't include wraps.
# Returns a dict mapping each (x, y) in disp_data to an index in j_data.
# If alignment fails, returns None.
# size is x, y (column, lineno)
def align_capture_data(disp_data, j_data, size):
	# TODO: Add checks for if arguments are 0-length or otherwise invalid
	jidx = 0
	didx = 0
	charmap = [] # map from index in disp_data to index in j_data
	jcharmap = [] # map from index in j_data to index in disp_data
	while didx < len(disp_data):
		if jidx >= len(j_data):
			charmap.append(len(j_data) - 1)
			didx += 1
			continue
		jc = j_data[jidx]
		dc = disp_data[didx]
		if jc == dc: # usual case - characters match
			charmap.append(jidx)
			jcharmap.append(didx)
			didx += 1
			jidx += 1
		elif dc == '\t' and jc == ' ':
			for i in range(8):
				if jidx < len(j_data) and j_data[jidx] == ' ':
					jcharmap.append(didx)
					jidx += 1
				else:
					break
		elif jc == '\t' and dc == ' ':
			for i in range(8):
				if didx < len(disp_data) and disp_data[didx] == ' ':
					charmap.append(jidx)
					didx += 1
				else:
					break
		elif dc == '\n' or dc == ' ' or dc == '\t':
			charmap.append(max(jidx - 1, 0))
			didx += 1
		elif jc == ' ' or jc == '\t':
			jcharmap.append(didx)
			jidx += 1
		else:
			return None
	# Pad maps to full length if necessary
	while len(charmap) < len(disp_data):
		charmap.append(len(j_data) - 1)
	while len(jcharmap) < len(j_data):
		jcharmap.append(len(disp_data) - 1)
	# Convert character mapping to mapping indexed by disp_data (x, y)
	xymap = {
		xy : charmap[didx] if didx < len(charmap) and didx < len(disp_data) else len(j_data) - 1
		for xy, didx in get_data_xy_idx_map(disp_data, size).items()
	}
	# Convert j character mapping to a mapping from j char index to display (x, y)
	didx_rev_coord_map = get_data_xy_idx_rev_map(disp_data, size)
	xymapj = [
		didx_rev_coord_map[min(didx, len(disp_data) - 1)]
		for didx in jcharmap
	]
	# Return values are:
	# 0. Mapping dict from tuple (x, y) display position to index into j_data
	# 1. Mapping list from index into j_data to (x, y) display position
	# 2. Mapping list from index into disp_data to index into j_data
	# 3. Mapping list from index into j_data to index into disp_data
	return xymap, xymapj, charmap, jcharmap

# Returns a mapping array from index in data (the pane capture data) to the (x, y) coordinates on screen
def get_data_xy_idx_rev_map(data, size):
	revmap = []
	lineno = 0
	col = 0
	for dchar in data:
		if dchar == '\n':
			revmap.append((col, lineno))
			lineno += 1
			col = 0
			continue
		if col >= size[0]:
			lineno += 1
			col = 0
		revmap.append((col, lineno))
		if dchar == '\t':
			col = min(col + 8, size[0])
		else:
			col += 1
	return revmap

# Return a map from (x,y) to index into data
def get_data_xy_idx_map(data, size):
	xymap = {}
	didx = 0
	for lineno in range(size[1]):
		lineended = False
		for col in range(size[0]):
			if didx >= len(data):
				xymap[(col, lineno)] = max(len(data) - 1, 0)
				continue
			dc = data[didx]
			if lineended or dc == '\n':
				lineended = True
				xymap[(col, lineno)] = max(didx - 1, 0)
			else:
				xymap[(col, lineno)] = didx if didx < len(data) else len(data) - 1
				didx += 1
		if didx < len(data) and data[didx] == '\n':
			didx += 1
	return xymap


def execute_copy(data):
	command = get_tmux_option('@copytk-copy-command', 'tmux load-buffer -')
	runshellcommand(command, sendstdin=data)
	log('Copied data.')

#n = 10000
#ls = gen_em_labels(n)
#for i in range(n):
#	print(next(ls))
#exit(0)

class ActionCanceled(Exception):
	def __init__(self):
		super().__init__('Action Canceled')

class PaneJumpAction:

	def __init__(self, stdscr):
		self.stdscr = stdscr
		log('start run easymotion internal', time=True)

		# Fetch information about the panes and capture original contents
		self.orig_pane = get_pane_info(args.t, capture=True, capturej=True)
		self.overlay_pane = get_pane_info(args.hidden_t)

		# Fetch options
		self.em_label_chars = get_tmux_option('@copytk-label-chars', 'asdghklqwertyuiopzxcvbnmfj;')

		# Sanitize the J capture data by removing trailing spaces on each line
		self.copy_data = '\n'.join(( line.rstrip() for line in self.orig_pane['contentsj'].split('\n') ))
		log(self.copy_data, 'copy_data')

		# Create a mapping from display coordinates to indexes into the copy data
		aligninfo = align_capture_data(self.orig_pane['contents'], self.copy_data, self.orig_pane['pane_size'])
		if aligninfo == None:
			log('alignment failed')
			# raise Exception('alignment failed')
			# Fall back to just mapping the display data to itself.  Will break wrapped lines.
			self.copy_data = self.orig_pane['contents']
			self.disp_copy_map = get_data_xy_idx_map(self.copy_data, self.orig_pane['pane_size'])
			self.copy_disp_map = get_data_xy_idx_rev_map(self.copy_data, self.orig_pane['pane_size'])
		else:
			self.disp_copy_map = aligninfo[0]
			self.copy_disp_map = aligninfo[1]

		# Fetch options
		self.cancel_keys = get_tmux_option_key_curses('@copytk-cancel-key', default='Escape Enter ^C', aslist=True)

		# Initialize curses stuff
		curses.curs_set(False)
		curses.start_color()
		curses.use_default_colors()
		curses.init_pair(1, curses.COLOR_RED, -1) # color for label first char
		curses.init_pair(2, curses.COLOR_YELLOW, -1) # color for label second+ char
		curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_YELLOW) # color for highlight
		curses.init_pair(4, curses.COLOR_RED, -1)
		self.stdscr.clear()

		# Track the size as known by curses
		self.curses_size = stdscr.getmaxyx() # note: in (y,x) not (x,y)

		# Set the contents to display
		self.display_content_lines = process_pane_capture_lines(self.orig_pane['contents'], self.orig_pane['pane_size'][1])
		self.reset()
		
	def reset(self, keep_highlight=False):
		# Initialize properties for later
		self.cur_label_pos = 0 # how many label chars have been keyed in
		self.match_locations = None # the currently valid search results [ (x, y, label) ]
		self.status_msg = None # Message in bottom-right of screen

		# Highlighted location
		if not keep_highlight:
			self.highlight_location = None
			self.highlight_ranges = None # range is inclusive

		# display current contents
		log('\n'.join(self.display_content_lines), 'display_content_lines')
		self.redraw()

	def flash_highlight_range(self, hlrange, noredraw=False, preflash=False):
		if not self.highlight_ranges:
			self.highlight_ranges = []
		if preflash:
			delayt = float(get_tmux_option('@copytk-preflash-time', '0.05'))
			self.redraw()
			time.sleep(delayt)
		if isinstance(hlrange, list):
			self.highlight_ranges.extend(hlrange)
		else:
			self.highlight_ranges.append(hlrange)
		self._redraw_highlight_ranges()
		self.stdscr.refresh()
		delayt = float(get_tmux_option('@copytk-flash-time', '0.5'))
		time.sleep(delayt)
		if isinstance(hlrange, list):
			self.highlight_ranges = self.highlight_ranges[:-len(hlrange)]
		else:
			self.highlight_ranges.pop()
		if not noredraw:
			self._redraw_contents()
			self.stdscr.refresh()

	def addstr(self, y, x, s, a=None):
		if len(s) == 0: return
		try:
			if a == None:
				self.stdscr.addstr(y, x, s)
			else:
				self.stdscr.addstr(y, x, s, a)
		except Exception as err:
			pass
			# note: errors are expected in writes to bottom-right
			#log(f'Error writing str to screen.  curses_size={self.curses_size} linelen={len(line)} i={i} err={str(err)}')

	def _redraw_contents(self):
		line_width = min(self.curses_size[1], self.orig_pane['pane_size'][0])
		max_line = min(self.curses_size[0], len(self.display_content_lines))
		for i in range(max_line):
			line = self.display_content_lines[i][:line_width].ljust(self.curses_size[0])
			self.addstr(i, 0, line)

	def _redraw_highlight_ranges(self):
		if not self.highlight_ranges: return
		line_width = min(self.curses_size[1], self.orig_pane['pane_size'][0])
		hlattr = curses.color_pair(3)
		for rng in self.highlight_ranges:
			for i in range(rng[0][1], rng[1][1] + 1):
				line = self.display_content_lines[i]
				if i < rng[0][1] or i > rng[1][1]: # whole line not hl
					continue
				elif i > rng[0][1] and i < rng[1][1]: # whole line hl
					self.addstr(i, 0, line.ljust(line_width), hlattr)
				elif i == rng[0][1] and i == rng[1][1]: # range starts and stops on this line
					self.addstr(i, rng[0][0], line[rng[0][0]:rng[1][0]+1], hlattr)
				elif i == rng[0][1]: # range starts on this line
					self.addstr(i, rng[0][0], line.ljust(line_width)[rng[0][0]:], hlattr)
				elif i == rng[1][1]: # range ends on this line
					self.addstr(i, 0, line[0:rng[1][0]+1], hlattr)
				else:
					assert(False)

	def _redraw_labels(self):
		line_width = min(self.curses_size[1], self.orig_pane['pane_size'][0])
		if self.match_locations:
			for col, row, label in self.match_locations:
				if col + len(label) > line_width:
					label = label[:line_width - col]
				if len(label) > self.cur_label_pos:
					try:
						self.stdscr.addstr(row, col, label[self.cur_label_pos], curses.color_pair(1))
					except Exception as err:
						pass
						#log(f'Error writing str to screen.  curses_size={self.curses_size} linelen={len(line)} i={i} err={str(err)}')
				if len(label) > self.cur_label_pos + 1:
					try:
						self.stdscr.addstr(row, col+1, label[self.cur_label_pos+1:], curses.color_pair(2))
					except Exception as err:
						pass
						#log(f'Error writing str to screen.  curses_size={self.curses_size} linelen={len(line)} i={i} err={str(err)}')

	def redraw(self):
		self._redraw_contents()
		self._redraw_labels()
		# highlight char
		if self.highlight_location:
			loc = self.highlight_location
			if loc[0] < self.curses_size[1] and loc[1] < self.curses_size[0] and not (loc[0] == self.curses_size[1] - 1 and loc[1] == self.curses_size[0] - 1):
				try:
					c = self.display_content_lines[loc[1]][loc[0]]
				except:
					c = '['
				self.stdscr.addch(loc[1], loc[0], c, curses.color_pair(3))
		# highlight ranges
		self._redraw_highlight_ranges()
		# status message
		if self.status_msg:
			try:
				self.stdscr.addstr(self.curses_size[0] - 1, self.curses_size[1] - len(self.status_msg), self.status_msg, curses.color_pair(4))
			except:
				pass
		# refresh
		self.stdscr.refresh()

	def setstatus(self, msg):
		self.status_msg = msg

	def cancel(self):
		raise ActionCanceled()

	def getkey(self, valid=None):
		if valid == None:
			valid = lambda k: len(k) == 1 and k.isprintable()
		while True:
			key = self.stdscr.getkey()
			#if key in ('^[', '^C', '\n', '\x1b'):
			if key in self.cancel_keys:
				self.cancel()
			if key == 'KEY_RESIZE':
				self.curses_size = self.stdscr.getmaxyx()
				self.redraw()
				continue
			if valid(key):
				return key
			#key = ' '.join([str(hex(ord(c))) for c in key])
			#self.stdscr.addstr(0, 0, key)


	def run(self):
		pass


class EasyMotionAction(PaneJumpAction):

	def __init__(self, stdscr, search_len=1):
		super().__init__(stdscr)
		self.search_len = search_len
		self.case_sensitive_search = get_tmux_option('@copytk-case-sensitive-search', 'upper') # value values: on, off, upper
		self.min_match_spacing = int(get_tmux_option('@copytk-min-match-spacing', '2'))

	def _em_filter_locs(self, locs):
		d = args.search_direction
		cursor = self.orig_pane['cursor']
		if d == 'forward' or d == 'down':
			return [
				loc
				for loc in locs
				if loc[1] > cursor[1] or (loc[1] == cursor[1] and loc[0] >= cursor[0])
			]
		elif d == 'reverse' or d == 'up' or d == 'backward':
			return [
				loc
				for loc in locs
				if loc[1] < cursor[1] or (loc[1] == cursor[1] and loc[0] < cursor[0])
			]
		else:
			return locs

	def _em_sort_locs_cursor_proximity(self, locs, cursor=None):
		# Sort locations by proximity to cursor
		if cursor == None:
			cursor = self.orig_pane['cursor']
		locs.sort(key=lambda pos: abs(cursor[0] - pos[0]) + abs(cursor[1] - pos[1]) * self.orig_pane['pane_size'][0])

	def _em_search_lines(self, datalines, srch, min_match_spacing=2, matchcase=False):
		if not matchcase: srch = srch.lower()
		results = [] # (x, y)
		for linenum, line in reversed(list(enumerate(datalines))):
			if not matchcase: line = line.lower()
			pos = 0
			while True:
				r = line.find(srch, pos)
				if r == -1: break
				results.append((r, linenum))
				pos = r + len(srch) + min_match_spacing
		return results

	def _em_input_search_chars(self):
		search_str = ''
		self.setstatus('INPUT CHAR')
		self.redraw()
		for i in range(self.search_len):
			search_str += self.getkey()
		self.setstatus(None)
		self.redraw()
		return search_str

	def get_locations(self, action):
		pane_search_lines = self.display_content_lines
		log('\n'.join(pane_search_lines), 'pane_search_lines')

		if action == 'search':
			search_str = self._em_input_search_chars()
			return self._em_search_lines(
				pane_search_lines,
				search_str,
				self.min_match_spacing,
				self.case_sensitive_search == 'on' or (self.case_sensitive_search == 'upper' and search_str.lower() != search_str)
			)
		elif action == 'lines':
			return [ (0, y) for y in range(self.orig_pane['pane_size'][1]) ]
		else:
			raise Exception('Invalid copytk easymotion action')

	def do_easymotion(self, action, filter_locs=None, sort_close_to=None):
		# Get possible jump locations sorted by proximity to cursor
		locs = self.get_locations(action)
		locs = self._em_filter_locs(locs)
		if filter_locs:
			locs = [ l for l in locs if filter_locs(l) ]
		if len(locs) == 0:
			raise ActionCanceled()
		self._em_sort_locs_cursor_proximity(locs, sort_close_to)

		# Assign each match a label
		label_it = gen_em_labels(len(locs), self.em_label_chars)
		self.match_locations = [ (ml[0], ml[1], next(label_it) ) for ml in locs ]

		# Draw labels
		self.redraw()

		# Wait for label presses
		keyed_label = ''
		while True: # loop over each key/char in the label
			keyed_label += self.getkey()
			self.cur_label_pos += 1
			self.match_locations = [ m for m in self.match_locations if m[2].startswith(keyed_label) ]
			if len(self.match_locations) < 2:
				break
			self.redraw()
		log('keyed label: ' + keyed_label, time=True)

		if len(self.match_locations) == 0:
			return None
		else:
			return (self.match_locations[0][0], self.match_locations[0][1])

	def run(self, action):
		log('easymotion swapping in hidden pane', time=True)
		swap_hidden_pane(True)

		loc = self.do_easymotion(action)
		
		# If a location was found, move cursor there in original pane
		if loc:
			log('match location: ' + str(loc), time=True)
			move_tmux_cursor((loc[0], loc[1]), self.orig_pane['pane_id'])


class EasyCopyAction(EasyMotionAction):

	def __init__(self, stdscr, search_len=1):
		super().__init__(stdscr, search_len)
		#self.orig_pane['contentsj'] = capture_pane_contents(self.orig_pane['pane_id'], 'J')

	def run(self):
		log('easycopy swapping in hidden pane', time=True)
		swap_hidden_pane(True)

		# Input searches to get bounds
		pos1 = self.do_easymotion('search')
		if not pos1: return
		self.highlight_location = pos1
		self.reset(keep_highlight=True)
		# restrict second search to after first position
		pos2 = self.do_easymotion(
			'search',
			filter_locs=lambda loc: loc[1] > pos1[1] or (loc[1] == pos1[1] and loc[0] > pos1[0]),
			sort_close_to=pos1
		)
		if not pos2: return

		# since typing last n letters of word, advance end position by n-1 (-1 because range is inclusive)
		pos2 = (pos2[0] + self.search_len - 1, pos2[1])

		# Find the data associated with this range and run the copy command
		selected_data = self.copy_data[self.disp_copy_map[pos1] : self.disp_copy_map[pos2] + 1]
		log('Copied: ' + selected_data)
		execute_copy(selected_data)

		# Flash selected range as confirmation
		self.flash_highlight_range((pos1, pos2))


class QuickCopyAction(PaneJumpAction):

	def __init__(self, stdscr, options_prefix='@copytk-quickcopy-'):
		super().__init__(stdscr)
		self.options_prefix = options_prefix
		self._load_options(options_prefix)
		self.em_label_chars = ''.join(( c for c in self.em_label_chars if c not in self.next_batch_char ))

	def _load_options(self, prefix='@copytk-quickcopy-'):
		# Load in the tiers of match expressions.
		# Options for this are in the form: @copytk-quickcopy-match-<Tier>-<TierIndex>
		# Each tier list is terminated by a missing option at the index.
		# The set of tiers is terminated by a missing 0 index for the tier.
		tier_exprs = [] # list (of tiers) of lists of strings
		tier_ctr = 0
		while True:
			l = get_tmux_option(prefix + 'match-' + str(tier_ctr), aslist=True, userlist=True)
			if l == None or len(l) == 0:
				break
			tier_exprs.append(l)
			tier_ctr += 1
		self.tier_exprs = tier_exprs
		self.next_batch_char = get_tmux_option_key_curses(prefix + 'next-batch-char', ' n', aslist=True)
		self.min_match_len = get_tmux_option(prefix + 'min-match-len', 4)
		self.pack_tiers = str2bool(get_tmux_option(prefix + 'pack-tiers', 'on'))

	def _matchobj(self, start, end, tier=0):
		return (
			tier,
			end-start,
			self.copy_data[start:end],
			(start, end),
			self.copy_disp_map[start] if start < len(self.copy_data) else len(self.copy_data) - 1,
			self.copy_disp_map[end - 1]
		)

	def _matchobjs(self, tuplist, tier=0):
		return [ self._matchobj(start, end, tier=tier) for start, end in tuplist ]
	
	def _find_lines_matches(self):
		start = 0
		for i, c in enumerate(self.copy_data):
			if c == '\n':
				if i > start:
					yield (start, i)
				start = i + 1
		if len(self.copy_data) > start + 1:
			yield (start, len(self.copy_data))

	# Returns an iterator over (start, end) tuples
	def find_expr_matches(self, expr):
		if expr in match_expr_presets:
			expr = match_expr_presets[expr]
		if expr == 'lines':
			for m in self._find_lines_matches():
				yield m
			return
		# regex expr
		log('Matching against expr ' + expr)
		flags = 0
		if expr.startswith('(?m)'):
			flags = re.MULTILINE
			expr = expr[4:]
		for match in re.finditer(expr, self.copy_data, flags):
			try:
				d = ( match.start(1), match.end(1) )
			except IndexError:
				d = ( match.start(0), match.end(0) )
			log('Found match: ' + str(d) + ': ' + self.copy_data[d[0]:d[1]])
			if d[0] < 0 or d[1] < 0:
				d = ( 0, 0 )
			yield d

	def find_matches(self):
		# Produce a list of matches where each entry is in this format:
		# ( tiernum, matchlen, data, ( copy data start, copy data end ), ( disp start x, disp start y ), ( disp end x, disp end y ) )
		allmatches = []
		for tier, exprs in enumerate(self.tier_exprs):
			for expr in exprs:
				allmatches.extend(self._matchobjs(self.find_expr_matches(expr), tier))
		# Filter out matches shorter than the minimum
		return [ m for m in allmatches if m[1] >= self.min_match_len ]

	def arrange_matches(self, matches, pack_tiers=True):
		# Arrange the set of matches into batches of non-overlapping ones, by tier, and by shortness (shorter preferred)
		# Do this by "writing" each match's range onto a virtual screen, marking each char, and pushing overlapping ones
		# to the next batch.
		# Sort tuples (first by tier then length)
		matches.sort()
		# Dedup matches
		c_match_set = set()
		newmatches = []
		for match in matches:
			if match[3] not in c_match_set:
				c_match_set.add(match[3])
				newmatches.append(match)
		matches = newmatches
		# Segment into batches by overlap
		batches = []
		log('start arrange_matches')
		while len(matches) > 0: # iterate over batches
			last_added_tier = None
			overlaps = []
			virt = [ False ] * len(self.copy_data)
			batch = []
			for m in matches: # iterate over remaining matches
				if not pack_tiers and last_added_tier != None and m[0] != last_added_tier:
					break
				# Check if overlaps
				o = False
				for i in range(m[3][0], m[3][1]):
					if virt[i]:
						o = True
						break
				if o:
					overlaps.append(m)
				else:
					batch.append(m)
					for i in range(m[3][0], m[3][1]):
						virt[i] = True
					last_added_tier = m[0]
			batches.append(batch)
			matches = overlaps
		return batches

	def run_batch(self, batch):
		# Returns a match object if one is selected. (actually a list of match objects that will all have same text)
		# Returns None to cycle to next batch
		# Throws ActionCanceled if canceled or invalid selection
		
		# Assign a code to each match in the batch
		labels = []
		match_text_label_map = {} # use this so matches with same text have same label
		label_it = gen_em_labels(len(batch), self.em_label_chars)
		for match in batch:
			if match[2] in match_text_label_map:
				labels.append(match_text_label_map[match[2]])
			else:
				l = next(label_it)
				labels.append(l)
				match_text_label_map[match[2]] = l
		
		# Set up match_locations and highlights
		self.match_locations = [ ( match[4][0], match[4][1], labels[i] ) for i, match in enumerate(batch) ]
		line_width = self.orig_pane['pane_size'][0]
		def updatehl():
			self.highlight_ranges = [
				(
					( min(match[4][0] + len(labels[i]) - self.cur_label_pos, line_width), match[4][1] ),
					( match[5][0], match[5][1] )
				)
				for i, match in enumerate(batch) 
			]
		updatehl()
		self.redraw()

		# Input label
		keyed_label = ''
		while True: # loop over each key/char in the label
			k = self.getkey() # checks for cancel key and throws
			if k in self.next_batch_char:
				return None
			keyed_label += k
			self.cur_label_pos += 1
			# Update match locations and highlights
			new_match_locations = []
			new_labels = []
			new_batch = []
			for i, label in enumerate(labels):
				if label.startswith(keyed_label):
					new_labels.append(label)
					new_match_locations.append(self.match_locations[i])
					new_batch.append(batch[i])
			batch = new_batch
			labels = new_labels
			self.match_locations = new_match_locations
			updatehl()
			self.match_locations = [ m for m in self.match_locations if m[2].startswith(keyed_label) ]
			# count remaining matches by ones with unique text rather than total count
			num_unique_texts = len(set(( m[2] for m in batch )))
			if num_unique_texts < 2:
				break
			self.redraw()
		log('keyed label: ' + keyed_label, time=True)

		self.reset()
		if len(batch) == 0:
			raise ActionCanceled() # invalid entry
		else:
			return batch

	def run_quickselect(self):
		log('quickcopy run')
		# Get a list of all matches
		matches = self.find_matches()
		if len(matches) == 0: raise ActionCanceled()
		log('got matches')

		# Group them into display batches
		batches = self.arrange_matches(matches, self.pack_tiers)
		log('arranged matches')

		swap_hidden_pane(True)
		log('swapped in hidden pane')

		# Display each batch until a valid match has been selected
		selected = None
		for batch in batches:
			selected = self.run_batch(batch)
			if selected: break
		if not selected: raise ActionCanceled()

		# Got result.
		selected_data = selected[0][2]
		log('Copied: ' + selected_data)
		return selected_data, selected

	def run(self):
		selected_data, selected = self.run_quickselect()
		execute_copy(selected_data)

		# Flash highlights
		self.match_locations = None
		hl_ranges = [ (match[4], match[5]) for match in selected ]
		flash_only_one = str2bool(get_tmux_option('@copytk-flash-only-one', 'on'))
		if flash_only_one: hl_ranges = [ hl_ranges[-1] ]
		self.flash_highlight_range(hl_ranges, preflash=True)


class QuickOpenAction(QuickCopyAction):
	
	def __init__(self, stdscr):
		super().__init__(stdscr, options_prefix='@copytk-quickopen-')
		self.command_extra_env = self.load_env_file()

	def load_env_file(self):
		fn = os.path.expanduser(get_tmux_option('@copytk-quickopen-env-file', '~/.tmux-copytk-env'))
		if not os.path.exists(fn):
			return {}
		ret = {}
		with open(fn, 'r') as f:
			for line in f:
				line = line.strip()
				if not len(line): continue
				if line[0] == '#': continue
				parts = line.split('=')
				if len(parts) < 2: continue
				name = parts[0]
				value = '='.join(parts[1:])
				if len(value) >= 2 and value[0] in ('"', "'") and value[-1] in ('"', "'"):
					value = value[1:-1]
				ret[name] = value
		log('Loaded env file: ' + str(ret))
		return ret

	def run(self):
		selected_data, selected = self.run_quickselect()
		log('quickopen selected: ' + selected_data)

		default_open_cmd = 'xdg-open'
		if platform.system() == 'Darwin':
			default_open_cmd = 'open'
		open_cmd = get_tmux_option('@copytk-quickopen-open-command', default_open_cmd)
		env = dict(os.environ)
		env.update(self.command_extra_env)
		full_cmd = 'nohup ' + open_cmd + " '" + selected_data + "' &>/dev/null & disown"
		log('Command: ' + full_cmd)
		log('Env: ' + str(env))
		subprocess.Popen(
			full_cmd,
			executable='/bin/bash',
			shell=True,
			env=env,
			close_fds=True
		)


def run_easymotion(stdscr):
	nkeys = 1
	if args.search_nkeys:
		nkeys = int(args.search_nkeys)
	action = args.action[11:]
	EasyMotionAction(stdscr, nkeys).run(action)

def run_easycopy(stdscr):
	nkeys = 1
	if args.search_nkeys:
		nkeys = int(args.search_nkeys)
	EasyCopyAction(stdscr, nkeys).run()

def run_quickcopy(stdscr):
	QuickCopyAction(stdscr).run()

def run_quickopen(stdscr):
	QuickOpenAction(stdscr).run()



def run_wrapper(main_action, args):
	log('running wrapper', time=True)
	pane = get_pane_info(args.t)
	# Wrap the inner utility in different ways depending on if the pane is zoomed or not.
	# This is because tmux does funny thingy when swapping zoomed panes.
	# When an ordinary pane, use 'pane-swap' mode.  In this case, the internal utility
	# is run as a command in a newly created pane of the same size in a newly created window.
	# The command pane is then swapped with the target pane, and swapped back once complete.
	# In 'window-switch' mode, the internal utility is run as a single pane in a new window,
	# then the active window is switched to that new window.  Once complete, the window is
	# switched back.
	if pane['zoomed']:
		z_win_id = runtmux([ 'new-window', '-dP', '-F', '#{session_id}:#{window_id}', '/bin/cat' ], one=True)
		hidden_pane = get_pane_info(z_win_id)
		swap_mode = 'window-switch'
	else:
		hidden_pane = create_window_pane_of_size(pane['pane_size'])
		swap_mode = 'pane-swap'
	thisfile = os.path.abspath(__file__)
	cmd = f'{python_command} "{thisfile}"'
	def addopt(opt, val=None):
		nonlocal cmd
		if val == None:
			cmd += ' \'' + opt + '\''
		else:
			cmd += ' \'' + opt + '\' \'' + str(val) + '\''
	addopt('--run-internal')
	addopt('-t', pane['pane_id'])
	addopt('--hidden-t', hidden_pane['pane_id'])
	addopt('--hidden-window', hidden_pane['window_id'])
	addopt('--orig-window', pane['window_id'])
	addopt('--swap-mode', swap_mode)

	if args.search_nkeys:
		addopt('--search-nkeys', args.search_nkeys)
	if args.search_direction:
		addopt('--search-direction', args.search_direction)

	cmd += f' "{main_action}"'
	#cmd += ' 2>/tmp/tm_wrap_log'
	log('wrapper triggering hidden pane respawn of inner process', time=True)
	runtmux([ 'respawn-pane', '-k', '-t', hidden_pane['pane_id_full'], cmd ])






argp = argparse.ArgumentParser(description='tmux pane utils')
argp.add_argument('-t', help='target pane')
argp.add_argument('--search-nkeys', help='number of characters to key in to search')
argp.add_argument('--search-direction', help='direction to search from cursor, both|forward|reverse')

# internal args
argp.add_argument('--run-internal', action='store_true')
argp.add_argument('--hidden-t')
argp.add_argument('--hidden-window')
argp.add_argument('--orig-window')
argp.add_argument('--swap-mode')

argp.add_argument('action')
args = argp.parse_args()

if not args.run_internal:
	log_clear()
	run_wrapper(args.action, args)
	exit(0)


assert(args.t)
assert(args.t.startswith('%'))
assert(args.hidden_t)
assert(args.hidden_t.startswith('%'))
assert(args.hidden_window)
assert(args.orig_window)
assert(args.swap_mode)

try:

	os.environ.setdefault('ESCDELAY', '10') # lower curses pause on escape
	if args.action.startswith('easymotion-'):
		curses.wrapper(run_easymotion)
	elif args.action == 'easycopy':
		curses.wrapper(run_easycopy)
	elif args.action == 'quickcopy':
		curses.wrapper(run_quickcopy)
	elif args.action == 'quickopen':
		curses.wrapper(run_quickopen)
	else:
		print('Invalid action')
		exit(1)

except ActionCanceled:
	pass

except Exception as ex:
	print('Error:')
	print(ex)
	traceback.print_exc()
	print('ENTER to continue ...')
	input()

finally:
	cleanup_internal_process()
	exit(0)




