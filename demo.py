import os
import time

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


# Panel-specific image output tuning.
PPM_CHANNEL_ORDER = 'BGR'
PPM_FLIP_X = True
PPM_SWAP_565_BYTES = True

# Built-in RGB LED channel order on this board.
# Keep GRB for ESP32-S3-LCD-1.47B onboard NeoPixel.
LED_CHANNEL_ORDER = 'GRB'


class RGBStatusLed:
    """Single RGB LED helper for boards with one NeoPixel on GPIO 38."""

    def __init__(self, pin=38):
        self._np = None
        if Pin is not None and neopixel is not None:
            self._np = neopixel.NeoPixel(Pin(pin, Pin.OUT), 1)

        # Pure green <-> pure blue cycling.
        self._palette = [
            (0, 255, 0),
            (0, 0, 255),
        ]
        self._index = 0

    def _write(self, r, g, b):
        if self._np is None:
            return
        if LED_CHANNEL_ORDER == 'RGB':
            self._np[0] = (r, g, b)
        elif LED_CHANNEL_ORDER == 'GRB':
            self._np[0] = (g, r, b)
        elif LED_CHANNEL_ORDER == 'BRG':
            self._np[0] = (b, r, g)
        else:
            self._np[0] = (r, g, b)
        self._np.write()

    def next_color(self):
        r, g, b = self._palette[self._index]
        self._index = (self._index + 1) % len(self._palette)
        self._write(r, g, b)


class CatApp:
    """Show /cat.ppm with animated saucers and cycle LED color every 5 seconds."""

    def __init__(self, display=None):
        self.display = display or ST7789Display(width=320, height=172, rotation=VERTICAL)
        self.display.init()
        self.graphics = Graphics(self.display.width, self.display.height)
        self._label_graphics = Graphics(self.display.width, self.display.height)
        self._label_color = rgb565(255, 255, 255)
        self._label_text = 'MEINEWELT'
        self._label_y = self.display.height - 18
        self._label_x = 12
        self._label_graphics.text(self._label_x, self._label_y, self._label_text, self._label_color)
        self.rgb_led = RGBStatusLed(pin=38)
        self.led_last_change = 0

        self._base_rows = None
        self._saucer_light = rgb565(245, 249, 255)
        self._saucer_shadow = rgb565(208, 226, 245)
        self._saucer_spans = (
            (16, 31),
            (11, 36),
            (7, 40),
            (4, 43),
            (2, 45),
            (0, 47),
            (1, 46),
            (3, 44),
            (6, 41),
            (10, 37),
            (15, 32),
        )
        self._flat_ufo_spans = (
            (18, 31),
            (14, 35),
            (10, 39),
            (8, 41),
            (6, 43),
            (5, 44),
            (6, 43),
            (8, 41),
            (11, 38),
            (15, 34),
            (20, 29),
        )
        self._saucers = [
            {
                'anchor_x': 86,
                'x': 86,
                'y': 20,
                'vx': 3,
                'x_scale': 0.78,
                'spans': self._flat_ufo_spans,
            },
            {
                'anchor_x': 206,
                'x': 206,
                'y': 10,
                'vx': -3,
                'x_scale': 0.82,
                'left_margin': 15,
            },
        ]

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

    def _draw_not_found(self):
        msg = 'IMAGE NOT FOUND'
        x = (self.display.width - len(msg) * 8) // 2
        y = (self.display.height - 8) // 2
        self.graphics.clear(BLACK)
        self.graphics.text(x, y, msg, rgb565(255, 255, 255))
        self.graphics.render_to_display(self.display)

    def _load_ppm_rows(self, path):
        try:
            os.stat(path)
        except OSError:
            self._base_rows = None
            return False

        rows = []
        with open(path, 'rb') as fp:
            header = self._read_ppm_header(fp)
            if header is None:
                self._base_rows = None
                return False

            width, height = header
            if width != self.display.width or height != self.display.height:
                self._base_rows = None
                return False

            for _ in range(height):
                src = fp.read(width * 3)
                if len(src) != width * 3:
                    self._base_rows = None
                    return False

                row = bytearray(width * 2)
                x = 0
                i = 0
                while x < width:
                    c = self._rgb_to_panel565(src[i], src[i + 1], src[i + 2])
                    self._set_row_pixel(row, width, x, c)
                    x += 1
                    i += 3
                rows.append(row)

        self._base_rows = rows
        return True

    def _apply_saucers_to_row(self, row, y):
        for saucer in self._saucers:
            spans = saucer.get('spans', self._saucer_spans)
            dy = y - saucer['y']
            if dy < 0 or dy >= len(spans):
                continue

            start, end = spans[dy]
            x_base = int(saucer['x'])
            x_scale = saucer.get('x_scale', 1.0)
            color = self._saucer_shadow if dy >= 5 else self._saucer_light
            start_scaled = int(start * x_scale)
            end_scaled = int(end * x_scale)
            for dx in range(start_scaled, end_scaled + 1):
                self._set_row_pixel(row, self.display.width, x_base + dx, color)

    def _saucer_width(self, saucer):
        x_scale = saucer.get('x_scale', 1.0)
        spans = saucer.get('spans', self._saucer_spans)
        min_start = spans[0][0]
        max_end = spans[0][1]
        for start, end in spans[1:]:
            if start < min_start:
                min_start = start
            if end > max_end:
                max_end = end
        return int((max_end - min_start + 1) * x_scale)

    def _apply_label_to_row(self, row, y):
        label_row = self._label_graphics._rows.get(y)
        if label_row is None:
            return
        for x in range(self.display.width):
            idx = x * 2
            color = (label_row[idx] << 8) | label_row[idx + 1]
            if color == 0:
                continue
            self._set_row_pixel(row, self.display.width, x, color)

    def _render_animated_frame(self):
        if self._base_rows is None:
            self._draw_not_found()
            return

        for y in range(self.display.height):
            row = bytearray(self._base_rows[y])
            self._apply_saucers_to_row(row, y)
            self._apply_label_to_row(row, y)
            self.display.write_row(y, row)

    def _update_saucers(self):
        for saucer in self._saucers:
            saucer['x'] += saucer['vx']
            w = self._saucer_width(saucer)
            left_margin = saucer.get('left_margin', 0)
            min_x = saucer['anchor_x'] - 26 - left_margin
            max_x = min(self.display.width - w - 1, saucer['anchor_x'] + 26)
            if saucer['x'] <= min_x:
                saucer['x'] = min_x
                saucer['vx'] = abs(saucer['vx'])
            elif saucer['x'] >= max_x:
                saucer['x'] = max_x
                saucer['vx'] = -abs(saucer['vx'])

    def draw_ppm_if_present(self, path):
        if self._base_rows is None:
            return self._load_ppm_rows(path)
        return True

    def render(self):
        if self.draw_ppm_if_present('/cat.ppm'):
            self._render_animated_frame()
        else:
            self._draw_not_found()

    def run(self):
        self.rgb_led.next_color()
        self.led_last_change = time.ticks_ms()
        last_frame = time.ticks_ms()

        while True:
            now = time.ticks_ms()
            if now - last_frame >= 120:
                last_frame = now
                self._update_saucers()
                self.render()

            if now - self.led_last_change >= 5000:
                self.led_last_change = now
                self.rgb_led.next_color()

            time.sleep_ms(20)


def main():
    app = CatApp()
    app.run()


if __name__ == '__main__':
    main()
