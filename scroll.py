#!/usr/bin/env python
# Scroll IRC Art Bot - Developed by acidvegas in Python (https://git.acid.vegas/scroll)

import asyncio
import io
import json
import random
import re
import ssl
import time
import urllib.request

class connection:
	server  = 'irc.network.com'
	port    = 6697
	ipv6    = False
	ssl     = True
	vhost   = None
	channel = '#chats'
	key     = None
	modes   = 'BdDg'

class identity:
	nickname = 'scroll'
	username = 'scroll'
	realname = 'git.acid.vegas/scroll'
	nickserv = None

# Settings
admin = 'acidvegas!~stillfree@most.dangerous.motherfuck' # CHANGE ME

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

def get_url(url, git=False):
	data = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'}
	if git:
		data['Accept'] = 'application/vnd.github.v3+json'
	req = urllib.request.Request(url, headers=data)
	return urllib.request.urlopen(req, timeout=10)

def is_admin(ident):
	return re.compile(admin.replace('*','.*')).search(ident)

def ssl_ctx():
	ctx = ssl.create_default_context()
	ctx.check_hostname = False
	ctx.verify_mode = ssl.CERT_NONE
	return ctx

class Bot():
	def __init__(self):
		self.db              = None
		self.last            = time.time()
		self.loops           = dict()
		self.host            = ''
		self.playing         = False
		self.settings        = {'flood':1, 'ignore':'big,birds,doc,gorf,hang,nazi,pokemon', 'lines':500, 'msg':0.03, 'palette':'RBG99', 'paste':True, 'png_width':80, 'results':25}
		self.slow            = False
		self.reader          = None
		self.writer          = None

	async def raw(self, data):
		self.writer.write(data[:510].encode('utf-8') + b'\r\n')
		await self.writer.drain()

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
				await self.raw(f'USER {identity.username} 0 * :{identity.realname}')
				await self.raw('NICK ' + identity.nickname)
			except Exception as ex:
				error('failed to connect to ' + connection.server, ex)
			else:
				await self.listen()
			finally:
				for item in self.loops:
					if self.loops[item]:
						self.loops[item].cancel()
				self.loops   = dict()
				self.playing = False
				self.slow    = False
				await asyncio.sleep(30)

	async def sync(self):
		cache   = self.db
		self.db = {'root':list()}
		try:
			sha     = [item['sha'] for item in json.loads(get_url('https://api.github.com/repos/ircart/ircart/contents', True).read().decode('utf-8')) if item['path'] == 'ircart'][0]
			files   = json.loads(get_url(f'https://api.github.com/repos/ircart/ircart/git/trees/{sha}?recursive=true', True).read().decode('utf-8'))['tree']
			for file in files:
				if file['type'] != 'tree':
					file['path'] = file['path'][:-4]
					if '/' in file['path']:
						dir  = file['path'].split('/')[0]
						name = file['path'].split('/')[1]
						self.db[dir] = self.db[dir]+[name,] if dir in self.db else [name,]
					else:
						self.db['root'].append(file['path'])
		except Exception as ex:
			try:
				await self.irc_error(connection.channel, 'failed to sync database', ex)
			except:
				error(connection.channel, 'failed to sync database', ex)
			finally:
				self.db = cache

	async def play(self, chan, name, paste=None):
		try:
			if paste:
				ascii = get_url(name)
			else:
				ascii = get_url(f'https://raw.githubusercontent.com/ircart/ircart/master/ircart/{name}.txt')
			if ascii.getcode() == 200:
				ascii = ascii.readlines()
				if len(ascii) > int(self.settings['lines']) and chan != '#scroll':
					await self.irc_error(chan, 'file is too big', f'take those {len(ascii):,} lines to #scroll')
				else:
					await self.action(chan, 'the ascii gods have chosen... ' + color(name, cyan))
					for line in ascii:
						try:
							line = line.decode()
						except:
							line = line.encode(chardet.detect(line)['encoding']).decode()  # Get fucked UTF-16
						await self.sendmsg(chan, line.replace('\n','').replace('\r','') + reset)
						await asyncio.sleep(self.settings['msg'])
			else:
				await self.irc_error(chan, 'invalid name', name)
		except Exception as ex:
			try:
				await self.irc_error(chan, 'error in play function', ex)
			except:
				error('error in play function', ex)
		finally:
			self.playing = False

	async def listen(self):
		while True:
			try:
				if self.reader.at_eof():
					break
				data = await asyncio.wait_for(self.reader.readuntil(b'\r\n'), 600)
				line = data.decode('utf-8').strip()
				args = line.split()
				debug(line)
				if line.startswith('ERROR :Closing Link:'):
					raise Exception('Connection has closed.')
				elif args[0] == 'PING':
					await self.raw('PONG '+args[1][1:])
				elif args[1] == '001':
					if connection.modes:
						await self.raw(f'MODE {identity.nickname} +{connection.modes}')
					if identity.nickserv:
						await self.sendmsg('NickServ', f'IDENTIFY {identity.nickname} {identity.nickserv}')
					await self.raw(f'JOIN {connection.channel} {connection.key}') if connection.key else await self.raw('JOIN ' + connection.channel)
					await self.raw('JOIN #scroll')
					await self.sync()
				elif args[1] == '311' and len(args) >= 6: # RPL_WHOISUSER
					nick = args[2]
					host = args[5]
					if nick == identity.nickname:
						self.host = host
				elif args[1] == '433':
					error('The bot is already running or nick is in use.')
				elif args[1] == 'INVITE' and len(args) == 4:
					invited = args[2]
					chan    = args[3][1:]
					if invited == identity.nickname and chan in (connection.channel, '#scroll'):
						await self.raw(f'JOIN {connection.channel} {connection.key}') if connection.key else await self.raw('JOIN ' + connection.channel)
				elif args[1] == 'JOIN' and len(args) >= 3:
					nick = args[0].split('!')[0][1:]
					host = args[0].split('@')[1]
					if nick == identity.nickname:
						self.host = host
				elif args[1] == 'KICK' and len(args) >= 4:
					chan   = args[2]
					kicked = args[3]
					if kicked == identity.nickname and chan in (connection.channel,'#scroll'):
						await asyncio.sleep(3)
						await self.raw(f'JOIN {connection.channel} {connection.key}') if connection.key else await self.raw('JOIN ' + connection.channel)
				elif args[1] == 'PRIVMSG' and len(args) >= 4:
					ident = args[0][1:]
					nick  = args[0].split('!')[0][1:]
					chan  = args[2]
					msg   = ' '.join(args[3:])[1:]
					if chan in  (connection.channel, '#scroll'):
						args = msg.split()
						if msg == '@scroll':
							await self.sendmsg(chan, bold + 'Scroll IRC Art Bot - Developed by acidvegas in Python - https://git.acid.vegas/scroll')
						elif args[0] == '.ascii':
							if msg == '.ascii stop':
								if self.playing:
									if chan in self.loops:
										self.loops[chan].cancel()
							elif time.time() - self.last < self.settings['flood']:
								if not self.slow:
									if not self.playing:
										await self.irc_error(chan, 'slow down nerd')
									self.slow = True
							elif len(args) >= 2 and not self.playing:
								self.slow = False
								if msg == '.ascii dirs':
									for dir in self.db:
										await self.sendmsg(chan, '[{0}] {1}{2}'.format(color(str(list(self.db).index(dir)+1).zfill(2), pink), dir.ljust(10), color('('+str(len(self.db[dir]))+')', grey)))
										await asyncio.sleep(self.settings['msg'])
								elif args[1] == 'img' and len(args) == 3:
									url = args[2]
									width = 512 - len(line.split(' :')[0])+4
									if url.startswith('https://') or url.startswith('http://'):
										try:
											content = get_url(url).read()
											ascii   = img2irc.convert(content, 512 - len(f":{identity.nickname}!{identity.username}@{self.host} PRIVMSG {chan} :\r\n"), int(self.settings['png_width']), self.settings['palette'])
										except Exception as ex:
											await self.irc_error(chan, 'failed to convert image', ex)
										else:
											if ascii:
												if len(ascii) <= self.settings['lines']:
													for line in ascii:
														await self.sendmsg(chan, line)
														await asyncio.sleep(self.settings['msg'])
												else:
													await self.irc_error('image is too big', 'take it to #scroll')
								elif msg == '.ascii list':
									await self.sendmsg(chan, underline + color('https://raw.githubusercontent.com/ircart/ircart/master/ircart/.list', light_blue))
								elif msg == '.ascii random':
									self.playing = True
									dir   = random.choice([item for item in self.db if item not in self.settings['ignore']])
									ascii = f'{dir}/{random.choice(self.db[dir])}'
									self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
								elif msg == '.ascii sync' and is_admin(ident):
									await self.sync()
									await self.sendmsg(chan, bold + color('database synced', light_green))
								elif args[1] == 'play' and len(args) == 3 and self.settings['paste']:
									url = args[2]
									if url.startswith('https://pastebin.com/raw/') and len(url.split('raw/')) > 1:
										self.loops[chan] = asyncio.create_task(self.play(chan, url, paste=True))
									else:
										await self.irc_error(chan, 'invalid pastebin url', paste)
								elif args[1] == 'random' and len(args) == 3:
									dir = args[2]
									if dir in self.db:
										self.playing = True
										ascii = f'{dir}/{random.choice(self.db[dir])}'
										self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
									else:
										await self.irc_error(chan, 'invalid directory name', dir)
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
											await self.sendmsg(chan, color(item.ljust(10), yellow) + color(str(self.settings[item]), grey))
									elif len(args) == 4 and is_admin(ident):
										setting = args[2]
										option  = args[3]
										if setting in self.settings:
											if setting in ('flood','lines','msg','png_width','results'):
												try:
													option = float(option)
													self.settings[setting] = option
													await self.sendmsg(chan, color('OK', light_green))
												except ValueError:
													await self.irc_error(chan, 'invalid option', 'must be a float or int')
											elif setting == 'paste':
												if option == 'on':
													self.settings[setting] = True
													await self.sendmsg(chan, color('OK', light_green))
												elif option == 'off':
													self.settings[setting] = False
													await self.sendmsg(chan, color('OK', light_green))
												else:
													await self.irc_error(chan, 'invalid option', 'must be on or off')
											else:
												self.settings[setting] = option
												await self.sendmsg(chan, color('OK', light_green))
										else:
											await self.irc_error(chan, 'invalid setting', setting)
								elif len(args) == 2:
									query = args[1]
									results = [dir+'/'+ascii for dir in self.db for ascii in self.db[dir] if query == ascii]
									if results:
										results = results[0].replace('root/','')
										self.playing = True
										self.loops[chan] = asyncio.create_task(self.play(chan, results))
									else:
										await self.irc_error(chan, 'no results found', query)
			except (UnicodeDecodeError, UnicodeEncodeError):
				pass
			except Exception as ex:
				error('fatal error occured', ex)
				break
			finally:
				self.last = time.time()

# Main
print('#'*56)
print('#{:^54}#'.format(''))
print('#{:^54}#'.format('Scroll IRC Art Bot'))
print('#{:^54}#'.format('Developed by acidvegas in Python'))
print('#{:^54}#'.format('https://git.acid.vegas/scroll'))
print('#{:^54}#'.format(''))
print('#'*56)
try:
	import chardet
except ImportError:
	raise SystemExit('missing required \'chardet\' library (https://pypi.org/project/chardet/)')
try:
	import img2irc
except ImportError:
	raise SystemExit('missing required \'img2irc\' file (https://github.com/ircart/scroll/blob/master/img2irc.py)')
asyncio.run(Bot().connect())
