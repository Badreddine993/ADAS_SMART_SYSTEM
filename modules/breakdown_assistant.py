
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import json
import threading
import queue


class BreakdownAssistant:
    def __init__(self, api_key):
        self.accident_data = {}
        self.collecting_accident_info = False
        self.accident_prompt_step = 0

        # Text-to-Speech Engine
        self.engine = pyttsx3.init()
        self.voices = self.engine.getProperty('voices')
        self.volume = self.engine.getProperty('volume')
        self.engine.setProperty('rate', 200)
        self.engine.setProperty('voice', self.voices[1].id)

        # Speech Queue for Thread-Safe Execution
        self.speech_queue = queue.Queue()
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()

        # Gemini AI Configuration
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config={
                "temperature": 1,
                "top_p": 0.95,
                "max_output_tokens": 8192,
            },
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
            ]
        )
        self.convo = self.model.start_chat(history=[])

    # ✅ Dedicated Speech Worker
    def _speech_worker(self):
        while True:
            text = self.speech_queue.get()
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print(f"[Speech Error]: {e}")
            self.speech_queue.task_done()

    # ✅ Queue Speech Requests
    def speak(self, text):
        self.speech_queue.put(text)

    # ✅ Store Accident Information
    def store_accident_info(self, accident_type, description):
        self.accident_data['type'] = accident_type
        self.accident_data['description'] = description

        with open("accident_data2.json", "w") as f:
            json.dump(self.accident_data, f, indent=4)
        print("Accident data saved:", self.accident_data)

    # ✅ Get Response from Gemini
    def get_response(self, user_input):
        prompt_template = """
        You are a helpful car assistant. Based on the input, provide relevant steps to assist the user:
        don't use special characters

        User input: "{user_input}"
        """
        formatted_prompt = prompt_template.format(user_input=user_input)
        self.convo.send_message(formatted_prompt)
        return self.convo.last.text

    # ✅ Process Accident Request from Text Input (Web Integration)
    def process_request_from_text(self, user_input):
        try:
            if "Accident" in user_input or "crash" in user_input:
                self.collecting_accident_info = True
                self.accident_prompt_step = 1
                self.speak("Can you please describe the type of accident?")
                return "Can you please describe the type of accident?"

            if self.collecting_accident_info:
                if self.accident_prompt_step == 1:
                    self.accident_type = user_input
                    self.accident_prompt_step = 2
                    self.speak("Can you describe the accident in more detail?")
                    return "Can you describe the accident in more detail?"
                elif self.accident_prompt_step == 2:
                    self.store_accident_info(self.accident_type, user_input)
                    self.speak("Thank you! I have saved the accident details.")
                    self.collecting_accident_info = False
                    self.accident_prompt_step = 0
                    return "Thank you! I have saved the accident details."

            response_from_gemini = self.get_response(user_input)
            self.speak(response_from_gemini)
            return response_from_gemini

        except Exception as e:
            print(f"Error in process_request_from_text: {str(e)}")
            self.speak("An error occurred while processing your request. Please try again.")
            return "An error occurred while processing your request. Please try again."
