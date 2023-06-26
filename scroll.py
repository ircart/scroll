#!/usr/bin/env python
# Scroll IRC Art Bot - Developed by acidvegas in Python (https://git.acid.vegas/scroll)

import asyncio
import json
import random
import re
import ssl
import time
import io
import urllib.request
from PIL import Image

class connection:
    server  = 'irc.server.com'
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

# used with .ascii img
img_width   = 80

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

# char for img2irc
CHAR = "\u2580"

def color(msg, foreground, background=None):
    return f'\x03{foreground},{background}{msg}{reset}' if background else f'\x03{foreground}{msg}{reset}'

def debug(data):
    print('{0} | [~] - {1}'.format(time.strftime('%I:%M:%S'), data))

def error(data, reason=None):
    print('{0} | [!] - {1} ({2})'.format(time.strftime('%I:%M:%S'), data, str(reason))) if reason else print('{0} | [!] - {1}'.format(time.strftime('%I:%M:%S'), data))

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
        self.playing         = False
        self.settings        = {'flood':1, 'ignore':'big,birds,doc,gorf,hang,nazi,pokemon', 'lines':300, 'msg':0.03, 'results':25, 'paste':True}
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
            sha     = [item['sha'] for item in json.loads(urllib.request.urlopen('https://api.github.com/repos/ircart/ircart/contents').read().decode('utf-8')) if item['path'] == 'ircart'][0]
            files   = json.loads(urllib.request.urlopen(f'https://api.github.com/repos/ircart/ircart/git/trees/{sha}?recursive=true').read().decode('utf-8'))['tree']
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
                ascii = urllib.request.urlopen(name, timeout=10)
            else:
                ascii = urllib.request.urlopen(f'https://raw.githubusercontent.com/ircart/ircart/master/ircart/{name}.txt', timeout=10)
            if ascii.getcode() == 200:
                ascii = ascii.readlines()
                if len(ascii) > int(self.settings['lines']) and chan != '#scroll':
                    await self.irc_error(chan, 'file is too big', 'take those {len(ascii):,} lines to #scroll')
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
                                elif args[1] == 'img' and len(args) == 3:
                                    url = args[2]
                                    if not url.startswith("http://") and not url.startswith("https://"):
                                        await self.irc_error(chan, 'invalid url', url)
                                        continue
                                    try:
                                        data = urllib.request.urlopen(args[2]).read()
                                    except:
                                        await self.irc_error(chan, 'invalid url', url)
                                        continue
                                    await self.img2irc(chan, data)
                                elif args[1] == 'settings':
                                    if len(args) == 2:
                                        for item in self.settings:
                                            await self.sendmsg(chan, color(item.ljust(10), yellow) + color(str(self.settings[item]), grey))
                                    elif len(args) == 4 and is_admin(ident):
                                        setting = args[2]
                                        option  = args[3]
                                        if setting in self.settings:
                                            if setting in ('flood','lines','msg','results'):
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


    async def img2irc(self, chan, raw_data):
        image = Image.open(io.BytesIO(raw_data))
        (width, height) = image.size
        img_height = img_width / width * height
        image.thumbnail((img_width, img_height), Image.Resampling.LANCZOS)
        ansi_image = AnsiImage(image)

        await self.irc_draw(chan, ansi_image)

    async def irc_draw(self, chan, ansi_image):
        buf = ""
        for (y, row) in enumerate(ansi_image.halfblocks):
            last_fg = -1
            last_bg = -1
            for (x, pixel_pair) in enumerate(row):
                fg = pixel_pair.top.irc
                bg = pixel_pair.bottom.irc

                if x != 0:
                    if fg == last_fg and bg == last_bg:
                        buf += CHAR
                    elif bg == last_bg:
                        buf += f"\x03{fg}{CHAR}"
                    else:
                        buf += f"\x03{fg},{bg}{CHAR}"
                else:
                    buf += f"\x03{fg},{bg}{CHAR}"

                last_fg = fg
                last_bg = bg

            if y != len(ansi_image.halfblocks) - 1:
                buf += "\n"
            else:
                buf += "\x0f"

        
        for line in buf.split("\n"):
            await self.sendmsg(chan, line)

RGB99 = [
    0xffffff, 0x000000, 0x00007f, 0x009300, 0xff0000, 0x7f0000, 0x9c009c, 0xfc7f00,
    0xffff00, 0x00fc00, 0x009393, 0x00ffff, 0x0000fc, 0xff00ff, 0x7f7f7f, 0xd2d2d2,
    0x470000, 0x472100, 0x474700, 0x324700, 0x004700, 0x00472c, 0x004747, 0x002747,
    0x000047, 0x2e0047, 0x470047, 0x47002a, 0x740000, 0x743a00, 0x747400, 0x517400,
    0x007400, 0x007449, 0x007474, 0x004074, 0x000074, 0x4b0074, 0x740074, 0x740045,
    0xb50000, 0xb56300, 0xb5b500, 0x7db500, 0x00b500, 0x00b571, 0x00b5b5, 0x0063b5,
    0x0000b5, 0x7500b5, 0xb500b5, 0xb5006b, 0xff0000, 0xff8c00, 0xffff00, 0xb2ff00,
    0x00ff00, 0x00ffa0, 0x00ffff, 0x008cff, 0x0000ff, 0xa500ff, 0xff00ff, 0xff0098,
    0xff5959, 0xffb459, 0xffff71, 0xcfff60, 0x6fff6f, 0x65ffc9, 0x6dffff, 0x59b4ff,
    0x5959ff, 0xc459ff, 0xff66ff, 0xff59bc, 0xff9c9c, 0xffd39c, 0xffff9c, 0xe2ff9c,
    0x9cff9c, 0x9cffdb, 0x9cffff, 0x9cd3ff, 0x9c9cff, 0xdc9cff, 0xff9cff, 0xff94d3,
    0x000000, 0x131313, 0x282828, 0x363636, 0x4d4d4d, 0x656565, 0x818181, 0x9f9f9f,
    0xbcbcbc, 0xe2e2e2, 0xffffff,
]


def hex_to_rgb(color):
    r = color >> 16
    g = (color >> 8) % 256
    b = color % 256
    return (r,g,b)

def rgb_to_hex(rgb):
    (r,g,b) = rgb
    return (r << 16) + (g << 8) + b

def color_distance_squared(c1, c2):
    dr = c1[0] - c2[0]
    dg = c1[1] - c2[1]
    db = c1[2] - c2[2]
    return dr * dr + dg * dg + db * db

class AnsiPixel:
    irc: None

    def __init__(self, pixel_u32):
        self.irc  = self.nearest_hex_color(pixel_u32, RGB99)

    def nearest_hex_color(self, pixel_u32, hex_colors):
        rgb_colors = [hex_to_rgb(color) for color in hex_colors]
        rgb_colors.sort(key=lambda rgb: color_distance_squared(hex_to_rgb(pixel_u32), rgb))
        hex_color = rgb_to_hex(rgb_colors[0])
        return hex_colors.index(hex_color)


class AnsiPixelPair:
    top: None
    bottom: None

    def __init__(self, top, bottom):
        self.top = top
        self.bottom = bottom

class AnsiImage:
    image = None
    bitmap = list(list())
    halfblocks = list(list())
    def __init__(self, image):
        self.bitmap = [[self.make_rgb_u32(image.getpixel((x, y))) for x in range(image.size[0])] for y in range(image.size[1])]
        
        if len(self.bitmap) % 2 != 0:
            self.bitmap.append([0 for x in range(image.size[0])])

        ansi_bitmap = [[AnsiPixel(y) for y in x] for x in self.bitmap]

        ansi_canvas = list(list())

        for two_rows in range(0, len(ansi_bitmap), 2):
            top_row = ansi_bitmap[two_rows]
            bottom_row = ansi_bitmap[two_rows+1]

            ansi_row = list()

            for i in range(len(self.bitmap[0])):
                top_pixel = top_row[i]
                bottom_pixel = bottom_row[i]

                pixel_pair = AnsiPixelPair(top_pixel, bottom_pixel)
                ansi_row.append(pixel_pair)

            ansi_canvas.append(ansi_row)

        self.image = image
        self.halfblocks = ansi_canvas


    def make_rgb_u32(self, pixel):
        return rgb_to_hex(pixel)
        

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
