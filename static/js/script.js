// ✅ Global Variables
let recognition;
let session = {};  // Keep track of conversation state
let fatigueDetectionActive = false;
let isRecognitionActive = false; // Prevent overlapping starts

// ✅ Start Voice Recognition
function startVoiceRecognition() {
    if (!window.webkitSpeechRecognition) {
        console.error('Speech Recognition is not supported in this browser.');
        alert('Your browser does not support Speech Recognition. Please use Google Chrome.');
        return;
    }

    recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false; // Restart manually after each response

    recognition.onstart = () => {
        isRecognitionActive = true;
        console.log('Speech recognition started.');
    };

    recognition.onresult = async function (event) {
        const command = event.results[0][0].transcript.trim();
        document.getElementById('response').innerText = `You said: ${command}`;
        
        // Send command to backend and handle the response
        await sendVoiceCommand(command);
    };

    recognition.onend = () => {
        isRecognitionActive = false;
        console.log('Speech recognition ended.');
        // Automatically restart recognition after speech ends
        setTimeout(() => {
            if (!isRecognitionActive) {
                recognition.start();
            }
        }, 1000); // Small delay before restarting
    };

    recognition.onerror = (event) => {
        isRecognitionActive = false;
        console.error('Speech recognition error:', event.error);
        // Restart only if the error was not 'aborted'
        if (event.error !== 'aborted') {
            setTimeout(() => {
                if (!isRecognitionActive) {
                    recognition.start();
                }
            }, 1000); // Restart on error after a brief delay
        }
    };

    try {
        recognition.start();
    } catch (error) {
        console.error('Failed to start speech recognition:', error);
    }
}

// ✅ Send Voice Commands to Backend
async function sendVoiceCommand(command) {
    const responseElement = document.getElementById('response');

    let startPoint = '';
    let destination = '';

    if (command.includes('navigate')) {
        startPoint = prompt("Enter the start point (if applicable):") || '';
        destination = prompt("Enter the destination (if applicable):") || '';
    }

    try {
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

        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        let result = await response.json();

        // Update session state
        session = result.session || {};

        // Display and speak response
        responseElement.innerText = result.response;
        if (result.speak) {
            speakText(result.response);
        }

        // Handle map updates
        if (result.response.includes('http')) {
            document.getElementById('mapFrame').src = result.response;
            document.getElementById('mapFrame').style.display = 'block';
        }
    } catch (error) {
        console.error('Error sending voice command:', error);
        responseElement.innerText = 'An error occurred. Please try again.';
    }
}

// ✅ Text-to-Speech Function
function speakText(text) {
    const synth = window.speechSynthesis;
    synth.cancel(); // Stop ongoing speech if any
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1;

    utterance.onend = () => {
        // Automatically restart recognition after speech ends
        setTimeout(() => {
            if (!isRecognitionActive) {
                recognition.start();
            }
        }, 1000);
    };

    synth.speak(utterance);
}

// ✅ Toggle Fatigue Detection
async function toggleFatigueDetection() {
    const fatigueBtn = document.getElementById('fatigueBtn');
    fatigueDetectionActive = !fatigueDetectionActive;

    const action = fatigueDetectionActive ? 'start' : 'stop';
    fatigueBtn.innerText = fatigueDetectionActive ? '🛑 Stop Fatigue Detection' : '🛡️ Start Fatigue Detection';

    try {
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
        videoFeed.src = fatigueDetectionActive ? '/video-feed' : 'about:blank';

        // Text-to-Speech Feedback
        speakText(result.status);
    } catch (error) {
        console.error('Error toggling fatigue detection:', error);
        document.getElementById('response').innerText = 'Failed to toggle fatigue detection.';
    }
}

// ✅ Lancer la détection d'objets et afficher la vidéo générée
function runObjectDetection() {
    fetch('/run-object-detection', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);

                // Affiche la vidéo générée
                const videoElement = document.getElementById('utilsVideo');
                const videoSource = document.getElementById('utilsVideoSource');
                
                videoSource.src = '/display-video';
                videoElement.style.display = 'block';
                videoElement.load();
                videoElement.play();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while running object detection.');
        });
}


// ✅ Initialize Voice Recognition on Page Load
window.onload = () => {
    startVoiceRecognition();
};
