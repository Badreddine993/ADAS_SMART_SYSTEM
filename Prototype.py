from flask import Flask, render_template, request, jsonify
import pyttsx3
import speech_recognition as sr
import google.generativeai as genai
import urllib.parse
import webbrowser
import subprocess
import re
import random
import threading
import asyncio


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# for sync
async def txt_to_spch_async(text):
    import pyttsx3
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, txt_to_spch, text)

def send_emergency_email():
    try:
        sender_email = "badreddineboukfa@gmail.com"  # Replace with your email
        sender_password = "xsibaqgaqcmsuzwt"  # Replace with your email password or app-specific password
        recipient_email = "b.badrst@gmail.com"
        
        # Email content
        subject = "Emergency Alert!"
        body = "The user has indicated they are in danger. Immediate assistance is required."
        
        # Set up the MIME structure
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect to the SMTP server and send the email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, sender_password)  # Login to the SMTP server
            server.sendmail(sender_email, recipient_email, msg.as_string())
        
        return "Emergency email sent successfully!"
    except Exception as e:
        return f"Failed to send emergency email: {e}"
# ✅ Google Gemini Configuration
genai.configure(api_key="AIzaSyD9huIFtlS1Ii8sZx7CcrBBIjjp-9saRMI")  # Replace with your API key


app = Flask(__name__)
def clean_response_text(text):
    return re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove bold markdown

# ✅ Text-to-Speech
def txt_to_spch(words):
    def speak():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 190)  # Speed of speech
            # List available voices
            voices = engine.getProperty('voices')
            
            # Choose an English voice
            for voice in voices:
                if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
            
            engine.say(words)
            engine.runAndWait()
        except Exception as e:
            print(f"[Error] TTS failed: {e}")

    # Run the speech synthesis in a separate thread
    threading.Thread(target=speak).start()

def spch_to_txt():
    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("Speak something...",end="\r")
            audio = r.listen(source, timeout=5)  # Adjust the timeout as needed
            print("Processing speech...",end="\r")
            user_input = r.recognize_google(audio).lower()
            if "link" in user_input:
                print("Please type the link...")
                txt_to_spch("Please type the link")
                user_input = input("> ").lower() 
            return user_input
    except sr.UnknownValueError:
        print("Sorry, I couldn't understand your speech.")
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
    except sr.WaitTimeoutError:
        print("No speech detected.")
    return None

# Generate Google Maps URL for iframe
def get_directions_on_maps_via_speech(start_point, destination, mode='driving'):
    # Generate a standard Google Maps directions URL
    return f"https://www.google.com/maps/dir/?api=1&origin={start_point}&destination={destination}&travelmode={mode}"






def get_gemini_response(prompt):
    try:
        print(f"[Gemini API] Prompt: {prompt}")
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error with Gemini API: {e}"


app_paths = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "camera": "explorer shell:AppsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
    "chrome": "chrome.exe",
    "mail": "https://mail.google.com/"
}

def open_app(app_name):
    try:
        app_path = app_paths.get(app_name.lower())
        if app_path:
            if app_name.lower() == 'mail':
                webbrowser.open_new_tab(app_path)
            else:
                subprocess.Popen(app_path, shell=True)
            return f"Opening {app_name}..."
        return f"Sorry, I don't know how to open {app_name}."
    except Exception as e:
        return f"Failed to open app: {e}"



def process_command(user_input, start_point=None, destination=None, mode='driving'):
    try:
        user_input = user_input.lower().strip()
        

        
        # Handle Emergency Keywords
        danger_keywords = ['help', 'emergency', 'danger', 'accident', 'urgent']
        if any(keyword in user_input for keyword in danger_keywords):
            send_email_response = send_emergency_email()
            return {"response": f"Emergency detected: {send_email_response}"}
        
        # Handle Navigation Command
        navigation_match = re.match(
            r"navigate from (.+?) to (.+?)(?: by (car|bus|walking))?", 
            user_input
        )
        
        if navigation_match:
            start_point = navigation_match.group(1).strip()
            destination = navigation_match.group(2).strip()
            mode = navigation_match.group(3).strip() if navigation_match.group(3) else 'driving'
            mode = {'car': 'driving', 'bus': 'transit', 'walking': 'walking'}.get(mode, 'driving')
            
            map_url = get_directions_on_maps_via_speech(start_point, destination, mode)
            webbrowser.open_new_tab(map_url)
            return {
                "response": f"Fetching directions from {start_point} to {destination} by {mode}.",
                "map_url": map_url
            }
            
        
        # Handle App Commands
        if user_input in ["open notepad", "open calculator", "open chrome", "open mail"]:
            app_name = user_input.replace("open ", "")
            return {"response": open_app(app_name)}
        
        # Fallback to Chat Response
        if user_input:
            return {"response": get_gemini_response(user_input)}
        
        return {"response": "Sorry, I didn't understand that."}
    
    except Exception as e:
        print(f"[ERROR] in process_command: {e}")
        return {"response": f"Error processing command: {e}"}

# # Integrating fatigue detiction with the chatbot
from playsound import playsound

def play_alert_sound():
    try:
        playsound('alert.mp3')  # Replace with your audio file path
    except Exception as e:
        print(f"Error playing sound: {e}")

import cv2
import dlib
from scipy.spatial import distance
from playsound import playsound
import threading

# Eye Aspect Ratio Calculation
def eye_aspect_ratio(eye):
    A = distance.euclidean(eye[1], eye[5])
    B = distance.euclidean(eye[2], eye[4])
    C = distance.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

# Fatigue Detection
def detect_fatigue_with_camera():
    cap = cv2.VideoCapture(0)  # Open camera
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor("/Users/badrdiscipline/Downloads/shape_predictor_68_face_landmarks.dat")
    
    EYE_AR_THRESH = 0.25
    EYE_AR_CONSEC_FRAMES = 15
    
    COUNTER = 0
    
    def play_alert():
        playsound(r'/Users/badrdiscipline/Desktop/SpeechToSpeech/wakeup.mp3')  # Replace with your audio file path
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector(gray)
        
        for face in faces:
            shape = predictor(gray, face)
            landmarks = [(shape.part(i).x, shape.part(i).y) for i in range(68)]
            
            left_eye = landmarks[36:42]
            right_eye = landmarks[42:48]
            
            left_ear = eye_aspect_ratio(left_eye)
            right_ear = eye_aspect_ratio(right_eye)
            
            ear = (left_ear + right_ear) / 2.0
            
            if ear < EYE_AR_THRESH:
                COUNTER += 1
                if COUNTER >= EYE_AR_CONSEC_FRAMES:
                    print("Fatigue detected! Please take a break.")
                    threading.Thread(target=play_alert).start()
                    COUNTER = 0
            else:
                COUNTER = 0
        
        cv2.imshow("Fatigue Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

# Test the function
detect_fatigue_with_camera()



# import pyttsx3
# import queue
# import threading

# # Global TTS Engine Initialization
# tts_engine = pyttsx3.init()
# tts_engine.setProperty('rate', 190)  # Speed of speech

# # Choose an English voice
# voices = tts_engine.getProperty('voices')
# for voice in voices:
#     if 'english' in voice.name.lower() or 'en' in voice.id.lower():
#         tts_engine.setProperty('voice', voice.id)
#         break

# # Create a Queue for TTS Requests
# tts_queue = queue.Queue()

# # TTS Worker Thread
# def tts_worker():
#     while True:
#         text = tts_queue.get()
#         if text is None:  # Sentinel to stop the worker
#             break
#         try:
#             tts_engine.say(text)
#             tts_engine.runAndWait()
#         except Exception as e:
#             print(f"[ERROR] TTS failed: {e}")
#         tts_queue.task_done()

# # Start the TTS Worker Thread
# tts_thread = threading.Thread(target=tts_worker, daemon=True)
# tts_thread.start()

# # Enqueue Text for TTS
# def txt_to_spch(text):
#     tts_queue.put(text)

# import atexit

# # Stop the TTS Worker Gracefully
# @atexit.register
# def shutdown():
#     tts_queue.put(None)
#     tts_thread.join()
# # ✅ Flask Routes

@app.route('/start-fatigue-detection', methods=['POST'])
def start_fatigue_detection():
    threading.Thread(target=detect_fatigue_with_camera).start()
    return jsonify({"response": "Fatigue detection started."})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_input = data.get('message', '').strip().lower()

        if not user_input:
            return jsonify({"response": "Please provide a valid command."})
        
        # Process Command
        result = process_command(user_input)
        
        print(f"[INFO] Generated Response: {result}")
        
        # Text-to-Speech
        txt_to_spch(clean_response_text(result.get('response', '')))
        
        return jsonify(result)
    
    except Exception as e:
        print(f"[ERROR] in /chat route: {e}")
        return jsonify({"response": f"An error occurred: {str(e)}"}), 500

    # try:
    #     data = request.json
    #     user_input = data.get('message', '').strip().lower()

    #     if not user_input:
    #         return jsonify({"response": "Please provide a valid command."})
        
    #     # Process Command
    #     result = process_command(user_input)
        
    #     print(f"[INFO] Generated Response: {result}")
        
    #     # Add text to TTS queue
    #     txt_to_spch(clean_response_text(result.get('response', '')))
        
    #     return jsonify(result)
    
    # except Exception as e:
    #     print(f"[ERROR] in /chat route: {e}")
    #     return jsonify({"response": f"An error occurred: {str(e)}"}), 500




if __name__ == '__main__':
    app.run(debug=True)