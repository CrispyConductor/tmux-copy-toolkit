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

logdir = '/tmp/tmplog'

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

def log_clear():
	if not logdir: return
	shutil.rmtree(logdir, ignore_errors=True)
	os.makedirs(logdir)

def log(message, fn=None):
	if not logdir: return
	if fn == None: fn = 'main.log'
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
	log('run tmux: ' + ' '.join(args))
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
		if val[0] == '"':
			assert(val[-1] == '"')
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

def get_tmux_option(name, default=None, optmode='g', aslist=False):
	opts = fetch_tmux_options(optmode)
	if aslist:
		ret = []
		if name in opts:
			ret.append(opts[name])
		i = 0
		while True:
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

def capture_pane_contents(target=None):
	args = [ 'capture-pane', '-p' ]
	if target != None:
		args += [ '-t', target ]
	return runtmux(args)[:-1]

def get_pane_info(target=None, capture=False):
	args = [ 'display-message', '-p' ]
	if target != None:
		args += [ '-t', target ]
	args += [ '#{session_id} #{window_id} #{pane_id} #{pane_width} #{pane_height} #{window_zoomed_flag}' ]
	r = runtmux(args, one=True).split(' ')
	rdict = {
		'session_id': r[0],
		'window_id': r[1],
		'window_id_full': r[0] + ':' + r[1],
		'pane_id': r[2],
		'pane_id_full': r[0] + ':' + r[1] + '.' + r[2],
		'pane_size': (int(r[3]), int(r[4])),
		'zoomed': bool(int(r[5]))
	}
	if capture:
		rdict['contents'] = capture_pane_contents(rdict['pane_id_full'])
	return rdict

def create_window_pane_of_size(size):
	# Create a new window in the background
	window_id_full = runtmux([ 'new-window', '-dP', '-F', '#{session_id}:#{window_id}', '/bin/sh' ], one=True)
	# Get the information about the new pane just created
	pane = get_pane_info(window_id_full)
	# If the width is greater than the target width, do a vertical split.
	# Note that splitting reduces width by at least 2 due to the separator
	tmuxcmds = []
	resize = False
	if pane['pane_size'][0] > size[0] + 1:
		tmuxcmds.append([ 'split-window', '-t', pane['pane_id_full'], '-hd', '/bin/sh' ])
		resize = True
	# If too tall, do a horizontal split
	if pane['pane_size'][1] > size[1] + 1:
		tmuxcmds.append([ 'split-window', '-t', pane['pane_id_full'], '-vd', '/bin/sh' ])
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
	log('move cursor to: ' + str(pos))
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



def gen_em_labels(n, min_nchars=1, max_nchars=None):
	# Generates easy-motion letter abbreviation sequences
	all_chars = 'asdghklqwertyuiopzxcvbnmfj;'
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

def em_search_lines(datalines, srch, min_match_spacing=2):
	results = [] # (x, y)
	for linenum, line in reversed(list(enumerate(datalines))):
		pos = 0
		while True:
			r = line.find(srch, pos)
			if r == -1: break
			results.append((r, linenum))
			pos = r + len(srch) + min_match_spacing
	return results

#n = 10000
#ls = gen_em_labels(n, 1, 2)
#for i in range(n):
#	print(next(ls))
#exit(0)

class ActionCanceled(Exception):
	def __init__(self):
		super().__init__('Action Canceled')

class PaneJumpAction:

	def __init__(self, stdscr):
		self.stdscr = stdscr
		log('start run easymotion internal')

		# Fetch information about the panes and capture original contents
		self.orig_pane = get_pane_info(args.t, capture=True)
		self.overlay_pane = get_pane_info(args.hidden_t)

		# Fetch options
		self.cancel_keys = get_tmux_option_key_curses('@copytk-cancel-key', default='Escape Enter ^C', aslist=True)

		# Initialize curses stuff
		curses.curs_set(False)
		curses.start_color()
		curses.use_default_colors()
		curses.init_pair(1, curses.COLOR_RED, -1) # color for label first char
		curses.init_pair(2, curses.COLOR_YELLOW, -1) # color for label second+ char
		self.stdscr.clear()

		# Track the size as known by curses
		self.curses_size = stdscr.getmaxyx() # note: in (y,x) not (x,y)

		# Set the contents to display
		self.display_content_lines = self.orig_pane['contents'].split('\n')

		# Initialize properties for later
		self.cur_label_pos = 0 # how many label chars have been keyed in
		self.match_locations = None # the currently valid search results [ (x, y, label) ]

		# display current contents
		log('\n'.join(self.display_content_lines), 'display_content_lines')
		self.redraw()

	def _redraw_contents(self):
		line_width = min(self.curses_size[1], self.orig_pane['pane_size'][0])
		for i in range(min(self.curses_size[0], len(self.display_content_lines))):
			self.stdscr.addstr(i, 0, self.display_content_lines[i][:line_width].ljust(self.curses_size[0]))

	def _redraw_labels(self):
		line_width = min(self.curses_size[1], self.orig_pane['pane_size'][0])
		if self.match_locations:
			for col, row, label in self.match_locations:
				if col + len(label) > line_width:
					label = label[:line_width - col]
				self.stdscr.addstr(row, col, label[self.cur_label_pos], curses.color_pair(1))
				if len(label) > self.cur_label_pos + 1:
					self.stdscr.addstr(row, col+1, label[self.cur_label_pos+1:], curses.color_pair(2))

	def redraw(self):
		self._redraw_contents()
		self._redraw_labels()
		self.stdscr.refresh()

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


	def run(self):
		swap_hidden_pane(True)

		# Input search string
		search_str = ''
		for i in range(self.search_len):
			search_str += self.getkey()

		# Find occurrences of search string in pane contents
		pane_search_lines = process_pane_capture_lines(self.orig_pane['contents'], self.orig_pane['pane_size'][1])
		log('\n'.join(pane_search_lines), 'pane_search_lines')
		match_locations = self._em_search_lines(
			pane_search_lines,
			search_str,
			self.min_match_spacing,
			self.case_sensitive_search == 'on' or (self.case_sensitive_search == 'upper' and search_str.lower() != search_str)
		)

		# Assign each match a label
		label_it = gen_em_labels(len(match_locations))
		self.match_locations = [ (ml[0], ml[1], next(label_it) ) for ml in match_locations ]

		# Draw labels
		self.redraw()

		# Wait for label presses
		keyed_label = ''
		while True: # loop over each key/char in the label
			keyed_label += self.getkey()
			self.cur_label_pos += 1
			# TODO: case sensitivity stuff
			self.match_locations = [ m for m in self.match_locations if m[2].startswith(keyed_label) ]
			if len(self.match_locations) < 2:
				break
			self.redraw()
		log('keyed label: ' + keyed_label)

		# If a location was found, move cursor there in original pane
		if len(self.match_locations) > 0:
			log('match location: ' + str(self.match_locations[0]))
			move_tmux_cursor((self.match_locations[0][0], self.match_locations[0][1]), self.orig_pane['pane_id'])

def run_easymotion(stdscr):
	nkeys = 1
	if args.search_nkeys:
		nkeys = int(args.search_nkeys)
	EasyMotionAction(stdscr, nkeys).run()







def run_wrapper(main_action, args):
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
		z_win_id = runtmux([ 'new-window', '-dP', '-F', '#{session_id}:#{window_id}', '/bin/sh' ], one=True)
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

	cmd += f' "{main_action}"'
	#cmd += ' 2>/tmp/tm_wrap_log'
	runtmux([ 'respawn-pane', '-k', '-t', hidden_pane['pane_id_full'], cmd ])






argp = argparse.ArgumentParser(description='tmux pane utils')
argp.add_argument('-t', help='target pane')
argp.add_argument('--search-nkeys', help='number of characters to key in to search')

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
	if args.action == 'easymotion':
		curses.wrapper(run_easymotion)
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




