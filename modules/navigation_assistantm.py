import pygame
import speech_recognition as sr
import openrouteservice
from gtts import gTTS
import html
import os
import re
import time


class NavigationAssistant:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openrouteservice.Client(key=self.api_key)
        self.temp_dir = os.path.join(os.path.expanduser("~"), "Desktop", "temp_audio")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def extract_locations(self, user_input):
        match = re.search(r'from (.+?) to (.+)', user_input, re.IGNORECASE)
        if match:
            origin = match.group(1).strip()
            destination = match.group(2).strip()
            return origin, destination
        return None, None

    def speech_to_text_realtime(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("Listening... Speak into the microphone.")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                text = recognizer.recognize_google(audio)
                print(f"You said: {text}")
                return text
            except sr.WaitTimeoutError:
                print("No speech detected")
                return None
            except sr.UnknownValueError:
                print("Could not understand audio")
                return None
            except sr.RequestError as e:
                print(f"Could not request results; {e}")
                return None

    def play_audio(self, file_path):
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    def text_to_speech(self, text):
        temp_file_path = os.path.join(self.temp_dir, "temp_speech.mp3")
        tts = gTTS(text=text, lang='en')
        tts.save(temp_file_path)

        try:
            self.play_audio(temp_file_path)
        finally:
            try:
                os.remove(temp_file_path)
            except:
                pass

    def geocode(self, location):
        try:
            print(f"Geocoding location: {location}")
            results = self.client.pelias_search(
                text=location,
                size=1,
                validate=True
            )

            if results and 'features' in results and results['features']:
                coords = results['features'][0]['geometry']['coordinates']
                print(f"Successfully geocoded {location} to coordinates: {coords}")
                return coords
            else:
                print(f"No coordinates found for location: {location}")
                return None

        except Exception as e:
            print(f"Geocoding error for {location}: {str(e)}")
            return None

    def get_itinerary(self, origin, destination):
        try:
            print(f"Requesting directions for coordinates: {origin} to {destination}")

            coordinates = [origin, destination]
            route = self.client.directions(
                coordinates=coordinates,
                profile='driving-car',
                format='json',
                instructions=True,
                language='en'
            )

            if 'routes' in route and route['routes']:
                steps = [
                    html.unescape(step['instruction'])
                    for step in route['routes'][0]['segments'][0]['steps']
                ]
                print(f"Successfully extracted {len(steps)} navigation steps")
                return steps

            print("Invalid route response format")
            return ["Unable to parse the route directions."]

        except openrouteservice.exceptions.ApiError as e:
            print(f"OpenRouteService API Error: {str(e)}")
            return [f"Navigation error: {str(e)}"]
        except Exception as e:
            print(f"Unexpected error in get_itinerary: {str(e)}")
            return [f"An unexpected error occurred: {str(e)}"]

    def process_request(self):
        try:
            print("Listening for your command...")
            user_input = self.speech_to_text_realtime()

            if not user_input:
                self.text_to_speech("I couldn't understand your speech. Please try again.")
                return

            origin, destination = self.extract_locations(user_input)

            if not origin or not destination:
                self.text_to_speech("I couldn't understand your origin and destination. Please try again.")
                return

            print(f"Origin: {origin}, Destination: {destination}")

            start_time = time.time()
            origin_coords = self.geocode(origin)
            destination_coords = self.geocode(destination)
            print(f"Geocoding took {time.time() - start_time:.2f} seconds")

            if not origin_coords or not destination_coords:
                self.text_to_speech("Could not find one or both locations. Please try again.")
                return

            start_time = time.time()
            itinerary = self.get_itinerary(origin_coords, destination_coords)
            print(f"Route calculation took {time.time() - start_time:.2f} seconds")

            if itinerary and itinerary[0].startswith("An unexpected error") or itinerary[0].startswith("Navigation error"):
                self.text_to_speech("I'm sorry, I couldn't calculate the route. Please try again.")
                return

            itinerary_text = " Then ".join(itinerary)
            self.text_to_speech(itinerary_text)

        except Exception as e:
            print(f"Error in process_request: {str(e)}")
            self.text_to_speech("An error occurred while processing your request. Please try again.")


# Example usage
api_key = "5b3ce3597851110001cf6248f60a658be95e4cee9f49f304ad8ad65d"
assistant = NavigationAssistant(api_key)
assistant.process_request()
