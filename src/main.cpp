#include <M5Unified.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <ESPmDNS.h>
#include <SPIFFS.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Web server port
AsyncWebServer server(80);

// Structure to hold configuration
struct Config {
  char wifi_ssid[32] = "";
  char wifi_password[64] = "";
  char mqtt_server[64] = "";
  int mqtt_port = 1883;
  char mqtt_user[32] = "";
  char mqtt_password[64] = "";
  char mqtt_client_id[32] = "M5AtomS3Vibration";
  char hostname[32] = "tresor.lab";
  float gyro_threshold = 0.5;
  float min_activity_threshold = 0.2;
  int debounce_time = 1000;
};

Config config;

// MQTT client
WiFiClient espClient;
PubSubClient client(espClient);

// MQTT topics
const char* topic_bubbles = "homeassistant/sensor/fermentation_bubbles";
const char* topic_temp1 = "homeassistant/sensor/temperature_1";
const char* topic_temp2 = "homeassistant/sensor/temperature_2";
const char* topic_sensitivity = "homeassistant/sensor/fermentation_sensitivity";
const char* topic_min_threshold = "homeassistant/sensor/fermentation_min_threshold";
const char* topic_debounce_time = "homeassistant/sensor/fermentation_debounce_time";

// ===== DS18B20 TEMPERATURE SENSORS =====
#define ONE_WIRE_BUS 2  // Pin for OneWire data bus
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// ===== VIBRATION DETECTION CONFIGURATION =====
int bubbleCount = 0;
unsigned long lastSendTime = 0;
const int sendInterval = 60000;       // Send data every minute (60000ms)
unsigned long lastDetectionTime = 0;  // For debouncing

// Bubble history data storage
const int MAX_HISTORY = 60; // Store 60 data points
int bubbleHistory[MAX_HISTORY];
float tempHistory1[MAX_HISTORY];
float tempHistory2[MAX_HISTORY];
int historyIndex = 0;

// Variables for improved detection
const int SAMPLES = 10;
float gyroReadings[3][SAMPLES];
int readingIndex = 0;

// Flag to indicate if we're in AP mode (for initial setup)
bool apMode = false;

void setup() {
  // Initialize M5Stack
  M5.begin();
  Serial.begin(115200);
  
  // Initialize IMU
  if (M5.imu.begin()) {
    Serial.println("IMU initialized successfully");
  } else {
    Serial.println("Failed to initialize IMU!");
  }
  
  // Set display brightness
  if (M5.Display.getBoard() != m5::board_t::board_unknown) {
    M5.Display.setBrightness(100);
  }
  
  // Clear the display
  M5.Display.clear();
  displayStatus("Booting...", GREEN);
  
  // Initialize SPIFFS
  if (!SPIFFS.begin(true)) {
    Serial.println("An error occurred while mounting SPIFFS");
    displayStatus("SPIFFS Error", RED);
    delay(3000);
  }
  
  // Initialize sensors
  sensors.begin();
  
  // Load saved configuration
  if (!loadConfiguration()) {
    // If no configuration found, start in AP mode
    startAPMode();
  } else {
    // Try to connect to saved WiFi
    connectToWifi();
    
    // If connection fails, start in AP mode
    if (WiFi.status() != WL_CONNECTED) {
      startAPMode();
    } else {
      // Set up normal operation
      setupMDNS();
      setupMQTT();
      setupWebServer();
      
      // Initialize bubble history arrays
      for (int i = 0; i < MAX_HISTORY; i++) {
        bubbleHistory[i] = 0;
        tempHistory1[i] = 0;
        tempHistory2[i] = 0;
      }
      
      displayStatus("Ready!", GREEN);
      delay(1000);
      displayConnectionStatus();
    }
  }
}

void loop() {
  // Update button state
  M5.update();
  
  if (!apMode) {
    // Only run main monitoring code when not in AP mode
    
    // Check WiFi and MQTT connections
    if (WiFi.status() != WL_CONNECTED) {
      connectToWifi();
    }
    
    if (!client.connected() && WiFi.status() == WL_CONNECTED) {
      reconnectMQTT();
    }
    
    client.loop();
    
    // Get gyroscope data
    float gyroX = 0, gyroY = 0, gyroZ = 0;
    
    if (M5.imu.getGyroData(&gyroX, &gyroY, &gyroZ) == 0) {
      // Store current reading in the circular buffer
      gyroReadings[0][readingIndex] = gyroX;
      gyroReadings[1][readingIndex] = gyroY;
      gyroReadings[2][readingIndex] = gyroZ;
      readingIndex = (readingIndex + 1) % SAMPLES;
      
      // Calculate running averages to smooth out noise
      float avgX = 0, avgY = 0, avgZ = 0;
      for (int i = 0; i < SAMPLES; i++) {
        avgX += gyroReadings[0][i] / SAMPLES;
        avgY += gyroReadings[1][i] / SAMPLES;
        avgZ += gyroReadings[2][i] / SAMPLES;
      }
      
      // Calculate magnitude
      float magnitude = sqrt(avgX*avgX + avgY*avgY + avgZ*avgZ);
      
      // Apply both thresholds
      float effectiveThreshold = max(config.gyro_threshold, config.min_activity_threshold);
      
      // Check for vibration
      unsigned long currentTime = millis();
      if (magnitude > effectiveThreshold && 
          (currentTime - lastDetectionTime > config.debounce_time)) {
        
        bubbleCount++;
        Serial.printf("Vibration detected! Magnitude: %.2f (Threshold: %.2f)\n", 
                     magnitude, effectiveThreshold);
        showBubbleAnimation();
        
        lastDetectionTime = currentTime;
      }
    }
    
    // Send data at regular intervals
    unsigned long currentTime = millis();
    if (currentTime - lastSendTime > sendInterval) {
      sendMQTT();
      updateHistory();
      bubbleCount = 0;
      lastSendTime = currentTime;
      
      displayConnectionStatus();
    }
  }
}

// Start in Access Point mode for initial setup
void startAPMode() {
  apMode = true;
  
  // Set up access point
  WiFi.mode(WIFI_AP);
  WiFi.softAP("Laboratoire Tresor Setup", "treasurelab");
  
  displayStatus("AP Mode", YELLOW);
  Serial.println("AP Mode Started");
  Serial.print("IP address: ");
  Serial.println(WiFi.softAPIP());
  
  // Display AP info
  M5.Display.clear();
  M5.Display.setTextSize(1);
  M5.Display.setTextColor(YELLOW);
  M5.Display.setCursor(5, 10);
  M5.Display.println("Laboratoire Tresor");
  M5.Display.setCursor(5, 30);
  M5.Display.println("Connect to WiFi:");
  M5.Display.setCursor(5, 45);
  M5.Display.println("Laboratoire Tresor Setup");
  M5.Display.setCursor(5, 60);
  M5.Display.println("Password: treasurelab");
  M5.Display.setCursor(5, 75);
  M5.Display.println("Then open: 192.168.4.1");
  
  // Setup web server for configuration
  setupConfigWebServer();
}

// Setup the configuration web server (AP mode)
void setupConfigWebServer() {
  // Serve the configuration page
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/config.html", "text/html");
  });
  
  // Handle configuration submission
  server.on("/save-config", HTTP_POST, [](AsyncWebServerRequest *request) {
    // Process form data
    if (request->hasParam("wifi_ssid", true)) {
      strncpy(config.wifi_ssid, request->getParam("wifi_ssid", true)->value().c_str(), sizeof(config.wifi_ssid) - 1);
    }
    
    if (request->hasParam("wifi_password", true)) {
      strncpy(config.wifi_password, request->getParam("wifi_password", true)->value().c_str(), sizeof(config.wifi_password) - 1);
    }
    
    if (request->hasParam("mqtt_server", true)) {
      strncpy(config.mqtt_server, request->getParam("mqtt_server", true)->value().c_str(), sizeof(config.mqtt_server) - 1);
    }
    
    if (request->hasParam("mqtt_port", true)) {
      config.mqtt_port = request->getParam("mqtt_port", true)->value().toInt();
    }
    
    if (request->hasParam("mqtt_user", true)) {
      strncpy(config.mqtt_user, request->getParam("mqtt_user", true)->value().c_str(), sizeof(config.mqtt_user) - 1);
    }
    
    if (request->hasParam("mqtt_password", true)) {
      strncpy(config.mqtt_password, request->getParam("mqtt_password", true)->value().c_str(), sizeof(config.mqtt_password) - 1);
    }
    
    if (request->hasParam("hostname", true)) {
      strncpy(config.hostname, request->getParam("hostname", true)->value().c_str(), sizeof(config.hostname) - 1);
    }
    
    if (request->hasParam("mqtt_client_id", true)) {
      strncpy(config.mqtt_client_id, request->getParam("mqtt_client_id", true)->value().c_str(), sizeof(config.mqtt_client_id) - 1);
    }
    
    // Save configuration to file
    saveConfiguration();
    
    // Send response
    request->send(200, "text/plain", "Configuration saved. Rebooting...");
    
    // Delay to allow response to be sent
    delay(1000);
    
    // Restart the device
    ESP.restart();
  });
  
  // Serve CSS and JS files
  server.on("/style.css", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/style.css", "text/css");
  });
  
  server.on("/script.js", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/script.js", "application/javascript");
  });
  
  // Start server
  server.begin();
}

// Setup the normal web server (connected mode)
void setupWebServer() {
  // Main dashboard
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/dashboard.html", "text/html");
  });
  
  // Configuration page
  server.on("/config", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/settings.html", "text/html");
  });
  
  // Get current configuration as JSON
  server.on("/api/config", HTTP_GET, [](AsyncWebServerRequest *request) {
    String jsonResponse;
    DynamicJsonDocument doc(1024);
    
    doc["wifi_ssid"] = config.wifi_ssid;
    // Don't send the WiFi password for security
    doc["mqtt_server"] = config.mqtt_server;
    doc["mqtt_port"] = config.mqtt_port;
    doc["mqtt_user"] = config.mqtt_user;
    // Don't send the MQTT password for security
    doc["mqtt_client_id"] = config.mqtt_client_id;
    doc["hostname"] = config.hostname;
    doc["gyro_threshold"] = config.gyro_threshold;
    doc["min_activity_threshold"] = config.min_activity_threshold;
    doc["debounce_time"] = config.debounce_time;
    
    serializeJson(doc, jsonResponse);
    request->send(200, "application/json", jsonResponse);
  });
  
  // Get current status as JSON
  server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest *request) {
    String jsonResponse;
    DynamicJsonDocument doc(1024);
    
    doc["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
    doc["mqtt_connected"] = client.connected();
    doc["ip_address"] = WiFi.localIP().toString();
    doc["hostname"] = config.hostname;
    doc["bubble_count"] = bubbleCount;
    doc["rssi"] = WiFi.RSSI();
    
    // Get temperatures
    sensors.requestTemperatures();
    float temp1 = sensors.getTempCByIndex(0);
    float temp2 = sensors.getTempCByIndex(1);
    
    doc["temp1"] = (temp1 != DEVICE_DISCONNECTED_C) ? temp1 : 0;
    doc["temp2"] = (temp2 != DEVICE_DISCONNECTED_C) ? temp2 : 0;
    doc["temp1_connected"] = (temp1 != DEVICE_DISCONNECTED_C);
    doc["temp2_connected"] = (temp2 != DEVICE_DISCONNECTED_C);
    
    serializeJson(doc, jsonResponse);
    request->send(200, "application/json", jsonResponse);
  });
  
  // Get history data for charts
  server.on("/api/history", HTTP_GET, [](AsyncWebServerRequest *request) {
    String jsonResponse;
    DynamicJsonDocument doc(4096);
    
    JsonArray bubbles = doc.createNestedArray("bubbles");
    JsonArray temps1 = doc.createNestedArray("temp1");
    JsonArray temps2 = doc.createNestedArray("temp2");
    
    // Add data points in chronological order
    for (int i = 0; i < MAX_HISTORY; i++) {
      int index = (historyIndex + i) % MAX_HISTORY;
      bubbles.add(bubbleHistory[index]);
      temps1.add(tempHistory1[index]);
      temps2.add(tempHistory2[index]);
    }
    
    serializeJson(doc, jsonResponse);
    request->send(200, "application/json", jsonResponse);
  });
  
  // Update sensitivity settings
  server.on("/api/update-settings", HTTP_POST, [](AsyncWebServerRequest *request) {
    // Not handling form data directly - this just acknowledges receipt
    request->send(200, "text/plain", "Settings received");
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
    // Parse the JSON body
    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, data, len);
    
    if (!error) {
      // Update configuration
      if (doc.containsKey("gyro_threshold")) {
        float newThreshold = doc["gyro_threshold"];
        if (newThreshold > 0.05 && newThreshold <= 5.0) {
          config.gyro_threshold = newThreshold;
          
          // Also publish to MQTT if connected
          if (client.connected()) {
            char payload[10];
            snprintf(payload, 10, "%.2f", newThreshold);
            client.publish(topic_sensitivity, payload);
          }
        }
      }
      
      if (doc.containsKey("min_activity_threshold")) {
        float newThreshold = doc["min_activity_threshold"];
        if (newThreshold >= 0.05 && newThreshold <= 1.0) {
          config.min_activity_threshold = newThreshold;
          
          // Also publish to MQTT if connected
          if (client.connected()) {
            char payload[10];
            snprintf(payload, 10, "%.2f", newThreshold);
            client.publish(topic_min_threshold, payload);
          }
        }
      }
      
      if (doc.containsKey("debounce_time")) {
        int newTime = doc["debounce_time"];
        if (newTime >= 200 && newTime <= 5000) {
          config.debounce_time = newTime;
          
          // Also publish to MQTT if connected
          if (client.connected()) {
            char payload[10];
            snprintf(payload, 10, "%d", newTime);
            client.publish(topic_debounce_time, payload);
          }
        }
      }
      
      // Save configuration
      saveConfiguration();
    }
  });
  
  // Serve CSS and JS files
  server.on("/style.css", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/style.css", "text/css");
  });
  
  server.on("/script.js", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/script.js", "application/javascript");
  });
  
  server.on("/chart.js", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/chart.js", "application/javascript");
  });
  
  // Start server
  server.begin();
}

// Connect to WiFi
void connectToWifi() {
  if (strlen(config.wifi_ssid) == 0) {
    Serial.println("No WiFi credentials configured");
    displayStatus("No WiFi Config", RED);
    return;
  }
  
  displayStatus("Connecting WiFi...", YELLOW);
  Serial.printf("Connecting to %s ", config.wifi_ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(config.wifi_ssid, config.wifi_password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    M5.Display.fillRect(0, 40, attempts * 6, 5, BLUE);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    displayStatus("WiFi Connected", GREEN);
  } else {
    Serial.println("\nWiFi connection failed!");
    displayStatus("WiFi Failed", RED);
  }
  delay(1000);
}

// Setup MQTT connection
void setupMQTT() {
  if (strlen(config.mqtt_server) == 0) {
    Serial.println("No MQTT server configured");
    return;
  }
  
  client.setServer(config.mqtt_server, config.mqtt_port);
  client.setCallback(callback);
  reconnectMQTT();
}

// Reconnect to MQTT
void reconnectMQTT() {
  if (strlen(config.mqtt_server) == 0) {
    return;
  }
  
  int attempts = 0;
  
  while (!client.connected() && attempts < 3) {
    Serial.print("Connecting to MQTT broker...");
    displayStatus("MQTT Connecting", YELLOW);
    
    if (client.connect(config.mqtt_client_id, config.mqtt_user, config.mqtt_password)) {
      Serial.println("connected!");
      
      // Subscribe to topics for parameter adjustments
      client.subscribe(topic_sensitivity);
      client.subscribe(topic_min_threshold);
      client.subscribe(topic_debounce_time);
      
      displayStatus("MQTT Connected", GREEN);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retry in 2s");
      delay(2000);
    }
    attempts++;
  }
  
  if (!client.connected()) {
    displayStatus("MQTT Failed", RED);
  }
}

// MQTT callback
void callback(char* topic, byte* payload, unsigned int length) {
  // Create null-terminated string from payload
  char msg[length + 1];
  strncpy(msg, (char*)payload, length);
  msg[length] = '\0';
  
  Serial.printf("Message arrived [%s]: %s\n", topic, msg);
  
  // If message is on sensitivity topic, update threshold
  if (strcmp(topic, topic_sensitivity) == 0) {
    float newThreshold = atof(msg);
    
    if (newThreshold > 0.05 && newThreshold <= 5.0) {
      config.gyro_threshold = newThreshold;
      Serial.printf("New sensitivity: %.2f°/s\n", config.gyro_threshold);
      saveConfiguration();
    }
  }
  // If message is for minimum threshold adjustment
  else if (strcmp(topic, topic_min_threshold) == 0) {
    float newMinThreshold = atof(msg);
    
    if (newMinThreshold >= 0.05 && newMinThreshold <= 1.0) {
      config.min_activity_threshold = newMinThreshold;
      Serial.printf("New minimum threshold: %.2f\n", config.min_activity_threshold);
      saveConfiguration();
    }
  }
  // If message is for debounce time adjustment
  else if (strcmp(topic, topic_debounce_time) == 0) {
    int newDebounceTime = atoi(msg);
    
    if (newDebounceTime >= 200 && newDebounceTime <= 5000) {
      config.debounce_time = newDebounceTime;
      Serial.printf("New debounce time: %dms\n", config.debounce_time);
      saveConfiguration();
    }
  }
}

// Setup mDNS for easy access
void setupMDNS() {
  if (MDNS.begin(config.hostname)) {
    Serial.printf("mDNS responder started. Device can be reached at http://%s.local\n", config.hostname);
  } else {
    Serial.println("Error setting up mDNS responder!");
  }
}

// Save configuration to file
bool saveConfiguration() {
  File file = SPIFFS.open("/config.json", "w");
  if (!file) {
    Serial.println("Failed to open config file for writing");
    return false;
  }
  
  DynamicJsonDocument doc(1024);
  
  doc["wifi_ssid"] = config.wifi_ssid;
  doc["wifi_password"] = config.wifi_password;
  doc["mqtt_server"] = config.mqtt_server;
  doc["mqtt_port"] = config.mqtt_port;
  doc["mqtt_user"] = config.mqtt_user;
  doc["mqtt_password"] = config.mqtt_password;
  doc["mqtt_client_id"] = config.mqtt_client_id;
  doc["hostname"] = config.hostname;
  doc["gyro_threshold"] = config.gyro_threshold;
  doc["min_activity_threshold"] = config.min_activity_threshold;
  doc["debounce_time"] = config.debounce_time;
  
  if (serializeJson(doc, file) == 0) {
    Serial.println("Failed to write config to file");
    return false;
  }
  
  file.close();
  return true;
}

// Load configuration from file
bool loadConfiguration() {
  if (!SPIFFS.exists("/config.json")) {
    Serial.println("Config file not found");
    return false;
  }
  
  File file = SPIFFS.open("/config.json", "r");
  if (!file) {
    Serial.println("Failed to open config file for reading");
    return false;
  }
  
  DynamicJsonDocument doc(1024);
  DeserializationError error = deserializeJson(doc, file);
  file.close();
  
  if (error) {
    Serial.println("Failed to parse config file");
    return false;
  }
  
  // Copy values from JSON to config struct
  strlcpy(config.wifi_ssid, doc["wifi_ssid"] | "", sizeof(config.wifi_ssid));
  strlcpy(config.wifi_password, doc["wifi_password"] | "", sizeof(config.wifi_password));
  strlcpy(config.mqtt_server, doc["mqtt_server"] | "", sizeof(config.mqtt_server));
  config.mqtt_port = doc["mqtt_port"] | 1883;
  strlcpy(config.mqtt_user, doc["mqtt_user"] | "", sizeof(config.mqtt_user));
  strlcpy(config.mqtt_password, doc["mqtt_password"] | "", sizeof(config.mqtt_password));
  strlcpy(config.mqtt_client_id, doc["mqtt_client_id"] | "M5AtomS3Vibration", sizeof(config.mqtt_client_id));
  strlcpy(config.hostname, doc["hostname"] | "tresor.lab", sizeof(config.hostname));
  config.gyro_threshold = doc["gyro_threshold"] | 0.5;
  config.min_activity_threshold = doc["min_activity_threshold"] | 0.2;
  config.debounce_time = doc["debounce_time"] | 1000;
  
  return true;
}

// Send data via MQTT
void sendMQTT() {
  if (!client.connected()) {
    return;
  }
  
  char payload[50];
  
  // Send bubble count data
  snprintf(payload, 50, "{\"blops\": %d}", bubbleCount);
  client.publish(topic_bubbles, payload);
  Serial.printf("MQTT sent: %s\n", payload);
  
  // Get temperature readings from DS18B20 sensors
  sensors.requestTemperatures();
  float temp1 = sensors.getTempCByIndex(0);
  float temp2 = sensors.getTempCByIndex(1);
  
  // Send temperature 1 data if sensor is connected
  if (temp1 != DEVICE_DISCONNECTED_C) {
    snprintf(payload, 50, "{\"temperature\": %.2f}", temp1);
    client.publish(topic_temp1, payload);
    Serial.printf("Temp1 sent: %.2f°C\n", temp1);
  }
  
  // Send temperature 2 data if sensor is connected
  if (temp2 != DEVICE_DISCONNECTED_C) {
    snprintf(payload, 50, "{\"temperature\": %.2f}", temp2);
    client.publish(topic_temp2, payload);
    Serial.printf("Temp2 sent: %.2f°C\n", temp2);
  }
}

// Update history arrays for charts
void updateHistory() {
  // Get temperature readings
  sensors.requestTemperatures();
  float temp1 = sensors.getTempCByIndex(0);
  float temp2 = sensors.getTempCByIndex(1);
  
  // Store in history arrays
  bubbleHistory[historyIndex] = bubbleCount;
  tempHistory1[historyIndex] = (temp1 != DEVICE_DISCONNECTED_C) ? temp1 : 0;
  tempHistory2[historyIndex] = (temp2 != DEVICE_DISCONNECTED_C) ? temp2 : 0;
  
  // Increment index
  historyIndex = (historyIndex + 1) % MAX_HISTORY;
}

// Display status message
void displayStatus(const char* message, uint16_t color) {
  M5.Display.clear();
  M5.Display.setTextSize(1);
  M5.Display.setTextColor(color);
  M5.Display.setCursor(10, M5.Display.height() / 2 - 10);
  M5.Display.println(message);
}

// Display connection status on screen
void displayConnectionStatus() {
  M5.Display.clear();
  M5.Display.setTextSize(1);
  
  // Title
  M5.Display.setTextColor(WHITE);
  M5.Display.setCursor(5, 5);
  M5.Display.println("Laboratoire Tresor");
  
  // WiFi status
  M5.Display.setCursor(5, 20);
  if (WiFi.status() == WL_CONNECTED) {
    M5.Display.setTextColor(GREEN);
    M5.Display.print("WiFi: OK");
    // Display WiFi signal strength
    M5.Display.setCursor(70, 20);
    M5.Display.printf("(%ddBm)", WiFi.RSSI());
  } else {
    M5.Display.setTextColor(RED);
    M5.Display.print("WiFi: Not Connected");
  }
  
  // MQTT status
  M5.Display.setCursor(5, 35);
  if (client.connected()) {
    M5.Display.setTextColor(GREEN);
    M5.Display.print("MQTT: Connected");
  } else {
    M5.Display.setTextColor(RED);
    M5.Display.print("MQTT: Disconnected");
  }
  
  // Host name
  M5.Display.setCursor(5, 50);
  M5.Display.setTextColor(CYAN);
  M5.Display.printf("Host: %s.local", config.hostname);
  
  // Bubble count
  M5.Display.setCursor(5, 65);
  M5.Display.setTextColor(YELLOW);
  M5.Display.printf("Bubbles: %d", bubbleCount);
  
  // Time until next send
  unsigned long timeRemaining = (sendInterval - (millis() - lastSendTime)) / 1000;
  M5.Display.setCursor(5, 80);
  M5.Display.setTextColor(WHITE);
  M5.Display.printf("Next send: %lus", timeRemaining);
}

// Bubble animation for visualization
void showBubbleAnimation() {
  int centerX = M5.Display.width() / 2;
  int centerY = M5.Display.height() / 2;
  
  uint16_t colors[] = {RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, MAGENTA, WHITE};
  
  for (int i = 5; i <= 30; i += 5) {
    uint16_t color = colors[random(0, 8)];
    M5.Display.fillCircle(centerX, centerY, i, color);
    delay(20);
  }
  
  delay(50);
  M5.Display.clear();
  displayConnectionStatus();
}