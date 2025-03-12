#
# Copyright (C) Sensry GmbH
# Maria-Reiche-Str. 1
# 01109 Dresden
#
# \author s.ginka@sensry.de
# \date 11.Feb.2023

import argparse
import json
import binascii
from array import array

poly = 0xEDB88320

table = array('L')
for byte in range(256):
    crc = 0
    for bit in range(8):
        if (byte ^ crc) & 1:
            crc = (crc >> 1) ^ poly
        else:
            crc >>= 1
        byte >>= 1
    table.append(crc)


def crc32(string):
    value = 0xffffffff
    for ch in string:
        value = table[(ord(ch) ^ value) & 0xff] ^ (value >> 8)

    return -1 - value


def get_storage_location():
    # secure MRAM
    secure_mram_addr = 0x1d100000
    max_forklift_size = 0x10000
    max_header_size = 0x100

    addr = secure_mram_addr + max_forklift_size + max_header_size
    return addr


def get_global_sram_location():
    return 0x1c010000


def add_header(json_file_name, binary_array):

    if len(binary_array) % 4 != 0:
        remainder = 4 - len(binary_array) % 4
        binary_array.extend(bytearray(remainder))

    size = len(binary_array)

    # set configuration values
    headerMagic = 0x34030205
    headerVersion = 0x00000012
    headerSize = 256

    platformType = 1
    storageLocation = get_storage_location()

    binaryCompressionType = 0
    binarySize = size
    binaryCrc = binascii.crc32(binary_array)
    binaryValidationMarkerAddress = 0x080

    versionStr = bytearray(64)

    execFlags = 0x01
    executionLocation = get_global_sram_location()
    executionEntryPointOffset = 0x00

    reservedSpace = bytearray(140)

    headerCrc = 0

    # build header
    header = bytearray()
    header.extend(headerMagic.to_bytes(4, byteorder = 'little'))
    header.extend(headerVersion.to_bytes(4, byteorder = 'little'))
    header.extend(headerSize.to_bytes(4, byteorder = 'little'))

    header.extend(platformType.to_bytes(4, byteorder = 'little'))
    header.extend(storageLocation.to_bytes(4, byteorder = 'little'))

    header.extend(binaryCompressionType.to_bytes(4, byteorder = 'little'))
    header.extend(binarySize.to_bytes(4, byteorder = 'little'))
    header.extend(binaryCrc.to_bytes(4, byteorder = 'little'))
    header.extend(binaryValidationMarkerAddress.to_bytes(4, byteorder = 'little'))

    header.extend(versionStr)

    header.extend(execFlags.to_bytes(4, byteorder = 'little'))
    header.extend(executionLocation.to_bytes(4, byteorder = 'little'))
    header.extend(executionEntryPointOffset.to_bytes(4, byteorder = 'little'))

    header.extend(reservedSpace)

    headerCrc = binascii.crc32(header)
    header.extend(headerCrc.to_bytes(4, byteorder = 'little'))

    image = header
    image.extend(binary_array)

    # extend binary to multiple of 16
    if len(image) % 16 != 0:
        remainder = 16 - len(image) % 16
        image.extend(bytearray(remainder))

    if json_file_name is not None:
        j = {
            "headerMagic": headerMagic,
            "headerVersion": headerVersion,
            "headerSize": headerSize,
            "platformType": platformType,
            "storageLocation": storageLocation,

            "binaryCompressionType": binaryCompressionType,
            "binarySize": binarySize,
            "binaryCrc": binaryCrc,
            "binaryValidationMarkerAddress": binaryValidationMarkerAddress,
            "versionStr": "",

            "execFlags": execFlags,
            "executionLocation": executionLocation,
            "binaryEntryPointOffset": executionEntryPointOffset,

            "headerCrc": headerCrc
        }

        print(f"writing meta data to [{json_file_name}]")
        with open(json_file_name, 'w') as f:
            json.dump(j, f, indent=2)
    else:
        print("no json meta data file given")

    return image


parser = argparse.ArgumentParser()

parser.add_argument("-b", "--binary", dest="binary_file", required=True, help="path to binary file")
parser.add_argument("-o", "--output", dest="output_file", required=True, help="path to image output file")
parser.add_argument("-j", "--json", dest="json_file", required=False, help="path to meta data json file")


def generate_ganymed_image(binary_file, output_file, json_file):

    print("---generating ganymed image---")
    file_name = binary_file
    print(f"source file [{file_name}]")
    fh = open(file_name, 'rb')
    binary = bytearray(fh.read())
    fh.close()

    print(f"binary file loaded, size {len(binary)} bytes")

    json_file_name = json_file
    binary = add_header(json_file_name, binary)

    output_file_name = output_file
    print(f"destination file [{output_file_name}]")
    nf = open(output_file_name, 'wb')
    nf.write(binary)
    nf.close()

    print(f"new ganymed image with header created [{output_file_name}]")

