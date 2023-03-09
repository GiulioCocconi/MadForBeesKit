#ifndef MFB_H
#define MFB_H

#include <Arduino.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP8266WiFi.h>

#ifndef DEBUG
	#define DEBUG 0
#endif

#ifndef DEVICE_NUMBER
	#define DEVICE_NUMBER 1
	#warning "DEVICE_NUMBER not defined (assuming 1)"
#endif

#ifndef MQTT_SERVER
	#define MQTT_SERVER "maqiatto.com"
	#define MQTT_PORT 1883
#endif

#define VERSION "0.1"

#define BAUDRATE 9600

#define CMD_TOPIC "cmd"

void init();

void setupWiFi();

void setupMQTT();
void reconnectMQTT();
void MQTTcallback(const char* topic, byte* payload, unsigned int length);
String topic(String s);

String readFromSerial();
void sendJsonResponse(JsonVariantConst source);

void run(String cmd);
void info(boolean onSerial);

void debug(String msg);


#endif
