
let recognition;
let session = {};  // Keep track of conversation state
let fatigueDetectionActive = false;


function startVoiceRecognition() {
    recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false; // Restart manually after each response

    recognition.onresult = async function(event) {
        const command = event.results[0][0].transcript.trim();
        document.getElementById('response').innerText = `You said: ${command}`;
        
        // Send command to backend and handle the response
        await sendVoiceCommand(command);
    };

    recognition.onend = () => {
        // Automatically restart recognition after speech ends
        setTimeout(() => {
            recognition.start();
        }, 1000); // Small delay before restarting
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setTimeout(() => {
            recognition.start();
        }, 1000); // Restart on error after a brief delay
    };

    recognition.start();
}


// Call this on page load
document.addEventListener('DOMContentLoaded', () => {
    requestMicrophonePermission();
});

async function sendVoiceCommand(command) {
    const responseElement = document.getElementById('response');

    let startPoint = '';
    let destination = '';

    if (command.includes('navigate')) {
        startPoint = prompt("Enter the start point (if applicable):") || '';
        destination = prompt("Enter the destination (if applicable):") || '';
    }

    let response = await fetch('/voice-command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            command: command,
            start_point: startPoint,
            destination: destination,
            session: session
        })
    });

    let result = await response.json();

    // Update session state
    session = result.session || {};

    // Display and speak response
    responseElement.innerText = result.response;
    if (result.speak) {
        speakText(result.response);
    }

    // Handle next steps in conversation
    if (session.navigation_step === 'awaiting_start_point') {
        console.log("Awaiting start point...");
    } else if (session.navigation_step === 'awaiting_destination') {
        console.log("Awaiting destination...");
    } else if (session.accident_step === 'awaiting_accident_type') {
        console.log("Awaiting accident type...");
    } else if (session.accident_step === 'awaiting_accident_details') {
        console.log("Awaiting accident details...");
    } else if (!session.navigation_step && !session.accident_step) {
        console.log("Session cleared.");
    }
    // Handle map updates
    if (result.response.includes('http')) {
        document.getElementById('mapFrame').src = result.response;
        document.getElementById('mapFrame').style.display = 'block';
    }
}


function speakText(text) {
    const synth = window.speechSynthesis;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1;

    utterance.onend = () => {
        // Automatically restart recognition after speech ends
        setTimeout(() => {
            recognition.start();
        }, 1000);
    };

    synth.speak(utterance);
}


async function toggleFatigueDetection() {
    const fatigueBtn = document.getElementById('fatigueBtn');
    fatigueDetectionActive = !fatigueDetectionActive;

    const action = fatigueDetectionActive ? 'start' : 'stop';
    fatigueBtn.innerText = fatigueDetectionActive ? '🛑 Stop Fatigue Detection' : '🛡️ Start Fatigue Detection';

    let response = await fetch('/toggle-fatigue', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ action: action })
    });

    let result = await response.json();
    document.getElementById('response').innerText = result.status;

    // Reload video feed
    const videoFeed = document.getElementById('videoFeed');
    if (fatigueDetectionActive) {
        videoFeed.src = '/video-feed';
    } else {
        videoFeed.src = '';
    }

    // Text-to-Speech Feedback
    speakText(result.status);
}
async function runObjectDetection() {
    try {
        let response = await fetch('/run-object-detection', { method: 'POST' });
        let result = await response.json();

        if (result.status === 'success') {
            alert(result.message);

            const videoElement = document.getElementById('utilsVideo');
            const videoSource = document.getElementById('utilsVideoSource');

            videoSource.src = '/display-video?' + new Date().getTime(); // Prevent caching
            videoElement.style.display = 'block';
            videoElement.load();

            videoElement.onloadeddata = () => {
                console.log('Video loaded successfully.');
                videoElement.play();
            };

            videoElement.onerror = (error) => {
                console.error('Error loading the video:', error);
                alert('Failed to load the video. Check backend logs.');
            };
        } else {
            alert(`Error: ${result.message}`);
            console.error('Object Detection Error:', result.message);
        }
    } catch (error) {
        console.error('Error running object detection:', error);
        alert('An error occurred while running object detection.');
    }
}


window.onload = () => {
    startVoiceRecognition();
};

