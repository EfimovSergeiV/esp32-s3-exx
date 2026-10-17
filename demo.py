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
    """Show /cat.ppm on display and cycle LED color every 5 seconds."""

    def __init__(self, display=None):
        self.display = display or ST7789Display(width=320, height=172, rotation=VERTICAL)
        self.display.init()
        self.graphics = Graphics(self.display.width, self.display.height)
        self.rgb_led = RGBStatusLed(pin=38)
        self.led_last_change = 0
        self._rendered_once = False

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
                    self._set_row_pixel(row, width, x, c)
                    x += 1
                    i += 3

                self.display.write_row(y, row)

        return True

    def render(self):
        if not self.draw_ppm_if_present('/cat.ppm'):
            self._draw_not_found()

    def run(self):
        self.rgb_led.next_color()
        self.led_last_change = time.ticks_ms()

        while True:
            if not self._rendered_once:
                self.render()
                self._rendered_once = True

            now = time.ticks_ms()
            if now - self.led_last_change >= 5000:
                self.led_last_change = now
                self.rgb_led.next_color()

            time.sleep_ms(300)


def main():
    app = CatApp()
    app.run()


if __name__ == '__main__':
    main()
