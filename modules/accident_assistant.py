import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import json

class BreakdownAssistant:
    def __init__(self, api_key):
        self.accident_data = {}
        self.listening = True
        self.sending_to_gemini = False
        self.collecting_accident_info = False
        self.accident_prompt_step = 0

        # text-to-speech
        self.engine = pyttsx3.init()
        self.voices = self.engine.getProperty('voices')
        self.volume = self.engine.getProperty('volume')

        
        genai.configure(api_key=api_key)
        self.generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 0,
            "max_output_tokens": 8192,
        }
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
        ]
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        self.convo = self.model.start_chat(history=[])

        # Wake word and exit words
        self.wake_word = "bro"
        self.exit_words = ["stop","exit"]

    def store_accident_info(self, accident_type, description):
        self.accident_data['type'] = accident_type
        self.accident_data['description'] = description

        with open("accident_data2.json", "w") as f:
            json.dump(self.accident_data, f, indent=4)
        print("Accident data saved:", self.accident_data)

    def get_response(self, user_input):
        prompt_template = """
        You are a helpful car assistant. Based on the input, provide relevant steps to assist the user:
        don't use special characters

        User input: "{user_input}"
        """
        formatted_prompt = prompt_template.format(user_input=user_input)
        self.convo.send_message(formatted_prompt)
        return self.convo.last.text

    def listen_and_process(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source)

            try:
                print("Listening...")
                audio = recognizer.listen(source, timeout=5.0)
                response = recognizer.recognize_google(audio).lower()
                print(response)

                if any(exit_word in response for exit_word in self.exit_words):
                    self.sending_to_gemini = False
                    print("Stopped sending responses to Gemini.")
                    return

                if self.wake_word in response and not self.sending_to_gemini:
                    self.sending_to_gemini = True
                    print("Resumed sending responses to Gemini.")
                    return

                if "accident" in response or "crash" in response:
                    self.collecting_accident_info = True
                    self.accident_prompt_step = 1
                    self.speak("Can you please describe the type of accident?")
                    return

                if self.collecting_accident_info:
                    if self.accident_prompt_step == 1:
                        self.accident_type = response
                        self.accident_prompt_step = 2
                        self.speak("Can you describe the accident in more detail?")
                    elif self.accident_prompt_step == 2:
                        self.store_accident_info(self.accident_type, response)
                        self.speak("Thank you! I have saved the accident details.")
                        self.collecting_accident_info = False
                        self.accident_prompt_step = 0
                    return

                if self.sending_to_gemini:
                    response_from_gemini = self.get_response(response)
                    self.speak(response_from_gemini)

            except sr.UnknownValueError:
                print("Didn't recognize anything.")

    def speak(self, text):
        self.engine.setProperty('rate', 200)
        self.engine.setProperty('volume', self.volume)
        self.engine.setProperty('voice', self.voices[1].id)
        self.engine.say(text)
        self.engine.runAndWait()

    def run(self):
        while self.listening:
            self.listen_and_process()

# Usage
if __name__ == "__main__":
    api_key = "AIzaSyA30_7TwLq0g3YrOT-HbuT6Srvkp0Vn6l4"
    assistant = BreakdownAssistant(api_key=api_key)
    assistant.run()
