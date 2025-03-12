import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s\t\t%(levelname)s\t\t%(message)s")
logger = logging.getLogger()
# logger.addHandler(logging.FileHandler('rocket_launcher.log', 'a'))