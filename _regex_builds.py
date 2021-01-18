# Note: The regexes in this file are not intended to correctly validate
# all instances of the given type.  They are designed to match the most
# common variants while specifically excluding less-common ones that could
# introduce false matches.

import re

def make_path_regexes():
	# This is not intended to match all valid paths - that would result in too many matches.
	# Note: Spaces, as a common delimiter, are handled specially.  They are only allowed in
	# paths with at least 3 elements, and never in the first or last element.  There cannot
	# be more than one consecutive space, and it cannot be at the beginning or end of the
	# element.
	edge_delimiters = r'[][\s:=,#$"{}<>()' + "'" + ']'
	edge_delimiters_w_slash = r'[][\s:=,#$"{}<>()/' + "'" + ']'
	leader = r'(?:^|' + edge_delimiters + ')'
	leader_w_slash = r'(?:^|' + edge_delimiters_w_slash + ')'
	follower = r'(?:$|' + edge_delimiters + ')'
	path_el = r'(?:[a-zA-Z0-9_-]{1,80}|\.|\.\.)'
	filename_core = r'[a-zA-Z0-9_-]{1,80}'
	inner_path_el = r'[a-zA-Z0-9_-]{1,60}\\? [a-zA-Z0-9_-]{1,60}'
	either_path_el = r'(?:' + path_el + '|' + inner_path_el + ')'
	basic_filename = filename_core + r'\.' + r'[a-zA-Z][a-zA-Z0-9]{0,5}'
	path_filename = either_path_el + r'\.' + r'[a-zA-Z0-9]{1,6}'
	sep = r'[\\/]'
	root = r'(?:/|~/|[A-Z]:' + sep + ')'
	abspath = root + r'(?:' + either_path_el + sep + ')*' + r'(?:' + path_filename + '|' + path_el + sep + '?)'
	relpath2 = path_el + sep + r'(?:' + path_el + sep + '?|' + path_filename + ')'
	relpath3 = path_el + sep + r'(?:' + either_path_el + sep + r')+' + r'(?:' + path_el + sep + '?|' + path_filename + ')'
	anypath = r'(?:' + abspath + '|' + relpath2 + '|' + relpath3 + ')'
	rabspath = leader + '(' + abspath + ')' + follower
	ranypath = leader + '(' + anypath + ')' + follower
	rfilename = leader_w_slash + '(' + basic_filename + ')' + follower
	return rabspath, ranypath, rfilename

def test_path_regexes():
	testpaths = r'''
	foo
	foo/bar
	foo/bar/baz
	baz.mp3
	123.456
	C:\fooo
	C:\fooo.bar
	C:/fooo.bar
	/fooo
	/fooo.bar
	/abc/def/ghi
	foo bar/baz
	foo/bar baz/fiz
	foo/bar baz/fiz.buz
	./copytk.tmux
	././copytk.tmux
	'''.split('\n')
	testpaths = [ p.strip() for p in testpaths if len(p.strip()) ]

	abspath, anypath, filename = make_path_regexes()

	print('abspath: ' + abspath)
	print('anypath: ' + anypath)
	print('filename: ' + filename)

	for p in testpaths:
		m1 = re.fullmatch(abspath, p)
		m2 = re.fullmatch(anypath, p)
		m3 = re.fullmatch(filename, p)
		print(f'{p} - {"ABS" if m1 else ""} {"PATH" if m2 else ""} {"FILE" if m3 else ""}')


# Note: This url regex is not a validator, nor is it intended to be.  It is intended
# to match the most common kinds of URLs that are used and avoid unintended matches.
# Notably, spaces in urls are not matched; with spaces there's too great a chance
# of false positives (without a more complicated algorithm for matching urls)

def make_url_regex():
	# Match only at beginning of line or after whitespace or a common delimiting character
	edge_delimiters = r'[][\s:=,#"{}()' + "'" + ']'
	leader = r'(?:^|' + edge_delimiters + ')'
	proto = r'[a-zA-Z][a-zA-Z0-9]{1,5}://'
	creds = r'[a-zA-Z0-9_]+(?::[a-zA-Z0-9_-]+)?@'
	ipaddr = r'(?:[0-2]?[0-9]{1,2}\.){3}[0-2]?[0-9]{1,2}'
	hostname = r'(?:[a-zA-Z0-9][\w-]*\.)*[a-zA-Z][\w-]*'
	servname = r'(?:' + hostname + '|' + ipaddr + r')(?::[0-9]{1,5})?'
	# to match parts of path and qs, we also want to match parens (some websites
	# unfortunately use them) but doing do will likely result in false positives.
	# To reduce the chance of false positives, ensure matching parens here.
	token = r'(?:[\w.~%/&-]+|(?:[\w.~%/&-]*\([\w.~%/&-]*\)[\w.~%/&-]*)+)'
	urlpath = '/' + token + r'?/?'
	querystringkv = token + r'+(?:=' + token + '?)?'
	querystring = r'\?(?:' + querystringkv + r'&)*(?:' + querystringkv + r')?'
	fragment = r'#(?:' + querystringkv + r'&)*(?:' + querystringkv + r')?'
	follower = r'(?:$|' + edge_delimiters + ')'
	url = leader + '(' + proto + '(?:' + creds + ')?' + servname + '(?:' + urlpath + ')?' + '(?:' + querystring + ')?' + '(?:' + fragment + ')?' + ')' + follower
	return url

def test_url_regex():
	# https://mathiasbynens.be/demo/url-regex
	# note: note all are intended to match exactly for usability with matching
	testurls = '''
	http://foo.com/blah_blah
	http://foo.com/blah_blah/
	http://foo.com/blah_blah_(wikipedia)
	http://foo.com/blah_blah_(wikipedia)_(again)
	http://1.2.3.4/blah_blah_(wikipedia)_(again)
	http://www.example.com/wpstyle/?p=364
	https://www.example.com/foo/?bar=baz&inga=42&quux
	http://✪df.ws/123
	http://userid:password@example.com:8080
	http://userid:password@example.com:8080/
	http://userid@example.com
	http://userid@example.com/
	http://userid@example.com:8080
	http://userid@example.com:8080/
	http://userid:password@example.com
	http://userid:password@example.com/
	http://142.42.1.1/
	http://142.42.1.1:8080/
	http://➡.ws/䨹
	http://⌘.ws
	http://⌘.ws/
	http://foo.com/blah_(wikipedia)#cite-1
	http://foo.com/blah_(wikipedia)_blah#cite-1
	http://foo.com/unicode_(✪)_in_parens
	http://foo.com/(something)?after=parens
	http://☺.damowmow.com/
	http://code.google.com/events/#&product=browser
	http://j.mp
	ftp://foo.bar/baz
	http://foo.bar/?q=Test%20URL-encoded%20stuff
	http://مثال.إختبار
	http://例子.测试
	http://उदाहरण.परीक्षा
	http://-.~_!$&'()*+,;=:%40:80%2f::::::@example.com
	http://1337.net
	http://a.b-c.de
	http://223.255.255.254
	http://
	http://.
	http://..
	http://../
	http://?
	http://??
	http://??/
	http://#
	http://##
	http://##/
	http://foo.bar?q=Spaces should be encoded
	//
	//a
	///a
	///
	http:///a
	foo.com
	rdar://1234
	h://test
	http:// shouldfail.com
	:// should fail
	http://foo.bar/foo(bar)baz quux
	ftps://foo.bar/
	http://-error-.invalid/
	http://a.b--c.de/
	http://-a.b.co
	http://a.b-.co
	http://0.0.0.0
	http://10.1.1.0
	http://10.1.1.255
	http://224.1.1.1
	http://1.1.1.1.1
	http://123.123.123
	http://3628126748
	http://.www.foo.bar/
	http://www.foo.bar./
	http://.www.foo.bar./
	http://10.1.1.1%
	'''.split('\n')
	testurls = [ u.strip() for u in testurls if len(u.strip()) ]

	url = make_url_regex()

	print(url)

	for u in testurls:
		m = re.fullmatch(url, u)
		if m:
			print(f'{u} - Match: {m.group(1)}')
		else:
			print(f'{u} - No Match')

def print_rex(name, r, comment=None):
	rxstr = "r'" + r.replace("'", "'+\"'\"+r'") + "'"
	if comment:
		print(f"\t# {comment}")
	print(f"\t'{name}': {rxstr},")

#test_url_regex()

#print('URL:')
print_rex('urls', make_url_regex(), 'matches common types of urls and things that look like urls')
print

#test_path_regexes()

absp, anyp, fn = make_path_regexes()
#print('ABS PATH:')
print_rex('abspaths', absp, 'Unix and window style absolute paths')
#print('PATH:')
print_rex('paths', anyp, 'Absolute or relative paths')
#print('FILE:')
print_rex('filenames', fn, 'Isolated filenames without paths')

