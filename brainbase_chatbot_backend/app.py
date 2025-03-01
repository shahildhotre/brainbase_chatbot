from aiohttp import web
import socketio
from openai import OpenAI
import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Initialize Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

# Initialize OpenAI client
print("OPENAI_API_KEY: ", os.getenv('OPENAI_API_KEY'))
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Get Amadeus credentials
amadeus_client_id = os.getenv('AMADEUS_CLIENT_ID')
amadeus_client_secret = os.getenv('AMADEUS_CLIENT_SECRET')

conversation_history = []

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    # Clean up any active sessions or resources for this client if needed
    # await sio.emit('disconnect_response', {
    #     'status': 'success',
    #     'message': 'Successfully disconnected'
    # }, room=sid)

@sio.event
async def chat_message(sid, data):
    try:

        global conversation_history
        conversation_history = data['messages']

        print("Conversation history: ", conversation_history)

        message = conversation_history[-1]['message'] 

        system_prompt = f'''You are a helpful trip planner assistant. your responsibility is to help the user to plan a trip using chain of thought reasoning. 
        From user input, you will identify which tasks and which Amadeus API to use out of 

        1) Flights
        2) Transports
        3) Hotels
        4) Experiences

        Example: 
        User: I want to book a flight to New York.
        You: ["Flights"]

        User: I want to book a hotel in New York.
        You: ["Hotels"]

        User: I want to book a transport from New York to Los Angeles.
        You: ["Transports"]

        User: I want to book a flight to New York and a hotel in New York.
        You: ["Flights", "Hotels"]

        User: Plan a trip from San Francisco to New York.
        You: ["Flights", "Hotels"]

        User: Hi, How are you?
        You: ["Generic"]

        Make sure your response is a list of tasks and you are selecting multiple APIs to complete the tasks out of the list.
        '''

        print("Open AI request message: ", message)
        response = client.chat.completions.create(
            model="gpt-4-0613",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.5,
            max_tokens=1000 
        )

        print(response.choices[0].message.content)

        ai_response = response.choices[0].message.content

        await sio.emit('chat_response', {
            'status': 'success',
            'message': ai_response
        })
            

        categories = eval(ai_response)

        displayed_steps = False

        print("Categories: ", categories)

        for task in categories:

            if(task.lower() == "generic"):
                print("Generic questions")
                api_response = gpt_response("You are an ai assistant. You are helpful and answer all the questions asked by the user", message)
            else: 

                system_prompt = f'''
                Your responsibility is to write a step by step plan using {message} to complete the user's request.
                
                Example:

                categories: ["Flight"]
                I'll take a following steps to book a flight for you:
                1. I'll search for flights from San Francisco to New York.
                2. I'll display the flights to you.
                2. I'll book the flight for you.
                
                categories: ["Flight", "Hotel"]
                I'll take a following steps to book a flight and a hotel for you:
                1. I'll search for flights from San Francisco to New York.
                2. I'll display the flights to you.
                3. I'll book the flight for you.
                4. I'll search for hotels in New York.
                5. I'll display the hotels to you.
                6. I'll book the hotel for you.


                Your response should be a step by step plan. like the example above.
                 
                '''

                if not displayed_steps:
                    step_by_step_response = gpt_response(system_prompt);
                    displayed_steps = True

                print("Step by step response: ", step_by_step_response)

                await sio.emit('chat_response', {
                    'status': 'success',
                    'message': step_by_step_response
                })

                if task.lower() == "flights":
                    api_response = await search_flights(conversation_history, sid)
                elif task.lower() == "hotels":
                    api_response = await search_hotels()
                elif task.lower() == "transports":
                    api_response = await search_transfers()
                elif task.lower() == "experiences":
                    api_response = await search_activities()
         
                
            print("API response: ", api_response)

            await sio.emit('chat_response', {
                'status': 'success',
                'message': api_response
            })


    except Exception as e:
        print("Error in chat_message:", str(e))  # Add explicit error logging
        await sio.emit('chat_response', {
            'status': 'error',
            'message': str(e)
        })

    # await sio.disconnect(sid)

    

    
    

async def accessTokens():

    print("Access tokens")

    url = "https://test.api.amadeus.com/v1/security/oauth2/token"

    print(amadeus_client_id, amadeus_client_secret)

    payload = f'grant_type=client_credentials&client_id={amadeus_client_id}&client_secret={amadeus_client_secret}'
    headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    access_token = response.json()['access_token']

    print(access_token)

    return access_token
    

async def search_flights(conversation_history, sid, origin="", destination="", date=""):

    # not_all_information_available = True

    # while(not_all_information_available):
    #     system_prompt = f'''
    #     You are a flight search assistant. Your responsibility is to search for information such as origin, destination and date from the conversation history {conversation_history}.

    #     if all 3 information is available, then return the information in the following format:
    #     Example
    #     {{
    #         origin: "San Francisco",
    #         destination: "New York",
    #         date: "2025-01-01"
    #     }}

    #     if any of the information is missing, then return the information in the following format:
    #     Example:
    #     {{
    #         origin: "San Francisco",
    #         destination: "New York",
    #         date: "not_available"
    #     }}

    #     Example 2:
    #     {{
    #         origin: "not_available",
    #         destination: "New York",
    #         date: "2025-01-01"
    #     }}
    #     '''

    #     response = gpt_response(system_prompt)

    #     system_prompt = f'''
    #         Help to check if all the information is available in the response {response}.

    #         if information is not available, then return the message for which information is missing.

    #         Example:
    #         Date is missing, Please provide the date.

    #         Example 2:
    #         Origin and Destination is missing, Please provide the origin and destination.

    #         Example 3:
    #         Destination is missing, Please provide the destination.

    #         If all the information is available, then return the message "All the information is available".

    #         '''

    #     follow_up_response = gpt_response(system_prompt)

    #     if "All the information is available" in follow_up_response:
    #         not_all_information_available = False

    #     await sio.emit('chat_response', {
    #         'status': 'success',
    #         'message': follow_up_response
    #     })

    #     print(response)


    access_token = await accessTokens();

    print(access_token, "flight")

    try:
        url = f"https://test.api.amadeus.com/v1/shopping/flight-destinations?origin=SFO"

        payload = {}
        files={}
        headers = {
        'Authorization': f'Bearer {access_token}'
        }

        flight_response = requests.request("GET", url, headers=headers, data=payload, files=files) 

        flight_data = flight_response.json()

        print("flight_response: ", flight_data)

        await sio.emit('chat_response', {
            'status': 'success',
            'data': flight_data['data'],
            'type': 'flight-results',
            'message': 'Flight search completed',
            'from': 'ai'
        })

        return "flight search completed"
    
    except Exception as error:
        raise Exception(str(error))

async def search_hotels(cityCode="", checkInDate="", checkOutDate=""):

    access_token = await accessTokens();

    try:
        url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city?cityCode=SFO"

        payload = {}
        headers = {
        'Authorization': f'Bearer {access_token}'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        print(response.text)

        return "hotel search completed"
    except Exception as error:
        raise Exception(str(error))

async def search_transfers(origin="", destination=""):
    try:
        return "Car booking from airport to hotel is completed"
       
    except Exception as error:
        raise Exception(str(error))

async def search_activities(latitude="", longitude=""):
    try:
        return "Activity booking is completed"
    except Exception as error:
        raise Exception(str(error))
    

def gpt_response(system_prompt, user_prompt = ""):

    response = client.chat.completions.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": system_prompt}
            # {"role": "user", "content": user_prompt}
        ],
        temperature=0.5,
        max_tokens=1000 
    )

    return response.choices[0].message.content

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8000)