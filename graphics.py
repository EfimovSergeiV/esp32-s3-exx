import framebuf

try:
    FRAMEBUF_RGB565 = framebuf.RGB565
except AttributeError:  # pragma: no cover - fallback for host-side validation
    FRAMEBUF_RGB565 = 1

BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
YELLOW = 0xFFE0
CYAN = 0x07FF
MAGENTA = 0xF81F
GRAY = 0x8410
DARK = 0x2104


class Graphics:
    """Row-buffered graphics layer that avoids a full-frame Python allocation."""

    def __init__(self, width, height, color_mode=None):
        if color_mode is None:
            color_mode = FRAMEBUF_RGB565
        self.width = width
        self.height = height
        self.color_mode = color_mode
        self.bg_color = BLACK
        self._rows = {}

    @property
    def buffer(self):
        out = bytearray(self.width * self.height * 2)
        for y in range(self.height):
            row = self._rows.get(y)
            if row is None:
                row = bytearray(self.width * 2)
                hi = (self.bg_color >> 8) & 0xFF
                lo = self.bg_color & 0xFF
                for i in range(0, len(row), 2):
                    row[i] = hi
                    row[i + 1] = lo
            start = y * self.width * 2
            out[start:start + len(row)] = row
        return out

    @buffer.deleter
    def buffer(self):
        self._rows = {}

    def _ensure_row(self, y):
        if y not in self._rows:
            row = bytearray(self.width * 2)
            hi = (self.bg_color >> 8) & 0xFF
            lo = self.bg_color & 0xFF
            for i in range(0, len(row), 2):
                row[i] = hi
                row[i + 1] = lo
            self._rows[y] = row
        return self._rows[y]

    def clear(self, color=BLACK):
        self.bg_color = color
        self._rows = {}

    def pixel(self, x, y, color):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        row = self._ensure_row(y)
        idx = x * 2
        row[idx] = (color >> 8) & 0xFF
        row[idx + 1] = color & 0xFF

    def hline(self, x, y, w, color):
        if w <= 0:
            return
        if y < 0 or y >= self.height:
            return
        if x < 0:
            w += x
            x = 0
        if x + w > self.width:
            w = self.width - x
        if w <= 0:
            return
        row = self._ensure_row(y)
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        for i in range(x * 2, (x + w) * 2, 2):
            row[i] = hi
            row[i + 1] = lo

    def vline(self, x, y, h, color):
        if h <= 0 or x < 0 or x >= self.width:
            return
        if y < 0:
            h += y
            y = 0
        if y + h > self.height:
            h = self.height - y
        if h <= 0:
            return
        for yy in range(y, y + h):
            self.pixel(x, yy, color)

    def rect(self, x, y, w, h, color, fill=False):
        if w <= 0 or h <= 0:
            return
        if fill:
            for yy in range(y, y + h):
                self.hline(x, yy, w, color)
        else:
            self.hline(x, y, w, color)
            self.hline(x, y + h - 1, w, color)
            self.vline(x, y, h, color)
            self.vline(x + w - 1, y, h, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def text(self, x, y, s, color=WHITE, scale=1):
        if not s:
            return
        if scale <= 1:
            if framebuf is not None:
                canvas_w = min(self.width, 172)
                canvas_h = 16
                canvas = bytearray(canvas_w * canvas_h * 2)
                fb = framebuf.FrameBuffer(canvas, canvas_w, canvas_h, self.color_mode)
                fb.fill(self.bg_color)
                fb.text(s, 0, 0, color)
                for yy in range(canvas_h):
                    row = self._ensure_row(y + yy)
                    src = yy * canvas_w * 2
                    x0 = max(0, x)
                    x1 = min(self.width, x + canvas_w)
                    for xx in range(x0, x1):
                        dst = xx * 2
                        src_idx = (xx - x0) * 2
                        row[dst:dst + 2] = canvas[src + src_idx:src + src_idx + 2]
            else:
                for yy in range(0, 8):
                    self.hline(x, y + yy, max(1, len(s) * 6), color)
            return

        if framebuf is None:
            return

        tmp_w = max(1, len(s) * 8)
        tmp_h = 16
        tmp = bytearray(tmp_w * tmp_h * 2)
        tmp_fb = framebuf.FrameBuffer(tmp, tmp_w, tmp_h, self.color_mode)
        tmp_fb.fill(self.bg_color)
        tmp_fb.text(s, 0, 0, color)

        for yy in range(tmp_h):
            for xx in range(tmp_w):
                if tmp_fb.pixel(xx, yy) == self.bg_color:
                    continue
                px = x + xx * scale
                py = y + yy * scale
                for dy in range(scale):
                    for dx in range(scale):
                        self.pixel(px + dx, py + dy, color)

        # Slightly offset a second pass to make the letters visibly bolder.
        for yy in range(tmp_h):
            for xx in range(tmp_w):
                if tmp_fb.pixel(xx, yy) == self.bg_color:
                    continue
                px = x + xx * scale + 1
                py = y + yy * scale
                if px < self.width and py < self.height:
                    for dy in range(scale):
                        if py + dy >= self.height:
                            continue
                        self.pixel(px, py + dy, color)

    def draw_panel(self, x, y, w, h, title=None, color=0x1E1E22, border=0xB7B7B7):
        self.rect(x, y, w, h, border, fill=False)
        self.rect(x + 1, y + 1, w - 2, h - 2, color, fill=True)
        if title:
            self.text(x + 6, y + 6, title, border)

    def draw_status_bar(self, x, y, w, value, max_value, color=GREEN):
        if max_value <= 0:
            return
        self.rect(x, y, w, 10, WHITE, fill=False)
        fill_w = max(0, min(w - 2, int((value / max_value) * (w - 2))))
        self.rect(x + 1, y + 1, fill_w, 8, color, fill=True)

    def draw_logo(self, x, y):
        self.rect(x, y, 50, 22, WHITE, fill=True)
        self.rect(x + 6, y + 6, 38, 10, GREEN, fill=True)
        self.text(x + 8, y + 8, 'ESP32', BLUE)

    def render_to_display(self, display):
        for y in range(self.height):
            row = self._rows.get(y)
            if row is None:
                row = bytearray(self.width * 2)
                hi = (self.bg_color >> 8) & 0xFF
                lo = self.bg_color & 0xFF
                for i in range(0, len(row), 2):
                    row[i] = hi
                    row[i + 1] = lo
            display.write_row(y, row)

    def render_to(self, display):
        self.render_to_display(display)

    def as_bytes(self):
        return self.buffer
