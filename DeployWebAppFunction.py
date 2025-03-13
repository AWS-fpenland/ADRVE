import time
import boto3
import json
import cfnresponse
import os
import tempfile

def lambda_handler(event, context):
    """Deploy web application to S3 bucket"""
    # Get parameters
    bucket_name = event['ResourceProperties']['WebAppBucket']
    cloudfront_distribution = event['ResourceProperties']['CloudFrontDistribution']
    api_endpoint = event['ResourceProperties']['ApiEndpoint']
    iot_endpoint = event['ResourceProperties']['IoTEndpoint']
    kinesis_video_stream = event['ResourceProperties']['KinesisVideoStreamName']
    identity_pool_id = event['ResourceProperties']['IdentityPoolId']
    region = event['ResourceProperties']['Region']
    project_name = event['ResourceProperties']['ProjectName']

    # Skip processing for DELETE events
    if event['RequestType'] == 'Delete':
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        return

    try:
        s3_client = boto3.client('s3')
        
        # Create index.html with configuration
        index_html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ADRVE Operator Interface</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/aws-sdk/2.1001.0/aws-sdk.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/amazon-kinesis-video-streams-webrtc/2.0.0/kvs-webrtc.min.js"></script>
            <script>
                // Configuration variables 
                window.config = {
                    apiEndpoint: '""" + api_endpoint + """',
                    region: '""" + region + """',
                    iotEndpoint: '""" + iot_endpoint + """',
                    identityPoolId: '""" + identity_pool_id + """',
                    streamName: '""" + kinesis_video_stream + """',
                    deviceId: 'adrve-edge-device',
                    topicPrefix: '""" + project_name + """'
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
        """
        
        # Create app.js with application logic
        app_js = """
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
        let signalingClient = null;
        let peerConnection = null;
        let dataChannel = null;
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
                
                // Initialize KVS WebRTC
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
        
        // Initialize KVS WebRTC
        async function initializeKVS() {
            // In a real implementation, this would use the KVS WebRTC SDK
            // For the POC, we're simulating the video feed
            
            console.log("Initializing KVS WebRTC (simulated for POC)");
            
            // Simulate connection delay
            await new Promise(resolve => setTimeout(resolve, 1500));
            
            // Use a fallback video for demonstration
            // In production, this would be the actual KVS WebRTC stream
            
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
            
            console.log("KVS WebRTC initialized (simulated)");
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
        """
        
        # Create app.css with styling
        app_css = """
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
        """
        
        # Create error.html
        error_html = """
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
        """
        
        # Create temporary files
        with tempfile.TemporaryDirectory() as tmpdirname:
            # Write files to temporary directory
            with open(os.path.join(tmpdirname, 'index.html'), 'w') as f:
                f.write(index_html)
            
            with open(os.path.join(tmpdirname, 'app.js'), 'w') as f:
                f.write(app_js)
            
            with open(os.path.join(tmpdirname, 'app.css'), 'w') as f:
                f.write(app_css)
            
            with open(os.path.join(tmpdirname, 'error.html'), 'w') as f:
                f.write(error_html)
            
            # Upload files to S3
            for file_name in ['index.html', 'app.js', 'app.css', 'error.html']:
                file_path = os.path.join(tmpdirname, file_name)
                
                # Set content type based on file extension
                content_type = 'text/html'
                if file_name.endswith('.js'):
                    content_type = 'application/javascript'
                elif file_name.endswith('.css'):
                    content_type = 'text/css'
                
                with open(file_path, 'rb') as f:
                    s3_client.upload_fileobj(
                        f,
                        bucket_name,
                        file_name,
                        ExtraArgs={'ContentType': content_type}
                    )
        
        print(f"Web application deployed to S3 bucket: {bucket_name}")
        
        # Create CloudFront invalidation
        cloudfront_client = boto3.client('cloudfront')
        cloudfront_client.create_invalidation(
            DistributionId=cloudfront_distribution,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 1,
                    'Items': ['/*']
                },
                'CallerReference': str(int(time.time()))
            }
        )
        
        print(f"CloudFront invalidation created for distribution: {cloudfront_distribution}")
        
        # Return success
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {'Status': 'Web application deployed'})

    except Exception as e:
        print(f"Error deploying web application: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': str(e)})