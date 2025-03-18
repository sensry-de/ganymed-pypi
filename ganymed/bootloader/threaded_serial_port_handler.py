#
# Copyright (C) Sensry GmbH
# Maria-Reiche-Str. 1
# 01109 Dresden
#
# \author s.ginka@sensry.de
# \date 11.Feb.2023

import serial
import threading
from queue import Queue, Empty
import serial.tools.list_ports

from .logging_module import *

class ThreadedSerialPortHandler:
    verbose_com = False

    def __init__(self, on_log_callback=None):
        self.port_list = []
        self.port = None
        self.port_name = ""
        self.debug_rx_tx = False

        # detect available ports
        self.detect_available_serial_ports()

        #
        self.receive_queue = Queue()

        # callback for logging
        if on_log_callback is not None:
            self.do_log = on_log_callback
        else:
            self.do_log = self.log

        self.response_callback = self.__print_data

        # start thread loops
        self.running = False
        self.receive_thread = None
        self.process_response_thread = None

    def log(self, text):
        logger.debug(" ".join([f">{str(text)}"]))

    def detect_supported_serial_port(self):
        ports = serial.tools.list_ports.comports()
        for port, desc, hw_id in sorted(ports):
            if "0403:6001" in hw_id:
                return port

        return ""

    def detect_available_serial_ports(self):
        self.port_list.clear()
        ports = serial.tools.list_ports.comports()
        for port, desc, hw_id in sorted(ports):
            self.port_list.append({
                "device": port,
                "description": desc,
                "hardware": hw_id,
            })
        return self.port_list

    def get_port_list(self):
        return self.port_list

    def is_connected(self):
        if self.port is None:
            return False
        return self.port.is_open

    def connect(self, port_name, baudrate, timeout):
        try:
            self.port = serial.Serial(port_name, baudrate, timeout=0.01, xonxoff=False, rtscts=False)
            if self.port.is_open:
                self.running = True
                self.port_name = port_name
                self.__start_threads()
                return True
            else:
                return False

        except Exception as e:
            logger.debug(" ".join([str(e)]))
            return False

    def disconnect(self):
        try:
            self.running = False
            self.receive_thread.join()
            self.process_response_thread.join()
            self.port.close()
            return True
        except:
            return False

    def __start_threads(self):
        self.receive_thread = threading.Thread(
            target=self.__read_async, args=())
        self.receive_thread.daemon = True
        self.receive_thread.start()

        # start process thread
        self.process_response_thread = threading.Thread(
            target=self.__process_response, args=())
        self.process_response_thread.daemon = True
        self.process_response_thread.start()

    def __read_async(self):
        logger.debug(" ".join(["serial port receive thread started"]))

        in_buf = bytearray()
        while self.running:

            try:
                char = self.port.read(size=128)
                in_buf += char

                if len(char) == 0 and len(in_buf) > 0:
                    # message received and no further bytes are coming; pitfall: always create a copy of the bytearray!
                    self.receive_queue.put(in_buf[:], block=True)
                    in_buf.clear()
            except:
                continue

        logger.debug(" ".join(["serial port receive thread stopped"]))

    def __process_response(self):
        logger.debug(" ".join(["process response thread started"]))
        while self.running:
            try:
                msg = self.receive_queue.get(block=True, timeout=0.5)

                if len(msg):
                    if self.debug_rx_tx:
                        logger.debug(" ".join([f"{self.port_name} RX> {msg.hex(' ')}"]))

                    self.response_callback(msg)

                self.receive_queue.task_done()
            except Empty:
                continue

        logger.debug(" ".join(["process response thread stopped"]))

    def send(self, byte_data, response_callback, debug=False):
        self.response_callback = response_callback
        self.debug_rx_tx = debug
        if self.port.is_open:
            # workaround -- uart/bootloader needs at least one additional byte
            byte_data.append(0x30)
            if self.debug_rx_tx:
                logger.debug(" ".join([f"{self.port_name} TX> {byte_data.hex(' ')}"]))
            self.port.write(byte_data)

    def __print_data(self, data):
        self.do_log(f"{data.decode()}")
        return

