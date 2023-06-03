#!/usr/bin/env python
# Scroll IRC Art Bot - Developed by acidvegas in Python (https://git.acid.vegas/scroll)

import asyncio
import random
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
	modes   = None

class identity:
	nickname = 'scroll'
	username = 'scroll'
	realname = 'git.acid.vegas/scroll'
	nickserv = None

class throttle:
	flood     = 3    # delay between each command
	max_lines = 300  # maximum number of lines in art file to be played outside of #scroll
	message   = 0.05 # delay between each line sent
	results   = 10   # maximum number of results returned from search

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

def ssl_ctx():
	ctx = ssl.create_default_context()
	ctx.check_hostname = False
	ctx.verify_mode = ssl.CERT_NONE
	return ctx

class Bot():
	def __init__(self):
		self.db              = dict()
		self.last            = 0
		self.loops           = dict()
		self.playing         = False
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
				self.loops   = dict()
				self.playing = False
				self.slow    = False
				await asyncio.sleep(30)

	async def sync(self):
		try:
			cache   = self.db
			self.db = dict()
			ascii   = urllib.request.urlopen('https://raw.githubusercontent.com/ircart/ircart/master/ircart/.list').readlines()
			for item in ascii:
				item = item.decode(chardet.detect(item)['encoding']).replace('\n','').replace('\r','')
				if '/' in item:
					dir  = item.split('/')[0]
					name = item.split('/')[1]
					self.db[dir] = self.db[dir]+[name,] if dir in self.db else [name,]
				else:
					self.db['root'] = self.db['root']+[item,] if 'root' in self.db else [item,]
		except Exception as ex:
			try:
				await self.irc_error(connection.channel, 'failed to sync database', ex)
			except:
				error(connection.channel, 'failed to sync database', ex)
			self.db = cache

	async def play(self, chan, name):
		try:
			ascii = urllib.request.urlopen(f'https://raw.githubusercontent.com/ircart/ircart/master/ircart/{name}.txt', timeout=10)
			if ascii.getcode() == 200:
				ascii = ascii.readlines()
				if len(ascii) > throttle.max_lines and chan != '#scroll':
					await self.irc_error(chan, 'file is too big', 'take it to #scroll')
				else:
					await self.action(chan, 'the ascii gods have chosen... ' + color(name, cyan))
					for line in ascii:
						await self.sendmsg(chan, line.decode(chardet.detect(line)['encoding']).replace('\n','').replace('\r','') + reset)
						await asyncio.sleep(throttle.message)
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
				data = await asyncio.wait_for(self.reader.readuntil(b'\r\n'), 200)
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
				elif args[1] == '433':
					error('The bot is already running or nick is in use.')
				elif args[1] == 'INVITE' and len(args) == 4:
					invited = args[2]
					chan    = args[3][1:]
					if invited == identity.nickname and chan in (connection.channel, '#scroll'):
						await self.raw(f'JOIN {connection.channel} {connection.key}') if connection.key else await self.raw('JOIN ' + connection.channel)
				elif args[1] == 'KICK' and len(args) >= 4:
					chan   = args[2]
					kicked = args[3]
					if kicked == identity.nickname and chan in (connection.channel,'#scroll'):
						await asyncio.sleep(3)
						await self.raw(f'JOIN {connection.channel} {connection.key}') if connection.key else await self.raw('JOIN ' + connection.channel)
				elif args[1] == 'PRIVMSG' and len(args) >= 4:
					nick = args[0].split('!')[0][1:]
					chan = args[2]
					msg  = ' '.join(args[3:])[1:]
					if chan in  (connection.channel, '#scroll'):
						args = msg.split()
						if msg == '@scroll':
							await self.sendmsg(chan, bold + 'Scroll IRC Art Bot - Developed by acidvegas in Python - https://git.acid.vegas/scroll')
						elif args[0] == '.ascii':
							if msg == '.ascii stop':
								if self.playing:
									if chan in self.loops:
										self.loops[chan].cancel()
							elif time.time() - self.last < throttle.flood:
								if not self.slow:
									if not self.playing:
										await self.irc_error(chan, 'slow down nerd')
									self.slow = True
							elif len(args) >= 2 and not self.playing:
								self.slow = False
								if msg == '.ascii dirs':
									for dir in self.db:
										await self.sendmsg(chan, '[{0}] {1}{2}'.format(color(str(list(self.db).index(dir)+1).zfill(2), pink), dir.ljust(10), color('('+str(len(self.db[dir]))+')', grey)))
										await asyncio.sleep(throttle.message)
								elif msg == '.ascii list':
									await self.sendmsg(chan, underline + color('https://raw.githubusercontent.com/ircart/ircart/master/ircart/.list', light_blue))
								elif msg == '.ascii random':
									self.playing = True
									dir   = random.choice(list(self.db))
									ascii = random.choice(self.db[dir]) if dir == 'root' else dir+'/'+random.choice(self.db[dir])
									self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
								elif args[1] == 'random' and len(args) == 3:
									dir = args[2]
									if dir in self.db:
										self.playing = True
										ascii = random.choice(self.db[dir])
										self.loops[chan] = asyncio.create_task(self.play(chan, dir+'/'+ascii))
									else:
										await self.irc_error(chan, 'invalid directory name', dir)
								elif args[1] == 'search' and len(args) == 3:
									query   = args[2]
									results = list()
									for dir in self.db:
										for ascii in self.db[dir]:
											if query in ascii:
												results.append({'dir':dir,'name':ascii})
									if results:
										for item in results[:throttle.results]:
											if item['dir'] == 'root':
												await self.sendmsg(chan, '[{0}] {1}'.format(color(str(results.index(item)+1).zfill(2), pink), item['name']))
											else:
												await self.sendmsg(chan, '[{0}] {1} {2}'.format(color(str(results.index(item)+1).zfill(2), pink), item['name'], color('('+item['dir']+')', grey)))
											await asyncio.sleep(throttle.message)
									else:
										await self.irc_error(chan, 'no results found', query)
								elif len(args) == 2:
									option = args[1]
									if [x for x in ('..','?','%','\\') if x in option]:
										await self.irc_error(chan, 'nice try nerd')
									elif option == 'random':
										self.playing = True
										self.loops[chan] = asyncio.create_task(self.play(chan, random.choice(self.db)))
									else:
										ascii = [dir+'/'+option for dir in self.db if option in self.db[dir]]
										if ascii:
											ascii = ascii[0]
											if ascii.startswith('root/'):
												ascii = ascii.split('/')[1]
											self.playing = True
											self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
										else:
											await self.irc_error(chan, 'no results found', option)
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
else:
	asyncio.run(Bot().connect())