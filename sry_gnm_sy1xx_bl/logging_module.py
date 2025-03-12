#
# Copyright (C) Sensry GmbH
# Maria-Reiche-Str. 1
# 01109 Dresden
#
# \author s.ginka@sensry.de
# \date 11.Feb.2023

import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s\t\t%(levelname)s\t\t%(message)s")
logger = logging.getLogger()
# logger.addHandler(logging.FileHandler('rocket_launcher.log', 'a'))