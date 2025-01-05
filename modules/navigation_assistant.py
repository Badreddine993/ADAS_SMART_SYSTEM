import openrouteservice
import html
import os
import re
import time
from gtts import gTTS
import pygame


class NavigationAssistant:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openrouteservice.Client(key=self.api_key)
        self.temp_dir = os.path.join(os.path.expanduser("~"), "Desktop", "temp_audio")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def text_to_speech(self, text):
        """Convert text to speech and play the audio."""
        temp_file_path = os.path.join(self.temp_dir, "temp_speech.mp3")
        tts = gTTS(text=text, lang='en')
        tts.save(temp_file_path)

        try:
            pygame.mixer.init()
            pygame.mixer.music.load(temp_file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        finally:
            try:
                os.remove(temp_file_path)
            except:
                pass

    def geocode(self, location):
        """Geocode a location into coordinates."""
        try:
            print(f"Geocoding location: {location}")
            results = self.client.pelias_search(
                text=location,
                size=1,
                validate=True
            )
            if results and 'features' in results and results['features']:
                coords = results['features'][0]['geometry']['coordinates']
                return coords
            else:
                return None
        except Exception as e:
            print(f"Geocoding error for {location}: {str(e)}")
            return None

    def get_itinerary(self, origin, destination):
        """Fetch route itinerary."""
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
                return steps
            return ["Unable to parse the route directions."]
        except openrouteservice.exceptions.ApiError as e:
            return [f"Navigation error: {str(e)}"]
        except Exception as e:
            return [f"An unexpected error occurred: {str(e)}"]

    def process_request_from_text(self, origin, destination):
        """Process request with text inputs for origin and destination."""
        try:
            if not origin or not destination:
                return "Please provide both origin and destination."

            origin_coords = self.geocode(origin)
            destination_coords = self.geocode(destination)

            if not origin_coords or not destination_coords:
                return "Could not find one or both locations. Please try again."

            itinerary = self.get_itinerary(origin_coords, destination_coords)

            if itinerary and (itinerary[0].startswith("An unexpected error") or itinerary[0].startswith("Navigation error")):
                return "I'm sorry, I couldn't calculate the route. Please try again."

            itinerary_text = " Then ".join(itinerary)
            self.text_to_speech(itinerary_text)
            return itinerary_text
        except Exception as e:
            print(f"Error in process_request_from_text: {str(e)}")
            self.text_to_speech("An error occurred while processing your request. Please try again.")
            return "An error occurred while processing your request. Please try again."
