// admin_dashboard.js (Realtime frontend)
const socket = new WebSocket(`wss://${window.location.host}/ws/admin/dashboard/`);

socket.onmessage = function(e) {
    const data = JSON.parse(e.data);
    switch(data.type) {
        case 'initial_data':
            updateAllCharts(data.metrics);
            break;
        case 'system_update':
            handleRealTimeUpdate(data.data);
            break;
        case 'new_notification':
            showNotification(data.notification);
            break;
    }
};

function updateAllCharts(metrics) {
    messageChart.data.datasets[0].data = metrics.message_distribution;
    messageChart.update();

    userActivityChart.data.datasets[0].data = metrics.active_users_history;
    userActivityChart.update();

    document.getElementById('uptime-counter').innerText = metrics.uptime;
}

// Enable realtime updates with EventSource
const eventSource = new EventSource('/realtime-updates/');

eventSource.onmessage = function(e) {
    const data = JSON.parse(e.data);
    socket.send(JSON.stringify({type: 'refresh'}));
};