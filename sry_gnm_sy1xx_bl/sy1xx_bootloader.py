#
# Copyright (C) Sensry GmbH
# Maria-Reiche-Str. 1
# 01109 Dresden
#
# \author s.ginka@sensry.de
# \date 11.Feb.2023

import threading
import time
from queue import Queue, Empty

from .logging_module import *

bSOF = 0x5C

CMD = {
    0xA0: "init",
    0xB0: "select",
    0xC0: "upload",
    0xD0: "boot"
}

CMD_RESPONSE = {
    0xA1: "init",
    0xB1: "select",
    0xC1: "upload",
    0xD1: "boot"
}

CMD_RESPONSE_CODE = {
    0x00: "not ok",
    0x01: "ok",
}

class Cmd(object):
    def __init__(self, cmd, done_callback=False):
        self.cmd = cmd
        self.done_callback = done_callback


class Sy1xxBootloader:

    def __init__(self, serial_handler, logging_callback, reset_callback=None, task_done_callback=None, serial_log = None):
        self.debug_rx_tx = False
        self.serial_handler = serial_handler
        self.do_log = logging_callback
        self.serial_log = serial_log
        self.callback_for_user_reset = reset_callback
        self.process_thread = None
        self.send_queue = Queue()
        self.cmd_queue = Queue()
        self.response_msg = bytearray()
        self.__start_process_thread()
        self.task_done_callback = task_done_callback
        return

    def run_init(self):
        # make sure that we are in bootloader
        self.__append_cmd_to_queue("request_loader")
        # get response from loader
        self.__append_cmd_to_queue("init", True)

    def run_boot(self):
        # make sure that we are in bootloader
        #self.__append_cmd_to_queue("request_loader")
        # actually boot
        self.__append_cmd_to_queue("boot", True)

    def kernel_to_sram(self, kernel_filename):
        if len(kernel_filename) == 0:
            return
        # make sure that we are in bootloader
        self.__append_cmd_to_queue("request_loader")
        # start upload
        self.__append_cmd_to_queue("image kernel")
        self.__append_cmd_to_queue(f"upload {kernel_filename}", True)

    def user_to_sram(self, user_filename):
        if len(user_filename) == 0:
            return
        # make sure that we are in bootloader
        self.__append_cmd_to_queue("request_loader")
        # start upload
        self.__append_cmd_to_queue("image user")
        self.__append_cmd_to_queue(f"upload {user_filename}", True)

    def clear_sram(self):
        clear = '-clear-'
        # make sure that we are in bootloader
        self.__append_cmd_to_queue("request_loader")
        # clear kernel
        self.__append_cmd_to_queue("image kernel")
        self.__append_cmd_to_queue(f"upload {clear}")
        # clear user
        self.__append_cmd_to_queue("image user")
        self.__append_cmd_to_queue(f"upload {clear}", True)

        return
    def store_to_mram(self, kernel_filename, toc_filename, ota_app_filename, user_filename):
        if len(kernel_filename) == 0:
            return
        # make sure that we are in bootloader
        self.__append_cmd_to_queue("request_loader")
        # start upload
        self.__append_cmd_to_queue("image mram")
        self.__append_cmd_to_queue(f"mram_upload {kernel_filename} {toc_filename} {ota_app_filename} {user_filename}", True)

    def clear_mram(self):
        # make sure that we are in bootloader
        self.__append_cmd_to_queue("request_loader")
        # start clear
        self.__append_cmd_to_queue("image mram")
        self.__append_cmd_to_queue("clear_mram", True)

    def request_uart_loader(self):
        self.__append_cmd_to_queue("request_loader", True)

    def run_bootloader(self):
        return self.__run_cmd("init")

    def exit_bootloader(self, kernel_file):
        #import os
        #os.system("./reset_jtag.sh")
        #self.__run_cmd("image mram")
        #self.kernel_to_sram("../dist/ganymed_firmware_partition0.bin")
        self.kernel_to_sram(kernel_file)
        self.__append_cmd_to_queue("boot", True)

    @staticmethod
    def add_mram_header(priv, flashaddr, img):
        if len(img) % 16 != 0:
            remainder = 16 - len(img) % 16
            img.extend(bytearray(remainder))

        size = len(img)
        magic = 0x34030205
        addr = flashaddr + 0x10

        logger.debug(" ".join(['Build MRAM header']))
        logger.debug(" ".join(['Size:          ' + str(size)]))
        logger.debug(" ".join(['Header located at: 0x{:08X}'.format(flashaddr)]))
        logger.debug(" ".join(['Image located at: 0x{:08X}'.format(addr)]))
        data = bytearray()
        data.extend(magic.to_bytes(4, byteorder='little'))
        data.extend(addr.to_bytes(4, byteorder='little'))
        data.extend(size.to_bytes(4, byteorder='little'))
        data.extend(priv.to_bytes(4, byteorder='little'))
        logger.debug(" ".join([''.join(format(x, '02x') for x in data)]))

        data.extend(img)

        return data

    def __start_process_thread(self):
        # process thread
        self.process_thread = threading.Thread(
            target=self.__process, args=())
        self.process_thread.daemon = True
        self.process_thread.start()

    def __process(self):
        logger.debug(" ".join(["sy1xx loader process thread started"]))
        while True:
            c = self.send_queue.get(block=True, timeout=None)
            cmd = c.cmd

            logger.debug(" ".join(["proc cmd", cmd]))
            # magic command
            if cmd == "request_loader":
                # test if we are in loader mode
                if not self.__run_cmd("init-ex"):
                    # ask user to manually reset the target
                    self.__request_user_reset()
                    # wait for response from loader

                    while True:
                        try:
                            while not self.__run_cmd("init-ex"):
                                time.sleep(0.1)
                                self.__request_user_reset()
                            break
                        except:
                            logger.debug(" ".join(["reboot exception"]))
                            continue

                self.do_log("target uart_loader detected successfully")

                if c.done_callback:
                    if self.task_done_callback:
                        self.task_done_callback(cmd, True)
                continue

            result_code = False

            if self.__run_cmd(cmd):
                result_code = True
                self.do_log(f"execute cmd {cmd} success")
            else:
                self.do_log(f"execute cmd {cmd} failed")
                # also clear the rest of the queue
                while not self.send_queue.empty():
                    self.send_queue.get()

            self.send_queue.task_done()

            if c.done_callback:
                if self.task_done_callback:
                    self.task_done_callback(cmd, result_code)

    def is_queue_empty(self):
        return self.send_queue.empty()

    def __append_cmd_to_queue(self, cmd, callback=False):
        self.send_queue.put(Cmd(cmd, callback), block=True, timeout=None)

    def __on_receive(self, msg):
        # 0x5C | PAYLOAD-LEN | CMD |  PAYLOAD   | FCS
        #    0 |   1         |   2 | 3 ... n    | n + 1
        if self.debug_rx_tx:
            logger.debug(" ".join([f"bootloader > receive > {msg.hex(' ')}"]))

        # merge the last remainder with current new msg
        self.response_msg += msg[:]

        unused = bytearray()
        start_detected = False
        end_detected = False
        frame = bytearray()

        # find SOF that identifies a command response
        while len(self.response_msg) > 0:
            b = self.response_msg.pop(0)

            if b == bSOF:
                # found SOF, so we drop all unused
                if len(unused) > 0:
                    self.do_log(unused.decode())
                unused.clear()
                frame.clear()
                start_detected = True

            if not start_detected:
                unused.append(b)
                continue
            else:
                # add byte to frame
                frame.append(b)
                if len(frame) < 2:
                    # to check the length of frame, we need at least 2 bytes
                    continue

                # payload length is usually byte 1
                payload_len = frame[1]
                header_len = 3
                fcs_len = 1
                # there are defined payload lengths of 2 and 6
                if payload_len != 2 and payload_len != 6:
                    # invalid frame
                    start_detected = False
                    frame.clear()
                    self.do_log("invalid bytes received")
                    continue

                frame_len = header_len + payload_len + fcs_len
                if frame_len == len(frame):
                    self.__decode_frame(frame, frame_len)
                    # reset
                    start_detected = False
                    frame.clear()
                continue

        if len(unused) > 0:
            try:
                self.serial_log(unused.decode())
            except:
                pass

        # we detected all frames, if something is left over, we need to store
        self.response_msg = frame[:]

    def __decode_frame(self, frame, frame_len):
        # 0x5C | PAYLOAD-LEN | CMD |  PAYLOAD   | FCS
        #    0 |   1         |   2 | 3 ... n    | n + 1

        sof = frame[0]
        payload_len = frame[1]
        cmd = frame[2]
        fcs = frame[frame_len - 1]

        # compare fcs
        if fcs != ord(self.__get_fcs(frame[:frame_len-1])):
            self.do_log("invalid FCS")
            return

        if payload_len == 2:
            status = frame[3]
            error_code = frame[4]
            if error_code == 0:
                self.cmd_queue.put(cmd, block=True, timeout=None)
                # logger.debug(" ".join([f"[{CMD_RESPONSE[cmd]}] success [{CMD_RESPONSE_CODE[status]}]\n"]))
            else:
                logger.debug(" ".join([f"[{CMD_RESPONSE[cmd]}] error [{error_code}]\n"]))

        if payload_len == 6:
            status = frame[3]
            error_code = frame[4]
            slot_size = frame[5:8]
            if error_code == 0:
                self.cmd_queue.put(cmd, block=True, timeout=None)
                logger.debug(" ".join([f"[{CMD_RESPONSE[cmd]}] success [{CMD_RESPONSE_CODE[status]}]"]))
            else:
                logger.debug(" ".join([f"[{CMD_RESPONSE[cmd]}[ error [{error_code}]"]))

        return

    def __build_frame(self, cmd, data):
        ret = bytearray(b'\x5c')
        ret.append(len(data))
        ret.extend(bytearray(cmd))
        ret.extend(bytearray(data))
        ret.extend(self.__get_fcs(ret))
        return ret[:]

    def __decode(self, msg):
        try:
            return msg.decode()
        except:
            logger.debug(" ".join(["Error in decoding. Trying latin-1 instead of utf-8"]))
            try:
                return msg.decode("latin-1")
            except:
                return "Unable to decode message"

    def __get_fcs(self, frame):
        ret = 0
        for b in frame:
            ret = ret ^ b
        ret = bytes([ret])
        return ret

    def image(self, data, file):
        ftmp = open(file, "wb")
        ftmp.write(data)
        ftmp.close()

    def write_mram(self, data, image_offset, upload_chunk_size, upload_sleep_between_chunks, response_timeout):
        i = 0
        upload_sleep_between_chunks = 0
        total_len = len(data)
        while i < total_len:
            time.sleep(upload_sleep_between_chunks)
            offset = i + image_offset
            payload = bytearray(offset.to_bytes(4, byteorder='little'))

            payload.extend(data[i:min(i + upload_chunk_size, total_len)])

            bdata = self.__build_frame(b'\xC0', payload)
            if not self.__execute(bdata, 0xC1, response_timeout):
                return False
            i += upload_chunk_size
            self.do_log(f"progress {i} of {total_len} -- {i / total_len * 100:.2f}%")
        return True

    def __run_cmd(self, cmd):
        response_timeout = 0.1
        upload_sleep_between_chunks = 0.001
        upload_chunk_size = 192 # must be multiple of 8
        upload_debug = False

        cmd_tok = cmd.split(' ')
        cmd = cmd_tok[0]
        args = cmd_tok[1:]
        if cmd == 'write':
            self.__send((args[1]).encode())

        elif cmd == 'init':
            bdata = self.__build_frame(b'\xA0', b'')
            if not self.__execute(bdata, 0xA1, response_timeout):
                return False

        elif cmd == 'init-ex':
            bdata = self.__build_frame(b'\xA0', b'')
            if not self.__execute(bdata, 0xA1, response_timeout, suppress_logging=True):
                return False

        elif cmd == 'image':
            if len(args) == 1:
                image_type = args[0]
            else:
                self.do_log('> missing parameter; valid options: kernel, user, mram')
                return False

            if image_type == 'kernel':
                bdata = self.__build_frame(b'\xB0', b'\x01')
            elif image_type == 'user':
                bdata = self.__build_frame(b'\xB0', b'\x02')
            elif image_type == 'mram':
                bdata = self.__build_frame(b'\xB0', b'\x03')
            else:
                self.do_log('> unrecognized image parameter; valid options: kernel, user, mram')
                return False

            if not self.__execute(bdata, 0xB1, response_timeout):
                return False

        elif cmd == 'mram_upload':
            if len(args) == 4:
                kernel_filename = args[0]
                toc_filename = args[1]
                ota_app_filename = args[2]
                user_filename = args[3]
            else:
                self.do_log('> missing parameter; please specify filepath')
                return False

            # assume SEC_MRAM
            flash_addr = 0x1D100000

            data = bytearray()

            fh = open(kernel_filename, 'rb')
            kernel_img = bytearray(fh.read())
            fh.close()

            data += self.add_mram_header(0x01, flash_addr, kernel_img)
            #data += kernel_img
            total_len = len(data)

            output_mode = 0
            if output_mode == 0:
                i = 0
                total_len = len(data)
                while i < total_len:
                    time.sleep(upload_sleep_between_chunks)
                    payload = bytearray(i.to_bytes(4, byteorder='little'))

                    payload.extend(data[i:min(i+upload_chunk_size, total_len)])

                    bdata = self.__build_frame(b'\xC0', payload)
                    if not self.__execute(bdata, 0xC1, response_timeout):
                        return False
                    i += upload_chunk_size
                    self.do_log(f"progress {i} of {total_len} -- {i/total_len*100:.2f}%")

            #globl_mram_addr = 0x1E000000
            #global_mram_offset = total_len #globl_mram_addr - flash_addr
            #flash_addr = globl_mram_addr
            user_image_offset = total_len
            #data = bytearray()

            if len(toc_filename) > 0:
                fh = open(toc_filename, 'rb')
                toc_img = bytearray(fh.read())
                fh.close()
                data = toc_img
                toc_img_offset = 0
                self.write_mram(data, toc_img_offset, upload_chunk_size, upload_sleep_between_chunks, response_timeout)
            else:
                # create toc according to files
                toc_filename = ""

            max_forklift_size = 0x10000
            #
            # gap_length = max_forklift_size - total_len
            # erase_img = bytearray(b'\xFF') * gap_length
            # self.write_mram(erase_img, total_len, upload_chunk_size, upload_sleep_between_chunks, response_timeout)

            if len(ota_app_filename) > 0:
                fh = open(ota_app_filename, 'rb')
                ota_img = bytearray(fh.read())
                fh.close()

                data = ota_img

                secure_mram_addr = 0x1d100000
                global_mram_addr = 0x1e000000

                max_header_size = 0x100

                ota_img_offset = max_forklift_size + max_header_size

                self.write_mram(data, ota_img_offset, upload_chunk_size, upload_sleep_between_chunks, response_timeout)

            # add user image
            if len(user_filename) > 0:
                fh = open(user_filename, 'rb')
                user_img = bytearray(fh.read())
                fh.close()

                data = user_img

                # secure MRAM
                secure_mram_addr = 0x1d100000
                global_mram_addr = 0x1e000000
                max_header_size = 0x100

                user_image_offset = 0x80000

                # if ("ota" in json_file_name):
                #     addr = secure_mram_addr + max_forklift_size + max_header_size
                # else:
                #     addr = global_mram_addr + max_header_size

                self.write_mram(data, user_image_offset, upload_chunk_size, upload_sleep_between_chunks, response_timeout)

            self.do_log('> upload finished')
            self.do_log('NOTE:')
            self.do_log('--')
            self.do_log('-- after upgrading the kernel a hard reset is needed to load the new kernel')
            self.do_log('-- (only valid for MRAM upload)')
            self.do_log('--')

            self.__request_user_reset()

        elif cmd == 'clear_mram':
            size = (70*1024)
            data = bytearray(size)
            # bit-wise invert of bytearray
            for index in range(len(data)):
                data[index] = 0xFF

            i = 0
            total_len = len(data)
            while i < total_len:
                time.sleep(upload_sleep_between_chunks)
                payload = bytearray(i.to_bytes(4, byteorder='little'))

                payload.extend(data[i:min(i + upload_chunk_size, total_len)])

                bdata = self.__build_frame(b'\xC0', payload)
                if not self.__execute(bdata, 0xC1, response_timeout):
                    return False
                i += upload_chunk_size
                self.do_log(f"progress {i} of {total_len} -- {i/total_len*100:.2f}%")

            self.do_log("erase complete")

        elif cmd == 'upload':
            if len(args) == 1:
                filename = args[0]
            else:
                self.do_log('> missing parameter; please specify filepath')
                return False

            try:
                if filename == '-clear-':
                    data = bytearray(64 * 1024)
                    # bit-wise invert of bytearray
                    for index in range(len(data)):
                        data[index] = 0xFF
                else:
                    fh = open(filename, 'rb')
                    data = bytearray(fh.read())
                    fh.close()

                self.do_log('> uploading...')

                i = 0
                total_len = len(data)
                while i < total_len:
                    time.sleep(upload_sleep_between_chunks)
                    payload = bytearray(i.to_bytes(4, byteorder='little'))
                    if upload_debug:
                        logger.debug(" ".join(['[debug] payload offset: ', int.from_bytes(payload, byteorder='little', signed=False)]))
                    payload.extend(data[i:min(i + upload_chunk_size, total_len)])
                    if upload_debug:
                        logger.debug(" ".join(['[debug] payload size: ', len(payload)]))
                    bdata = self.__build_frame(b'\xC0', payload)
                    if not self.__execute(bdata, 0xC1, response_timeout):
                        return False
                    i += upload_chunk_size
                    self.do_log(f"progress {i} of {total_len} -- {i/total_len*100:.2f}%")

                self.do_log('> upload finished')
            except FileNotFoundError:
                self.do_log('> error: file not found: ' + filename)
            except Exception as e:
                self.do_log('> error: ', e)

        elif cmd == 'boot':
            bdata = self.__build_frame(b'\xD0', b'')
            if not self.__execute(bdata, 0xD1, response_timeout):
                return False

        elif cmd.split(' ', 1)[0] == 'uart':
            if len(cmd.split(' ', 1)) >= 2:
                params = cmd.split(' ', 1)[1]
            else:
                self.do_log('> missing parameter; valid option: 1 to n')
                return False

            bdata = self.__build_frame(b'\xD0', b'')
            for x in range(0, int(params)):
                self.__send(bdata)
                time.sleep(0.5)

        return True

    def __send(self, byte_data):
        try:
            if not self.serial_handler.is_connected():
                self.do_log("not connected")
                return
            if self.debug_rx_tx:
                logger.debug(" ".join([f"bootloader > send > {byte_data.hex(' ')}"]))
            self.serial_handler.send(byte_data, self.__on_receive, debug=False)
        except:
            print("error on write")

    def __execute(self, data, response, timeout, suppress_logging=False):
        while True:
            self.__send(data)
            try:
                res = self.cmd_queue.get(True, timeout)
                if res == response:
                    return True
                else:
                    self.do_log("cmd> invalid response")
                    return False
            except Empty as e:
                if not suppress_logging:
                    self.do_log("cmd> response timeout")
                return False

    def __request_user_reset(self):
        if self.callback_for_user_reset:
            self.callback_for_user_reset()
        self.do_log('NOTE:')
        self.do_log('--')
        self.do_log('-- request_loader -- please reset target now')
        self.do_log('--')
