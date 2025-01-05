// Show Loading Spinner
function showLoadingSpinner() {
    document.getElementById('loading-spinner').style.display = 'block';
}

function hideLoadingSpinner() {
    document.getElementById('loading-spinner').style.display = 'none';
}


async function sendMessage() {
    showLoadingSpinner();
    let userInput = document.getElementById('userInput').value;
    const responseElement = document.getElementById('response');

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: userInput })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();

        // Display chatbot response
        if (data.response) {
            responseElement.innerText = data.response;
        } else {
            responseElement.innerText = "No valid response from the server.";
        }

        // Automatically open the map in a new window/tab
        if (data.map_url) {
            window.open(data.map_url, '_blank');
        }

    } catch (error) {
        console.error('Error:', error);
        responseElement.innerText = `Error: ${error.message}`;
    } finally {
        hideLoadingSpinner();
    }
}

// Loading Spinner Control
function showLoadingSpinner() {
    document.getElementById('loading-spinner').style.display = 'block';
}

function hideLoadingSpinner() {
    document.getElementById('loading-spinner').style.display = 'none';
}






// Voice Recognition
// Voice Recognition
function startVoiceRecognition() {
    if (!('webkitSpeechRecognition' in window)) {
        alert('Your browser does not support speech recognition. Please use Chrome.');
        return;
    }

    const recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US'; // Set language
    recognition.interimResults = true; // Show live transcription
    recognition.maxAlternatives = 1;

    // Show spinner during speech
    showLoadingSpinner();

    recognition.start();

    recognition.onresult = function (event) {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript + ' ';
        }

        document.getElementById('userInput').value = transcript.trim();
    };

    recognition.onerror = function (event) {
        console.error('Speech recognition error:', event.error);
        alert('Speech recognition error: ' + event.error);
    };

    recognition.onend = function () {
        hideLoadingSpinner();
        sendMessage();
    };
}
document.getElementById('sendButton').addEventListener('click', async () => {
    const userInput = document.getElementById('userInput').value.trim();
    let origin = null;
    let destination = null;

    let response = await fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: userInput })
    });

    let result = await response.json();

    if (result.follow_up === 'origin') {
        origin = prompt("Please provide the starting point:");
        response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: "navigate", origin: origin })
        });
        result = await response.json();
    }

    if (result.follow_up === 'destination') {
        destination = prompt("Please provide the destination point:");
        response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: "navigate", origin: origin, destination: destination })
        });
        result = await response.json();
    }

    document.getElementById('response').innerText = result.response;
});

