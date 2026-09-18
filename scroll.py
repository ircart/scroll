#!/usr/bin/env python
# Scroll IRC Art Bot - Developed by acidvegas in Python (https://git.supernets.org/acidvegas/scroll)
# scroll/scroll.py

import asyncio
import os
import random
import re
import ssl
import time

try:
	import aiohttp
except ImportError:
	raise SystemExit('missing required aiohttp library (pip install aiohttp)')

try:
	import chardet
except ImportError:
	raise SystemExit('missing required chardet library (pip install chardet)')


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
		self.loops           = dict()
		self.nickname        = identity.nickname
		self.playing         = False
		self.settings        = {
			'flood'        : 1,
			'ignore'       : 'big,birds,doc,gorf,hang,nazi,pokemon',
			'linelen'      : 512,
			'lines'        : 500,
			'msg'          : 0.5,
			'results'      : 25}
		self.slow            = False
		self.reader          = None
		self.writer          = None

	async def raw(self, data):
		self.writer.write(data.encode('utf-8')[:int(self.settings['linelen'])-2] + b'\r\n')
		await self.writer.drain()

	def trim(self, chan, line):
		# Cut on whole characters & color codes so the line relayed to the channel fits the server line limit
		room = int(self.settings['linelen']) - len(f':{self.nickname}!{self.host} PRIVMSG {chan} :{reset}\r\n'.encode('utf-8'))
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
										ascii = f'{query}/{random.choice(self.db[query])}'
										self.playing = True
										self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
									else:
										results = [{'name':ascii,'dir':dir} for dir in self.db for ascii in self.db[dir] if query in ascii]
										if results:
											ascii = random.choice(results)
											ascii = f'{ascii["dir"]}/{ascii["name"]}'
											self.playing = True
											self.loops[chan] = asyncio.create_task(self.play(chan, ascii))
										else:
											await self.irc_error(chan, 'invalid directory name or search query', query)
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
											if setting in ('flood','linelen','lines','msg','results'):
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
