from paho.mqtt import client as mqtt_client
from pydub import AudioSegment
from pydub.playback import play

import queue
import os
import json
import logging
import ssl

logging.basicConfig(level=logging.DEBUG)

root = os.path.dirname(__file__)

audioqueue = queue.Queue()

directories = []
audiofiles = {}

audiocounters = {}
audiocount = {}


broker = os.getenv("MQTT_BROKER")
port = os.getenv("MQTT_PORT")
client_id = 'audioplayer'
username = os.getenv("MQTT_USERNAME")
password = os.getenv("MQTT_PASSWORD")

connected = False
client = None

for option in os.listdir("{}/media".format(root)):
    if option[:1] == ".":
        continue
    if os.path.isdir("{}/media/{}".format(root, option)):
        directories.append(option)

for dir in directories:
    hasWave = False
    audiofiles[dir] = []
    for option in os.listdir("{}/media/{}".format(root, dir)):
        if option[-4:] == ".wav":
            hasWave = True
            audiofiles[dir].append("{}/media/{}/{}".format(root, dir, option))
    if not hasWave:
        del(audiofiles[dir])
    else:
        audiocount[dir] = len(audiofiles[dir])
        audiocounters[dir] = 0


def play_file(filename, filetype, left, right):
    logging.info("Playing file {}".format(filename))
    if left and right:
        platform = 0
    elif left:
        platform = 1
    elif right:
        platform = 2
    client.publish("signalling/audio/playing", prep_payload({"file": filename, "audio": filetype, "platform": platform}))
    file = AudioSegment.from_file(filename)

    if (file.channels == 2):
        file, _ = file[:len(file)].split_to_mono()

    silent = AudioSegment.silent(len(file), frame_rate=file.frame_rate)
    if left and right:
        new = AudioSegment.from_mono_audiosegments(file[:len(file)], file[:len(file)])
    elif left:
        new = AudioSegment.from_mono_audiosegments(file[:len(file)], silent)
    elif right:
        new = AudioSegment.from_mono_audiosegments(silent, file[:len(file)])
    else:
        return
    play(new)
    client.publish("signalling/audio/played", prep_payload({"file": filename, "audio": filetype, "platform": platform}))
    logging.info("Finished playing {}".format(filename))

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.debug("Connected to MQTT Broker!")
        global connected
        connected = True
    else:
        logging.debug("Failed to connect, return code %d\n", rc)

def connect_mqtt():
    # Set Connecting Client ID
    global client
    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.connect(broker, port)
    client.on_message = on_message
    return client

def on_message(client, userdata, message):
    outermessage = json.loads(message.payload.decode("utf-8"))
    try:
        payload = outermessage['payload']
        platform = payload['platform']
        audio = payload['audio']
    except KeyError:
        # Invalid message
        logging.debug("Invalid message: {}".format(message.payload))
        return

    left = False
    right = False
    audiofile = ""
    if platform == 0:
        # Play on both platforms
        left = True
        right = True
    elif platform == 1:
        # Just platform 1
        left = True
    elif platform == 2:
        # Just platform 2
        right = True
    else:
        # Invalid platform selection
        return
    
    # Check it is a valid sound
    try:
        audiofiles[audio]
    except KeyError:
        # Invalid audio file
        logging.debug("Invalid audio file requested: {}".format(audio))
        return
    currentIndex = audiocounters[audio]
    filename = audiofiles[audio][currentIndex]

    audioqueue.put((filename, audio, left, right))

    audiocounters[audio] = (currentIndex + 1) % audiocount[audio]

def prep_payload(input):
    payload = {
        "username": "system",
        "source": "audioplayer",
        "payload": input
    }
    return json.dumps(payload)

def main():
    logging.info("Booting")

    logging.info("Connecting to MQTT")
    client = connect_mqtt()
    client.loop_start()
    while not connected:
        pass
    logging.info("Connected")
    client.subscribe("signalling/audio/play")
    while True:
        if not audioqueue.empty():
            filename, filetype, left, right = audioqueue.get()
            play_file(filename, filetype, left, right)

main()