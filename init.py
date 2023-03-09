from enum import IntEnum
import os
import sys
import shutil
import subprocess

import json
import tomlkit
import paho.mqtt.client as mqtt

import serial
import serial.tools.list_ports

import pprint
import time

DEBUG = True

EMAIL_BUGREPORT = "coccogiulio8@gmail.com"

KIT_DIR = os.getcwd()
PIO_DIR = "ESPCode"

HEADER_FILENAME = "BiosensorsNetwork.h"
PIO_HEADER_FILE = os.path.join(PIO_DIR, "include", HEADER_FILENAME)

CONFIG_FILENAME = "config.toml"

class Error(IntEnum):
    BROKER_CONNECTION = 1
    INTERNET_CONNECTION = 2
    WIFI_CONNECTION = 3
    CONFIG_CORRUPTED = 4
    ESP_NOT_DETECTED = 5
    UPLOAD_TO_ESP = 6
    ESP_WIFI = 7
    ESP_MQTT = 8



def myExit(status):
    status = int(status)

    print()
    print("Thank you for using MadForBees")

    if status != 0 or DEBUG:
        print("Please report any bug to " + EMAIL_BUGREPORT)

    sys.exit(status)


def debug(msg):
    if DEBUG:
        print("[DEBUG] " + str(msg))
        print()


def serialReceive(s):
    res = s.read_until();
    msg = res.decode("ascii").strip()
    debug("Serial message recived: " + msg)
    if msg[0] == "[":
        return serialReceive(s)
    return msg

def detectEsp():
    serialList = serial.tools.list_ports.comports(include_links=False)

    if len(serialList) == 0:
        print("ESP not detected!")
        myExit(Error.ESP_NOT_DETECTED)

    if len(serialList) > 1:
        print("Warning: More than one device is connected (selecting first)!")
        debug(serialList)

    return serialList[0].device


#TODO: Rendere il sistema potenzialmente indipendente da maqiatto.

class MQTTBroker():
    def __init__(self, username, psw, BNN):
        self.username = username
        self.psw = psw
        self.topicPrefix = f"{self.username}/{BNN}/" # Bisogna sempre mettere / alla fine
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, password=self.psw)

    def dump(self):
        print("Broker config dump:")
        print()
        print("Username: " + self.username)
        print("Password: " + self.psw)
        print()

    def checkConnection(self):
        try:
            self.client.connect("maqiatto.com")
        except Exception as e:
            if DEBUG:
                print(e)
            print("The script couldn't establish a connection to the broker")
            print("Check your internet connection")
            myExit(Error.INTERNET_CONNECTION)

    def checkForTopics(self, size): # TODO: THIS FUNCTION IS NOT USED IN THIS VERSION. (BUG PAHO?)
        for i in range(1, size+1):
            topicName = self.topicPrefix + str(i)
            debug("Testing for topic " + topicName)

            status, _ = self.client.subscribe(topicName)

            if status != 0:
                if DEBUG:
                    print("Status " + str(status))
                    print("The script couldn't establish a connection to topic " + str(i))
                    print("Check your broker config and the credentials provided")
                    myExit(Error.BROKER_CONNECTION)

class Config():
    def __init__(self):
        self.name = ""

        self.configFileName = ""
        self.headerFileName = ""

        self.size = 0
        self.broker = None
        self.wifiSSID = ""
        self.wifiPSW = ""

    def newConfig(self, BNN, size, broker, wifiSSID, wifiPSW):
        self.setNames(BNN)
        self.size = size
        self.broker = broker
        self.wifiSSID = wifiSSID
        self.wifiPSW = wifiPSW
        return self

    def setNames(self, BNN):
        self.name = BNN
        self.configFileName = os.path.join(BNN, CONFIG_FILENAME)
        self.headerFileName = os.path.join(BNN, HEADER_FILENAME)

    def readFromFile(self, BNN):
        # TODO: CONSIDERARE L'UTILIZZO DI JSON ANCHE PER IL FILE DI CONFIGURAZIONE
        self.setNames(BNN)
        if not os.path.exists(self.configFileName):
            if not os.path.exists(BNN):
                return None
            else:
                print(f"Config for {BNN} is corrupted!")
                print("You can try to save it looking at the folder named as the BNN")
                myExit(Error.CONFIG_CORRUPTED)

        file = open(self.configFileName, "r")
        configContent = file.read()
        file.close()

        configFile = tomlkit.parse(configContent)

        self.name = BNN
        self.size = configFile["Network"]["size"]
        self.wifiSSID = configFile["WIFI"]["SSID"]
        self.wifiPSW = configFile["WIFI"]["password"]

        brokerUsername = configFile["MQTT"]["username"]
        brokerPSW = configFile["MQTT"]["password"]

        self.broker = MQTTBroker(brokerUsername, brokerPSW, BNN);

        return self

    def readFromDevice(self):
        input("Connect a biosensor and press enter...")
        currentEsp = detectEsp()
        debug("currentEsp: " + currentEsp)

        s = serial.Serial(port=currentEsp)
        s.write(b"getInfo\n")
        response = serialReceive(s)

        configJson = json.loads(response)
        pprint.PrettyPrinter().pprint(configJson)
        print()

        self.setNames(configJson["BNN"])
        self.size = configJson["NetworkSize"]
        self.wifiSSID = configJson["WifiSSID"]
        self.wifiPSW = configJson["WifiPSW"]
        self.broker = MQTTBroker(configJson["MqttUser"], configJson["MqttPSW"], self.name)

        return self

    def write(self):
        networkTable = tomlkit.table()
        wifiTable = tomlkit.table()
        mqttTable = tomlkit.table()

        networkTable.add("size", self.size)

        wifiTable.add("SSID", self.wifiSSID)
        wifiTable.add("password", self.wifiPSW)

        mqttTable.add("username", self.broker.username)
        mqttTable.add("password", self.broker.psw)

        configFile = tomlkit.document()
        configFile.add("Network", networkTable)
        configFile.add("WIFI", wifiTable)
        configFile.add("MQTT", mqttTable)

        if not os.path.exists(self.name):
           os.mkdir(self.name)

        if os.path.exists(self.configFileName):
            choice = input("Found a config with the same name. Overwrite it [y/N]? ")
            if not (choice.lower() == "y"):
                return
            else:
                print("Overwritten with new config!")

        file = open(self.configFileName, "w")
        file.write(tomlkit.dumps(configFile))
        file.close()


    def generateHeader(self):
        if os.path.exists(self.headerFileName):
            os.remove(self.headerFileName)
            print("Regenerating header file...")
        else:
            print("Generating header file from config...")

        file = open(self.headerFileName, "w")
        file.writelines([
            "#ifndef BN_H\n",
            "#define BN_H\n\n",
            f"#define BNN \"{self.name}\"\n",
            f"#define N_SIZE {self.size}\n\n",
            f"#define WIFI_SSID \"{self.wifiSSID}\"\n",
            f"#define WIFI_PSW \"{self.wifiPSW}\"\n\n",
            f"#define BROKER_USERNAME \"{self.broker.username}\"\n",
            f"#define BROKER_PSW \"{self.broker.psw}\"\n",
            f"#define TOPIC_PREFIX \"{self.broker.topicPrefix}\"\n\n"
            "#endif"])

        file.close()
        print("Header file generated!")

    def setupNetwork(self):
        # SOSTITUISCE IL FILE HEADER DI DEFAULT CON QUELLO DELLA CONFIGURAZIONE CORRENTE
        print("Setting header file...")
        self.generateHeader()
        shutil.copyfile(self.headerFileName, PIO_HEADER_FILE)
        os.chdir(PIO_DIR)

        choice = input("Is the chosen wifi network available here? [y/N]? ")

        for i in range(1, self.size + 1):
            input(f"Please insert biosensor #{str(i)} and press enter...")

            currentEsp = detectEsp()
            s = serial.Serial(port=currentEsp)

            debug("CURRENT ESP: " + currentEsp)

            # SETTA LA VARIABILE PER IL DEFINE DEL NUMERO DEVICE
            print()
            print("Setting ENV VARS...")
            os.environ["PLATFORMIO_BUILD_FLAGS"] = f"-DDEVICE_NUMBER={str(i)}"

            print("Starting upload...")

            #TODO: TESTARE PER WINDOWS
            processList = ["pio", "run", "-t", "upload"]
            if DEBUG:
                processList += ["-e", "debug"]

            compileProcess = subprocess.run(processList)
            compileStatus = compileProcess.returncode
            debug("Compile returncode: " + str(compileStatus))

            if compileStatus != 0:
                print("There was an unexpected error uploading the code to the ESP...")
                myExit(Error.UPLOAD_TO_ESP)

            print("UPLOAD DONE!")
            print()

            # TODO: Fare check per avvenuta connessione a wifi e a broker (tramite serial)
            #       se ci sono errori allora stampa messaggio ed esci
            #
            if (choice.lower() == "y"):
                print("Checking biosensor connection...")
                time.sleep(2)
                debug("Setting managed mode...")
                s.write(b"managedMode\n")

                debug("Connecting to wifi...")
                s.write(b"connectWifi\n")

                resp = serialReceive(s)

                while resp != "WifiConnected":
                    if resp == "WifiTimeout":
                        print("Your wireless credentials are wrong, please fix the config")
                        myExit(Error.ESP_WIFI)
                    resp = serialReceive(s)

                debug("Check broker")
                s.write(b"connectMqtt\n")

                resp = serialReceive(s)

                while resp != "MqttConnected":
                    if resp == "MqttTimeout":
                        print("Your wireless credentials are wrong, please fix the config")
                        myExit(Error.ESP_MQTT)
                    resp = serialReceive(s)




        os.chdir(KIT_DIR)
        print("All biosensors have been programmed!")

    def dump(self):
        print(self.name + " config dump:")
        print()
        print("Size: " + str(self.size))
        print("WIFI SSID: " + self.wifiSSID)
        print("WIFI password: " + self.wifiPSW)
        print()
        self.broker.dump()

    def delete(self):
        if os.path.isdir(self.name):
            shutil.rmtree(self.name)
        print(self.name + " network configuration is now deleted")

    def exit(self):
        pass


def checkUpdates():
    pass


def setupNewBN(BNN):
    config = Config().readFromFile(BNN)

    if (config != None):
        print()
        print("You've already configured a network called " + BNN);
        print()
        config.dump()

        choice = input("Would you like to reconfigure your devices [Y/n]? ")
        print()

        if (choice.lower() == "n"):
            myExit(0)
        else:
            config.setupNetwork()
            myExit(0)


    bNumber = int(input("Please input the number of biosensors: "))

    BROKER_USERNAME = input("Please input your MQTT Username: ")
    BROKER_PSW = input("Please input your MQTT Password: ")

    broker = MQTTBroker(BROKER_USERNAME, BROKER_PSW, BNN)

    WIFI_SSID = input("Please input WiFi SSID: ")
    WIFI_PSW = input("Please input WiFi Password: ")
    print()

    config = Config().newConfig(BNN, bNumber, broker, WIFI_SSID, WIFI_PSW)
    config.write()
    config.setupNetwork()

    myExit(0)

def choose():
    choice = -1
    while not (choice >= 0 and choice <= 2):
        print("What would you like to do?")
        print("1] Setup a new network")
        print("2] Read config from an existing network")
        print("0] Exit")
        try:
            choice = int(input("Your choice: "))
        except Exception as e:
            debug(e)
            choice = -1
        except:
            myExit(0)
    print()
    return choice


if __name__ == "__main__":
    print("Welcome! Using this script you'll be able to manage your MadForBees Networks ;)")

    try:
        os.chdir(os.path.dirname(sys.argv[0]))
    except Exception:
        pass

    choice = choose()

    if choice == 0:
        myExit(0)

    checkUpdates()

    if choice == 1:
        BNN = input("Please input the desired BNN: ")
        setupNewBN(BNN)


    if choice == 2:
        config = Config().readFromDevice()

        choice = input("Would you like to export it [Y/n]? ")

        if  choice.lower() == "n":
            myExit(0)

        config.write()


