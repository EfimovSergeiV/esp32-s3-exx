```zsh
# Debian 13
esptool.py erase_flash

# esptool --chip esp32s3 --port /dev/ttyACM0 erase-flash

esptool --chip esp32s3 --port /dev/ttyACM0 --baud 460800 write-flash 0x0 ESP32_GENERIC_S3-20260824-v1.29.0.bin



./ImageMagick-7.1.2-34-gcc-x86_64.AppImage cat.png -resize 320x172^ -gravity center -extent 320x172 -strip ppm:cat.ppm
```


```zsh

mpremote connect /dev/ttyACM0 fs cp main.py :main.py
mpremote connect /dev/ttyACM0 fs cp display.py :display.py
mpremote connect /dev/ttyACM0 fs cp graphics.py :graphics.py
mpremote connect /dev/ttyACM0 fs cp demo.py :demo.py
mpremote connect /dev/ttyACM0 reset


```


# ESP32-S3-LCD-1.47B MicroPython port

This repository contains a plain MicroPython version of the original Waveshare demo flow for the ESP32-S3-LCD-1.47B board.

The original project is built around:
- ST7789 panel controller
- SPI bus at 12 MHz, SPI mode 0
- ESP32-S3 GPIO map:
  - SPI SCLK = 40
  - SPI MOSI = 45
  - CS = 42
  - DC = 41
  - RST = 39
  - BL = 46
- I2C for QMI8658 at SCL=47, SDA=48
- Boot button on GPIO 0
- ADC battery input on GPIO 1

## Project structure

- `main.py` — entry point
- `demo.py` — UI loop with screen switching and display rendering
- `display.py` — ST7789 panel driver and backlight controller
- `graphics.py` — basic primitives based on `framebuf`
- `sensors.py` — battery, QMI8658, WiFi scan helpers

## What was ported

- ST7789 reset and init sequence
- panel window addressing and RGB565 writes
- backlight PWM control
- read battery voltage from ADC
- QMI8658 read skeleton for acceleration and gyro values
- WiFi scan with standard `network.WLAN`
- screen switching behavior matching the original demo flow
- graphically similar dashboard screens for the onboard status demo

## Limitations

Plain MicroPython does not provide the LVGL runtime used by the original Arduino/ESP-IDF demo. Therefore, this port replaces LVGL with the native `framebuf` API, keeping the same hardware configuration and similar UI flow but not reproducing LVGL object widgets pixel-perfect.

The Bluetooth scan used in the original app is not available in ordinary MicroPython without a vendor-specific or custom build, so it is represented as a documented limitation rather than a fake implementation.

## Loading onto the board

Connect the board to USB and ensure a standard MicroPython firmware is running.

From the repository root:

```zsh
mpremote connect /dev/ttyACM0 fs mkdir :lib
mpremote connect /dev/ttyACM0 fs cp main.py :main.py
mpremote connect /dev/ttyACM0 fs cp display.py :display.py
mpremote connect /dev/ttyACM0 fs cp graphics.py :graphics.py
mpremote connect /dev/ttyACM0 fs cp sensors.py :sensors.py
mpremote connect /dev/ttyACM0 fs cp demo.py :demo.py

mpremote connect /dev/ttyACM0 run main.py
```

```bash
mpremote connect /dev/ttyACM0
mpremote fs mkdir /lib || true
# mpremote fs cp main.py /main.py
mpremote connect /dev/ttyACM0 fs cp main.py :main.py

mpremote fs cp display.py /display.py
mpremote fs cp graphics.py /graphics.py
mpremote fs cp sensors.py /sensors.py
mpremote fs cp demo.py /demo.py
mpremote run /main.py
```

If you prefer mounting the directory, this also works:

```bash
mpremote connect /dev/ttyACM0 mip install
mpremote mount .
```

Then run:

```python
import main
main.main()
```

## Verification performed

This workspace was statically validated with Python syntax checks:

```bash
python3 -m compileall .
```

This confirms the MicroPython modules parse cleanly in the standard Python compiler, which is the strongest available local check without access to the target board.

## Coverage matrix

| Original function | Status | Notes |
| --- | --- | --- |
| ST7789 init | ✅ | Implemented from the repo's register sequence |
| SPI mode 0 / 12 MHz | ✅ | Configured in `display.py` |
| display window writes | ✅ | `set_window()` + `write_frame()` |
| backlight PWM | ✅ | Controlled with `machine.PWM` |
| ADC battery read | ✅ | `BatteryMonitor` |
| QMI8658 access | ✅ | Minimal driver/refresh path |
| WiFi scan | ✅ | Standard MicroPython via `network.WLAN` |
| BLE scan | ⚠️ not feasible | Not available in ordinary MicroPython |
| LVGL widgets | ❌ replaced | Replaced with `framebuf` rendering |
| full LVGL demo app | ❌ replaced | Equivalent dashboard flow preserved |

## Notes for hardware testing

To verify on device, run `main.py` and press the BOOT key to rotate the screens. The code is designed around the same pins and timings extracted from the original Waveshare demo.
