# Sensry Ganymed Sy1xx Package

available modules:

* ganymed.bootloader

## Installation

If installed for the first time:

```bash
pip install ganymed
```

If an older version is installed and a newer version is available:

```bash
pip install --upgrade ganymed
```



## Sensry Ganymed Sy1xx Bootloader -- ganymed.bootloader

The Sensry Ganymed SY1xx Bootloader is a tool designed for interfacing with the bootloader of Sensry Ganymed SY1xx series devices. It enables users to flash firmware, update bootloader configurations, and manage device firmware over supported communication interfaces (such as UART, USB, or SPI). The tool is useful for developers working with Sensry Ganymed SY1xx microcontrollers, allowing efficient firmware deployment and maintenance. 


### Flash image permanently

We flash the application image together with the coreguard runtime image.

```python
import os
from ganymed.bootloader import Bootloader

# convert binary to application ganymed-image
application_gnm = Bootloader.convert_zephyr_bin("zephyr_demo_app.bin")

# create the loader
flash = Bootloader()

# connect to serial
flash.connect("/dev/ttyUSB0")

# set the controller into bootloader mode
flash.enter_loading_mode()

# clear the internal flash
flash.clear_mram()

# write the new binaries
flash.write_image(application_gnm)

print("done")
```

### Flash Debug Mode

In debug mode, we flash the debug version of the coreugard only. The application image will be loaded via JTAG to the internal RAM for debugging, setting breakpoints and inspect core status. 

```python
import os
from ganymed.bootloader import Bootloader

# create the loader
flash = Bootloader()

# connect to serial
flash.connect("/dev/ttyUSB0")

# set the controller into bootloader mode
flash.enter_loading_mode()

# clear the internal flash
flash.clear_mram()

# write the new binaries
flash.write_debug_mode()

print("done")
```
