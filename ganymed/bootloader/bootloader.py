#
# Copyright (C) Sensry GmbH
# Maria-Reiche-Str. 1
# 01109 Dresden
#
# \author s.ginka@sensry.de
# \date 11.Feb.2023

import os.path
import threading
import importlib.resources

from .logging_module import logger
from .sy1xx_bootloader import Sy1xxBootloader
from .threaded_serial_port_handler import ThreadedSerialPortHandler
from .generate_ganymed_image import generate_ganymed_image


class Bootloader:

    def __init__(self):
        self.connected = False
        self.job_done = threading.Event()
        self.serial_port = ThreadedSerialPortHandler()
        self.bootloader = Sy1xxBootloader(serial_handler=self.serial_port, logging_callback=self.log,
                                 reset_callback=self.bootloader_reset_cb,
                                 task_done_callback=self.bootloader_task_done_callback,
                                 serial_log=self.on_serial_log)
        self.coreguard = self.get_firmware_coreguard_path("flash")

    def log(self, text):
        return

    def on_serial_log(self, data):
        self.log(data)

    def bootloader_reset_cb(self):
        logger.debug(" ".join(["reset cb from bootloader requested..."]))

    def bootloader_task_done_callback(self, cmd, result_code):
        print("job done")
        self.job_done.set()

    def connect(self, port):
        if self.serial_port.connect(port, 1000000, 5):
            self.log(f"connected to {port}")
            self.connected = True
        else:
            self.log(f"failed to connect to {port}")
            self.connected = False

    @staticmethod
    def get_firmware_coreguard_path(name="flash"):
        filename = f"coreguard-{name}.bin"
        posix_path = importlib.resources.files("ganymed").joinpath("bootloader", "firmware", filename)
        return str(posix_path)

    def write_debug_mode(self):
        self.coreguard = self.get_firmware_coreguard_path("debug")
        self.__write_ganymed_image_to_mram()

    def write_image(self, application_gnm):
        self.coreguard = self.get_firmware_coreguard_path("flash")
        self.__write_ganymed_image_to_mram(application_gnm)

    def __write_ganymed_image_to_mram(self, application_gnm=""):
        if not self.connected:
            self.log("not connected")
            return

        values = {
            "kernel_file": self.coreguard,
            "ota_app_file": application_gnm,
            "toc_file": "",
            "user_file": "",
        }

        kernel_filename = values["kernel_file"]

        toc_filename = ""

        if "toc_file" in values.keys():
            toc_filename = values["toc_file"]


        ota_app_filename = values["ota_app_file"]

        user_filename = ""

        if "user_file" in values.keys():
            user_filename = values["user_file"]

        if kernel_filename is None:
            kernel_filename = os.path.join("../../bin", "coreguard-bl.bin")

        if user_filename is None:
            user_filename = "../dist/ganymed_firmware_partition1.bin"

        if len(kernel_filename) > 0:
            self.job_done.clear()
            self.log(f"kernel to MRAM {kernel_filename}")
            self.bootloader.store_to_mram(kernel_filename, toc_filename, ota_app_filename, user_filename)
            self.job_done.wait()
            print("finished writing to MRAM")

    def clear_mram(self):
        if not self.connected:
            self.log("not connected")
            return
        self.job_done.clear()
        self.bootloader.clear_mram()
        self.job_done.wait()
        print("finished clearing MRAM")

    def enter_loading_mode(self):
        print("\n\n")
        print("--- please press reset button if requested!! ---")
        print("\n\n")
        self.job_done.clear()
        self.bootloader.run_init()
        self.job_done.wait()
        print("entered loading mode")

    @staticmethod
    def convert_zephyr_bin(zephyr_bin):
        zephyr_gnm = zephyr_bin + ".gnm"
        zephyr_meta = zephyr_bin + ".meta"
        generate_ganymed_image(zephyr_bin, zephyr_gnm, zephyr_meta)
        return zephyr_gnm

