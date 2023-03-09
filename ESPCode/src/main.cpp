#include "BiosensorsNetwork.h"
#include <MadForBees.h>

StaticJsonDocument<512> infoResponse;
StaticJsonDocument<48>  standardKitResponse;
StaticJsonDocument<64>  mqttPayload;

WiFiClient espClient;
PubSubClient mqttClient(espClient);

boolean managed = false;

void initInfo() {
	infoResponse["Version"] = VERSION;
	infoResponse["BNN"] = BNN;
	infoResponse["DeviceNumber"] = DEVICE_NUMBER;
	infoResponse["NetworkSize"] = N_SIZE;
	infoResponse["WifiSSID"] = WIFI_SSID;
	infoResponse["WifiPSW"] = WIFI_PSW;
	infoResponse["MqttServer"] = MQTT_SERVER;
	infoResponse["MqttPort"] = MQTT_PORT;
	infoResponse["MqttUser"] = BROKER_USERNAME;
	infoResponse["MqttPSW"] = BROKER_PSW;
	infoResponse["MqttPrefix"] = TOPIC_PREFIX;
	infoResponse["ConnectedWifi"] = false;
	infoResponse["ConnectedMqtt"] = false;
}

void debug(String msg) {
	if (DEBUG)
		Serial.println("[DEBUG] " + msg);
}

String readFromSerial() {
	String res = "";
	if (Serial.available())
		res = Serial.readStringUntil('\n');

	return res;
}

boolean isTimeout(long time, int timeout) {
	return (millis() - time) >= (timeout * 1000);
}

void sendJsonResponse(JsonVariantConst source) {
	serializeJson(source, Serial);
	Serial.println();
}

void setupWiFi() {
	long time = millis();
	debug("Connecting to WiFi...");
	delay(10);
	WiFi.mode(WIFI_STA);
	WiFi.begin(WIFI_SSID, WIFI_PSW);
	while (WiFi.status() != WL_CONNECTED) {
		delay(500);

		if (isTimeout(time, 20)) {
			Serial.println("WifiTimeout");
			return;
		}
	}
	infoResponse["ConnectedWifi"] = true;
	Serial.println("WifiConnected");
}

void setupMQTT() {
	mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
	mqttClient.setCallback(MQTTcallback);
	reconnectMQTT();
}


void reconnectMQTT() {
	infoResponse["ConnectedMqtt"] = false;

	long time = millis();

	debug("Connecting to MQTT...");
	String clientId = String(BNN) + "_" + String(DEVICE_NUMBER);
	while (!mqttClient.connected()) {
		if (!mqttClient.connect(clientId.c_str(), BROKER_USERNAME, BROKER_PSW)) {
			Serial.println("MQTT Error code: " + String(mqttClient.state()));
			delay(5000);
			if (isTimeout(time, 30)) {
				Serial.println("MqttTimeout");
				return;
			}
		}
	}
	infoResponse["ConnectedMqtt"] = true;
	Serial.println("MqttConnected!");
	String cmd = topic(CMD_TOPIC);
	mqttClient.subscribe(cmd.c_str());
	debug("Subscribed to " + cmd);
}

void MQTTcallback(const char* topic, byte* payload, unsigned int length) {

	// Sample cmd: 1_getInfo

	String payloadString = "";

	for (unsigned int i = 0; i < length; i++)
		payloadString += (char) payload[i];

	debug(payloadString);
	unsigned int position = payloadString.indexOf('_');

	String device_n = "";
	for (unsigned int i = 0; i < position; i++) {
		device_n += (char) payload[i];
	}

	if (device_n == String(DEVICE_NUMBER))
		run(payloadString.substring(position));
}

String topic(String s) {
	return String(TOPIC_PREFIX) + s;
}

void run(String cmd) {
	if (cmd.compareTo("") == 0)
		return;

	if (cmd.compareTo("echo") == 0)
		Serial.println("UP!");
	else if (cmd.compareTo("connectWifi") == 0)
		setupWiFi();
	else if (cmd.compareTo("connectMqtt") == 0)
		setupMQTT();
	else if (cmd.compareTo("getInfo") == 0)
		sendJsonResponse(infoResponse);
	else
		debug("Unknown command: " + cmd);

}


void setup() {
	Serial.begin(9600);
	debug("DEBUG MODE IS ON!");

	long startTime = millis();

	while (!isTimeout(startTime, 20))
		if (readFromSerial().compareTo("managedMode") == 0) {
			debug("managedMode setted");
			managed = true;
			break;
		}

	initInfo();
	if (!managed) {
		debug("managedMode is not setted, setting up...");
		setupWiFi();
		setupMQTT();
	}

}

void loop() {
	run(readFromSerial());
	if (!managed) {
		if (WiFi.status() == WL_CONNECTED) {
			// Main loop per scambio dati

			// Se perde la connessione ad MQTT ma è ancora connesso al WiFi
			if (!mqttClient.connected())
				reconnectMQTT();
			else
				mqttClient.loop();
		}
		else {
			infoResponse["ConnectedWifi"] = false;
			infoResponse["ConnectedMqtt"] = false;
		}
	}
}

