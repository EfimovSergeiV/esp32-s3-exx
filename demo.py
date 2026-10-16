import time

if not hasattr(time, 'sleep_ms'):
    def _sleep_ms(ms):
        time.sleep(ms / 1000.0)
    time.sleep_ms = _sleep_ms

if not hasattr(time, 'ticks_ms'):
    def _ticks_ms():
        return int(time.time() * 1000)
    time.ticks_ms = _ticks_ms

from display import ST7789Display, rgb565
from graphics import Graphics, BLACK, BLUE, GREEN, RED, WHITE, YELLOW, GRAY
from sensors import BatteryMonitor, QMI8658, wifi_scan_count

try:
    from machine import Pin
except ImportError:  # pragma: no cover
    class Pin:
        IN = 0
        OUT = 1
        PULL_UP = 2

        def __init__(self, *args, **kwargs):
            pass

        def value(self):
            return 1


class DemoApp:
    def __init__(self, display=None):
        self.display = display or ST7789Display()
        self.display.init()
        self.graphics = Graphics(172, 320)
        self.battery = BatteryMonitor(pin=1)
        self.imu = QMI8658()
        self.button = Pin(0, Pin.IN, Pin.PULL_UP)
        self.screen_index = 0
        self.button_pressed = False
        self.press_started = 0
        self.page_names = [
            'Onboard',
            'Sensors',
            'System',
        ]

    def get_page_name(self):
        return self.page_names[self.screen_index % len(self.page_names)]

    def read_button_event(self):
        now = time.ticks_ms()
        pressed = self.button.value() == 0
        if pressed and not self.button_pressed:
            self.button_pressed = True
            self.press_started = now
        elif not pressed and self.button_pressed:
            hold = now - self.press_started
            self.button_pressed = False
            if hold > 800:
                self.screen_index = (self.screen_index + 1) % len(self.page_names)
            else:
                self.screen_index = (self.screen_index + 1) % len(self.page_names)

    def render_base(self):
        self.graphics.clear(BLACK)
        self.graphics.rect(4, 4, 164, 34, WHITE, fill=False)
        self.graphics.text(10, 12, 'ESP32-S3 LCD 1.47B', WHITE)
        self.graphics.text(10, 28, self.get_page_name(), GREEN)
        self.graphics.text(114, 28, 'Demo', YELLOW)

    def render_screen_onboard(self):
        self.render_base()
        self.graphics.draw_panel(8, 48, 156, 70, 'System')
        self.graphics.text(18, 68, 'SD Card: 16 GB', WHITE)
        self.graphics.text(18, 86, 'Flash: 16 MB', WHITE)
        self.graphics.text(18, 104, 'Battery: %.2f V' % self.battery.read_volts(), GREEN)

        self.graphics.draw_panel(8, 130, 156, 76, 'Wireless')
        self.graphics.text(18, 150, 'WiFi scan:', WHITE)
        self.graphics.text(18, 168, str(wifi_scan_count()) + ' APs', YELLOW)
        self.graphics.text(18, 186, 'BT scan: not supported', GRAY)

        self.graphics.draw_panel(8, 220, 156, 70, 'Backlight')
        self.graphics.text(18, 240, 'Brightness: 90%', WHITE)
        self.graphics.draw_status_bar(18, 258, 120, 90, 100, GREEN)

    def render_screen_sensors(self):
        self.render_base()
        accel, gyro = self.imu.refresh()
        self.graphics.draw_panel(8, 48, 156, 100, 'Accel')
        self.graphics.text(18, 68, 'X: %.2f g' % accel[0], WHITE)
        self.graphics.text(18, 86, 'Y: %.2f g' % accel[1], WHITE)
        self.graphics.text(18, 104, 'Z: %.2f g' % accel[2], WHITE)

        self.graphics.draw_panel(8, 164, 156, 100, 'Gyro')
        self.graphics.text(18, 184, 'X: %.1f dps' % gyro[0], WHITE)
        self.graphics.text(18, 202, 'Y: %.1f dps' % gyro[1], WHITE)
        self.graphics.text(18, 220, 'Z: %.1f dps' % gyro[2], WHITE)

        self.graphics.draw_panel(8, 276, 156, 26, 'Status')
        self.graphics.text(18, 286, 'QMI8658 ready' if self.imu.initialized else 'QMI8658 absent', GREEN if self.imu.initialized else RED)

    def render_screen_system(self):
        self.render_base()
        self.graphics.draw_panel(8, 52, 156, 52, 'Core')
        self.graphics.text(18, 72, 'CPU: ESP32-S3', WHITE)
        self.graphics.text(18, 90, 'Flash: 16 MB | PSRAM: 8 MB', WHITE)

        self.graphics.draw_panel(8, 118, 156, 66, 'Display')
        self.graphics.text(18, 140, '172x320', WHITE)
        self.graphics.text(18, 158, 'SPI Mode 0 / 12 MHz', WHITE)

        self.graphics.draw_panel(8, 196, 156, 60, 'Demo')
        self.graphics.text(18, 218, 'Button toggles', WHITE)
        self.graphics.text(18, 236, 'screens every press', WHITE)

        self.graphics.draw_panel(8, 268, 156, 32, 'Info')
        self.graphics.text(18, 282, 'MicroPython ready', GREEN)

    def render(self):
        if self.screen_index == 0:
            self.render_screen_onboard()
        elif self.screen_index == 1:
            self.render_screen_sensors()
        else:
            self.render_screen_system()
        self.graphics.render_to_display(self.display)

    def run(self):
        last_tick = time.ticks_ms()
        while True:
            self.read_button_event()
            if time.ticks_ms() - last_tick >= 100:
                last_tick = time.ticks_ms()
                self.render()
            time.sleep_ms(20)


def main():
    app = DemoApp()
    app.run()


if __name__ == '__main__':
    main()
