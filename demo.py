import time
import os
import random

if not hasattr(time, 'sleep_ms'):
    def _sleep_ms(ms):
        time.sleep(ms / 1000.0)
    time.sleep_ms = _sleep_ms

if not hasattr(time, 'ticks_ms'):
    def _ticks_ms():
        return int(time.time() * 1000)
    time.ticks_ms = _ticks_ms

from display import ST7789Display, VERTICAL, rgb565
from graphics import Graphics, BLACK

try:
    from machine import Pin
    import neopixel
except ImportError:  # pragma: no cover
    Pin = None
    neopixel = None


CAT_ART = [
    '................................................',
    '................................................',
    '................................................',
    '....ttt.........................................',
    '...tttt.........................................',
    '....ttt...oooooooooooooooo......................',
    '....ttt..oooooooooooooooooo.....................',
    '....ttt.oooooooooooooooooooo......ee...ee.......',
    '....tttoooooooooooooooooooooo....eeee.eeee......',
    '....tttoooooooooooooooooooooo....eeee.eeee......',
    '.....ttoooooooooooooooooooooo....eeee.eeee......',
    '......oooooooooowwwwwwooooooo.....eeeeeee.......',
    '......ooooooooowwwwwwwwoooooo.......eee.........',
    '......ooooooooowwwwwwwwoooooo...................',
    '......ooooooooowwwwwwwwoooooo...................',
    '......ooooooooooowwwwoooooooo...................',
    '......oooooooooooooooooooooooo...................',
    '......ooooooooooooooooooooooo....................',
    '......ooooooooooooooooooooooo....................',
    '......ooooooossss..ssss..ssss....................',
    '......ooooooossss..ssss..ssss....................',
    '......ooooooossss..ssss..ssss....................',
    '................................................',
    '................................................',
]

CAT_PALETTE = {
    '.': None,
    'o': rgb565(232, 146, 55),
    'w': rgb565(245, 235, 225),
    's': rgb565(162, 96, 45),
    't': rgb565(232, 146, 55),
    'e': rgb565(245, 200, 170),
}

HELLO_GLYPHS = {
    ' ': (
        '00000',
        '00000',
        '00000',
        '00000',
        '00000',
        '00000',
        '00000',
    ),
    'H': (
        '10001',
        '10001',
        '11111',
        '10001',
        '10001',
        '10001',
        '10001',
    ),
    'E': (
        '11111',
        '10000',
        '11110',
        '10000',
        '10000',
        '10000',
        '11111',
    ),
    'L': (
        '10000',
        '10000',
        '10000',
        '10000',
        '10000',
        '10000',
        '11111',
    ),
    'O': (
        '01110',
        '10001',
        '10001',
        '10001',
        '10001',
        '10001',
        '01110',
    ),
    'M': (
        '10001',
        '11011',
        '10101',
        '10101',
        '10001',
        '10001',
        '10001',
    ),
    'I': (
        '11111',
        '00100',
        '00100',
        '00100',
        '00100',
        '00100',
        '11111',
    ),
    'N': (
        '10001',
        '11001',
        '10101',
        '10011',
        '10001',
        '10001',
        '10001',
    ),
    'W': (
        '10001',
        '10001',
        '10001',
        '10101',
        '10101',
        '11011',
        '10001',
    ),
    'T': (
        '11111',
        '00100',
        '00100',
        '00100',
        '00100',
        '00100',
        '00100',
    ),
}

# PPM rendering compatibility switches for this panel.
# RGB means no channel remap. BRG compensates the current panel pipeline where
# blue appears as green and green appears as red.
PPM_CHANNEL_ORDER = 'BGR'
PPM_FLIP_X = True
PPM_SWAP_565_BYTES = True


class RGBStatusLed:
    """Single RGB LED helper for boards with one NeoPixel on GPIO 38."""

    def __init__(self, pin=38):
        self._np = None
        if Pin is not None and neopixel is not None:
            self._np = neopixel.NeoPixel(Pin(pin, Pin.OUT), 1)
        self._palette = [
            (255, 64, 32),
            (255, 180, 40),
            (80, 255, 80),
            (50, 180, 255),
            (180, 90, 255),
            (255, 80, 180),
            (255, 255, 255),
        ]

    def _write(self, r, g, b):
        if self._np is None:
            return
        self._np[0] = (r, g, b)
        self._np.write()

    def random_color(self):
        r, g, b = random.choice(self._palette)
        self._write(r, g, b)


class CatApp:
    """Minimal cat-only demo in horizontal mode (320x172)."""

    def __init__(self, display=None):
        self.display = display or ST7789Display(width=320, height=172, rotation=VERTICAL)
        self.display.init()
        self.graphics = Graphics(self.display.width, self.display.height)
        self.rgb_led = RGBStatusLed(pin=38)
        self.led_last_change = 0
        self._rendered_once = False

    def draw_background(self):
        sky = rgb565(40, 130, 210)
        ground = rgb565(63, 156, 72)
        grass_dark = rgb565(42, 126, 57)
        flower = rgb565(255, 235, 120)

        self.graphics.clear(sky)
        self.graphics.rect(0, 118, 320, 54, ground, fill=True)
        for x in range(0, 320, 6):
            h = 4 + ((x // 6) % 4)
            self.graphics.vline(x, 118 - h, h, grass_dark)
        for x in range(14, 320, 38):
            self.graphics.rect(x, 138, 2, 2, flower, fill=True)

    def draw_pixel_cat(self, x, y, scale=4):
        for row_idx, row in enumerate(CAT_ART):
            for col_idx, ch in enumerate(row):
                color = CAT_PALETTE.get(ch)
                if color is None:
                    continue
                self.graphics.rect(
                    x + col_idx * scale,
                    y + row_idx * scale,
                    scale,
                    scale,
                    color,
                    fill=True,
                )

        # Eyes and whiskers over pixel body.
        eye = rgb565(30, 30, 30)
        whisker = rgb565(238, 238, 238)
        self.graphics.rect(x + 160, y + 38, 6, 6, eye, fill=True)
        self.graphics.line(x + 150, y + 52, x + 126, y + 50, whisker)
        self.graphics.line(x + 150, y + 58, x + 122, y + 58, whisker)
        self.graphics.line(x + 150, y + 64, x + 126, y + 68, whisker)

    def _read_ppm_header(self, fp):
        magic = fp.readline().strip()
        if magic != b'P6':
            return None

        tokens = []
        while len(tokens) < 3:
            line = fp.readline()
            if not line:
                return None
            if line.startswith(b'#'):
                continue
            tokens.extend(line.split())

        width = int(tokens[0])
        height = int(tokens[1])
        maxval = int(tokens[2])
        if maxval != 255:
            return None
        return width, height

    def _rgb_to_panel565(self, r, g, b):
        if PPM_CHANNEL_ORDER == 'RGB':
            rr, gg, bb = r, g, b
        elif PPM_CHANNEL_ORDER == 'RBG':
            rr, gg, bb = r, b, g
        elif PPM_CHANNEL_ORDER == 'GRB':
            rr, gg, bb = g, r, b
        elif PPM_CHANNEL_ORDER == 'GBR':
            rr, gg, bb = g, b, r
        elif PPM_CHANNEL_ORDER == 'BRG':
            rr, gg, bb = b, r, g
        elif PPM_CHANNEL_ORDER == 'BGR':
            rr, gg, bb = b, g, r
        else:
            rr, gg, bb = r, g, b
        return rgb565(rr, gg, bb)

    def _hello_layout(self):
        text = 'MEINEWELT'
        scale = 2
        spacing = 2
        char_w = 5 * scale
        char_h = 7 * scale
        total_w = len(text) * char_w + (len(text) - 1) * spacing
        x0 = 20
        y0 = self.display.height - char_h - 8
        pad = 4
        return text, scale, spacing, char_w, char_h, total_w, x0, y0, pad

    def _set_row_pixel(self, row, width, x, color):
        if x < 0 or x >= width:
            return
        dst_x = (width - 1 - x) if PPM_FLIP_X else x
        dst = dst_x * 2
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        if PPM_SWAP_565_BYTES:
            row[dst] = lo
            row[dst + 1] = hi
        else:
            row[dst] = hi
            row[dst + 1] = lo

    def _draw_glyph_row(self, row, width, y, base_x, base_y, glyph, color, scale):
        gy = y - base_y
        if gy < 0 or gy >= 7 * scale:
            return
        glyph_row = gy // scale
        pattern = glyph[glyph_row]
        for col_idx, bit in enumerate(pattern):
            if bit != '1':
                continue
            px = base_x + col_idx * scale
            for sx in range(scale):
                self._set_row_pixel(row, width, px + sx, color)

    def _apply_hello_to_ppm_row(self, row, y, width):
        text, scale, spacing, char_w, char_h, total_w, x0, y0, pad = self._hello_layout()
        shadow = rgb565(0, 0, 0)
        fg = rgb565(255, 255, 255)

        cursor = x0
        for ch in text:
            glyph = HELLO_GLYPHS[ch]
            self._draw_glyph_row(row, width, y, cursor + 1, y0 + 1, glyph, shadow, scale)
            self._draw_glyph_row(row, width, y, cursor, y0, glyph, fg, scale)
            cursor += char_w + spacing

    def _draw_hello_on_graphics(self):
        text, scale, spacing, char_w, char_h, total_w, x0, y0, pad = self._hello_layout()
        shadow = rgb565(0, 0, 0)
        fg = rgb565(255, 255, 255)

        cursor = x0
        for ch in text:
            glyph = HELLO_GLYPHS[ch]
            for row_idx, pattern in enumerate(glyph):
                for col_idx, bit in enumerate(pattern):
                    if bit != '1':
                        continue
                    px = cursor + col_idx * scale
                    py = y0 + row_idx * scale
                    self.graphics.rect(px + 1, py + 1, scale, scale, shadow, fill=True)
                    self.graphics.rect(px, py, scale, scale, fg, fill=True)
            cursor += char_w + spacing

    def draw_ppm_if_present(self, path):
        try:
            os.stat(path)
        except OSError:
            return False

        with open(path, 'rb') as fp:
            header = self._read_ppm_header(fp)
            if header is None:
                return False
            width, height = header
            if width != self.display.width or height != self.display.height:
                return False

            for y in range(height):
                src = fp.read(width * 3)
                if len(src) != width * 3:
                    return False

                row = bytearray(width * 2)
                x = 0
                i = 0
                while x < width:
                    c = self._rgb_to_panel565(src[i], src[i + 1], src[i + 2])
                    if PPM_FLIP_X:
                        dst = (width - 1 - x) * 2
                    else:
                        dst = x * 2
                    hi = (c >> 8) & 0xFF
                    lo = c & 0xFF
                    if PPM_SWAP_565_BYTES:
                        row[dst] = lo
                        row[dst + 1] = hi
                    else:
                        row[dst] = hi
                        row[dst + 1] = lo
                    x += 1
                    i += 3
                self._apply_hello_to_ppm_row(row, y, width)
                self.display.write_row(y, row)

        return True

    def render(self):
        if self.draw_ppm_if_present('/cat.ppm'):
            return
        self.draw_background()
        self.draw_pixel_cat(58, 16, scale=4)
        self._draw_hello_on_graphics()
        self.graphics.render_to_display(self.display)

    def run(self):
        self.rgb_led.random_color()
        self.led_last_change = time.ticks_ms()
        while True:
            if not self._rendered_once:
                self.render()
                self._rendered_once = True

            now = time.ticks_ms()
            if now - self.led_last_change >= 5000:
                self.led_last_change = now
                self.rgb_led.random_color()

            time.sleep_ms(300)


def main():
    app = CatApp()
    app.run()


if __name__ == '__main__':
    main()
