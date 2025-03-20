#!/bin/bash

# Script to manually update the web application
# This script will:
# 1. Create updated web app files
# 2. Upload them to S3
# 3. Invalidate the CloudFront cache

# Configuration
S3_BUCKET="adrve-webapp-056689112963"
CLOUDFRONT_DISTRIBUTION_ID="E2BAXYOQC6RIHK"
REGION="us-west-2"
API_ENDPOINT="https://qs1sbfchsa.execute-api.us-west-2.amazonaws.com/prod"
IOT_ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --query 'endpointAddress' --output text)
STREAM_NAME="adrve-video-stream"
IDENTITY_POOL_ID="us-west-2:4979dca7-4346-43b6-b0bb-0822bf749cdb"
PROJECT_NAME="adrve"

# Create a temporary directory
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TEMP_DIR"

# Create index.html
cat > $TEMP_DIR/index.html << EOL
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADRVE Operator Interface</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/aws-sdk/2.1001.0/aws-sdk.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script>
        // Configuration variables 
        window.config = {
            apiEndpoint: '${API_ENDPOINT}',
            region: '${REGION}',
            iotEndpoint: '${IOT_ENDPOINT}',
            identityPoolId: '${IDENTITY_POOL_ID}',
            streamName: '${STREAM_NAME}',
            deviceId: 'adrve-edge-device',
            topicPrefix: '${PROJECT_NAME}'
        };
    </script>
    <link rel="stylesheet" href="app.css">
</head>
<body>
    <div class="header">
        <h1>ADRVE Operator Interface</h1>
    </div>
    
    <div class="container">
        <div class="video-container">
            <div class="video-wrapper">
                <video id="videoPlayer" autoplay playsinline muted></video>
                <div id="detectionOverlay" class="detection-overlay"></div>
            </div>
        </div>
        
        <div class="controls">
            <h2>Device Controls</h2>
            <div>
                <button id="connectBtn">Connect</button>
                <button id="stopBtn" class="stop">Emergency Stop</button>
                <button id="resumeBtn">Resume</button>
            </div>
            <div id="connectionStatus" class="status disconnected">
                Disconnected
            </div>
        </div>
        
        <div class="detection-panel">
            <h2>Latest Detections</h2>
            <div id="detectionsList"></div>
        </div>
        
        <div class="command-history">
            <h2>Command History</h2>
            <div id="commandHistory"></div>
        </div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
EOL

# Create app.js
cat > $TEMP_DIR/app.js << 'EOL'
// Get configuration from window.config
const config = window.config;

// AWS Configuration
AWS.config.region = config.region;
AWS.config.credentials = new AWS.CognitoIdentityCredentials({
    IdentityPoolId: config.identityPoolId
});

// Global variables
let iotClient = null;
let kinesisVideoClient = null;
let connected = false;
let latestDetections = {
    edge: [],
    cloud: []
};

// DOM elements
const videoPlayer = document.getElementById('videoPlayer');
const detectionOverlay = document.getElementById('detectionOverlay');
const detectionsList = document.getElementById('detectionsList');
const commandHistory = document.getElementById('commandHistory');
const connectBtn = document.getElementById('connectBtn');
const stopBtn = document.getElementById('stopBtn');
const resumeBtn = document.getElementById('resumeBtn');
const connectionStatus = document.getElementById('connectionStatus');

// Initialize the application
async function init() {
    connectBtn.addEventListener('click', connect);
    stopBtn.addEventListener('click', sendStopCommand);
    resumeBtn.addEventListener('click', sendResumeCommand);
    
    try {
        await AWS.config.credentials.getPromise();
        console.log("AWS credentials loaded successfully");
    } catch (error) {
        console.error("Failed to load AWS credentials:", error);
        connectionStatus.textContent = "Failed to initialize AWS credentials";
    }
    
    // Start fetching detections periodically
    setInterval(fetchLatestDetections, 5000);
}

// Connect to the edge device
async function connect() {
    try {
        connectionStatus.textContent = "Connecting...";
        
        // Initialize IoT client
        initializeIoT();
        
        // Initialize KVS connection
        await initializeKVS();
        
        connected = true;
        connectionStatus.textContent = "Connected";
        connectionStatus.className = "status connected";
    } catch (error) {
        console.error("Connection failed:", error);
        connectionStatus.textContent = "Connection failed: " + error.message;
        connectionStatus.className = "status disconnected";
    }
}

// Initialize AWS IoT client
function initializeIoT() {
    AWS.config.credentials.get(function(err) {
        if (err) {
            console.error("Error getting AWS credentials:", err);
            return;
        }
        
        // Initialize the IoT client
        iotClient = new AWS.IotData({ endpoint: config.iotEndpoint });
        
        console.log("IoT client initialized");
    });
}

// Fetch latest detections from API
async function fetchLatestDetections() {
    try {
        const response = await fetch(`${config.apiEndpoint}/detections`);
        const data = await response.json();
        
        if (data && data.length > 0) {
            // Process the latest detections
            for (const item of data.slice(0, 5)) {
                if (item.detectionResults) {
                    const source = item.detectionResults.source || 'cloud';
                    const detections = [];
                    
                    // Process objects from detection results
                    for (const obj of item.detectionResults.objects || []) {
                        detections.push({
                            box: obj.box || obj.location || [0, 0, 100, 100],
                            class: obj.type || obj.class || 'unknown',
                            confidence: obj.confidence || 0.5
                        });
                    }
                    
                    // Update based on source
                    if (source === 'edge') {
                        latestDetections.edge = detections;
                    } else {
                        latestDetections.cloud = detections;
                    }
                }
            }
            
            // Update UI
            updateDetectionOverlay();
            updateDetectionsList();
        }
    } catch (error) {
        console.error("Error fetching detections:", error);
    }
}

// Initialize KVS connection
async function initializeKVS() {
    try {
        console.log("Initializing KVS connection");
        
        // Make sure AWS credentials are loaded
        await AWS.config.credentials.getPromise();
        
        // Create KVS client
        kinesisVideoClient = new AWS.KinesisVideo({
            region: config.region,
            credentials: AWS.config.credentials
        });
        
        // Get HLS URL for the stream
        const getHLSStreamingSessionURL = await kinesisVideoClient.getDataEndpoint({
            StreamName: config.streamName,
            APIName: 'GET_HLS_STREAMING_SESSION_URL'
        }).promise();
        
        const hlsEndpoint = getHLSStreamingSessionURL.DataEndpoint;
        
        // Create KVS client with HLS endpoint
        const kvsHlsClient = new AWS.KinesisVideoArchivedMedia({
            region: config.region,
            endpoint: hlsEndpoint,
            credentials: AWS.config.credentials
        });
        
        // Get HLS URL
        const hlsResponse = await kvsHlsClient.getHLSStreamingSessionURL({
            StreamName: config.streamName,
            PlaybackMode: 'LIVE',
            HLSFragmentSelector: {
                FragmentSelectorType: 'SERVER_TIMESTAMP',
                TimestampRange: {
                    StartTimestamp: new Date(Date.now() - 30000) // 30 seconds ago
                }
            },
            ContainerFormat: 'FRAGMENTED_MP4',
            DiscontinuityMode: 'ALWAYS',
            DisplayFragmentTimestamp: 'NEVER',
            MaxMediaPlaylistFragmentResults: 5,
            ExpireAfter: 3600
        }).promise();
        
        const hlsUrl = hlsResponse.HLSStreamingSessionURL;
        console.log("HLS URL obtained:", hlsUrl);
        
        // Set the video source to the HLS URL
        if (Hls.isSupported()) {
            const hls = new Hls({
                debug: false,
                enableWorker: true,
                lowLatencyMode: true,
                backBufferLength: 30
            });
            
            hls.loadSource(hlsUrl);
            hls.attachMedia(videoPlayer);
            
            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                console.log("HLS manifest parsed, attempting to play");
                videoPlayer.play().catch(error => {
                    console.error("Error playing video:", error);
                });
            });
            
            hls.on(Hls.Events.ERROR, function(event, data) {
                console.error("HLS error:", data);
                if (data.fatal) {
                    switch(data.type) {
                        case Hls.ErrorTypes.NETWORK_ERROR:
                            console.log("Network error, trying to recover");
                            hls.startLoad();
                            break;
                        case Hls.ErrorTypes.MEDIA_ERROR:
                            console.log("Media error, trying to recover");
                            hls.recoverMediaError();
                            break;
                        default:
                            console.error("Fatal error, cannot recover");
                            initializeFallbackVideo();
                            break;
                    }
                }
            });
        } else if (videoPlayer.canPlayType('application/vnd.apple.mpegurl')) {
            // For Safari
            videoPlayer.src = hlsUrl;
            videoPlayer.addEventListener('loadedmetadata', function() {
                videoPlayer.play().catch(error => {
                    console.error("Error playing video:", error);
                });
            });
        } else {
            console.error("HLS is not supported on this browser");
            initializeFallbackVideo();
        }
        
        console.log("KVS connection initialized");
    } catch (error) {
        console.error("Error initializing KVS connection:", error);
        
        // Fall back to simulated video
        initializeFallbackVideo();
    }
}

// Initialize fallback video if KVS connection fails
function initializeFallbackVideo() {
    console.log("Falling back to simulated video");
    
    // For this POC, we'll use a canvas to simulate video
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d');
    
    // Create a video stream from the canvas
    const stream = canvas.captureStream(30);
    videoPlayer.srcObject = stream;
    
    // Simple animation to simulate video feed
    function drawFrame() {
        // Clear canvas
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw simulated scene
        ctx.fillStyle = '#333333';
        ctx.fillRect(100, 100, 440, 280);
        
        // Draw simulated street
        ctx.fillStyle = '#555555';
        ctx.fillRect(0, 350, 640, 130);
        
        // Draw timestamp
        ctx.fillStyle = '#ffffff';
        ctx.font = '14px Arial';
        ctx.fillText(new Date().toISOString(), 10, 20);
        
        // Draw some simulated objects
        // These would be based on actual detections in production
        
        // Car
        ctx.fillStyle = '#0000ff';
        ctx.fillRect(200, 300, 100, 50);
        
        // Person
        ctx.fillStyle = '#00ff00';
        ctx.fillRect(400, 280, 30, 70);
        
        requestAnimationFrame(drawFrame);
    }
    
    drawFrame();
    
    console.log("Simulated video initialized as fallback");
}

// Update the detection overlay on the video
function updateDetectionOverlay() {
    // Clear previous overlay
    detectionOverlay.innerHTML = '';
    
    // Get video dimensions
    const videoWidth = videoPlayer.clientWidth;
    const videoHeight = videoPlayer.clientHeight;
    
    // Add edge detections (green)
    latestDetections.edge.forEach(detection => {
        addDetectionBox(detection, "edge", videoWidth, videoHeight);
    });
    
    // Add cloud detections (blue)
    latestDetections.cloud.forEach(detection => {
        addDetectionBox(detection, "cloud", videoWidth, videoHeight);
    });
}

// Add a detection box to the overlay
function addDetectionBox(detection, source, videoWidth, videoHeight) {
    if (!detection.box || detection.box.length !== 4) return;
    
    // Get box coordinates
    const [x1, y1, x2, y2] = detection.box;
    
    // Create box element
    const box = document.createElement('div');
    box.className = `detection-box ${source}`;
    box.style.left = `${(x1 / 640) * videoWidth}px`;
    box.style.top = `${(y1 / 480) * videoHeight}px`;
    box.style.width = `${((x2 - x1) / 640) * videoWidth}px`;
    box.style.height = `${((y2 - y1) / 480) * videoHeight}px`;
    
    // Create label
    const label = document.createElement('div');
    label.className = 'detection-label';
    label.style.left = `${(x1 / 640) * videoWidth}px`;
    label.style.top = `${((y1 / 480) * videoHeight) - 20}px`;
    label.textContent = `${detection.class} (${Math.round(detection.confidence * 100)}%)`;
    
    // Add to overlay
    detectionOverlay.appendChild(box);
    detectionOverlay.appendChild(label);
}

// Update the detections list
function updateDetectionsList() {
    // Clear previous list
    detectionsList.innerHTML = '';
    
    // Combine detections
    const allDetections = [
        ...latestDetections.edge.map(d => ({ ...d, source: 'edge' })),
        ...latestDetections.cloud.map(d => ({ ...d, source: 'cloud' }))
    ];
    
    // Sort by confidence (descending)
    allDetections.sort((a, b) => b.confidence - a.confidence);
    
    // Create list items
    allDetections.forEach(detection => {
        const item = document.createElement('div');
        item.className = 'detection-item';
        item.textContent = `[${detection.source.toUpperCase()}] ${detection.class} (${Math.round(detection.confidence * 100)}% confidence)`;
        detectionsList.appendChild(item);
    });
    
    // If no detections
    if (allDetections.length === 0) {
        const item = document.createElement('div');
        item.textContent = 'No detections';
        detectionsList.appendChild(item);
    }
}

// Send stop command to edge device
function sendStopCommand() {
    sendCommand('stop', 'Operator triggered emergency stop');
}

// Send resume command to edge device
function sendResumeCommand() {
    sendCommand('resume', 'Operator resumed operation');
}

// Send a command to the edge device
async function sendCommand(command, reason) {
    if (!connected) {
        alert("Not connected to device");
        return;
    }
    
    try {
        const response = await fetch(`${config.apiEndpoint}/commands`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command: command,
                reason: reason,
                deviceId: config.deviceId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Add to command history
            addCommandToHistory({
                command: command,
                reason: reason,
                timestamp: data.timestamp
            });
            
            console.log(`${command} command sent successfully`);
        } else {
            alert(`Failed to send ${command} command: ${data.error}`);
        }
    } catch (error) {
        console.error(`Error sending ${command} command:`, error);
        alert(`Error sending ${command} command: ${error.message}`);
    }
}

// Add a command to the history
function addCommandToHistory(command) {
    const item = document.createElement('div');
    item.className = `command-item ${command.command}`;
    
    const time = new Date(command.timestamp * 1000).toLocaleTimeString();
    item.textContent = `[${time}] ${command.command.toUpperCase()}: ${command.reason}`;
    
    // Add to top of history
    commandHistory.insertBefore(item, commandHistory.firstChild);
}

// Initialize the application when the page loads
window.addEventListener('load', init);
EOL

# Create app.css
cat > $TEMP_DIR/app.css << 'EOL'
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f0f0f0;
}
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}
.header {
    background-color: #232f3e;
    color: white;
    padding: 15px;
    text-align: center;
}
.video-container {
    display: flex;
    flex-direction: column;
    margin-top: 20px;
}
.video-wrapper {
    position: relative;
    margin-bottom: 20px;
}
video {
    width: 100%;
    border: 1px solid #ddd;
    background-color: #000;
    height: 480px;
}
.controls {
    background-color: white;
    padding: 15px;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-top: 20px;
}
.detection-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
}
.detection-box {
    position: absolute;
    border: 2px solid;
    box-sizing: border-box;
}
.detection-box.edge {
    border-color: green;
}
.detection-box.cloud {
    border-color: blue;
}
.detection-label {
    position: absolute;
    background-color: rgba(0,0,0,0.7);
    color: white;
    padding: 2px 5px;
    font-size: 12px;
    white-space: nowrap;
}
.detection-panel {
    background-color: white;
    padding: 15px;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-top: 20px;
    max-height: 300px;
    overflow-y: auto;
}
.detection-item {
    padding: 8px;
    border-bottom: 1px solid #eee;
}
.command-history {
    background-color: white;
    padding: 15px;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-top: 20px;
    max-height: 200px;
    overflow-y: auto;
}
.command-item {
    padding: 8px;
    border-bottom: 1px solid #eee;
}
.command-item.stop {
    background-color: rgba(255,0,0,0.1);
}
button {
    background-color: #ff9900;
    color: white;
    border: none;
    padding: 10px 15px;
    border-radius: 4px;
    cursor: pointer;
    margin-right: 10px;
}
button:hover {
    background-color: #e88a00;
}
button.stop {
    background-color: #d13212;
}
button.stop:hover {
    background-color: #ba2b0f;
}
.status {
    margin-top: 10px;
    padding: 10px;
    border-radius: 4px;
}
.status.connected {
    background-color: rgba(0,128,0,0.1);
    color: green;
}
.status.disconnected {
    background-color: rgba(255,0,0,0.1);
    color: red;
}
EOL

# Create error.html
cat > $TEMP_DIR/error.html << 'EOL'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error - ADRVE</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
        }
        h1 {
            color: #d13212;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        .link {
            color: #0073bb;
            text-decoration: none;
        }
        .link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Page Not Found</h1>
        <p>Sorry, the page you're looking for doesn't exist.</p>
        <p><a class="link" href="/">Return to Home</a></p>
    </div>
</body>
</html>
EOL

# Upload files to S3
echo "Uploading files to S3 bucket: $S3_BUCKET"
aws s3 cp $TEMP_DIR/index.html s3://$S3_BUCKET/index.html --content-type "text/html"
aws s3 cp $TEMP_DIR/app.js s3://$S3_BUCKET/app.js --content-type "application/javascript"
aws s3 cp $TEMP_DIR/app.css s3://$S3_BUCKET/app.css --content-type "text/css"
aws s3 cp $TEMP_DIR/error.html s3://$S3_BUCKET/error.html --content-type "text/html"

# Invalidate CloudFront cache
echo "Invalidating CloudFront cache for distribution: $CLOUDFRONT_DISTRIBUTION_ID"
aws cloudfront create-invalidation --distribution-id $CLOUDFRONT_DISTRIBUTION_ID --paths "/*"

# Clean up
echo "Cleaning up temporary directory"
rm -rf $TEMP_DIR

echo "Web application update complete!"
echo "You can access the web application at: https://d1r42o1nj38hxi.cloudfront.net"
