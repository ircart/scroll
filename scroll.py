#!/usr/bin/env python
# Scroll IRC Art Bot - Developed by acidvegas in Python (https://git.supernets.org/acidvegas/scroll)
# scroll/scroll.py

import asyncio
import io
import ipaddress
import os
import random
import re
import resource
import socket
import ssl
import tempfile
import time
import urllib.parse

try:
	import aiohttp
except ImportError:
	raise SystemExit('missing required aiohttp library (pip install aiohttp)')

try:
	import chardet
except ImportError:
	raise SystemExit('missing required chardet library (pip install chardet)')

try:
	from PIL import Image # Only needed for .ascii img
except ImportError:
	Image = None


class connection:
	server  = 'irc.supernets.org'
	port    = 6697
	ipv6    = False
	ssl     = True
	vhost   = None # Must in ('ip', port) format
	channel = '#superbowl'
	key     = None
	modes   = 'BdDg'

class identity:
	nickname = 'scroll'
	username = 'scroll'
	realname = 'git.acid.vegas/scroll'
	nickserv = None

class repo:
	url    = 'https://git.supernets.org'
	repo   = 'ircart/ircart'
	branch = 'master'

class img2irc:
	binary  = os.path.expanduser('~/.cargo/bin/img2irc')
	bytes   = 10 * 1024 * 1024   # Max download size
	pixels  = 4096               # Max image width & height
	formats = ('PNG', 'JPEG', 'GIF', 'WEBP')
	memory  = 1024 * 1024 * 1024 # Max memory for the img2irc process
	timeout = 30                 # Max seconds for the img2irc process
	width   = 80                 # Default & max output width in columns

# img2irc options that take a value & their (min, max) where a cap is needed (--render is forced to irc & --scale is not allowed)
img2irc_values = {'width': (1, img2irc.width), 'height': (1, None), 'crop': None, 'filter': None, 'rotate': None, 'blocks': None, 'brightness': None, 'contrast': None,
	'gamma': None, 'saturation': None, 'hue': None, 'dither': (0, 8), 'luma-brightness': None, 'luma-contrast': None, 'luma-gamma': None, 'luma-saturation': None,
	'colorspace': None, 'pixelize': (0, 50), 'gaussianblur': (0, 20), 'lumablur': (0, 20), 'oil': None, 'glyphs': None, 'include': None, 'include-range': None,
	'exclude': None, 'exclude-range': None}
img2irc_flags  = ('fliph', 'flipv', 'braille', 'invert', 'luma-invert', 'grayscale', 'nograyscale', 'boxblur', 'halftone', 'sepia', 'normalize', 'noise', 'emboss',
	'identity', 'laplace', 'denoise', 'sharpen', 'cali', 'dramatic', 'firenze', 'golden', 'lix', 'lofi', 'neue', 'obsidian', 'pastelpink', 'ryo', 'frostedglass',
	'solarize', 'edgedetection', 'smooth', 'smooth-features', 'perceptual-score')
img2irc_short  = {'w': 'width', 'H': 'height', 'b': 'brightness', 'c': 'contrast', 'g': 'gamma', 's': 'saturation', 'u': 'hue', 'i': 'invert', 'd': 'dither',
	'B': 'luma-brightness', 'C': 'luma-contrast', 'G': 'luma-gamma', 'S': 'luma-saturation', 'I': 'luma-invert'}


# Settings
admin = 'acidvegas!*@*' # Can use wildcards (Must be in nick!user@host format)
flags = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flagged.txt') # Where .ascii flag saves flagged art for review

# Formatting Control Characters / Color Codes
bold        = '\x02'
italic      = '\x1D'
underline   = '\x1F'
reverse     = '\x16'
reset       = '\x0f'
white       = '00'
black       = '01'
blue        = '02'
green       = '03'
red         = '04'
brown       = '05'
purple      = '06'
orange      = '07'
yellow      = '08'
light_green = '09'
cyan        = '10'
light_cyan  = '11'
light_blue  = '12'
pink        = '13'
grey        = '14'
light_grey  = '15'


def color(msg, foreground, background=None):
	return f'\x03{foreground},{background}{msg}{reset}' if background else f'\x03{foreground}{msg}{reset}'

def debug(data):
	print('{0} | [~] - {1}'.format(time.strftime('%I:%M:%S'), data))

def error(data, reason=None):
	print('{0} | [!] - {1} ({2})'.format(time.strftime('%I:%M:%S'), data, str(reason))) if reason else print('{0} | [!] - {1}'.format(time.strftime('%I:%M:%S'), data))

def is_admin(ident):
	return re.fullmatch(re.escape(admin).replace(r'\*', '.*'), ident)

def img2irc_args(tokens, lines):
	options = dict()
	while tokens:
		token = tokens.pop(0)
		if token.startswith('--'):
			name, _, value = token[2:].partition('=')
		elif re.fullmatch(r'-[a-zA-Z].*', token) and token[1] in img2irc_short:
			name, value = img2irc_short[token[1]], token[2:]
		else:
			raise ValueError(f'unknown option {token}')
		if name in img2irc_flags and not value:
			options[name] = None
		elif name in img2irc_values:
			if not value:
				if not tokens:
					raise ValueError(f'missing value for --{name}')
				value = tokens.pop(0)
			if img2irc_values[name]:
				low, high = img2irc_values[name][0], img2irc_values[name][1] or lines
				if not value.isdigit() or not low <= int(value) <= high:
					raise ValueError(f'--{name} must be {low}-{high}')
			if name == 'oil' and (not re.fullmatch(r'\d+,\d+(\.\d+)?', value) or int(value.split(',')[0]) > 10):
				raise ValueError('--oil must be radius,intensity with a radius of 0-10')
			options[name] = value
		else:
			raise ValueError(f'unknown option {token}')
	return options

def img_ready():
	# .ascii img needs both the Pillow library & the img2irc binary from setup.sh
	return Image is not None and os.path.isfile(img2irc.binary)

def is_public(address):
	ip = ipaddress.ip_address(address)
	return (getattr(ip, 'ipv4_mapped', None) or ip).is_global

def check_image(data):
	try:
		image = Image.open(io.BytesIO(data), formats=img2irc.formats)
	except Image.UnidentifiedImageError:
		raise ValueError('not a ' + '/'.join(img2irc.formats) + ' image')
	with image:
		if max(image.size) > img2irc.pixels:
			raise ValueError(f'image is {image.width}x{image.height}, max is {img2irc.pixels}x{img2irc.pixels}')
		image.load()
		return image.format

def limit_process():
	resource.setrlimit(resource.RLIMIT_AS, (img2irc.memory, img2irc.memory))
	resource.setrlimit(resource.RLIMIT_CPU, (img2irc.timeout, img2irc.timeout))

class PublicResolver(aiohttp.ThreadedResolver):
	async def resolve(self, host, port=0, family=socket.AF_INET):
		hosts = await super().resolve(host, port, family)
		if not all(is_public(item['host']) for item in hosts):
			raise OSError(0, f'{host} is not a public address')
		return hosts

def ssl_ctx():
	ctx = ssl.create_default_context()
	ctx.check_hostname = False
	ctx.verify_mode = ssl.CERT_NONE
	return ctx

class Bot():
	def __init__(self):
		self.db              = dict()
		self.host            = ''
		self.last            = time.time()
		self.lastimg         = 0
		self.loops           = dict()
		self.nickname        = identity.nickname
		self.playing         = False
		self.settings        = {
			'flood'        : 1,
			'ignore'       : 'big,birds,doc,gorf,hang,nazi,pokemon',
			'imgflood'     : 5,
			'linelen'      : 512,
			'lines'        : 500,
			'msg'          : 0.03,
			'results'      : 25}
		self.slow            = False
		self.reader          = None
		self.writer          = None

	async def raw(self, data):
		self.writer.write(data.encode('utf-8')[:int(self.settings['linelen'])-2] + b'\r\n')
		await self.writer.drain()

	def room(self, chan):
		# Bytes left for text once the server relays our PRIVMSG to the channel
		return int(self.settings['linelen']) - len(f':{self.nickname}!{self.host} PRIVMSG {chan} :{reset}\r\n'.encode('utf-8'))

	def trim(self, chan, line):
		# Cut on whole characters & color codes so the line relayed to the channel fits the server line limit
		room = self.room(chan)
		size = 0
		for match in re.finditer(r'\x03(\d{1,2}(,\d{1,2})?)?|.', line, re.S):
			size += len(match.group().encode('utf-8'))
			if size > room:
				return line[:match.start()]
		return line

	async def action(self, chan, msg):
		await self.sendmsg(chan, f'\x01ACTION {msg}\x01')

	async def sendmsg(self, target, msg):
		await self.raw(f'PRIVMSG {target} :{msg}')

	async def irc_error(self, chan, msg, reason=None):
		await self.sendmsg(chan, '[{0}] {1} {2}'.format(color('ERROR', red), msg, color(f'({reason})', grey))) if reason else await self.sendmsg(chan, '[{0}] {1}'.format(color('ERROR', red), msg))

	async def connect(self):
		while True:
			try:
				options = {
					'host'       : connection.server,
					'port'       : connection.port,
					'limit'      : 1024,
					'ssl'        : ssl_ctx() if connection.ssl else None,
					'family'     : 10 if connection.ipv6 else 2,
					'local_addr' : connection.vhost
				}
				self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(**options), 15)
				self.nickname = identity.nickname
				await self.raw(f'USER {identity.username} 0 * :{identity.realname}')
				await self.raw('NICK ' + self.nickname)
			except Exception as ex:
				error('failed to connect to ' + connection.server, ex)
			else:
				await self.listen()
			finally:
				if self.writer:
					self.writer.close()
				for item in self.loops:
					if self.loops[item]:
						self.loops[item].cancel()
				self.loops   = dict()
				self.playing = False
				self.slow    = False
				await asyncio.sleep(30)

	async def sync(self):
		db       = {'root': []}
		page     = 1
		per_page = 1000  # Gitea's default per_page limit

		while True:
			try:
				timeout = aiohttp.ClientTimeout(total=30)
				headers = {'User-Agent': 'scroll/1.0'}
				async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
					async with session.get(f'{repo.url}/api/v1/repos/{repo.repo}/git/trees/{repo.branch}?recursive=1&page={page}&per_page={per_page}', ssl=False) as resp:
						if resp.status != 200:
							error('failed to sync database', await resp.text())
							return False
						files = await resp.json()

						# Process files from this page
						for file in files['tree']:
							if file['path'].startswith('ircart/') and file['path'].endswith('.txt') and not file['path'].startswith('ircart/.'):
								name = file['path'][7:-4]
								if '/' in name:
									dir, fname = name.split('/', 1)
									db[dir] = db[dir]+[fname,] if dir in db else [fname,]
								else:
									db['root'].append(name)

						# Check if we've processed all pages
						if not files.get('truncated', False):
							break

						page += 1

			except Exception as ex:
				error('failed to sync database', ex)
				return False

		self.db = db
		return True

	async def play(self, chan, name):
		try:
			async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), headers={'User-Agent': 'scroll/1.0'}) as session:
				async with session.get(f'{repo.url}/{repo.repo}/raw/branch/{repo.branch}/ircart/{name}.txt') as resp:
					if resp.status != 200:
						return await self.irc_error(chan, 'invalid name', name)
					raw = await resp.read()
			try:
				ascii, encoding = raw.decode('utf-8-sig'), 'UTF-8'
			except UnicodeDecodeError:
				encoding = chardet.detect(raw)['encoding'] or 'UTF-8'
				ascii = raw.decode(encoding, errors='replace')
			ascii = ascii.replace('\r', '').rstrip('\n').split('\n')
			if len(ascii) > int(self.settings['lines']) and chan != '#scroll':
				await self.irc_error(chan, 'file is too big', f'take those {len(ascii):,} lines to #scroll')
			else:
				await self.action(chan, 'the ascii gods have chosen... ' + color(name, cyan) + ' ' + color(f'({encoding})', grey))
				for line in ascii:
					await self.sendmsg(chan, self.trim(chan, line) + reset)
					await asyncio.sleep(self.settings['msg'])
		except Exception as ex:
			try:
				await self.irc_error(chan, f'error playing {name}', ex)
			except Exception:
				error(f'error playing {name}', ex)
		finally:
			self.playing = False

	async def dupe(self, chan, name, copies):
		await self.action(chan, 'the ascii gods have doubled... ' + color(name, cyan) + ' ' + color(f'({len(copies)} copies: {", ".join(copies)})', grey))
		for item in copies:
			await self.play(chan, item)
			self.playing = True
		self.playing = False

	async def help(self, chan, topic=None):
		def arg(text):
			return color(text, cyan)
		bar = color('|', grey)
		if topic == 'img':
			rows = [
				('-w, --width',          f'1-{img2irc.width}',                'output width in columns ' + color(f'(default {img2irc.width})', grey)),
				('-H, --height',         f'1-{int(self.settings["lines"])}', 'output height in rows'),
				('--crop',               'x1,y1,x2,y2',                       'crop the image'),
				('--rotate',             'degrees',                           'rotate the image'),
				('--fliph',              None,                                'flip horizontally'),
				('--flipv',              None,                                'flip vertically'),
				('--filter',             'name',                              'nearest, triangle, catmull-rom, gaussian or lanczos3 ' + color('(default nearest)', grey)),
				('--glyphs, --blocks',   'types',                             'full, half, quarter, eighth, triangle, corner, geometric, box, legacy ' + color('(default all)', grey)),
				('--include',            'chars',                             'only use these characters'),
				('--include-range',      'start-end',                         'only use this unicode range ' + color('(e.g. 2580-259F)', grey)),
				('--exclude',            'chars',                             'never use these characters'),
				('--exclude-range',      'start-end',                         'never use this unicode range'),
				('--smooth',             None,                                'smooth rough glyph transitions'),
				('--smooth-features',    None,                                'experimental feature smoothing'),
				('--perceptual-score',   None,                                'experimental perceptual quality scoring'),
				('--braille',            None,                                'use braille dots instead of blocks'),
				('-b, --brightness',     'n',                                 'adjust brightness ' + color('(0 = no change)', grey)),
				('-c, --contrast',       'n',                                 'adjust contrast ' + color('(0 = no change)', grey)),
				('-g, --gamma',          '0-255',                             'adjust gamma'),
				('-s, --saturation',     'n',                                 'adjust saturation ' + color('(0 = no change)', grey)),
				('-u, --hue',            '0-360',                             'rotate hue'),
				('-i, --invert',         None,                                'invert colors'),
				('-d, --dither',         '0-8',                               'dithering'),
				('--colorspace',         'name',                              'hsl, hsv, hsluv or lch ' + color('(default hsv)', grey)),
				('--grayscale',          None,                                'black & white'),
				('--nograyscale',        None,                                'leave grays out of the palette'),
				('-B, --luma-brightness', 'n',                                'braille luma brightness'),
				('-C, --luma-contrast',  'n',                                 'braille luma contrast'),
				('-G, --luma-gamma',     '0-255',                             'braille luma gamma'),
				('-S, --luma-saturation', 'n',                                'braille luma saturation'),
				('-I, --luma-invert',    None,                                'braille inverted luminance'),
				('--pixelize',           '0-50',                              'pixelize size'),
				('--gaussianblur',       '0-20',                              'gaussian blur radius'),
				('--lumablur',           '0-20',                              'gaussian blur radius, luminance only'),
				('--boxblur',            None,                                'box blur'),
				('--oil',                'radius,intensity',                  'oil painting ' + color('(radius 0-10)', grey)),
				('--<effect>',           None,                                'halftone, sepia, normalize, noise, emboss, laplace, sharpen, edgedetection, solarize, frostedglass'),
				('--<filter>',           None,                                'cali, dramatic, firenze, golden, lix, lofi, neue, obsidian, pastelpink, ryo')]
			width = max(len(option + (f' <{value}>' if value else '')) for option, value, _ in rows) + 1
			lines = [color('OPTION'.ljust(width) + 'DESCRIPTION', yellow)]
			for option, value, text in rows:
				plain = option + (f' <{value}>' if value else '')
				lines.append(option + (' ' + arg(f'<{value}>') if value else '') + ' ' * (width - len(plain)) + f'{bar} {text}')
			lines.append(f'{color("example:", grey)} .ascii img https://example.com/cat.png -w 60 --braille -c 20 ' + color(f'(png, jpeg, gif or webp up to {img2irc.bytes // 1024 // 1024} MB & {img2irc.pixels}x{img2irc.pixels})', grey))
		else:
			lines = [
				color('COMMAND                              DESCRIPTION', yellow),
				f'@scroll                              {bar} information about scroll',
				'.ascii ' + color('[dir/]', pink) + arg('<name>') + f'                  {bar} play the {arg("<name>")} art file, optionally from a ' + color('[dir]', pink),
				f'.ascii dirs                          {bar} list of art directories',
				'.ascii dupe ' + color('[name]', pink) + f'                   {bar} play every copy of the next unflagged duplicate name, or ' + color('[name]', pink),
				f'.ascii flag {arg("<name>")} {arg("<reason>")}          {bar} flag bad art for review ' + color('(admin only)', grey),
				'.ascii help ' + (color('[img]', pink) if img_ready() else '     ') + f'                    {bar} show this help' + (' or the .ascii img options' if img_ready() else ''),
				f'.ascii img {arg("<url>")} ' + color('[options]', pink) + f'           {bar} convert an image to art ' + color('(see .ascii help img)', grey),
				f'.ascii list                          {bar} list of art filenames',
				'.ascii random ' + color('[dir|query]', pink) + f'            {bar} play random art, optionally from a ' + color('[dir]', pink) + ' or ' + color('[query]', pink),
				f'.ascii search {arg("<query>")}                {bar} search art files that match {arg("<query>")}',
				'.ascii settings ' + color('[<setting> <option>]', pink) + f' {bar} view settings or change one ' + color('(admin only)', grey),
				f'.ascii stop                          {bar} stop playing art',
				f'.ascii sync                          {bar} sync the ascii database to pump the newest art ' + color('(admin only)', grey)]
		for line in lines:
			if '.ascii img ' in line and not img_ready():
				continue
			await self.sendmsg(chan, self.trim(chan, line))
			await asyncio.sleep(self.settings['msg'])

	async def fetch(self, url):
		# Download an image from a public http(s) address, following up to 3 redirects
		connector = aiohttp.TCPConnector(resolver=PublicResolver())
		async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15), headers={'User-Agent': 'scroll/1.0'}) as session:
			for _ in range(4):
				parts = urllib.parse.urlsplit(url)
				if parts.scheme not in ('http', 'https') or not parts.hostname:
					raise ValueError('url must be http or https')
				if ':' in parts.hostname or parts.hostname.replace('.', '').isdigit(): # aiohttp connects to these directly without the resolver
					try:
						public = is_public(parts.hostname)
					except ValueError:
						public = False
					if not public:
						raise ValueError(f'{parts.hostname} is not a public address')
				async with session.get(url, allow_redirects=False) as resp:
					if resp.status in (301, 302, 303, 307, 308) and 'Location' in resp.headers:
						url = urllib.parse.urljoin(str(resp.url), resp.headers['Location'])
						continue
					if resp.status != 200:
						raise ValueError(f'http status {resp.status}')
					if int(resp.headers.get('Content-Length', 0)) > img2irc.bytes:
						raise ValueError(f'image is over {img2irc.bytes // 1024 // 1024} MB')
					data = b''
					async for chunk in resp.content.iter_chunked(65536):
						data += chunk
						if len(data) > img2irc.bytes:
							raise ValueError(f'image is over {img2irc.bytes // 1024 // 1024} MB')
					return data
			raise ValueError('too many redirects')

	async def img(self, chan, url, tokens):
		proc = None
		try:
			options = img2irc_args(tokens, int(self.settings['lines']))
			width   = int(options.pop('width', img2irc.width))
			data    = await self.fetch(url)
			fmt     = await asyncio.to_thread(check_image, data)
			with tempfile.NamedTemporaryFile(suffix='.' + {'JPEG': 'jpg'}.get(fmt, fmt.lower())) as fd:
				fd.write(data)
				fd.flush()
				# Shrink the width until every line fits the server line limit
				deadline = time.time() + img2irc.timeout
				for _ in range(4):
					argv = [img2irc.binary, fd.name, '--render=irc', f'--width={width}'] + [f'--{k}' if v is None else f'--{k}={v}' for k, v in options.items()]
					proc = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, preexec_fn=limit_process)
					try:
						out, err = await asyncio.wait_for(proc.communicate(), max(1, deadline - time.time()))
					except asyncio.TimeoutError:
						raise ValueError(f'took longer than {img2irc.timeout}s')
					if proc.returncode:
						raise ValueError(err.decode('utf-8', 'replace').strip().split('\n')[0].removeprefix('error: ') or f'img2irc exited with {proc.returncode}')
					ascii   = out.decode('utf-8', 'replace').rstrip('\n').split('\n')
					longest = max(len(line.encode('utf-8')) for line in ascii)
					if longest <= self.room(chan) or width == 1:
						break
					width = max(1, width * self.room(chan) // longest)
			if len(ascii) > int(self.settings['lines']) and chan != '#scroll':
				await self.irc_error(chan, 'image is too big', f'take those {len(ascii):,} lines to #scroll')
			else:
				await self.action(chan, 'the ascii gods have painted... ' + color(url, cyan) + ' ' + color(f'({fmt}, {width} columns)', grey))
				for line in ascii:
					await self.sendmsg(chan, self.trim(chan, line) + reset)
					await asyncio.sleep(self.settings['msg'])
		except Exception as ex:
			try:
				await self.irc_error(chan, 'error converting image', ex)
			except Exception:
				error('error converting image', ex)
		finally:
			if proc and proc.returncode is None:
				proc.kill()
				await proc.wait()
			self.playing = False

	async def listen(self):
		while not self.reader.at_eof():
			try:
				data = await asyncio.wait_for(self.reader.readuntil(b'\r\n'), 300)
			except Exception as ex:
				error('connection lost', ex)
				break
			try:
				line = data.decode('utf-8').strip()
				args = line.split()
				debug(line)
				if len(args) < 2:
					continue
				elif args[0] == 'ERROR':
					break
				elif args[0] == 'PING':
					await self.raw('PONG ' + args[1])
				elif args[1] == '001':
					self.nickname = args[2]
					if connection.modes:
						await self.raw(f'MODE {self.nickname} +{connection.modes}')
					if identity.nickserv:
						await self.sendmsg('NickServ', f'IDENTIFY {identity.nickname} {identity.nickserv}')
					await asyncio.sleep(6)
					await self.raw(f'JOIN {connection.channel} {connection.key}') if connection.key else await self.raw('JOIN ' + connection.channel)
					await self.raw('JOIN #scroll')
					await self.sync()
				elif args[1] == '433':
					self.nickname = identity.nickname + str(random.randint(10, 99))
					await self.raw('NICK ' + self.nickname)
				elif args[1] == 'NICK' and len(args) == 3:
					if args[0].split('!')[0][1:] == self.nickname:
						self.nickname = args[2].lstrip(':')
				elif args[1] == 'JOIN' and args[0].split('!')[0][1:] == self.nickname:
					self.host = args[0].split('!')[1]
				elif args[1] == '396' and len(args) >= 4: # RPL_HOSTHIDDEN
					self.host = self.host.split('@')[0] + '@' + args[3]
				elif args[1] == 'INVITE' and len(args) == 4:
					invited = args[2]
					chan    = args[3].lstrip(':')
					if invited == self.nickname and chan in (connection.channel, '#scroll'):
						await self.raw(f'JOIN {chan} {connection.key}') if chan == connection.channel and connection.key else await self.raw('JOIN ' + chan)
				elif args[1] == 'KICK' and len(args) >= 4:
					chan   = args[2]
					kicked = args[3]
					if kicked == self.nickname and chan in (connection.channel, '#scroll'):
						await asyncio.sleep(3)
						await self.raw(f'JOIN {chan} {connection.key}') if chan == connection.channel and connection.key else await self.raw('JOIN ' + chan)
				elif args[1] == 'PRIVMSG' and len(args) >= 4:
					ident = args[0][1:]
					chan  = args[2]
					msg   = ' '.join(args[3:])[1:]
					if chan in (connection.channel, '#scroll'):
						args = msg.split()
						if msg == '@scroll':
							await self.sendmsg(chan, bold + 'Scroll IRC Art Bot - Developed by acidvegas in Python - https://git.supernets.org/ircart/scroll')
						elif args and args[0] == '.ascii':
							if msg == '.ascii stop':
								if self.playing:
									if chan in self.loops:
										self.loops[chan].cancel()
							elif len(args) >= 4 and args[1] == 'flag' and is_admin(ident):
								results = [dir+'/'+ascii for dir in self.db for ascii in self.db[dir] if args[2] in (ascii, dir+'/'+ascii)]
								if results:
									name = results[0].replace('root/','')
									with open(flags, 'a') as fd:
										fd.write('{0} | {1} | {2} | {3}\n'.format(time.strftime('%Y-%m-%d %H:%M:%S'), name, ident, ' '.join(args[3:])))
									await self.sendmsg(chan, color('flagged ' + name, light_green))
								else:
									await self.irc_error(chan, 'no results found', args[2])
							elif time.time() - self.last < self.settings['flood']:
								if not self.slow:
									if not self.playing:
										await self.irc_error(chan, 'slow down nerd')
									self.slow = True
							elif len(args) >= 2 and not self.playing:
								self.slow = False
								self.last = time.time()
								if msg == '.ascii dirs':
									for dir in self.db:
										await self.sendmsg(chan, '[{0}] {1}{2}'.format(color(str(list(self.db).index(dir)+1).zfill(2), pink), dir.ljust(10), color('('+str(len(self.db[dir]))+')', grey)))
										await asyncio.sleep(self.settings['msg'])
								elif msg == '.ascii list':
									await self.sendmsg(chan, underline + color(f'{repo.url}/{repo.repo}/src/branch/{repo.branch}/ircart/.list', light_blue))
								elif args[1] == 'random' and len(args) in (2,3):
									if len(args) == 3:
										query = args[2]
									else:
										choices = [item for item in self.db if item not in self.settings['ignore'].split(',') and self.db[item]]
										if not choices:
											await self.irc_error(chan, 'database is empty', 'try .ascii sync')
											continue
										query = random.choice(choices)
									if query in self.db and self.db[query]:
										ascii = f'{query}/{random.choice(self.db[query])}'.replace('root/','')
										self.playing = True
										self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
									else:
										results = [{'name':ascii,'dir':dir} for dir in self.db for ascii in self.db[dir] if query in ascii]
										if results:
											ascii = random.choice(results)
											ascii = f'{ascii["dir"]}/{ascii["name"]}'.replace('root/','')
											self.playing = True
											self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
										else:
											await self.irc_error(chan, 'invalid directory name or search query', query)
								elif args[1] == 'img' and len(args) >= 3:
									if not img_ready():
										await self.irc_error(chan, 'image support is not enabled', 'run setup.sh')
									elif time.time() - self.lastimg < self.settings['imgflood']:
										await self.irc_error(chan, 'slow down nerd', f'{self.settings["imgflood"]}s between images')
									else:
										self.lastimg     = time.time()
										self.playing     = True
										self.loops[chan] = asyncio.create_task(self.img(chan, args[2], args[3:]))
								elif msg == '.ascii sync' and is_admin(ident):
									if await self.sync():
										await self.sendmsg(chan, bold + color('database synced', light_green))
									else:
										await self.irc_error(chan, 'failed to sync database')
								elif args[1] == 'search' and len(args) == 3:
									query   = args[2]
									results = [{'name':ascii,'dir':dir} for dir in self.db for ascii in self.db[dir] if query in ascii]
									if results:
										for item in results[:int(self.settings['results'])]:
											if item['dir'] == 'root':
												await self.sendmsg(chan, '[{0}] {1}'.format(color(str(results.index(item)+1).zfill(2), pink), item['name']))
											else:
												await self.sendmsg(chan, '[{0}] {1} {2}'.format(color(str(results.index(item)+1).zfill(2), pink), item['name'], color('('+item['dir']+')', grey)))
											await asyncio.sleep(self.settings['msg'])
									else:
										await self.irc_error(chan, 'no results found', query)
								elif args[1] == 'settings':
									if len(args) == 2:
										for item in self.settings:
											await self.sendmsg(chan, color(item.ljust(13), yellow) + color(str(self.settings[item]), grey))
									elif len(args) == 4 and is_admin(ident):
										setting = args[2]
										option  = args[3]
										if setting in self.settings:
											if setting in ('flood','imgflood','linelen','lines','msg','results'):
												try:
													option = float(option)
													self.settings[setting] = option
													await self.sendmsg(chan, color('OK', light_green))
												except ValueError:
													await self.irc_error(chan, 'invalid option', 'must be a float or int')
											else:
												self.settings[setting] = option
												await self.sendmsg(chan, color('OK', light_green))
										else:
											await self.irc_error(chan, 'invalid setting', setting)
								elif args[1] == 'help' and len(args) in (2, 3):
									if len(args) == 3 and (args[2] != 'img' or not img_ready()):
										await self.irc_error(chan, 'no help for', args[2])
									else:
										await self.help(chan, args[2] if len(args) == 3 else None)
								elif args[1] == 'dupe' and len(args) in (2,3):
									dupes = dict()
									for dir in self.db:
										for ascii in self.db[dir]:
											dupes.setdefault(ascii, []).append(ascii if dir == 'root' else dir+'/'+ascii)
									dupes = {name: dupes[name] for name in sorted(dupes) if len(dupes[name]) > 1}
									if len(args) == 3:
										name = args[2] if args[2] in dupes else None
									else:
										flagged = set()
										if os.path.exists(flags):
											with open(flags) as fd:
												flagged = {line.split(' | ')[1] for line in fd if line.count(' | ') >= 3}
										name = next((name for name in dupes if not flagged.intersection(dupes[name])), None)
									if name:
										self.playing = True
										self.loops[chan] = asyncio.create_task(self.dupe(chan, name, dupes[name]))
									else:
										await self.irc_error(chan, 'no duplicates found', args[2]) if len(args) == 3 else await self.irc_error(chan, 'no unflagged duplicates left')
								elif len(args) == 2:
									query = args[1]
									results = [dir+'/'+ascii for dir in self.db for ascii in self.db[dir] if query in (ascii, dir+'/'+ascii)]
									if results:
										results = results[0].replace('root/','')
										self.playing = True
										self.loops[chan] = asyncio.create_task(self.play(chan, results))
									else:
										await self.irc_error(chan, 'no results found', query)
			except (UnicodeDecodeError, UnicodeEncodeError):
				pass
			except Exception as ex:
				error('error handling line', ex)



if __name__ == '__main__':
	# Main
	print('#'*56)
	print('#{:^54}#'.format(''))
	print('#{:^54}#'.format('Scroll IRC Art Bot'))
	print('#{:^54}#'.format('Developed by acidvegas in Python'))
	print('#{:^54}#'.format('https://git.supernets.org/ircart/scroll'))
	print('#{:^54}#'.format(''))
	print('#'*56)
	asyncio.run(Bot().connect())
