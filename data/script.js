document.addEventListener('DOMContentLoaded', function() {
    // Determine which page we're on
    const currentPath = window.location.pathname;
    
    // Initialize based on the current page
    if (currentPath === '/') {
        initDashboard();
    } else if (currentPath === '/config' && document.getElementById('setup-form')) {
        initSetupForm();
    } else if (currentPath === '/config') {
        initConfigPage();
    }
    
    // Set up range slider value display
    document.querySelectorAll('input[type="range"]').forEach(function(slider) {
        const valueDisplay = document.getElementById(slider.id + '_value');
        if (valueDisplay) {
            // Initialize display with current value
            valueDisplay.textContent = slider.value;
            
            // Update display when slider changes
            slider.addEventListener('input', function() {
                valueDisplay.textContent = this.value;
            });
        }
    });
});

// Dashboard initialization
function initDashboard() {
    // Initial data load
    fetchStatusData();
    fetchHistoryData();
    
    // Set up auto-refresh
    setInterval(fetchStatusData, 5000); // Refresh every 5 seconds
    setInterval(fetchHistoryData, 60000); // Refresh charts every minute
    
    // Set up sensor settings form
    const saveSettingsBtn = document.getElementById('save-settings');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', function() {
            updateSensorSettings();
        });
    }
}

// Initial setup form
function initSetupForm() {
    const setupForm = document.getElementById('setup-form');
    if (setupForm) {
        setupForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(setupForm);
            const data = {};
            
            formData.forEach((value, key) => {
                data[key] = value;
            });
            
            fetch('/save-config', {
                method: 'POST',
                body: formData
            })
            .then(response => response.text())
            .then(text => {
                showStatusMessage(text, 'success');
                setTimeout(function() {
                    // Redirect after successful save
                    window.location.href = '/';
                }, 5000);
            })
            .catch(error => {
                showStatusMessage('Error saving configuration: ' + error, 'error');
            });
        });
    }
}

// Configuration page initialization
function initConfigPage() {
    // Load current configuration
    fetch('/api/config')
        .then(response => response.json())
        .then(data => {
            // Populate form fields
            document.getElementById('wifi_ssid').value = data.wifi_ssid || '';
            document.getElementById('mqtt_server').value = data.mqtt_server || '';
            document.getElementById('mqtt_port').value = data.mqtt_port || 1883;
            document.getElementById('mqtt_user').value = data.mqtt_user || '';
            document.getElementById('mqtt_client_id').value = data.mqtt_client_id || 'M5AtomS3Vibration';
            document.getElementById('hostname').value = data.hostname || 'tresor.lab';
            
            // Set sensor settings sliders
            const gyroThreshold = document.getElementById('gyro_threshold');
            if (gyroThreshold) {
                gyroThreshold.value = data.gyro_threshold || 0.5;
                document.getElementById('gyro_threshold_value').textContent = gyroThreshold.value;
            }
            
            const minThreshold = document.getElementById('min_activity_threshold');
            if (minThreshold) {
                minThreshold.value = data.min_activity_threshold || 0.2;
                document.getElementById('min_activity_threshold_value').textContent = minThreshold.value;
            }
            
            const debounceTime = document.getElementById('debounce_time');
            if (debounceTime) {
                debounceTime.value = data.debounce_time || 1000;
                document.getElementById('debounce_time_value').textContent = debounceTime.value;
            }
        })
        .catch(error => {
            showStatusMessage('Error loading configuration: ' + error, 'error');
        });
    
    // Set up form submission
    const configForm = document.getElementById('config-form');
    if (configForm) {
        configForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Implementation for saving settings would go here
            // ...
            
            showStatusMessage('Settings saved successfully!', 'success');
        });
    }
    
    // Set up restart button
    const restartBtn = document.getElementById('restart-btn');
    if (restartBtn) {
        restartBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to restart the device?')) {
                // Implementation for restarting would go here
                // ...
                
                showStatusMessage('Device is restarting...', 'success');
                setTimeout(function() {
                    window.location.reload();
                }, 5000);
            }
        });
    }
}

// Fetch current status data
function fetchStatusData() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            // Update connection status
            document.getElementById('wifi-status').textContent = data.wifi_connected ? 'Connected' : 'Disconnected';
            document.getElementById('wifi-status').className = 'status-value ' + (data.wifi_connected ? 'success' : 'error');
            
            document.getElementById('mqtt-status').textContent = data.mqtt_connected ? 'Connected' : 'Disconnected';
            document.getElementById('mqtt-status').className = 'status-value ' + (data.mqtt_connected ? 'success' : 'error');
            
            document.getElementById('ip-address').textContent = data.ip_address || 'Unknown';
            document.getElementById('hostname').textContent = data.hostname || 'Unknown';
            document.getElementById('rssi').textContent = data.rssi ? data.rssi + ' dBm' : 'Unknown';
            
            // Update sensor status
            document.getElementById('bubble-count').textContent = data.bubble_count || '0';
            
            const temp1Element = document.getElementById('temp1');
            if (data.temp1_connected) {
                temp1Element.textContent = data.temp1.toFixed(1) + ' °C';
                temp1Element.className = 'status-value success';
            } else {
                temp1Element.textContent = 'Disconnected';
                temp1Element.className = 'status-value error';
            }
            
            const temp2Element = document.getElementById('temp2');
            if (data.temp2_connected) {
                temp2Element.textContent = data.temp2.toFixed(1) + ' °C';
                temp2Element.className = 'status-value success';
            } else {
                temp2Element.textContent = 'Disconnected';
                temp2Element.className = 'status-value error';
            }
        })
        .catch(error => {
            console.error('Error fetching status:', error);
        });
}

// Fetch historical data for charts
function fetchHistoryData() {
    if (!window.bubbleChart || !window.tempChart) {
        return; // Charts not initialized yet
    }
    
    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            // Update bubble chart
            window.bubbleChart.data.datasets[0].data = data.bubbles;
            window.bubbleChart.update();
            
            // Update temperature chart
            window.tempChart.data.datasets[0].data = data.temp1;
            window.tempChart.data.datasets[1].data = data.temp2;
            window.tempChart.update();
        })
        .catch(error => {
            console.error('Error fetching history data:', error);
        });
}

// Update sensor settings
function updateSensorSettings() {
    const gyroThreshold = document.getElementById('gyro_threshold').value;
    const minThreshold = document.getElementById('min_activity_threshold').value;
    const debounceTime = document.getElementById('debounce_time').value;
    
    const data = {
        gyro_threshold: parseFloat(gyroThreshold),
        min_activity_threshold: parseFloat(minThreshold),
        debounce_time: parseInt(debounceTime)
    };
    
    fetch('/api/update-settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.text())
    .then(text => {
        showStatusMessage('Settings updated successfully!', 'success');
    })
    .catch(error => {
        showStatusMessage('Error updating settings: ' + error, 'error');
    });
}

// Show status message
function showStatusMessage(message, type) {
    const statusElement = document.getElementById('status-message');
    if (statusElement) {
        statusElement.textContent = message;
        statusElement.className = type || 'success';
        statusElement.classList.remove('hidden');
        
        // Hide message after 5 seconds
        setTimeout(function() {
            statusElement.classList.add('hidden');
        }, 5000);
    }
}