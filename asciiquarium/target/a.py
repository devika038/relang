#!/usr/bin/env python3
"""
asciiquarium.py - Faithful Python port of asciiquarium.pl (original by Kirk Baucom,
ASCII art by Joan Stark). Same fish, castle, seaweed, and waterline art, and the
same digit->color mask coloring system, running on Python's curses instead of
Perl's Term::Animation.

Controls:
    q - quit
    r - redraw (recreate all entities)
    p - toggle pause
"""

import curses
import random
import time

# ---------------------------------------------------------------------------
# ASCII ART  (transcribed directly from asciiquarium.pl's add_old_fish,
# add_castle, add_environment, and add_bubble subs)
# ---------------------------------------------------------------------------

# Each tuple is (shape, mask). Mask digits: 1 body, 2 dorsal fin, 3 flippers,
# 4 eye (always forced to white, like the original's s/4/W/), 5 mouth,
# 6 tailfin, 7 gills. Digit -> random color letter, same as rand_color() below.
OLD_FISH = [
    (r"""
       \
     ...\..,
\  /'       \
 >=     (  ' >
/  \      / /
    `"'"'/''
""", r"""
       2
     1112111
6  11       1
 66     7  4 5
6  1      3 1
    11111311
"""),
    (r"""
      /
  ,../...
 /       '\  /
< '  )     =<
 \ \      /  \
  `'\'"'"'
""", r"""
      2
  1112111
 1       11  6
5 4  7     66
 1 3      1  6
  11311111
"""),
    (r"""
    \
\ /--\
>=  (o>
/ \__/
    /
""", r"""
    2
6 1111
66  745
6 1111
    3
"""),
    (r"""
  /
 /--\ /
<o)  =<
 \__/ \
  \
""", r"""
  2
 1111 6
547  66
 1111 6
  3
"""),
    (r"""
       \:.
\;,   ,;\\\\\,,
  \\\;;:::::::o
  ///;;::::::::<
 /;` ``/////``
""", r"""
       222
666   1122211
  6661111111114
  66611111111115
 666 113333311
"""),
    (r"""
      .:/
   ,,///;,   ,;/
 o:::::::;;///
>::::::::;;\\\\\
  ''\\\\\\\\\'' ';\
""", r"""
      222
   1122211   666
 4111111111666
51111111111666
  113333311 666
"""),
    (r"""
  __
><_'>
   '
""", r"""
  11
61145
   3
"""),
    (r"""
 __
<'_><
 `
""", r"""
 11
54116
 3
"""),
    (r"""
   ..\,
>='   ('>
  '''/''
""", r"""
   1121
661   745
  111311
"""),
    (r"""
  ,/..
<')   `=<
 ``\```
""", r"""
  1211
547   166
 113111
"""),
    (r"""
   \
  / \
>=_('>
  \_/
   /
""", r"""
   2
  1 1
661745
  111
   3
"""),
    (r"""
  /
 / \
<')_=<
 \_/
  \
""", r"""
  2
 1 1
547166
 111
  3
"""),
    (r"""
  ,\
>=('>
  '/
""", r"""
  12
66745
  13
"""),
    (r"""
 /,
<')=<
 \`
""", r"""
 21
54766
 31
"""),
    (r"""
  __
\/ o\
/\__/
""", r"""
  11
61 41
61111
"""),
    (r"""
 __
/o \/
\__/\
""", r"""
 11
14 16
11116
"""),
]

CASTLE_SHAPE = r"""
               T~~
               |
              /^\
             /   \
 _   _   _  /     \  _   _   _
[ ]_[ ]_[ ]/ _   _ \[ ]_[ ]_[ ]
|_=__-_ =_|_[ ]_[ ]_|_=-___-__|
 | _- =  | =_ = _    |= _=   |
 |= -[]  |- = _ =    |_-=_[] |
 | =_    |= - ___    | =_ =  |
 |=  []- |-  /| |\   |=_ =[] |
 |- =_   | =| | | |  |- = -  |
 |_______|__|_|_|_|__|_______|
"""

CASTLE_MASK = r"""
                RR

              yyy
             y   y
            y     y
           y       y



              yyy
             yy yy
            y y y y
            yyyyyyy
"""

WATERLINE_SEGMENTS = [
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "^^^^ ^^^  ^^^   ^^^    ^^^^      ",
    "^^^^      ^^^^     ^^^    ^^     ",
    "^^      ^^^^      ^^^    ^^^^^^  ",
]

BUBBLE_FRAMES = ['.', 'o', 'O', 'O', 'O']

COLOR_LETTERS = ['c', 'C', 'r', 'R', 'y', 'Y', 'b', 'B', 'g', 'G', 'm', 'M']

# Note: the shark/whale/big-fish blocks below had runs of '?' in the source
# text where the original clearly has runs of spaces (a formatting artifact
# from how the .pl file was pasted in). Each '?' is reconstructed here as one
# space. Ship, splat, castle, and the 8 classic fish had no such corruption
# and are transcribed exactly as-is.

SHARK_IMAGE = [
    r"""
                              __
                             ( `\
  ,                          )   `\
;' `.                        (     `\__
 ;   `.             __..---''          `~~~~-._
  `.   `.____...--''                       (b  `--._
    >                     _.-'      .((      ._     )
  .`.-`--...__         .-'     -.___.....-(|/|/|/|/'
 ;.'         `. ...----`.___.',,,_______......---'
 '           '-'
""",
    r"""
                     __
                    /' )
                  /'   (                          ,
              __/'     )                        .' `;
      _.-~~~~'          ``---..__             .'   ;
 _.--'  b)                       ``--...____.'   .'
(     _.      )).      `-._                     <
 `\|\|\|\|)-.....___.-     `-.         __...--'-.'.
   `---......_______,,,`.___.'----... .'         `.;
                                     `-`           `
""",
]

SHARK_MASK = [
    r"""




                                           cR

                                          cWWWWWWWW

""",
    r"""




        Rc

  WWWWWWWWc

""",
]

WHALE_IMAGE = [
    r"""
        .-----:
      .'       `.
,    /       (o) \
\`._/          ,__)
""",
    r"""
    :-----.
  .'       `.
 / (o)       \    ,
(__,          \_.'/
""",
]

WHALE_MASK = [
    r"""
             C C
           CCCCCCC
           C  C  C
        BBBBBBB
      BB       BB
B    B       BWB B
BBBBB          BBBB
""",
    r"""
   C C
 CCCCCCC
 C  C  C
    BBBBBBB
  BB       BB
 B BWB       B    B
BBBB          BBBBB
""",
]

WATER_SPOUT_FRAMES = [
    "\n\n   :",
    "\n\n   :\n   :",
    "\n  . .\n  -:-\n   :",
    "\n  . .\n .-:-.\n   :",
    "\n  . .\n'.-:-.`\n'  :  '",
    "\n\n .- -.\n;  :  ;",
    "\n\n\n;     ;",
]

SHIP_IMAGE = [
    r"""
     |    |    |
    )_)  )_)  )_)
   )___))___))___)\
  )____)____)_____)\\\
_____|____|____|____\\\\\__
\                   /
""",
    r"""
         |    |    |
        (_(  (_(  (_(
      /(___((___((___(
    //(_____(____(____(
__///____|____|____|_____
    \                   /
""",
]

SHIP_MASK = [
    r"""
     y    y    y

                  w
                   ww
yyyyyyyyyyyyyyyyyyyywwwyy
y                   y
""",
    r"""
         y    y    y

      w
    ww
yywwwyyyyyyyyyyyyyyyyyyyy
    y                   y
""",
]

BIG_FISH_1_IMAGE = [
    r"""
 ______
`""-.  `````-----.....__
     `.  .      .       `-.
       :     .     .       `.
 ,     :   .    .          _ :
: `.   :                  (@) `._
 `. `..'     .     =`-.       .__)
   ;     .        =  ~  :     .-"
 .' .'`.   .    .  =.-'  `._ .'
: .'   :               .   .'
 '     '  .    .     .   .-'
   .'____....----''.'=.'
   ""             .'.'
               ''"'`
""",
    r"""
                           ______
          __.....-----'''''  .-""'
       .-'       .      .  .'
     .'       .     .     :
    : _          .    .   :     ,
 _.' (@)                  :   .' :
(__.       .-'=     .     `..' .'
 "-.     :  ~  =        .     ;
   `. _.'  `-.=  .    .   .'`. `.
     `.   .               :   `. :
       `-.   .     .    .  `.   `
          `.=`.``----....____`.
            `.`.             ""
              '`"``
""",
]

BIG_FISH_1_MASK = [
    r"""
 111111
11111  11111111111111111
     11  2      2       111
       1     2     2       11
 1     1   2    2          1 1
1 11   1                  1W1 111
 11 1111     2     1111       1111
   1     2        1  1  1     111
 11 1111   2    2  1111  111 11
1 11   1               2   11
 1   11  2    2     2   111
   111111111111111111111
   11             1111
               11111
""",
    r"""
                           111111
          11111111111111111  11111
       111       2      2  11
     11       2     2     1
    1 1          2    2   1     1
 111 1W1                  1   11 1
1111       1111     2     1111 11
 111     1  1  1        2     1
   11 111  1111  2    2   1111 11
     11   2               1   11 1
       111   2     2    2  11   1
          111111111111111111111
            1111             11
              11111
""",
]

BIG_FISH_2_IMAGE = [
    r"""
                _ _ _
             .='\ \ \`"=,
           .'\ \ \ \ \ \ \
\'=._     / \ \ \_\_\_\_\_\
\'=._'.  /\ \,-"`- _ - _ - '-.
  \`=._\|'.\/- _ - _ - _ - _- \
  ;"= ._\=./_ -_ -_ {`"=_    @ \
   ;="_-_=- _ -  _ - {"=_"-     \
   ;_=_--_.,          {_.='   .-/
  ;.="` / ';\        _.     _.-`
  /_.='/ \/ /;._ _ _{.-;`/"`
/._=_.'   '/ / / / /{.= /
/.='       `'./_/_.=`{_/
""",
    r"""
            _ _ _
        ,="`/ / /'=.
       / / / / / / /'.
      /_/_/_/_/_/ / / \     _.='/
   .-' - _ - _ -`"-,/ /\  .'_.='/
  / -_ - _ - _ - _ -\/.'|/_.=`/
 / @    _="`} _- _- _\.=/_. =";
/     -"_="} - _  - _ -=_-_"=;
\-.   '=._}          ,._--_=_;
 `-._     ._        /;' \ `"=.;
     `"\`;-.}_ _ _.;\ \/ \'=._\
        \ =.}\ \ \ \ \'   '._=_.\
         \}`=._\_\.'`       '=.\
""",
]

BIG_FISH_2_MASK = [
    r"""
                1 1 1
             1111 1 11111
           111 1 1 1 1 1 1
11111     1 1 1 11111111111
1111111  11 111112 2 2 2 2 111
  111111111112 2 2 2 2 2 2 22 1
  111 1111 12 22 22 11111    W 1
   11111112 2 2  2 2 111111     1
   111111111          11111   111
  11111 11111        11     1111
  111111 11 1111 1 111111111
1111111   11 1 1 1 1111 1
1111       1111111111111
""",
    r"""
            1 1 1
        11111 1 1111
       1 1 1 1 1 1 111
      11111111111 1 1 1     11111
   111 2 2 2 2 211111 11  1111111
  1 22 2 2 2 2 2 2 211111111111
 1 W    11111 22 22 2111111 111
1     111111 2 2  2 2 21111111
111   11111          111111111
 1111     11        111 1 11111
     111111111 1 1111 11 111111
        1 1111 1 1 1 11   1111111
         1111111111111       1111
""",
]

SPLAT_FRAMES = [
    "\n\n   .\n  ***\n   '\n",
    "\n\n \",*;`\n \"*,**\n *\"'~'\n",
    "\n  , ,\n \" \",\"'\n *\" *'\"\n  \" ; .\n",
    "* ' , ' `\n' ` * . '\n ' `' \",'\n* ' \" * .\n\" * ', '",
]

# ---------------------------------------------------------------------------
# Coloring: same idea as the original's rand_color() sub - each digit 1-9
# gets mapped to a random color letter (consistently for that fish instance).
# ---------------------------------------------------------------------------

def rand_color(mask):
    """Assign a random color letter to each digit 1-9 in the mask, leaving
    any already-literal color letters (like the shark/whale/ship masks use)
    untouched. Matches the original's rand_color() sub."""
    for digit in '123456789':
        mask = mask.replace(digit, random.choice(COLOR_LETTERS))
    return mask


def rand_color_mask(mask):
    """Force digit 4 (eye) to 'W' like the original's s/4/W/, then assign a
    random color letter to each remaining digit 1-9, same as rand_color()."""
    mask = mask.replace('4', 'W')
    return rand_color(mask)


def lines(text):
    """Strip a single leading/trailing newline (like Perl's q{} blocks) and
    split into lines, without stripping internal whitespace."""
    if text.startswith('\n'):
        text = text[1:]
    if text.endswith('\n'):
        text = text[:-1]
    return text.split('\n')


# ---------------------------------------------------------------------------
# Curses color pair setup
# ---------------------------------------------------------------------------

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    pair_map = {}
    base = {
        'c': curses.COLOR_CYAN, 'C': curses.COLOR_CYAN,
        'r': curses.COLOR_RED, 'R': curses.COLOR_RED,
        'y': curses.COLOR_YELLOW, 'Y': curses.COLOR_YELLOW,
        'b': curses.COLOR_BLUE, 'B': curses.COLOR_BLUE,
        'g': curses.COLOR_GREEN, 'G': curses.COLOR_GREEN,
        'm': curses.COLOR_MAGENTA, 'M': curses.COLOR_MAGENTA,
        'w': curses.COLOR_WHITE, 'W': curses.COLOR_WHITE,
    }
    pair_num = 1
    for letter, color in base.items():
        curses.init_pair(pair_num, color, -1)
        bold = letter.isupper()
        pair_map[letter] = curses.color_pair(pair_num) | (curses.A_BOLD if bold else 0)
        pair_num += 1

    curses.init_pair(pair_num, curses.COLOR_CYAN, -1)
    pair_map['waterline'] = curses.color_pair(pair_num)
    pair_num += 1

    curses.init_pair(pair_num, curses.COLOR_GREEN, -1)
    pair_map['seaweed'] = curses.color_pair(pair_num)
    pair_num += 1

    curses.init_pair(pair_num, curses.COLOR_YELLOW, -1)
    pair_map['default_fish'] = curses.color_pair(pair_num)
    pair_num += 1

    pair_map['default'] = curses.A_NORMAL
    return pair_map


def safe_addstr(win, y, x, ch, attr, maxy, maxx):
    if 0 <= y <= maxy and 0 <= x <= maxx:
        try:
            win.addstr(y, x, ch, attr)
        except curses.error:
            pass


def draw_masked(win, shape_lines, mask_lines, x, y, colors, maxy, maxx,
                 default_attr=None):
    if default_attr is None:
        default_attr = colors['default_fish']
    for row, shape_line in enumerate(shape_lines):
        mask_line = mask_lines[row] if mask_lines and row < len(mask_lines) else ''
        draw_y = y + row
        if draw_y < 0 or draw_y > maxy:
            continue
        for col, ch in enumerate(shape_line):
            if ch == ' ':
                continue
            draw_x = x + col
            mask_ch = mask_line[col] if col < len(mask_line) else ' '
            attr = colors.get(mask_ch, default_attr) if mask_ch != ' ' else default_attr
            safe_addstr(win, draw_y, draw_x, ch, attr, maxy, maxx)


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

class Fish:
    def __init__(self, maxy, maxx, colors):
        design = random.choice(OLD_FISH)
        shape_lines = lines(design[0])
        mask_lines = lines(rand_color_mask(design[1]))
        going_right = random.choice([True, False])
        if not going_right:
            # mirror is baked into the art choice via left/right variants,
            # so we don't flip text - just pick direction of travel
            pass
        self.shape = shape_lines
        self.mask = mask_lines
        self.height = len(shape_lines)
        self.width = max((len(l) for l in shape_lines), default=1)
        self.dx = random.uniform(0.25, 1.5) * (1 if going_right else -1)
        self.x = float(-self.width) if going_right else float(maxx)
        max_h = 9
        min_h = max(max_h + 1, maxy - self.height)
        self.y = float(random.randint(max_h, min_h))
        self.colors = colors
        self.bubble_chance = 0.03

    def update(self):
        self.x += self.dx

    def offscreen(self, maxx):
        return self.x + self.width < 0 or self.x > maxx

    def draw(self, win, maxy, maxx):
        draw_masked(win, self.shape, self.mask, int(self.x), int(self.y),
                    self.colors, maxy, maxx)

    def mouth_pos(self):
        # roughly the leading edge of the fish, used to spawn bubbles
        if self.dx > 0:
            return int(self.x + self.width), int(self.y + self.height // 2)
        return int(self.x), int(self.y + self.height // 2)


class Bubble:
    def __init__(self, x, y, colors):
        self.x = float(x)
        self.y = float(y)
        self.frame = 0
        self.tick = 0
        self.colors = colors

    def update(self):
        self.y -= 0.5
        self.tick += 1
        if self.tick % 2 == 0:
            self.frame = (self.frame + 1) % len(BUBBLE_FRAMES)

    def offscreen(self, maxy):
        return self.y < 4  # dies at the waterline, like the original

    def draw(self, win, maxy, maxx):
        safe_addstr(win, int(self.y), int(self.x), BUBBLE_FRAMES[self.frame],
                    self.colors['c'], maxy, maxx)


class Seaweed:
    def __init__(self, maxy, maxx, colors):
        self.height = random.randint(3, 6)
        self.x = random.randint(1, max(1, maxx - 2))
        self.y = maxy - self.height
        self.speed = random.uniform(0.25, 0.30)
        self.tick = 0
        self.frame = 0
        self.colors = colors
        self.frames = self._build_frames()

    def _build_frames(self):
        left, right = [], []
        for i in range(1, self.height + 1):
            if i % 2:
                left.append('(')
                right.append(' )')
            else:
                left.append(' )')
                right.append('(')
        return [left, right]

    def update(self):
        self.tick += 1
        if self.tick % 8 == 0:
            self.frame = 1 - self.frame

    def draw(self, win, maxy, maxx):
        for row, ch in enumerate(self.frames[self.frame]):
            safe_addstr(win, self.y + row, self.x, ch, self.colors['seaweed'],
                        maxy, maxx)


class RandomObject:
    """Generic multi-frame masked sprite, used for shark/whale/ship/big fish -
    the original's 'random objects' that occasionally cross the screen."""

    def __init__(self, frames, y, dx, colors, default_letter=None, kind='object'):
        self.frames = frames  # list of (shape_lines, mask_lines_or_None)
        self.frame_idx = 0
        self.tick = 0
        self.dx = dx
        self.width = max((len(l) for f in frames for l in f[0]), default=1)
        self.height = max(len(f[0]) for f in frames)
        self.x = float(-self.width) if dx > 0 else float(200)  # caller sets real x after
        self.y = float(y)
        self.colors = colors
        self.default_attr = colors.get(default_letter, colors['default_fish']) if default_letter else colors['default_fish']
        self.kind = kind
        self.alive = True

    def update(self):
        self.x += self.dx
        self.tick += 1
        if len(self.frames) > 1 and self.tick % 6 == 0:
            self.frame_idx = (self.frame_idx + 1) % len(self.frames)

    def offscreen(self, maxx):
        return self.x + self.width < 0 or self.x > maxx

    def draw(self, win, maxy, maxx):
        shape_lines, mask_lines = self.frames[self.frame_idx]
        draw_masked(win, shape_lines, mask_lines, int(self.x), int(self.y),
                    self.colors, maxy, maxx, default_attr=self.default_attr)


class Splat:
    """Short-lived 'eaten' effect, spawned where the shark catches a fish."""

    def __init__(self, x, y, colors):
        self.frames = [lines(f) for f in SPLAT_FRAMES]
        self.frame_idx = 0
        self.tick = 0
        self.x = x - 4
        self.y = y - 2
        self.colors = colors
        self.attr = colors.get('R', colors['default_fish'])

    def update(self):
        self.tick += 1
        if self.tick % 3 == 0:
            self.frame_idx += 1

    def done(self):
        return self.frame_idx >= len(self.frames)

    def draw(self, win, maxy, maxx):
        if self.done():
            return
        for row, line in enumerate(self.frames[self.frame_idx]):
            for col, ch in enumerate(line):
                if ch != ' ':
                    safe_addstr(win, self.y + row, self.x + col, ch, self.attr, maxy, maxx)


def spawn_shark(maxy, maxx, colors):
    direction = random.choice([0, 1])
    dx = 2.0 if direction == 0 else -2.0
    frame = (lines(SHARK_IMAGE[direction]), lines(SHARK_MASK[direction]))
    y = random.randint(9, max(10, maxy - 19))
    obj = RandomObject([frame], y, dx, colors, default_letter='c', kind='shark')
    obj.x = -53.0 if direction == 0 else float(maxx)
    obj.teeth_offset = 44 if direction == 0 else 9
    return obj


def spawn_whale(maxy, maxx, colors):
    direction = random.choice([0, 1])
    dx = 1.0 if direction == 0 else -1.0
    spout_align = 11 if direction == 0 else 1
    mask_lines = lines(WHALE_MASK[direction])
    base_lines = lines(WHALE_IMAGE[direction])
    padded_mask = ["", "", ""] + mask_lines
    frames = []
    for _ in range(5):
        frames.append((["", "", ""] + base_lines, padded_mask))
    for spout in WATER_SPOUT_FRAMES:
        spout_lines = spout.split('\n')
        spout_lines = [(' ' * spout_align + l) if l else '' for l in spout_lines]
        while len(spout_lines) < 3:
            spout_lines.insert(0, '')
        frames.append((spout_lines[-3:] + base_lines, padded_mask))
    obj = RandomObject(frames, 0, dx, colors, default_letter='w', kind='whale')
    obj.x = -18.0 if direction == 0 else float(maxx)
    return obj


def spawn_ship(maxy, maxx, colors):
    direction = random.choice([0, 1])
    dx = 1.0 if direction == 0 else -1.0
    frame = (lines(SHIP_IMAGE[direction]), lines(SHIP_MASK[direction]))
    obj = RandomObject([frame], 0, dx, colors, default_letter='w', kind='ship')
    obj.x = -24.0 if direction == 0 else float(maxx)
    return obj


def spawn_big_fish(maxy, maxx, colors):
    variant = random.choice([1, 2])
    if variant == 1:
        image, mask, width_guess = BIG_FISH_1_IMAGE, BIG_FISH_1_MASK, 34
    else:
        image, mask, width_guess = BIG_FISH_2_IMAGE, BIG_FISH_2_MASK, 33
    direction = random.choice([0, 1])
    dx = (3.0 if variant == 1 else 2.5) * (1 if direction == 0 else -1)
    shape_lines = lines(image[direction])
    mask_lines = lines(rand_color(mask[direction]))
    y = random.randint(9, max(10, maxy - 15))
    obj = RandomObject([(shape_lines, mask_lines)], y, dx, colors,
                        default_letter='Y', kind='big_fish')
    obj.x = float(-width_guess) if direction == 0 else float(maxx)
    return obj


RANDOM_OBJECT_SPAWNERS = [spawn_ship, spawn_whale, spawn_big_fish, spawn_shark]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def draw_environment(win, maxy, maxx, colors):
    for i, seg in enumerate(WATERLINE_SEGMENTS):
        repeat = maxx // len(seg) + 2
        line = (seg * repeat)[:maxx + 1]
        y = i + 5
        if y <= maxy:
            safe_addstr(win, y, 0, line, colors['waterline'], maxy, maxx)


def draw_castle(win, maxy, maxx, colors):
    shape_lines = lines(CASTLE_SHAPE)
    mask_lines = lines(CASTLE_MASK)
    x = maxx - 32
    y = maxy - 13
    draw_masked(win, shape_lines, mask_lines, x, y, colors, maxy, maxx)


def build_scene(maxy, maxx, colors):
    seaweed_count = max(1, maxx // 15)
    seaweed = [Seaweed(maxy, maxx, colors) for _ in range(seaweed_count)]

    screen_area = max(0, maxy - 9) * maxx
    fish_count = max(3, screen_area // 350)
    fish = [Fish(maxy, maxx, colors) for _ in range(fish_count)]

    return seaweed, fish


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    colors = init_colors()

    maxy, maxx = stdscr.getmaxyx()
    maxy, maxx = maxy - 1, maxx - 1

    seaweed, fish = build_scene(maxy, maxx, colors)
    bubbles = []
    splats = []
    random_objects = [random.choice(RANDOM_OBJECT_SPAWNERS)(maxy, maxx, colors)]
    spawn_cooldown = 0
    paused = False

    while True:
        key = stdscr.getch()
        if key == ord('q'):
            break
        elif key == ord('r'):
            maxy, maxx = stdscr.getmaxyx()
            maxy, maxx = maxy - 1, maxx - 1
            seaweed, fish = build_scene(maxy, maxx, colors)
            bubbles = []
            splats = []
            random_objects = [random.choice(RANDOM_OBJECT_SPAWNERS)(maxy, maxx, colors)]
        elif key == ord('p'):
            paused = not paused

        if not paused:
            stdscr.erase()
            draw_environment(stdscr, maxy, maxx, colors)

            for sw in seaweed:
                sw.update()
                sw.draw(stdscr, maxy, maxx)

            draw_castle(stdscr, maxy, maxx, colors)

            for f in fish:
                f.update()
                f.draw(stdscr, maxy, maxx)
                if random.random() < f.bubble_chance * 0.1:
                    bx, by = f.mouth_pos()
                    bubbles.append(Bubble(bx, by, colors))

            for obj in random_objects:
                obj.update()
                obj.draw(stdscr, maxy, maxx)
                # shark-eats-small-fish collision, like the original's
                # fish_collision / add_splat
                if obj.kind == 'shark' and getattr(obj, 'teeth_offset', None) is not None:
                    teeth_x = obj.x + obj.teeth_offset
                    teeth_y = obj.y + 7
                    for f in fish:
                        if f.height <= 5 and abs(f.x - teeth_x) < 3 and abs(f.y - teeth_y) < 2:
                            splats.append(Splat(int(f.x), int(f.y), colors))
                            f.x = -9999  # force offscreen removal
                            break

            for sp in splats:
                sp.update()
                sp.draw(stdscr, maxy, maxx)

            for b in bubbles:
                b.update()
                b.draw(stdscr, maxy, maxx)

            fish = [f for f in fish if not f.offscreen(maxx)]
            while len(fish) < max(3, (max(0, maxy - 9) * maxx) // 350):
                fish.append(Fish(maxy, maxx, colors))

            bubbles = [b for b in bubbles if not b.offscreen(maxy)]
            splats = [sp for sp in splats if not sp.done()]

            random_objects = [o for o in random_objects if not o.offscreen(maxx)]
            spawn_cooldown -= 1
            if not random_objects and spawn_cooldown <= 0:
                random_objects.append(random.choice(RANDOM_OBJECT_SPAWNERS)(maxy, maxx, colors))
                spawn_cooldown = random.randint(80, 200)

            stdscr.refresh()

        time.sleep(0.08)


if __name__ == "__main__":
    curses.wrapper(main)