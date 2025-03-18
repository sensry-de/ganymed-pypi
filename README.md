# Sensry Ganymed Sy1xx Package

available modules:

* ganymed.bootloader

## Installation

```bash
pip install ganymed
```


## Sensry Ganymed Sy1xx Bootloader -- ganymed.bootloader

The Sensry Ganymed SY1xx Bootloader is a tool designed for interfacing with the bootloader of Sensry Ganymed SY1xx series devices. It enables users to flash firmware, update bootloader configurations, and manage device firmware over supported communication interfaces (such as UART, USB, or SPI). The tool is useful for developers working with Sensry Ganymed SY1xx microcontrollers, allowing efficient firmware deployment and maintenance. 


```python
import os
from ganymed.bootloader import Bootloader

# define the file to be uploaded
application_bin = "zephyr_demo_app.bin"

# create the loader
flash = Bootloader()

# convert binary to application ganymed-image
application_gnm = flash.convert_zephyr_bin(application_bin)

# connect to serial
flash.connect("/dev/ttyUSB0")

# set the controller into bootloader mode
flash.enter_loading_mode()

# clear the internal flash
flash.clear_mram()

# enable the flash mode
flash.set_flash_mode()

# alternatively enable debug mode to enable ram debugging
# flash.set_debug_mode()

# write the new binaries
flash.write_ganymed_image_to_mram(application_gnm)

print("done")
```
