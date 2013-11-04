#!/usr/bin/env python
# Copyright 2009 Jeremy Worboys <jemthealmighty@gmail.com>
# Licensed for distribution under the GPL version 3
#
# TODO:
# 		[-] Write documentation for most objects/methods.
#		[-] Add styling to `Form` object
#		[ ] Add style inheritance
#		[-] Make use of 'left', 'center', 'right' in positioning
# 		[ ] Clean up `get_surface` method for most objects.
#		[ ] Move attribute styling to object `style` property
#		[ ] Impliment a Style object
# 		[ ] Integrate `style` property as part of `FormObject`
#				rather than individual objects.
# 		[ ] Find and fix any bottle-necks.
#		[ ] Add form objects as attributes of Form object.
#				Objects referenced as <form>.<obj_name> -> <form>._objects[<obj_name>]
#				Include a <form>.active -> <form>._objects[<form>._index[<form>.selected]]
#		[=] Non-blocking form functionality.
#				Done by calling <form>.update(<screen>, <event>)
#				from a seperate event loop.
#					- Problem with quitting
# 		[-] Scroll bar border width bug [N.B. Something to do with "...-(?)//2" ].
#				(Needs rewrite due to issues with border size)
#		[#] Add/Rem hooks with <object>.[add/rem]_hook('<hook>', function, args)
#				Hooks run after the function they are assigned to.
#			Hooks:
#				<Form>
#					__focus_switch__
#					__next__
#					__previous__
#					__draw__
#					__update__
#					__clear__
#				<FormObject>
#					__focus_switch__
#					__focus__
#					__blur__
#					__update__
#					__change_value__
#		[-] Implement mouse recognition
#				When drawing each surface return a list of tuples:
#				[(Rect hotspot, {action: (function, args, kwargs),}),] which will update a form list.
#				On each form update: scan mouse actions against Rects and run appropriate
#				function for the action.
# 		[ ] Major error checking.

import pygame, time
import pygame.locals as PL

FPS						= 25		# Frames per second
CURSOR_FLASH_SPEED		= .7		# Seconds
KEY_REPEAT_DELAY		= 500		# Milliseconds
KEY_REPEAT_INTERVAL		= 150		# Milliseconds
SCROLL_BAR_WIDTH		= 10		# Pixels
STANDARD_MARGIN 		= (20,20)	# (H,V) Pixels

_IMAGES_				= [] 		# A container for all updating Image objects
_CLOCK_					= pygame.time.Clock()

class HookController(dict):
	def __init__(self, parent):
		dict.__init__(self)
		self.parent = parent

	def run(self, *hooks):
		''' Run created hooks '''
		for hook in hooks:
			if hook in self:
				if hook[:2] == '__':
					self[hook][0](self.parent, *self[hook][1], **self[hook][2])
				elif hook[0] == '_':
					self[hook][0](*self[hook][1], **self[hook][2])
				return

class Form(object):
	def __init__(self, auto_submit=True, alpha=0, bg_color=(200,200,200,255), bg_surf=None, bg_surf_align=(0,0)):
		''' N.B. Be very careful with transparent backgrounds!
		Alpha:
			-1: Fade into `color`
			 0: Solid `color`
			 1: Alpha `color` on `bg_surf` '''
		self._auto_submit = auto_submit
		self._objects = {}
		self._index = {}
		self._selected = 0
		self._hooks = HookController(self)
		self._hotspots = None
		# Background settings
		if alpha == 1 and bg_surf == None:
			alpha = -1
		if alpha == 0:
			bg_color = bg_color[:3]
		self._alpha = int(alpha)
		self._bg_color = bg_color
		self._bg_surf = bg_surf
		self._bg_surf_align = bg_surf_align
		self._flip = True

	def _next(self):
		# Run hook
		self._hooks.run('__next__', '__focus_switch__')
		# Do next
		o = self._objects[self._index[self._selected]]
		if not isinstance(o, Select) or not o._is_active:
			o.blur()
			if self._selected+1 in self._index:
				self._selected += 1
			else:
				self._selected = 0
			o = self._objects[self._index[self._selected]]
			o.focus()
		if o._tab_skip:
			self._next()

	def _previous(self):
		# Run hook
		self._hooks.run('__previous__', '__focus_switch__')
		# Do previous
		o = self._objects[self._index[self._selected]]
		if not isinstance(o, Select) or not o._is_active:
			o.blur()
			if self._selected-1 in self._index:
				self._selected -= 1
			else:
				self._selected = len(self._index)-1
			o = self._objects[self._index[self._selected]]
			o.focus()
		if o._tab_skip:
			self._previous()

	def _click(self, pos):
		# Run hook
		self._hooks.run('__click__')
		# Get set of actions
		actions = [h[1]['click'] for h in self._hotspots if h[0].collidepoint(pos)]
		# Run actions
		for a in actions:
			a[0](*a[1], **a[2])

	def _draw(self, screen):
		# Run hook
		self._hooks.run('__draw__')
		# Make sure the form has objects
		if not len(self._objects):
			raise AttributeError('Form has no objects.')
		if abs(self._alpha) == 1:
			if self._bg_surf:
				screen.blit(self._bg_surf, self._bg_surf_align)
			surf = pygame.Surface(screen.get_size()).convert_alpha()
			surf.fill(self._bg_color)
			screen.blit(surf, (0,0))
			if self._alpha == 1:
				self._alpha += 1
		elif self._alpha == 0:
			screen.fill(self._bg_color)
		c_y = 20
		blit_top, top_o = None, None
		self._hotspots = []
		for i in xrange(0, len(self._objects)):
			o = self._objects[self._index[i]]
			if o._in_frame:
				continue
			s = o.get_surface()
			left = (o.style['left'],(screen.get_width()-s.get_width())//2)[o.style['left']=='center']
			if isinstance(o, Select) and o._is_active:
				if o.style['position'] == 'absolute':
					blit_top = [s, (left, o.style['top']-(s.get_height()-o.style['height'])//2)]
					top_o = o
				else:
					blit_top = [s, (left, o.style['top']+c_y-(s.get_height()-o.style['height'])//2)]
					top_o = o
					c_y += o.style['top']+o.style['height']+o.style['bottom']
			else:
				if o.style['position'] == 'absolute':
					rect = screen.blit(s, (left, o.style['top']))
				else:
					rect = screen.blit(s, (left, c_y+o.style['top']))
					c_y += o.style['top']+s.get_height()+o.style['bottom']
			if isinstance(o, Frame):
				m = (left, o.style['top'])
				for h in o._hotspots:
					h[0].move_ip(*m)
				self._hotspots.extend(o._hotspots)
			else:
				hs = o.hotspots()
				if hs:
					self._hotspots.append((rect, hs))
		if blit_top:
			rect = screen.blit(*blit_top)
			hs = top_o.hotspots()
			if hs:
				self._hotspots.append((rect, hs))
		if self._flip:
			pygame.display.flip()

	def add_hook(self, name, function, args=(), kwargs={}):
		self._hooks[name] = (function, args, kwargs)

	def rem_hook(self, name):
		if name in self._hooks:
			del self._hooks[name]

	def get_value(self, name):
		if not name in self._objects:
			raise KeyError('Form does not contain a "%s" object' % name)
		return self._objects[name].value()

	def clear(self):
		# Run hook
		self._hooks.run('__clear__')
		# Restore all values to default
		for _, obj in self._objects.iteritems():
			obj._reset()

	def submit(self):
		# Stop running
		self._running = False

	def add_object(self, name, obj, index=None):
		''' Add object to Form with reference "name". '''
		if name not in self._objects:
			# Add object reference
			self._objects[name] = obj
			# Add object index
			if not index or index >= len(self._index):
				index = len(self._index)
				self._index[index] = name
			else:
				for i in xrange(index, len(self._index)-1):
					self._index[i+1] = self._index[i]
				self._index[index] = name
			# Add all containing objects
			if isinstance(obj, Frame):
				for j in xrange(len(obj._index)):
					n = obj._index[j]
					self.add_object(n, obj._objects[n], index+j+1)
		else:
			raise ValueError('Form object already contains a "%s" object' % name)

	def rem_object(self, name):
		''' Removes object initialized with "name" from the form.\n\nN.B. This is currently a slow, cpu heavy, operation. '''
		if name in self._objects:
			# Remove all containing objects
			if isinstance(self._objects[name], Frame):
				for _,n in self._objects[name]._index.iteritems():
					self.rem_object(n)
			# Update parent
			parent = self._objects[name]._in_frame
			if parent:
				parent.rem_object(name)
			# Delete object
			self._objects.__delitem__(name)
			# Update indexes
			x = dict([(v, k) for (k, v) in self._index.iteritems()])[name]
			for i in xrange(x+1, len(self._index)-1):
				self._index[i] = self._index[i+1]
			# Remove index
			self._index.__delitem__(i+1)
			# Check that the removed item wasn't selected
			if self._selected >= len(self._index):
				self._selected = len(self._index)-1
		else:
			raise KeyError('Form object does not contain a "%s" object' % name)

	def update(self, screen, e):
		''' Runs event on form and then displays to screen. '''
		# Run hook
		self._hooks.run('__update__')
		# Do update
		if e.type == PL.QUIT:
			self._running = False
			return None
		elif e.type == PL.MOUSEBUTTONUP and self._hotspots:
			self._click(e.pos)
		elif e.type == PL.KEYDOWN:
			# Move between objects
			if e.key == PL.K_TAB:
				m = pygame.key.get_mods()
				if m & PL.KMOD_LSHIFT or m & PL.KMOD_RSHIFT:
					self._previous()
				else:
					self._next()
			# Check whether selected object wants the event
			elif not self._objects[self._index[self._selected]].update(e):
				pass
			# Submit form
			elif e.key == PL.K_RETURN and self._auto_submit:
				self.submit()
		# Draw the form
		self._draw(screen)

	def run(self, screen):
		''' Displays the form on "screen" blocking the script until the form is submitted.\nReturns a FormResult object. '''
		# Make sure the form has objects
		if not len(self._objects):
			raise AttributeError('Form has no objects.')
		if self._objects[self._index[self._selected]]._tab_skip:
			self._next()
		# Loopdy-loop
		self._running = True
		self._draw(screen)
		while self._running:
			# Show next image frame
			for i in _IMAGES_:
				i._next()
			# Run events and draw form
			self.update(screen, pygame.event.poll())
			# Limit FPS
			_CLOCK_.tick(FPS)
		return FormResult(self._objects)

class FormResult(dict):
	def __init__(self, objects):
		dict.__init__(self)
		for name, obj in objects.iteritems():
			val = obj.value()
			if val:
				self.__setattr__(name, val)
				self[name] = val

class FormObject(object):
	''' A base used for most form objects '''
	def __init__(self, value):
		self._value = self._default = value
		self._has_focus = False
		self._tab_skip = False
		self._in_frame = None
		self._hooks = HookController(self)

	def _reset(self):
		''' Restore value to default '''
		# Run hook
		self._hooks.run('__change_value__')
		self._value = self._default

	def hotspots(self):
		''' Return a dict of {event -> action} or None '''
		return None

	def add_hook(self, name, function, args):
		self._hooks[name] = (function, args)

	def rem_hook(self, name):
		if name in self._hooks:
			del self._hooks[name]

	def update(self, e):
		''' Deal with events '''
		# Run hook
		self._hooks.run('__update__')
		return True

	def focus(self):
		''' When the object gains focus '''
		# Run hook
		self._hooks.run('__focus__', '__focus_switch__')
		self._has_focus = True

	def blur(self):
		''' When the object loses focus '''
		# Run hook
		self._hooks.run('__blur__', '__focus_switch__')
		self._has_focus = False

class Seperator(FormObject):
	def __init__(self, color=(0,0,0), width=100, size=1, **kwargs):
		# Initialise as a form object
		FormObject.__init__(self, None)
		self._tab_skip = True
		# Style
		self._color = color
		self._width = int(width)
		self._size = int(size)
		# Default box styles
		self.style = {
			'position'		: 'relative',
			'top'			: STANDARD_MARGIN[1]//2,
			'bottom'		: STANDARD_MARGIN[1]//2,
			'left'			: 'center',
			'right'			: 0
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			if s in self.style:
				self.style[s] = v

	def value(self):
		return None

	def get_surface(self):
		# Create surface
		line = pygame.Surface((self._width, self._size)).convert_alpha()
		# Add box
		line.fill(self._color)
		return line

class Image(FormObject):
	def __init__(self, images, start=0, auto_scroll=True, int_align=('center','center'), **kwargs):
		# Initialise as a form object
		FormObject.__init__(self, None)
		self._tab_skip = True
		# Register as an updating image
		if auto_scroll:
			global _IMAGES_
			_IMAGES_.append(self)
		# Store some info
		try:
			self._images = list(images)
		except TypeError:
			self._images = [images]
		self._index = start
		self._int_align = int_align
		# Default box styles
		self.style = {
			# Appearance
			'border_width'	: 0,
			'border_color'	: (0,0,0),
			'bg_color'		: (255,255,255, 0),
			# Size
			'height'		: None,
			'width'			: None,
			# Position
			'position'		: 'relative',
			'top'			: STANDARD_MARGIN[1]//2,
			'bottom'		: STANDARD_MARGIN[1]//2,
			'left'			: STANDARD_MARGIN[0]//2,
			'right'			: STANDARD_MARGIN[0]//2
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			if s in self.style:
				self.style[s] = v

	def _next(self):
		# Run hook
		self._hooks.run('__change_value__')
		# Do next
		self._index += 1
		if self._index >= len(self._images):
			self._index = 0

	def value(self):
		return None

	def get_surface(self):
		# Make sure the frame has objects
		if not len(self._images):
			raise AttributeError('Image has no images.')
		img = self._images[self._index]
		width = (img.get_width(),self.style['width'])[self.style['width']!=None]
		height = (img.get_height(),self.style['height'])[self.style['height']!=None]
		surf = pygame.Surface((width, height)).convert_alpha()
		surf.fill(self.style['bg_color'])
		if self.style['border_width'] > 0:
			pygame.draw.rect(surf, self.style['border_color'], (0, 0, width-self.style['border_width']//2, height-self.style['border_width']//2), self.style['border_width'])
		left = (self._int_align[0],(surf.get_width()-img.get_width())//2)[self._int_align[0]=='center']
		top = (self._int_align[1],(surf.get_height()-img.get_height())//2)[self._int_align[1]=='center']
		surf.blit(img, (left, top))
		return surf

class Frame(FormObject):
	def __init__(self, size, pos, **kwargs):
		# Initialise as a form object
		FormObject.__init__(self, None)
		self._tab_skip = True
		# Store some info
		self.position = pos
		self._objects = {}
		self._index = {}
		self._hotspots = None
		# Default box styles
		self.style = {
			# Appearance
			'border_width'	: 0,
			'border_color'	: (0,0,0),
			'bg_color'		: (255,255,255, 0),
			# Size
			'height'		: size[1],
			'width'			: size[0],
			# Position
			'position'		: 'absolute',
			'top'			: pos[1],
			'bottom'		: 0,
			'left'			: pos[0],
			'right'			: 0
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			if s in self.style:
				self.style[s] = v

	def value(self):
		return None

	def add_object(self, name, obj, index=None):
		''' Add object to Form with reference "name". '''
		if name not in self._objects:
			# Reference as child
			obj._in_frame = self
			# Add object reference
			self._objects[name] = obj
			# Add object index
			if not index or index >= len(self._index):
				self._index[len(self._index)] = name
			else:
				for i in xrange(index, len(self._index)-1):
					self._index[i+1] = self._index[i]
				self._index[index] = name
		else:
			raise ValueError('Form object already contains a(n) "%s" object' % name)

	def rem_object(self, name):
		''' Removes object initialized with "name" from the form.\n\nN.B. This is currently a slow, cpu heavy, operation. '''
		if name in self._objects:
			# Delete object
			self._objects.__delitem__(name)
			# Update indexes
			x = dict([(v, k) for (k, v) in self._index.iteritems()])[name]
			for i in xrange(x+1, len(self._index)-1):
				self._index[i] = self._index[i+1]
			# Remove index
			self._index.__delitem__(i+1)
			# Check that the removed item wasn't selected
			if self._selected >= len(self._index):
				self._selected = len(self._index)-1
		else:
			raise KeyError('Form object does not contain a(n) "%s" object' % name)

	def get_surface(self):
		# Make sure the frame has objects
		if not len(self._objects):
			raise AttributeError('Frame has no objects.')
		surf = pygame.Surface((self.style['width'], self.style['height'])).convert_alpha()
		surf.fill(self.style['bg_color'])
		if self.style['border_width'] > 0:
			pygame.draw.rect(surf, self.style['border_color'], (0, 0, self.style['width']-self.style['border_width']//2, self.style['height']-self.style['border_width']//2), self.style['border_width'])
		c_y = self.style['border_width']
		blit_top, top_o = None, None
		self._hotspots = []
		for i in xrange(0, len(self._objects)):
			o = self._objects[self._index[i]]
			if o._in_frame and o._in_frame != self:
				continue
			s = o.get_surface()
			left = (o.style['left'],(surf.get_width()-s.get_width())//2)[o.style['left']=='center']
			if isinstance(o, Select) and o._is_active:
				if o.style['position'] == 'absolute':
					blit_top = [s, (left, o.style['top']-(s.get_height()-o.style['height'])//2)]
					top_o = o
				else:
					blit_top = [s, (left, o.style['top']+c_y-(s.get_height()-o.style['height'])//2)]
					top_o = o
					c_y += o.style['top']+o.style['height']+o.style['bottom']
			else:
				if o.style['position'] == 'absolute':
					rect = surf.blit(s, (left, o.style['top']))
				else:
					rect = surf.blit(s, (left, c_y+o.style['top']))
					c_y += o.style['top']+s.get_height()+o.style['bottom']
			hs = o.hotspots()
			if hs:
				self._hotspots.append((rect, hs))
		if blit_top:
			rect = surf.blit(*blit_top)
			hs = top_o.hotspots()
			if hs:
				self._hotspots.append((rect, hs))
		return surf

class Text(FormObject):
	''' Displays text on a form '''
	def __init__(self, value, label_font=None, label_size=22, label_color=(0,0,0), label_style=[], **kwargs):
		# Initialise as a form object
		FormObject.__init__(self, value)
		self._tab_skip = True
		# Create font
		if isinstance(label_font, pygame.font.Font):
			self._font = label_font
		else:
			self._font = pygame.font.Font(label_font, int(label_size))
		# Style font
		self._color = label_color
		for s in label_style:
			if s == 'bold' : self._font.set_bold(True)
			elif s == 'italic' : self._font.set_italic(True)
			elif s == 'underline' : self._font.set_underline(True)
		# Default box styles
		self.style = {
			# Position
			'position'		: 'relative',
			'top'			: STANDARD_MARGIN[1]//2,
			'bottom'		: STANDARD_MARGIN[1]//2,
			'left'			: STANDARD_MARGIN[0]//2,
			'right'			: STANDARD_MARGIN[0]//2
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			# Remove 'label_'
			s = s[6:]
			if s in self.style:
				self.style[s] = v

	def get_surface(self):
		return self._font.render(self._value, True, self._color)

	def value(self):
		return None

class TextInput(FormObject):
	''' A bare text input field '''
	def __init__(self, value='', max_chars=25, input_font=None, input_size=22, input_color=(0,0,0), input_style=[], **kwargs):
		# Initialise as a form object
		FormObject.__init__(self, value)
		# Store some information
		self._max_chars = max_chars
		self._cursor_pos = len(self._value)
		self._cursor_reset()
		# Create font
		if isinstance(input_font, pygame.font.Font):
			self._font = input_font
		else:
			self._font = pygame.font.Font(input_font, int(input_size))
		# Style font
		self._color = input_color
		for s in input_style:
			if s == 'bold' : self._font.set_bold(True)
			elif s == 'italic' : self._font.set_italic(True)
			elif s == 'underline' : self._font.set_underline(True)
		# Default box styles
		self.style = {
			# Appearance
			'border_width'	: 1,
			'border_color'	: (0,0,0),
			'bg_color'		: (255,255,255),
			# Size
			'height'		: 26,
			'width'			: 200,
			# Position
			'position'		: 'relative',
			'top'			: STANDARD_MARGIN[1]//2,
			'bottom'		: STANDARD_MARGIN[1]//2,
			'left'			: STANDARD_MARGIN[0]//2,
			'right'			: STANDARD_MARGIN[0]//2
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			# Remove 'input_'
			s = s[6:]
			if s in self.style:
				self.style[s] = v

	def _cursor_reset(self, on=True):
		# Update the next cursor switch and
		self._cursor_switch = time.time()+CURSOR_FLASH_SPEED
		if on:
			self._cursor_on = True
		else:
			self._cursor_on ^= True

	def _cursor_forward(self):
		# Move cursor forwards
		if self._cursor_pos < len(self._value):
			self._cursor_pos += 1

	def _cursor_back(self):
		# Move cursor backwards
		if self._cursor_pos > 0:
			self._cursor_pos -= 1

	def _type_char(self, char):
		# Run hook
		self._hooks.run('__change_value__')
		# Add a character behind the cursor
		if len(self._value) < self._max_chars:
			self._value = ''.join([
					self._value[:self._cursor_pos],
					char,
					self._value[self._cursor_pos:]
				])
			self._cursor_pos += 1

	def _backspace(self):
		# Run hook
		self._hooks.run('__change_value__')
		# Remove the character behind the cursor
		if len(self._value) > 0:
			self._value = ''.join([
					self._value[:self._cursor_pos-1],
					self._value[self._cursor_pos:]
				])
			self._cursor_pos -= 1

	def update(self, e):
		# Run hook
		self._hooks.run('__update__')
		# Do update
		r = False
		# Control events when self has focus
		if e.type == PL.KEYDOWN:
			key = pygame.key.name(e.key)
			ukey = e.unicode
			# Catch enter
			if key == 'return':
				return True
			# Move cursor
			elif key == 'left':
				self._cursor_back()
			elif key == 'right':
				self._cursor_forward()
			# Edit text
			elif key == 'backspace':
				self._backspace()
			elif key == 'space':
				self._type_char(' ')
			elif len(ukey) == 1:
				self._type_char(ukey)
			# Signal event unused
			else:
				r = True
			# Update cursor switch
			self._cursor_reset()
		else:
			r = True
		return r

	def focus(self):
		# Run hook
		self._hooks.run('__focus__', '__focus_switch__')
		# When the object gets selected
		self._has_focus = True
		if self._value == self._default:
			self._value = ''
			self._cursor_pos = 0
		# Enable key repeating
		pygame.key.set_repeat(KEY_REPEAT_DELAY, KEY_REPEAT_INTERVAL)
		# Update cursor switch
		self._cursor_reset()

	def blur(self):
		# Run hook
		self._hooks.run('__blur__', '__focus_switch__')
		# When the object loses focus
		self._has_focus = False
		if self._value.strip() == '':
			self._value = self._default
		# Disable key repeating
		pygame.key.set_repeat()

	def get_surface(self):
		# Create surface
		box = pygame.Surface((self.style['width'], self.style['height'])).convert_alpha()
		# Add box
		width = self.style['width'] + self.style['border_width']*2
		height = self.style['height'] + self.style['border_width']*2
		pygame.draw.rect(box, self.style['bg_color'], (0, 0, self.style['width'], self.style['height']))
		if self.style['border_width'] > 0:
			pygame.draw.rect(box, self.style['border_color'], (0, 0, self.style['width']-self.style['border_width']//2, self.style['height']-self.style['border_width']//2), self.style['border_width'])
		# Create text
		to_cursor = self._font.render(self._value[:self._cursor_pos], True, self._color)
		full_text = self._font.render(self._value, True, self._color)
		# Determine diplayed area
		tw, th = to_cursor.get_size()
		padding = (height - th)//2 + 1
		offset = tw - self.style['width'] + 2*padding
		offset = (int(offset),0)[offset<0]
		# Add text to box
		box.blit(full_text, (padding, padding), (offset,0,self.style['width']-2*padding,th))
		# Switch cursor
		if time.time() >= self._cursor_switch:
			self._cursor_reset(False)
		# Draw cursor
		if self._has_focus and self._cursor_on:
			pygame.draw.line(box, self.style['border_color'], (tw+padding-offset,padding//2), (tw+padding-offset,th+padding))
		return box

	def value(self):
		return self._value

class Input(FormObject):
	''' A labeled input box '''
	def __init__(self, label, value='', **kwargs):
		# Initialise as a form object
		FormObject.__init__(self, value)
		# Separate kwargs
		label_kwargs = dict([(k,v) for k,v in kwargs.iteritems() if k.startswith('label_')])
		input_kwargs = dict([(k,v) for k,v in kwargs.iteritems() if k.startswith('input_')])
		# Create objects
		self._label = Text(label, **label_kwargs)
		self._input = TextInput(value, **input_kwargs)
		# Default box styles
		self.style = {
			# Appearance
			'border_width'	: 0,
			'border_color'	: (0,0,0),
			'bg_color'		: (255,255,255,0),
			# Position
			'position'		: 'relative',
			'top'			: STANDARD_MARGIN[1]//2,
			'bottom'		: STANDARD_MARGIN[1]//2,
			'left'			: STANDARD_MARGIN[0]//2,
			'right'			: STANDARD_MARGIN[0]//2
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			if s in self.style:
				self.style[s] = v

	def _reset(self):
		# Run hook
		self._hooks.run('__change_value__')
		# Restore value to default
		self._input._reset()

	def update(self, e):
		# Run hook
		self._hooks.run('__update__')
		# Send events straight to input
		return self._input.update(e)

	def focus(self):
		# Run hook
		self._hooks.run('__focus__', '__focus_switch__')
		# Give both focus states
		self._label.focus()
		self._input.focus()

	def blur(self):
		# Run hook
		self._hooks.run('__blur__', '__focus_switch__')
		# Remove focus states
		self._label.blur()
		self._input.blur()

	def get_surface(self):
		# Get child surfaces and their sizes
		l = self._label.get_surface()
		i = self._input.get_surface()
		sl, si = l.get_size(), i.get_size()
		# Get own dimensions
		padding = 10 # pixels
		width = sl[0]+padding+si[0]
		height = max(sl[1], si[1])
		# Create own surface
		surf = pygame.Surface((width, height)).convert_alpha()
		surf.fill((0,0,0,0)) # Transparent
		# Add child surfaces v-centered
		surf.blit(l, (0,(height-sl[1])//2+1))
		surf.blit(i, (width-si[0],(height-si[1])//2))
		return surf

	def value(self):
		return self._input.value()

class Button(FormObject):
	''' A button '''
	def __init__(self, value, function, args, font=None, size=22, color=(50,50,50), focus_color=(0,0,0), style=[], **kwargs):
		'''
			value 				-> displayed text
			function			-> a function refernce eg. max
			args				-> a tuple of arguments eg. (10, 20)
			Thus when the button is activated function(args) is called eg. max(10, 20)
		'''
		# Initialise as a form object
		FormObject.__init__(self, value)
		# Store data
		self._value = value
		self._function = function
		self._args = ((args,), args)[isinstance(args, tuple)]
		# Create font
		if isinstance(font, pygame.font.Font):
			self._font = font
		else:
			self._font = pygame.font.Font(font, int(size))
		# Style font
		self._color = color
		self._focus_color = focus_color
		for s in style:
			if s == 'bold' : self._font.set_bold(True)
			elif s == 'italic' : self._font.set_italic(True)
			elif s == 'underline' : self._font.set_underline(True)
		# Default box styles
		self.style = {
			# Appearance
			'border_width'	: 1,
			'border_color'	: (0,0,0),
			'bg_color'		: (255,255,255),
			'bg_focus_color': (205,155,255),
			# Size
			'height'		: 1,
			'width'			: 1,
			# Position
			'position'		: 'relative',
			'top'			: STANDARD_MARGIN[1]//2,
			'bottom'		: STANDARD_MARGIN[1]//2,
			'left'			: STANDARD_MARGIN[0]//2,
			'right'			: STANDARD_MARGIN[0]//2
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			if s in self.style:
				self.style[s] = v
		# Get rendered text height
		tw, th = self._font.size(self._value)
		# Adjust constraints to fit text
		self.style['width'] = max(self.style['width'], tw+4+self.style['border_width'])
		self.style['height'] = max(self.style['height'], th+4+self.style['border_width'])
		# Determine padding
		self._padding = (
			(self.style['width'] - tw)//2 + self.style['border_width'],
			(self.style['height'] - th)//2 + self.style['border_width'])

	def hotspots(self):
		return {'click': (self.run, (), {})}

	def update(self, e):
		# Run hook
		self._hooks.run('__update__')
		# Control events when self has focus
		if e.type == PL.KEYDOWN:
			# Enter/Return pressed -> run function
			if e.key == PL.K_RETURN:
				self.run()
				return False
		# Signal event unused
		return True

	def run(self):
		# Run the function with or without args
		if self._args:
			self._function(*self._args)
		else:
			self._function()

	def get_surface(self):
		# Create text
		text = self._font.render(self._value, True, (self._color, self._focus_color)[self._has_focus])
		# Create surface
		box = pygame.Surface((self.style['width'], self.style['height'])).convert_alpha()
		# Add box
		box.fill((self.style['bg_color'], self.style['bg_focus_color'])[self._has_focus])
		if self.style['border_width'] > 0:
			pygame.draw.rect(box, self.style['border_color'], (0, 0, self.style['width']-self.style['border_width']//2, self.style['height']-self.style['border_width']//2), self.style['border_width'])
		# Add text to box [centered H & V]
		box.blit(text, self._padding)
		return box

	def value(self):
		return None

class Select(FormObject):
	def __init__(self, value=-1, font=None, size=22, color=(0,0,0), style=[], **kwargs):
		# Initialise as a form object
		FormObject.__init__(self, value)
		# Create internals
		self._options = {}
		self._index = {}
		self._is_active = False
		# Create font
		if isinstance(font, pygame.font.Font):
			self._font = font
		else:
			self._font = pygame.font.Font(font, int(size))
			self._size = size
		# Style font
		self._color = color
		self._style = style
		for s in style:
			if s == 'bold' : self._font.set_bold(True)
			elif s == 'italic' : self._font.set_italic(True)
			elif s == 'underline' : self._font.set_underline(True)
		# Default box styles
		self.style = {
			# Appearance
			'border_width'	: 1,
			'border_color'	: (0,0,0),
			'scroll_color'	: (105,0,205),
			'bg_color'		: (255,255,255),
			'bg_focus_color': (205,155,255),
			# Size
			'height'		: 26,
			'width'			: 200,
			# Position
			'position'		: 'relative',
			'top'			: STANDARD_MARGIN[1]//2,
			'bottom'		: STANDARD_MARGIN[1]//2,
			'left'			: STANDARD_MARGIN[0]//2,
			'right'			: STANDARD_MARGIN[0]//2
		}
		# Apply custom box styles
		for s, v in kwargs.iteritems():
			if s in self.style:
				self.style[s] = v

	def _cursor_up(self):
		# Move cursor down
		if self._value > 0:
			self._value -= 1

	def _cursor_down(self):
		# Move cursor up
		if self._value < len(self._index)-1:
			self._value += 1

	def add_option(self, name, value, index=None, **kwargs):
		for k in ['font','color','style']:
			if k not in kwargs:
				kwargs[k] = getattr(self, '_'+k)
		if name not in self._options:
			# Add object reference
			self._options[name] = SelectOption(name, value, **kwargs)
			# Add object index
			if not index or index >= len(self._index):
				self._index[len(self._index)] = name
			else:
				for i in xrange(index, len(self._index)-1):
					self._index[i+1] = self._index[i]
				self._index[index] = name
			# Adjust size for new text
			tw, th = self._options[name]._font.size(name)
			# Adjust constraints to fit text
			self.style['width'] = max(self.style['width'], STANDARD_MARGIN[0]//2+tw+4+self.style['border_width']*2+SCROLL_BAR_WIDTH)
			self.style['height'] = max(self.style['height'], th+4+self.style['border_width'])
			# Determine padding
			self._padding = (
				STANDARD_MARGIN[0]//2,
				#(self.style['width'] - tw)//2 + self.style['border_width'],
				(self.style['height'] - th)//2 + self.style['border_width'])
		else:
			raise ValueError('Select object already contains a "%s" option' % name)

	def rem_option(self, name=None):
		if not name:
			name = self._index[len(self._index)-1]
		if name in self._options:
			# Delete object
			self._options.__delitem__(name)
			# Update indexes
			x = dict([(v, k) for (k, v) in self._index.iteritems()])[name]
			for i in xrange(x+1, len(self._index)-1):
				self._index[i] = self._index[i+1]
			# Remove index
			self._index.__delitem__(len(self._index)-1)
			# Check that the removed item wasn't selected
			if self._value >= len(self._index):
				self._value = len(self._index)-1
		else:
			raise KeyError('Select object does not contain a "%s" option' % name)

	def update(self, e):
		# Run hook
		self._hooks.run('__update__')
		# Default: event used
		r = False
		# Control events when self has focus
		if e.type == PL.KEYDOWN:
			key = pygame.key.name(e.key)
			# Switch activity
			if e.key == PL.K_RETURN:
				if self._is_active:
					# Run hook
					self._hooks.run('__change_value__')
				self._is_active ^= True
			# Move cursor
			elif key == 'up' and self._is_active:
				self._cursor_up()
			elif key == 'down' and self._is_active:
				self._cursor_down()
			# Signal event unused
			else:
				r = True
		else:
			r = True
		return r

	def get_surface(self):
		# Make sure the object has options
		if not len(self._options):
			raise AttributeError('Select has no options.')
		# Create side-arrow
		arrow = pygame.Surface((self.style['height']-self.style['border_width'], self.style['height']))
		# Fill and border
		arrow.fill((200,200,200))
		if self.style['border_width'] > 0:
			pygame.draw.rect(arrow, self.style['border_color'], (-self.style['border_width'], 0, self.style['height']-self.style['border_width']//2, self.style['height']-self.style['border_width']//2), self.style['border_width'])
		# The arrow
		cw, ch = (s//2 for s in arrow.get_size())
		cw -= self.style['border_width']//2
		ch += self.style['border_width']//2
		if self._is_active:
			points = [(cw+cw//3, ch//2), (cw//(3./2), ch), (cw+cw//3, ch+ch//2)]
		else:
			points = [(cw//2, ch//(3./2)), (cw, ch+ch//3), (cw+cw//2, ch//(3./2))]
		pygame.draw.aalines(arrow, self.style['border_color'], False, points, 1)
		# Create surface
		if self._is_active:
			# Create ranges
			count = 5
			if len(self._index) < count:
				count = len(self._index)
				irange = (0, count)
			elif self._value < 2:
				irange = (0, count)
			elif self._value > len(self._index)-3:
				irange = (len(self._index)-count, len(self._index))
			else:
				irange = (self._value-2, self._value+3)
			# Create box
			height = (self._font.get_linesize()+self._padding[1]*2)*count - 1
			box = pygame.Surface((self.style['width']+self.style['height']-self.style['border_width'], height)).convert_alpha()
			box.fill((0,0,0,0))
			# Add box
			pygame.draw.rect(box, self.style['bg_color'], (0, 0, self.style['width'], height))
			if self.style['border_width'] > 0:
				pygame.draw.rect(box, self.style['border_color'], (0, 0, self.style['width']-self.style['border_width']//2, height-self.style['border_width']//2), self.style['border_width'])
			# Create hilight
			hilight = pygame.Surface((self.style['width']-(3*self.style['border_width']+SCROLL_BAR_WIDTH), self.style['height']))
			hilight.fill(self.style['bg_focus_color'])
			# Scroll bar
			sp = (height - 2.*self.style['border_width'])/len(self._index)
			lx = self.style['width']-(SCROLL_BAR_WIDTH + 2*self.style['border_width'])
			s1 = sp*irange[0]+self.style['border_width']
			s2 = sp*irange[1]+self.style['border_width'] - s1
			pygame.draw.rect(box, self.style['border_color'], (lx, 0, self.style['border_width'], box.get_height()))
			pygame.draw.rect(box, self.style['scroll_color'], (lx+self.style['border_width'], s1, SCROLL_BAR_WIDTH, s2))
			# Create text
			cy = self._padding[1]+self.style['border_width']
			for i in xrange(*irange):
				# Hilight
				if i == self._value:
					box.blit(hilight, (self.style['border_width'], cy-self._padding[1]))
				# Text
				text = self._options[self._index[i]].get_surface()
				box.blit(text, (self._padding[0], cy))
				cy += self._font.get_linesize()+self._padding[1]*2
		else:
			# Create text
			if self._value >= 0:
				text = self._options[self._index[self._value]].get_surface()
			else:
				text = None
			box = pygame.Surface((self.style['width']+self.style['height']-self.style['border_width'], self.style['height'])).convert_alpha()
			# Add box
			box.fill((self.style['bg_color'],self.style['bg_focus_color'])[self._has_focus])
			if self.style['border_width'] > 0:
				pygame.draw.rect(box, self.style['border_color'], (0, 0, self.style['width']-self.style['border_width']//2, self.style['height']-self.style['border_width']//2), self.style['border_width'])
			# Add text to box [centered H & V]
			if text:
				box.blit(text, self._padding)
		# Add arrow to main surface
		box.blit(arrow, (self.style['width'], (box.get_height()-arrow.get_height())//2))
		return box

	def value(self):
		if self._value >= 0:
			return self._options[self._index[self._value]]._value
		else:
			return None


class SelectOption(FormObject):
	def __init__(self, name, value, font=None, size=22, color=(0,0,0), style=[]):
		# Store some info
		self._name = name
		self._value = value
		# Create font
		if isinstance(font, pygame.font.Font):
			self._font = font
		else:
			self._font = pygame.font.Font(font, int(size))
		# Style font
		self._color = color
		for s in style:
			if s == 'bold' : self._font.set_bold(True)
			elif s == 'italic' : self._font.set_italic(True)
			elif s == 'underline' : self._font.set_underline(True)

	def get_surface(self):
		return self._font.render(self._name, True, self._color)

if __name__ == '__main__':
	# Run example
	import sys
	pygame.init()
	screen = pygame.display.set_mode((400,300))
	# Create form
	f = Form(False)
	# Add objects
	f.add_object('text', Text('I am some text', label_style=['bold','underline']))
	f.add_object('input', Input('Test', 'default', label_size=18, input_border_color=(255,100,100), input_border_width=0, input_bg_color=(0,0,0,0)))
	f.add_object('input2', Input('More Input:', 'More testing', position='absolute', top=100, left=20))
	sel = Select(border_width=2, top=50)
	sel.add_option('option1', 1)
	sel.add_option('option2', 2)
	sel.add_option('option3 which is really long', 3)
	sel.add_option('option4', 4)
	sel.add_option('option5', 5)
	sel.add_option('option6', 6)
	f.add_object('select', sel)
	f.add_object('submit', Button('Submit', f.submit, ()))
	f.add_object('reset', Button('Reset', f.clear, ()))

	# Run form
	r = f.run(screen)
	# Display results
	for kv in r.iteritems():
		print '%s:\t%s' % kv
	# End
	pygame.quit()
