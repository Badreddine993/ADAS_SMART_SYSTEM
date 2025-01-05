from flask import Flask, render_template, jsonify, request, Response, send_file
from modules import NavigationAssistant, BreakdownAssistant
import threading
import cv2
import time
import pygame
from facial_tracking.facialTracking import FacialTracker
import facial_tracking.conf as conf
import os
# Initialize Flask App
app = Flask(__name__)

# ✅ Navigation and Breakdown Assistants Initialization
LOCATION_API_KEY = "5b3ce3597851110001cf6248f60a658be95e4cee9f49f304ad8ad65d"
GEMINI_API_KEY = "AIzaSyAhNAU0icDpLsTGZ_7HXjMiqoogyW-Z93Y" #"AIzaSyA30_7TwLq0g3YrOT-HbuT6Srvkp0Vn6l4"
navigation_assistant = NavigationAssistant(LOCATION_API_KEY)
breakdown_assistant = BreakdownAssistant(GEMINI_API_KEY)
@app.route('/run-object-detection', methods=['POST'])
def run_object_detection():
    # Exécuter le script de détection d'objets
    try:
        import subprocess
        subprocess.run(['python', 'LIDAR-CAMERA.py'], check=True)
        return jsonify({"status": "success", "message": "Object detection completed. Video is ready to display."})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/display-video')
def display_video():
    try:
        return send_file('static/videos/lidar_frame_stack.mp4', mimetype='video/mp4')
    except Exception as e:
        print(f"Error serving video: {str(e)}")
        return Response(f"Error: {str(e)}", status=500)

    
# ✅ Audio Configuration for Fatigue Detection
pygame.mixer.init()
EYE_CLOSED_ALERT = r"sound/siren-alert-96052.mp3"
YAWN_ALERT = r"sound/siren-alert-96052.mp3"
eye_alert_sound = pygame.mixer.Sound(EYE_CLOSED_ALERT)
yawn_alert_sound = pygame.mixer.Sound(YAWN_ALERT)

# ✅ Fatigue Detection State Variables
fatigue_detection_active = False
fatigue_thread = None
frame_buffer = None  # Shared frame buffer
stop_stream = threading.Event()  # Use threading Event for better control


# ✅ Utility Function: Play Sound
def play_sound_for_duration(sound, duration):
    sound.play()
    start_time = time.time()
    while time.time() - start_time < duration:
        time.sleep(0.1)
    sound.stop()


# ✅ Fatigue Detection Thread
def fatigue_detection():
    global fatigue_detection_active, frame_buffer
    cap = cv2.VideoCapture(conf.CAM_ID)
    cap.set(3, conf.FRAME_W)
    cap.set(4, conf.FRAME_H)
    facial_tracker = FacialTracker()
    eye_alert_triggered = False
    yawn_alert_triggered = False

    stop_stream.clear()  # Reset stop flag

    while fatigue_detection_active and not stop_stream.is_set():
        success, frame = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            continue

        facial_tracker.process_frame(frame)
        frame = cv2.flip(frame, 1)
        frame_buffer = frame  # Update shared buffer

        if facial_tracker.detected:
            if facial_tracker.eyes_status == "eye closed" and not eye_alert_triggered:
                play_sound_for_duration(eye_alert_sound, 5)
                eye_alert_triggered = True
            elif facial_tracker.eyes_status != "eye closed":
                eye_alert_triggered = False

            if facial_tracker.yawn_status == "yawning" and not yawn_alert_triggered:
                play_sound_for_duration(yawn_alert_sound, 5)
                yawn_alert_triggered = True
            elif facial_tracker.yawn_status != "yawning":
                yawn_alert_triggered = False

        time.sleep(0.05)  # Avoid CPU overload

    cap.release()
    frame_buffer = None
    stop_stream.set()


# ✅ Start/Stop Fatigue Detection
@app.route('/toggle-fatigue', methods=['POST'])
def toggle_fatigue():
    global fatigue_detection_active, fatigue_thread

    action = request.json.get('action')
    if action == 'start' and not fatigue_detection_active:
        fatigue_detection_active = True
        fatigue_thread = threading.Thread(target=fatigue_detection)
        fatigue_thread.start()
        return jsonify({"status": "Fatigue detection started"})

    if action == 'stop' and fatigue_detection_active:
        fatigue_detection_active = False
        stop_stream.set()
        if fatigue_thread:
            fatigue_thread.join()
        return jsonify({"status": "Fatigue detection stopped"})

    return jsonify({"status": "Invalid action or already in the requested state"})


# ✅ Video Stream Generator
def generate_frames():
    global frame_buffer
    while fatigue_detection_active and not stop_stream.is_set():
        if frame_buffer is not None:
            try:
                # Encode frame as JPEG
                success, buffer = cv2.imencode('.jpg', frame_buffer)
                if not success:
                    print("Failed to encode frame")
                    continue
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                print(f"Error in generate_frames: {e}")
                break
        time.sleep(0.05)




@app.route('/video-feed')
def video_feed():
    if not fatigue_detection_active:
        return Response("<h3>⚠️ Fatigue detection is not active. Please start it first.</h3>",
                        mimetype='text/html')
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
    


# ✅ Voice Command Route
@app.route('/voice-command', methods=['POST'])
def voice_command():
    data = request.json
    user_input = data.get('command', '').lower()
    session = data.get('session', {})  # Maintain state between requests

    ## 🚗 **Navigation Assistant**
    if user_input == 'one' and 'navigation_step' not in session:
        session['navigation_step'] = 'awaiting_start_point'
        response = "Navigation Assistant activated. Please say your start point."
        return jsonify({"response": response, "speak": True, "session": session})

    if session.get('navigation_step') == 'awaiting_start_point' and user_input:
        session['start_point'] = user_input
        session['navigation_step'] = 'awaiting_destination'
        response = f"Start point set to {user_input}. Please say your destination."
        return jsonify({"response": response, "speak": True, "session": session})

    if session.get('navigation_step') == 'awaiting_destination' and user_input:
        session['destination'] = user_input
        start_point = session['start_point']
        destination = session['destination']
        
        steps = navigation_assistant.get_itinerary(
            navigation_assistant.geocode(start_point),
            navigation_assistant.geocode(destination)
        )
        response = f"Route from {start_point} to {destination}: " + " Then ".join(steps)
        session.clear()
        return jsonify({"response": response, "speak": True, "session": session})

    ## ⚠️ **Breakdown Assistant with Gemini Integration**
    if user_input == 'two' and 'accident_step' not in session:
        session['accident_step'] = 'awaiting_accident_type'
        response = "Breakdown Assistant activated. Can you please describe the type of accident?"
        return jsonify({"response": response, "speak": True, "session": session})

    if session.get('accident_step') == 'awaiting_accident_type' and user_input:
        session['accident_type'] = user_input
        session['accident_step'] = 'awaiting_accident_details'
        response = "Got it. Can you describe the accident in more detail?"
        return jsonify({"response": response, "speak": True, "session": session})

    if session.get('accident_step') == 'awaiting_accident_details' and user_input:
        accident_type = session['accident_type']
        accident_details = user_input
        
        # Store accident information
        breakdown_assistant.store_accident_info(accident_type, accident_details)
        
        # Generate solution using Gemini
        gemini_prompt = f"""
        You are an automotive breakdown assistant. Based on the following accident details, provide clear and actionable advice:

        Accident Type: {accident_type}
        Details: {accident_details}
        """
        
        solution = breakdown_assistant.get_response(gemini_prompt)
        
        session.clear()
        
        response = f"Thank you! I have saved the accident details.\nGemini Suggests: {solution}"
        return jsonify({"response": response, "speak": True, "session": session})

    ## Default Fallback
    if user_input == '3':
        response = "Exiting the system. Goodbye!"
    else:
        response = breakdown_assistant.get_response(user_input)

    return jsonify({"response": response, "speak": True, "session": session})



@app.route('/')
def index():
    return render_template('index.html')



if __name__ == '__main__':
    app.run(debug=True, threaded=True)
