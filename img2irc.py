#!/usr/bin/env python
# Scroll IRC Art Bot - Developed by acidvegas in Python (https://git.acid.vegas/scroll)

'''
Props:
	- forked idea from malcom's img2irc (https://github.com/waveplate/img2irc)
	- big props to wrk (wr34k) for forking this + opencv implementation
'''

try:
	import cv2
except ImportError:
	raise SystemExit('missing required \'opencv-python\' library (https://pypi.org/project/opencv-python/)')
try:
	import numpy as np
except ImportError:
	raise SystemExit('missing required \'numpy\' library (https://pypi.org/project/numpy/)')

palettes = {
	'RGB16': [0xffffff, 0x000000, 0x00007f, 0x009300, 0xff0000, 0x7f0000, 0x9c009c, 0xfc7f00,
			  0xffff00, 0x00fc00, 0x009393, 0x00ffff, 0x0000fc, 0xff00ff,      0x0,      0x0],
	'RGB88': [0xffffff, 0x000000, 0x00007f, 0x009300, 0xff0000, 0x7f0000, 0x9c009c, 0xfc7f00,
			  0xffff00, 0x00fc00, 0x009393, 0x00ffff, 0x0000fc, 0xff00ff,      0x0,      0x0,
			  0x470000, 0x472100, 0x474700, 0x324700, 0x004700, 0x00472c, 0x004747, 0x002747,
			  0x000047, 0x2e0047, 0x470047, 0x47002a, 0x740000, 0x743a00, 0x747400, 0x517400,
			  0x007400, 0x007449, 0x007474, 0x004074, 0x000074, 0x4b0074, 0x740074, 0x740045,
			  0xb50000, 0xb56300, 0xb5b500, 0x7db500, 0x00b500, 0x00b571, 0x00b5b5, 0x0063b5,
			  0x0000b5, 0x7500b5, 0xb500b5, 0xb5006b, 0xff0000, 0xff8c00, 0xffff00, 0xb2ff00,
			  0x00ff00, 0x00ffa0, 0x00ffff, 0x008cff, 0x0000ff, 0xa500ff, 0xff00ff, 0xff0098,
			  0xff5959, 0xffb459, 0xffff71, 0xcfff60, 0x6fff6f, 0x65ffc9, 0x6dffff, 0x59b4ff,
			  0x5959ff, 0xc459ff, 0xff66ff, 0xff59bc, 0xff9c9c, 0xffd39c, 0xffff9c, 0xe2ff9c,
			  0x9cff9c, 0x9cffdb, 0x9cffff, 0x9cd3ff, 0x9c9cff, 0xdc9cff, 0xff9cff, 0xff94d3],
	'RGB99': [0xffffff, 0x000000, 0x00007f, 0x009300, 0xff0000, 0x7f0000, 0x9c009c, 0xfc7f00,
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
			  0xbcbcbc, 0xe2e2e2, 0xffffff]
}

def convert(data, max_line_len, img_width=80, palette='RGB99', quantize_colors=None):
	if palette not in palettes:
		raise Exception('invalid palette option')
	palette = palettes[palette]
	np_arr = np.asarray(bytearray(data), dtype="uint8")
	image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
	del data
	return convert_image(image, quantize_colors, max_line_len, img_width, palette)

def convert_image(orig_image, quantize_colors, max_line_len, img_width, palette):
	image = ircize(orig_image, img_width, quantize_colors)
	CHAR = '\u2580'
	buf = list()
	for i in range(0, image.shape[0], 2):
		if i+1 >= image.shape[0]:
			bitmap = [[bgr_to_hex(image[i, x]) for x in range(image.shape[1])]]
			bitmap += [[0 for _ in range(image.shape[1])]]
		else:
			bitmap = [[bgr_to_hex(image[y, x]) for x in range(image.shape[1])] for y in [i, i+1]]
		top_row = [AnsiPixel(px, palette) for px in bitmap[0]]
		bottom_row = [AnsiPixel(px, palette) for px in bitmap[1]]
		buf += [""]
		last_fg = last_bg = -1
		ansi_row = list()
		for j in range(image.shape[1]):
			top_pixel = top_row[j]
			bottom_pixel = bottom_row[j]
			pixel_pair = AnsiPixelPair(top_pixel, bottom_pixel)
			fg = pixel_pair.top.irc
			bg = pixel_pair.bottom.irc
			if j != 0:
				if fg == last_fg and bg == last_bg:
					buf[-1] += CHAR
				elif bg == last_bg:
					buf[-1] += f'\x03{fg}{CHAR}'
				else:
					buf[-1] += f'\x03{fg},{bg}{CHAR}'
			else:
				buf[-1] += f'\x03{fg},{bg}{CHAR}'
			last_fg = fg
			last_bg = bg
		if len(buf[-1].encode('utf-8', 'ignore')) > max_line_len:
			if img_width - 5 < 5:
				raise Exception('image would get too small')
			return convert_image(orig_image, quantize_colors, max_line_len, img_width-5, palette)
	return buf

def ircize(image, img_width, quantize_colors):
	(height, width, _) = image.shape
	img_height = img_width / width * height
	image = cv2.resize(image, (int(img_width), int(img_height)), interpolation=cv2.INTER_AREA)
	brightness = np.sum(image) / (255 * image.shape[0] * image.shape[1])
	minimum_brightness = 0.72
	ratio = brightness / minimum_brightness
	if ratio < 1:
		image = cv2.convertScaleAbs(image, alpha = 1 / ratio, beta = 0)
	imgf = np.float32(image).reshape(-1, 3)
	criteria = (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,20,2.0)
	compactness, label, center = cv2.kmeans(imgf, quantize_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
	center = np.uint8(center)
	final_img = center[label.flatten()]
	image = final_img.reshape(image.shape)
	return image

def hex_to_rgb(color):
	r = (color >> 16) & 255
	g = (color >> 8) & 255
	b = color & 255
	return (r,g,b)

def rgb_to_hex(rgb):
	if len(list(rgb)) < 3:
		r = g = b = rgb[0]
	else:
		r = rgb[0]
		g = rgb[1]
		b = rgb[2]

	return (r << 16) + (g << 8) + b

def bgr_to_hex(bgr):
	return rgb_to_hex((bgr[0], 0, 0)) if len(list(bgr)) < 3 else rgb_to_hex((bgr[2], bgr[1], bgr[0]))

def color_distance_squared(c1, c2):
	d1 = abs(c1[0] - c2[0])
	d2 = abs(c1[1] - c2[1])
	d3 = abs(c1[2] - c2[2])
	return d1 * d1 + d2 * d2 + d3 * d3

class AnsiPixel:
	def __init__(self, pixel_u32, palette):
		self.irc = self.nearest_hex_color(pixel_u32, palette)

	def nearest_hex_color(self, pixel_u32, hex_colors):
		rgb_colors = [hex_to_rgb(color) for color in hex_colors]
		rgb_colors.sort(key=lambda rgb: color_distance_squared(hex_to_rgb(pixel_u32), rgb))
		hex_color = rgb_to_hex(rgb_colors[0])
		return hex_colors.index(hex_color)

class AnsiPixelPair:
	def __init__(self, top, bottom):
		self.top = top
		self.bottom = bottom
