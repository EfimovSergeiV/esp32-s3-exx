import time

try:
    from machine import ADC, I2C, Pin
    import network
except ImportError:  # pragma: no cover - host-only validation
    class _DummyADC:
        ATTN_11DB = 0

        def __init__(self, *args, **kwargs):
            pass

        def atten(self, *args, **kwargs):
            return None

        def read_uv(self):
            return 0

    class _DummyI2C:
        def __init__(self, *args, **kwargs):
            pass

        def readfrom(self, *args, **kwargs):
            return b"\x00"

        def writeto(self, *args, **kwargs):
            return None

    class _DummyPin:
        IN = 0
        OUT = 1
        PULL_UP = 2

        def __init__(self, *args, **kwargs):
            pass

    ADC = _DummyADC
    I2C = _DummyI2C
    Pin = _DummyPin
    network = None


class BatteryMonitor:
    def __init__(self, pin=1, calibration=0.992857):
        self.pin = pin
        self.calibration = calibration
        self.adc = ADC(Pin(pin))
        try:
            self.adc.atten(ADC.ATTN_11DB)
        except AttributeError:
            pass

    def read_volts(self):
        try:
            mv = self.adc.read_uv() / 1000.0
        except AttributeError:
            mv = self.adc.read() * 3.3 * 1000.0 / 4095.0
        return (mv / self.calibration) * 3.0 / 1000.0


class QMI8658:
    """Thin driver for the QMI8658 inertial sensor used by the original demo."""

    QMI8658_L_SLAVE_ADDRESS = 0x6B
    QMI8658_H_SLAVE_ADDRESS = 0x6A
    QMI8658_REVISION_ID = 0x01
    QMI8658_CTRL1 = 0x02
    QMI8658_CTRL2 = 0x03
    QMI8658_CTRL3 = 0x04
    QMI8658_CTRL5 = 0x06
    QMI8658_CTRL7 = 0x08
    QMI8658_AX_L = 0x35
    QMI8658_AX_H = 0x36
    QMI8658_AY_L = 0x37
    QMI8658_AY_H = 0x38
    QMI8658_AZ_L = 0x39
    QMI8658_AZ_H = 0x3A
    QMI8658_GX_L = 0x3B
    QMI8658_GX_H = 0x3C
    QMI8658_GY_L = 0x3D
    QMI8658_GY_H = 0x3E
    QMI8658_GZ_L = 0x3F
    QMI8658_GZ_H = 0x40

    def __init__(self, scl=47, sda=48, addr=0x6B):
        self.addr = addr
        self.i2c = I2C(1, scl=Pin(scl), sda=Pin(sda), freq=400000)
        self.accel = [0.0, 0.0, 0.0]
        self.gyro = [0.0, 0.0, 0.0]
        self.initialized = False
        self.init()

    def init(self):
        try:
            chip = self.read_reg(self.QMI8658_REVISION_ID)
            self.initialized = chip is not None
        except Exception:
            self.initialized = False

    def read_reg(self, reg):
        try:
            data = self.i2c.readfrom(self.addr, 1, reg)
            return data[0]
        except Exception:
            return None

    def write_reg(self, reg, value):
        try:
            self.i2c.writeto(self.addr, bytearray((reg, value)))
            return True
        except Exception:
            return False

    def read_s16(self, low_reg, high_reg):
        lo = self.read_reg(low_reg)
        hi = self.read_reg(high_reg)
        if lo is None or hi is None:
            return 0
        value = (hi << 8) | lo
        if value >= 0x8000:
            value -= 0x10000
        return value

    def refresh(self):
        if not self.initialized:
            return self.accel, self.gyro
        ax = self.read_s16(self.QMI8658_AX_L, self.QMI8658_AX_H)
        ay = self.read_s16(self.QMI8658_AY_L, self.QMI8658_AY_H)
        az = self.read_s16(self.QMI8658_AZ_L, self.QMI8658_AZ_H)
        gx = self.read_s16(self.QMI8658_GX_L, self.QMI8658_GX_H)
        gy = self.read_s16(self.QMI8658_GY_L, self.QMI8658_GY_H)
        gz = self.read_s16(self.QMI8658_GZ_L, self.QMI8658_GZ_H)
        self.accel = [ax / 32768.0 * 4.0, ay / 32768.0 * 4.0, az / 32768.0 * 4.0]
        self.gyro = [gx / 32768.0 * 64.0, gy / 32768.0 * 64.0, gz / 32768.0 * 64.0]
        return self.accel, self.gyro


def wifi_scan_count():
    if network is None:
        return 0
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        return len(wlan.scan())
    except Exception:
        return 0


def button_state(pin_number=0):
    try:
        btn = Pin(pin_number, Pin.IN, Pin.PULL_UP)
        return btn.value() == 0
    except Exception:
        return False


def if_connected_to_wifi():
    if network is None:
        return False
    try:
        wlan = network.WLAN(network.STA_IF)
        return wlan.isconnected()
    except Exception:
        return False
