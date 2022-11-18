"""! @brief Main entry point"""


import logging
from mqtt import mqtt
from audio import audio

logging.basicConfig(level=logging.DEBUG)

def main():
    """! Main entry point"""

    logging.info("Booting")
    mqtt.init()
    audio.init()
    while True:
        audio.loop()

main()
