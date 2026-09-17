// Initialize charts when DOM content is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Set up Chart.js configuration
    const ctx1 = document.getElementById('bubble-chart').getContext('2d');
    const ctx2 = document.getElementById('temperature-chart').getContext('2d');
    
    // Set chart defaults
    Chart.defaults.color = '#ddd';
    Chart.defaults.font.family = 'Arial, sans-serif';
    
    // Create bubble rate chart
    window.bubbleChart = new Chart(ctx1, {
        type: 'bar',
        data: {
            labels: generateTimeLabels(60), // 60 minutes
            datasets: [{
                label: 'Bubbles per Minute',
                data: Array(60).fill(0), // Initialize with zeros
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Fermentation Activity (Bubbles per Minute)',
                    font: {
                        size: 16
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + context.raw + ' bubbles';
                        }
                    }
                },
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Bubbles'
                    },
                    ticks: {
                        stepSize: 1
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time (minutes ago)'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        autoSkip: true,
                        maxTicksLimit: 12
                    }
                }
            }
        }
    });
    
    // Create temperature chart
    window.tempChart = new Chart(ctx2, {
        type: 'line',
        data: {
            labels: generateTimeLabels(60), // 60 minutes
            datasets: [
                {
                    label: 'Temperature 1',
                    data: Array(60).fill(0), // Initialize with zeros
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                    tension: 0.2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                },
                {
                    label: 'Temperature 2',
                    data: Array(60).fill(0), // Initialize with zeros
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2,
                    tension: 0.2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Temperature History',
                    font: {
                        size: 16
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + context.raw.toFixed(1) + ' °C';
                        }
                    }
                }
            },
            scales: {
                y: {
                    title: {
                        display: true,
                        text: 'Temperature (°C)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time (minutes ago)'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        autoSkip: true,
                        maxTicksLimit: 12
                    }
                }
            }
        }
    });
    
    // Initial data fetch
    fetchHistoryData();
});

// Generate time labels for x-axis (minutes ago)
function generateTimeLabels(count) {
    const labels = [];
    for (let i = count - 1; i >= 0; i--) {
        labels.push(i === 0 ? 'now' : `-${i}`);
    }
    return labels;
}

// Fetch history data for charts
function fetchHistoryData() {
    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            updateBubbleChart(data.bubbles);
            updateTemperatureChart(data.temp1, data.temp2);
        })
        .catch(error => {
            console.error('Error fetching history data:', error);
        });
}

// Update bubble chart with new data
function updateBubbleChart(bubbleData) {
    if (!window.bubbleChart) {
        return;
    }
    
    window.bubbleChart.data.datasets[0].data = bubbleData;
    
    // Adjust y-axis max value based on data
    const maxBubbles = Math.max(...bubbleData, 1);
    window.bubbleChart.options.scales.y.max = calculateYAxisMax(maxBubbles);
    
    window.bubbleChart.update();
}

// Update temperature chart with new data
function updateTemperatureChart(temp1Data, temp2Data) {
    if (!window.tempChart) {
        return;
    }
    
    window.tempChart.data.datasets[0].data = temp1Data;
    window.tempChart.data.datasets[1].data = temp2Data;
    
    // Find min and max temperatures for better scaling
    const allTemps = [...temp1Data, ...temp2Data].filter(t => t > 0);
    if (allTemps.length > 0) {
        const minTemp = Math.min(...allTemps);
        const maxTemp = Math.max(...allTemps);
        
        // Set y-axis range with some padding
        window.tempChart.options.scales.y.min = Math.max(0, Math.floor(minTemp - 2));
        window.tempChart.options.scales.y.max = Math.ceil(maxTemp + 2);
    }
    
    window.tempChart.update();
}

// Calculate appropriate y-axis max value
function calculateYAxisMax(maxValue) {
    if (maxValue <= 5) return 5;
    if (maxValue <= 10) return 10;
    if (maxValue <= 20) return 20;
    if (maxValue <= 50) return 50;
    return Math.ceil(maxValue / 10) * 10;
}

// Add event listener for window resize to redraw charts
window.addEventListener('resize', function() {
    if (window.bubbleChart) {
        window.bubbleChart.resize();
    }
    if (window.tempChart) {
        window.tempChart.resize();
    }
});

// Function to update the charts manually
function refreshCharts() {
    fetchHistoryData();
}

// Add export functionality
function exportData() {
    if (!window.bubbleChart || !window.tempChart) {
        console.error('Charts not initialized');
        return;
    }
    
    const bubbleData = window.bubbleChart.data.datasets[0].data;
    const temp1Data = window.tempChart.data.datasets[0].data;
    const temp2Data = window.tempChart.data.datasets[1].data;
    const labels = window.bubbleChart.data.labels;
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Time,Bubbles,Temperature 1,Temperature 2\n";
    
    for (let i = 0; i < labels.length; i++) {
        csvContent += `${labels[i]},${bubbleData[i]},${temp1Data[i]},${temp2Data[i]}\n`;
    }
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "fermentation_data.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Create event handler for chart refresh button if it exists
document.addEventListener('DOMContentLoaded', function() {
    const refreshBtn = document.getElementById('refresh-charts');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshCharts);
    }
    
    const exportBtn = document.getElementById('export-data');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportData);
    }
});