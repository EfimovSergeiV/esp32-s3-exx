import time

if not hasattr(time, 'sleep_ms'):
    def _sleep_ms(ms):
        time.sleep(ms / 1000.0)
    time.sleep_ms = _sleep_ms

if not hasattr(time, 'ticks_ms'):
    def _ticks_ms():
        return int(time.time() * 1000)
    time.ticks_ms = _ticks_ms

try:
    import framebuf
except ImportError:  # pragma: no cover - host-only validation
    framebuf = None

try:
    from machine import Pin, SPI, PWM
except ImportError:  # pragma: no cover - only for host-side syntax checks
    class _MissingPin:
        OUT = 0
        IN = 1
        PULL_UP = 2

        def __init__(self, *args, **kwargs):
            pass

        def value(self, *args, **kwargs):
            return 0

    class _MissingSPI:
        def __init__(self, *args, **kwargs):
            pass

        def write(self, *args, **kwargs):
            return 0

    class _MissingPWM:
        def __init__(self, *args, **kwargs):
            pass

        def duty(self, *args, **kwargs):
            return 0

    Pin = _MissingPin
    SPI = _MissingSPI
    PWM = _MissingPWM


LCD_WIDTH = 172
LCD_HEIGHT = 320
OFFSET_X = 34
OFFSET_Y = 0
VERTICAL = 0
HORIZONTAL = 1
SPI_FREQUENCY = 10_000_000


class ST7789Display:
    """ST7789 driver tuned for the Waveshare ESP32-S3-LCD-1.47B panel."""

    def __init__(
        self,
        width=LCD_WIDTH,
        height=LCD_HEIGHT,
        spi_bus=2,
        sclk=40,
        mosi=45,
        miso=-1,
        cs=42,
        dc=41,
        rst=39,
        bl=46,
        rotation=HORIZONTAL,
    ):
        self.width = width
        self.height = height
        self.rotation = rotation
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.rst = Pin(rst, Pin.OUT, value=1)
        self.backlight = PWM(Pin(bl), freq=1000, duty=0)
        self._rowbuf = bytearray(width * 2)

        if miso >= 0:
            self.spi = SPI(
                spi_bus,
                baudrate=SPI_FREQUENCY,
                polarity=0,
                phase=0,
                sck=Pin(sclk),
                mosi=Pin(mosi),
                miso=Pin(miso),
            )
        else:
            self.spi = SPI(
                spi_bus,
                baudrate=SPI_FREQUENCY,
                polarity=0,
                phase=0,
                sck=Pin(sclk),
                mosi=Pin(mosi),
            )

    def reset(self):
        self.cs.value(1)
        self.rst.value(0)
        time.sleep_ms(50)
        self.rst.value(1)
        time.sleep_ms(50)

    def write_command(self, cmd):
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytes((cmd & 0xFF,)))
        self.cs.value(1)

    def write_data(self, data):
        self.cs.value(0)
        self.dc.value(1)
        if isinstance(data, int):
            self.spi.write(bytes((data & 0xFF,)))
        else:
            self.spi.write(data if isinstance(data, (bytes, bytearray, memoryview)) else bytes(data))
        self.cs.value(1)

    def write_row(self, y, row_data):
        row_len = len(row_data)
        if row_len == 0:
            return
        if row_len > self.width * 2:
            row_len = self.width * 2
        self.set_window(0, y, self.width - 1, y)
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(row_data[:row_len])
        self.cs.value(1)

    def write_window_bytes(self, x0, y0, x1, y1, data):
        self.set_window(x0, y0, x1, y1)
        self.cs.value(0)
        self.dc.value(1)
        self.spi.write(data)
        self.cs.value(1)

    def init(self):
        self.reset()
        self.write_command(0x11)
        time.sleep_ms(120)

        self.write_command(0x36)
        if self.rotation == HORIZONTAL:
            self.write_data(0x08)
        else:
            # Keep controller memory orientation in default mode and rotate
            # through set_window() mapping for reliable 320x172 landscape.
            self.write_data(0x08)

        self.write_command(0x3A)
        self.write_data(0x05)

        self.write_command(0xB0)
        self.write_data(bytes((0x00, 0xE8)))

        self.write_command(0xB2)
        self.write_data(bytes((0x0C, 0x0C, 0x00, 0x33, 0x33)))

        self.write_command(0xB7)
        self.write_data(0x35)

        self.write_command(0xBB)
        self.write_data(0x35)

        self.write_command(0xC0)
        self.write_data(0x2C)

        self.write_command(0xC2)
        self.write_data(0x01)

        self.write_command(0xC3)
        self.write_data(0x13)

        self.write_command(0xC4)
        self.write_data(0x20)

        self.write_command(0xC6)
        self.write_data(0x0F)

        self.write_command(0xD0)
        self.write_data(bytes((0xA4, 0xA1)))

        self.write_command(0xD6)
        self.write_data(0xA1)

        self.write_command(0xE0)
        self.write_data(bytes((
            0xF0, 0x00, 0x04, 0x04, 0x04, 0x05, 0x29, 0x33,
            0x3E, 0x38, 0x12, 0x12, 0x28, 0x30,
        )))

        self.write_command(0xE1)
        self.write_data(bytes((
            0xF0, 0x07, 0x0A, 0x0D, 0x0B, 0x07, 0x28, 0x33,
            0x3E, 0x36, 0x14, 0x14, 0x29, 0x32,
        )))

        self.write_command(0x21)
        self.write_command(0x11)
        time.sleep_ms(120)
        self.write_command(0x29)
        self.set_backlight(90)

    def set_backlight(self, level):
        if level < 0:
            level = 0
        if level > 100:
            level = 100
        try:
            duty = int((level / 100.0) * 65535)
            self.backlight.duty_u16(duty)
        except AttributeError:
            self.backlight.duty(int((level / 100.0) * 1023))

    def set_window(self, x0, y0, x1, y1):
        if self.rotation == HORIZONTAL:
            x0 += OFFSET_X
            x1 += OFFSET_X
            y0 += OFFSET_Y
            y1 += OFFSET_Y
        else:
            x0, y0, x1, y1 = y0, x0, y1, x1
            # For a 320x172 logical landscape canvas:
            # physical_x = logical_y + OFFSET_X, physical_y = logical_x + OFFSET_Y
            x0 += OFFSET_X
            x1 += OFFSET_X
            y0 += OFFSET_Y
            y1 += OFFSET_Y

        self.write_command(0x2A)
        self.write_data(bytes(((x0 >> 8) & 0xFF, x0 & 0xFF, (x1 >> 8) & 0xFF, x1 & 0xFF)))
        self.write_command(0x2B)
        self.write_data(bytes(((y0 >> 8) & 0xFF, y0 & 0xFF, (y1 >> 8) & 0xFF, y1 & 0xFF)))
        self.write_command(0x2C)

    def draw_pixel(self, x, y, color):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        self.set_window(x, y, x, y)
        self.write_data(((color >> 8) & 0xFF, color & 0xFF))

    def draw_hline(self, x, y, width, color):
        if width <= 0 or y < 0 or y >= self.height:
            return
        if x < 0:
            width += x
            x = 0
        if x + width > self.width:
            width = self.width - x
        if width <= 0:
            return
        self.set_window(x, y, x + width - 1, y)
        row = bytearray(width * 2)
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        for i in range(0, len(row), 2):
            row[i] = hi
            row[i + 1] = lo
        self.write_window_bytes(x, y, x + width - 1, y, row)

    def draw_vline(self, x, y, height, color):
        if height <= 0 or x < 0 or x >= self.width:
            return
        if y < 0:
            height += y
            y = 0
        if y + height > self.height:
            height = self.height - y
        if height <= 0:
            return
        for row in range(height):
            self.draw_pixel(x, y + row, color)

    def fill_rect(self, x, y, width, height, color):
        if width <= 0 or height <= 0:
            return
        if x < 0:
            width += x
            x = 0
        if y < 0:
            height += y
            y = 0
        if x + width > self.width:
            width = self.width - x
        if y + height > self.height:
            height = self.height - y
        if width <= 0 or height <= 0:
            return
        for row in range(height):
            self.draw_hline(x, y + row, width, color)

    def draw_rect(self, x, y, width, height, color, fill=False):
        if fill:
            self.fill_rect(x, y, width, height, color)
            return
        self.draw_hline(x, y, width, color)
        self.draw_hline(x, y + height - 1, width, color)
        self.draw_vline(x, y, height, color)
        self.draw_vline(x + width - 1, y, height, color)

    def draw_line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.draw_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_text(self, x, y, text, color):
        if not text or framebuf is None:
            return
        if isinstance(text, str):
            text = text.encode('utf-8')
        font_h = 16
        canvas = bytearray(self.width * font_h * 2)
        fb = framebuf.FrameBuffer(canvas, self.width, font_h, framebuf.RGB565)
        fb.fill(0)
        fb.text(text.decode('utf-8'), 0, 0, color)
        for row in range(font_h):
            start = row * self.width * 2
            row_data = memoryview(canvas)[start:start + self.width * 2]
            self.write_row(y + row, row_data)

    def write_frame(self, fb):
        if hasattr(fb, 'render_to'):
            fb.render_to(self)
            return
        if hasattr(fb, 'buf'):
            data = fb.buf
        elif hasattr(fb, 'buffer'):
            data = fb.buffer
        else:
            data = fb
        if data is None or len(data) == 0:
            return
        if len(data) == self.width * self.height * 2:
            mv = memoryview(data)
            stride = self.width * 2
            for y in range(self.height):
                self.write_row(y, mv[y * stride:(y + 1) * stride])
            return
        self.write_window_bytes(0, 0, self.width - 1, self.height - 1, data)


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
