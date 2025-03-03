from aiohttp import web
import socketio
from openai import OpenAI
import os
from dotenv import load_dotenv
import requests
import asyncio

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
task_metadata = {}

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.event
async def chat_message(sid, data):
    try:
        global conversation_history, task_metadata
        conversation_history = data['messages']
        
        # Get the latest message's conversation ID
        conversation_id = conversation_history[-1].get('conversation_id')
        
        # Check if this is a sheet message (child conversation)
        is_sheet_message = conversation_id.startswith('child_')
        parent_conversation_id = conversation_history[-1].get('parent_conversation_id')

        if is_sheet_message:
            print(f"Processing sheet message for flight conversation: {conversation_id}")
            # Handle sheet-specific logic here
            # The context will already include flight details from the original emit
            flight_context = data.get('context', {}).get('flightDetails')
            hotel_context = data.get('context', {}).get('hotelDetails')
            if flight_context:
                print(f"Flight context available: {flight_context}")
                follow_up_response_msg = follow_up_response(flight_context, conversation_history[-1]['message'], conversation_id)


            if hotel_context:
                print(f"Hotel context available: {hotel_context}")
                follow_up_response_msg = follow_up_response(hotel_context, conversation_history[-1]['message'], conversation_id)
                print("Follow up response msg: ", follow_up_response_msg)

            if(follow_up_response_msg != "booking_completed"):
                await sio.emit('chat_response', {
                'status': 'success',
                    'message': follow_up_response_msg,
                    'conversation_id': conversation_id
                })
                return

            await sio.emit('chat_response', {
                'status': 'success',
                'message': "Booking Completed. Thank you for using Brainbase",
                'conversation_id': conversation_id
            })

            current_task = task_metadata[parent_conversation_id]['current_task']
            await sio.emit('chat_response', {
                'status': 'success',
                'message': f"{current_task} booking is completed",
                'conversation_id': parent_conversation_id
            })

            print("Parent conversation id: ", parent_conversation_id)

            task_metadata[parent_conversation_id]['categories_count'] = task_metadata[parent_conversation_id]['categories_count'] - 1
            task_metadata[parent_conversation_id]['current_status'] = False

            if task_metadata[parent_conversation_id]['categories_count'] == 0:
                await sio.emit('chat_response', {
                    'status': 'success',
                    'message': "All tasks completed",
                    'conversation_id': parent_conversation_id
                })

                    

                task_metadata[parent_conversation_id]['step_by_step']['completed'] = False
                task_metadata[parent_conversation_id]['generic']['completed'] = False
                task_metadata[parent_conversation_id]['step_by_step']['data'] = None
                task_metadata[parent_conversation_id]['generic']['data'] = None
                task_metadata[parent_conversation_id]['flights']['completed'] = False
                task_metadata[parent_conversation_id]['hotels']['completed'] = False
                task_metadata[parent_conversation_id]['transports']['completed'] = False
                task_metadata[parent_conversation_id]['experiences']['completed'] = False
            else:
                # Get the next task to process
                categories = eval(task_metadata[parent_conversation_id]['ai_response'])
                
                # Find the next task after the current one
                try:
                    current_index = categories.index(current_task.capitalize())
                    if current_index + 1 < len(categories):
                        next_task = categories[current_index + 1]
                        api_response = await process_task(next_task, conversation_history, sid, parent_conversation_id, categories, task_metadata)
                        
                except ValueError:
                    print(f"Current task {current_task} not found in categories")

                   
            return
        else:   
            print(f"Processing main chat message: {conversation_id}")
            # Continue with existing main chat logic
        
        

        # Initialize or reset task metadata for new conversation
        conversation_id = conversation_history[-1].get('conversation_id')
        # parent_conversation_id = conversation_history[-1].get('parent_conversation_id')
        if conversation_id not in task_metadata and 'child' not in conversation_id:
            task_metadata[conversation_id] = {
                'flights': {'completed': False, 'data': None},
                'hotels': {'completed': False, 'data': None},
                'transports': {'completed': False, 'data': None},
                'experiences': {'completed': False, 'data': None},
                'step_by_step': {'completed': False, 'data': None},
                'generic': {'completed': False, 'data': None},
                'current_status': False,
                'ai_response': None, 
                'flight_search_completed': False,
                'categories_count': 0,
                'origin': "",
                'destination': "",
                'date': "",
                'current_task': ""
            }
        

        print("Conversation history: ", conversation_history)

        message = conversation_history[-1]['message'] 

        if task_metadata[conversation_id]['current_status'] == False:
            ai_response = await identify_categories(message, conversation_history, sid, conversation_id)
            categories = eval(ai_response)
            task_metadata[conversation_id]['categories_count'] = len(categories)
            task_metadata[conversation_id]['ai_response'] = ai_response
            task_metadata[conversation_id]['current_status'] = True
        else:
            ai_response = task_metadata[conversation_id]['ai_response']
            categories = eval(ai_response)
        
        if contains_generic(categories):
            if not task_metadata[conversation_id]['generic']['completed']:
                print("Generic questions")

                system_prompt = f'''

                You are an travel planning assistant designed to help the user to plan a trip. Sometime you will be asked to answer questions. Your response for the question should be max 1-2 sentences.

                Message: Hello
                Response: Hello! How can I help you with your trip planning?

                Message: What do you do?
                Response: I am an travel planning assistant designed to help the user to plan a trip.

                Message: What is your name?
                Response: I am Brainbase.

                I want only the response to the question.
                '''

                api_response = generic_gpt_response(system_prompt, message)

                await sio.emit('chat_response', {
                    'status': 'success',
                    'message': api_response,
                    'conversation_id': conversation_id,
                    'from': 'ai',
                })

                task_metadata[conversation_id]['current_status'] = False
                task_metadata[conversation_id]['categories_count'] = task_metadata[conversation_id]['categories_count'] - 1
        else:
            if not task_metadata[conversation_id]['step_by_step']['completed']:
                step_by_step_response = await get_step_by_step_response(categories, sid, conversation_id)
                task_metadata[conversation_id]['step_by_step']['completed'] = True
                task_metadata[conversation_id]['step_by_step']['data'] = step_by_step_response
                task_metadata[conversation_id]['generic']['completed'] = True
                task_metadata[conversation_id]['generic']['data'] = ""


            for task in categories:
                api_response = await process_task(task, conversation_history, sid, conversation_id, categories, task_metadata)
                if api_response:
                    await sio.emit('chat_response', {
                        'status': 'success',
                        'message': api_response,
                        'conversation_id': conversation_id
                    })
                return

        if task_metadata[conversation_id]['categories_count'] == 0:

            task_metadata[conversation_id]['step_by_step']['completed'] = False
            task_metadata[conversation_id]['generic']['completed'] = False
            task_metadata[conversation_id]['step_by_step']['data'] = None
            task_metadata[conversation_id]['generic']['data'] = None

            print("Task metadata: ", task_metadata)

            await sio.emit('chat_response', {
                'status': 'success',
                'message': "All tasks completed",
                'conversation_id': conversation_id
            })


            

        task_metadata[conversation_id]['transports']['completed'] = True
        task_metadata[conversation_id]['experiences']['completed'] = True

            
    except Exception as e:
        print("Error in chat_message:", str(e))  # Add explicit error logging
        await sio.emit('chat_response', {
            'status': 'error',
            'message': str(e),
            'conversation_id': conversation_id
        })


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
    

def validate_task_info_response(response, category):
    """
    Validates that the GPT response is in the correct format for flight information.
    Returns (bool, dict): Tuple of (is_valid, parsed_response)
    """
    try:
        # Try to evaluate the response string as a dictionary
        response_dict = eval(response)
        
        # Check if it's a dictionary
        if not isinstance(response_dict, dict):
            print("Response is not a dictionary")
            return False, None
            
        # Check if all required keys are present
        if category == "flights":
            required_keys = {'origin', 'destination', 'date'}
        elif category == "hotels":
            required_keys = {'destination', 'date'}
        elif category == "return_journey":
            required_keys = {'return_journey'}
       

        if not all(key in response_dict for key in required_keys):
            print("Missing required keys")
            return False, None
            
        # Check if values are strings
        if not all(isinstance(response_dict[key], str) for key in required_keys):
            print("Invalid value types")
            return False, None
            
        return True, response_dict
        
    except Exception as e:
        print(f"Failed to parse response: {e}")
        return False, None


async def search_flights(conversation_history, sid, conversation_id, categories, task_metadata, origin="", destination="", date=""):
    print("Search flights")
    not_all_information_available = True

    while(not_all_information_available):
        system_prompt = f'''
            You are a flight search assistant. Your responsibility is to search for information such as origin, destination and date from the use conversation history and respond in the following format.

            if all 3 information is available, then return the information in the following json format:
            Response Example:
            {{
                "origin": "San Francisco",
                "destination": "New York",
                "date": "2025-01-01",
            }}

            if any of the information is missing, then return the information in the following json format:
            Response Example:
            {{
                "origin": "San Francisco",
                "destination": "not_available",
                "date": "2025-01-01",
            }}

            Response Example:
            {{
                "origin": "San Francisco",
                "destination": "not_available",
                "date": "not_available",
            }}  

            Rule: Stick with the above format, no other response is allowed. You should not ask any questions.
            '''
            
        formatted_messages = []
        for msg in conversation_history:
            if isinstance(msg, dict) and 'message' in msg:
                # Skip messages containing card data or flight results
                if not isinstance(msg['message'], dict) and msg.get('type') != 'flight-result':
                    formatted_messages.append(msg['message'])
        
        conversation_text = "\n".join(formatted_messages)
        
        response = gpt_response(system_prompt, conversation_text)

        print("Response: ", response)
        is_valid, flight_info = validate_task_info_response(response, "flights")
        
        if not is_valid:
            print("Invalid response format, retrying...")
            continue

        print("Flight info response:", response)

        if "not_available" in flight_info['origin'] or "not_available" in flight_info['destination'] or "not_available" in flight_info['date']:
            system_prompt = f'''
            Based on this user response:
            Create a clear question asking the user to provide the missing information.
            Only ask for the missing fields, one at a time.
            '''
                
            question = gpt_response(system_prompt, response)
            
            # Send question to user and wait for response
            await sio.emit('chat_response', {
                'status': 'success',
                'message': question,
                'requires_input': True,
                'input_type': 'flight_info',
                'conversation_id': conversation_id
            })

            return "Flight information is required"
                
        else:
            not_all_information_available = False
            flight_info = eval(response)
            print("Complete flight info:", flight_info)

            origin = flight_info['origin']
            destination = flight_info['destination']
            date = flight_info['date']

            task_metadata[conversation_id]['origin'] = origin
            task_metadata[conversation_id]['destination'] = destination
            task_metadata[conversation_id]['date'] = date

    # ReturnFlight = True
    # while(ReturnFlight == True):

    #     system_prompt = f'''

    #         You are a flight search assistant. Your responsibility is to search for return journey information from the user conversation history and respond in the following format.

    #         if return journey is required, then return the information in the following json format:
    #         Response Example:
    #         {{
    #             "return_journey": "yes"
    #         }}

    #         if return journey is not required, then return the information in the following json format:
    #         Response Example:
    #         {{
    #             "return_journey": "no"
    #         }}

    #         Rule: Stick with the above format, no other response is allowed. You should not ask any questions.
    #     '''

    #     formatted_messages = []
    #     for msg in conversation_history:
    #         if isinstance(msg, dict) and 'message' in msg:
    #             formatted_messages.append(msg['message'])
        
    #     conversation_text = "\n".join(formatted_messages)

    #     response = gpt_response(system_prompt, conversation_text)

    #     print("Response: ", response)

    #     is_valid, return_journey = validate_task_info_response(response, "return_journey")

    #     if not is_valid:
    #         print("Invalid response format, retrying...")
    #         continue

    #     if return_journey == "yes":

    #         system_prompt = f''' Ask for return date
        


            # Now that we have all information, perform the actual flight search

    try:
        if task_metadata[conversation_id]['flight_search_completed'] == False:

            access_token = await accessTokens();

            print(access_token, "flight")

            url = f"https://test.api.amadeus.com/v2/shopping/flight-offers?originLocationCode={origin.upper()}&destinationLocationCode={destination.upper()}&departureDate={date}&adults=1&nonStop=true&currencyCode=USD"

            payload = {}
            files={}
            headers = {
            'Authorization': f'Bearer {access_token}'
            }

            flight_response = requests.request("GET", url, headers=headers, data=payload, files=files) 

            flight_data = flight_response.json()

            print("flight_response: ", flight_data)

            # Validate flight data structure
            if isinstance(flight_data, dict) and 'data' in flight_data:
                await sio.emit('chat_response', {
                    'status': 'success',
                    'data': flight_data['data'],
                    'type': 'flight-results',
                    'message': 'Flight search completed',
                    'from': 'ai',
                    'conversation_id': conversation_id
                })

                await sio.emit('chat_response', {
                'status': 'success',
                'message': "Flight search is completed please select a flight to book",
                'conversation_id': conversation_id
            })

            else:
                await sio.emit('chat_response', {
                    'status': 'error',
                    'message': 'No flight data available, please try again',
                    'type': 'flight-results',
                    'from': 'ai',
                    'conversation_id': conversation_id
                })

            task_metadata[conversation_id]['flights']['completed'] = True
            task_metadata[conversation_id]['flights']['data'] = flight_data

            
            task_metadata[conversation_id]['flight_search_completed'] = True

            return "flight search completed"

        else:

            await sio.emit('chat_response', {
                'status': 'success',
                'message': "Flight booking is completed",
                'conversation_id': conversation_id
            })

            return "flight booked"



    
    
    except Exception as error:
        raise Exception(str(error))

    # finally:
    #     # Remove the event handler
    #     sio.handlers.pop('flight_info_response', None)
    # return "Flight search completed successfully"

async def search_hotels(conversation_history, sid, conversation_id, categories, task_metadata, destination="", date=""):

    access_token = await accessTokens();

    destination = task_metadata[conversation_id]['destination']
    date = task_metadata[conversation_id]['date']

    await sio.emit('chat_response', {
        'status': 'success',
        'message': "Now booking hotel in destination",
        'conversation_id': conversation_id
    })
    not_all_information_available = False

    if destination == "" or date == "":
        not_all_information_available = True

    while(not_all_information_available):

        system_prompt = f'''
            You are a hotel search assistant. Your responsibility is to search for information such as destination and date from the use conversation history and respond in the following format.

            if all 2 information is available, then return the information in the following json format:
            Response Example:
            {{
                "destination": "JFK",
                "date": "2025-01-01"
            }}

            if any of the information is missing, then return the information in the following json format:
            Response Example:
            {{
                "destination": "JFK",
                "date": "not_available"
            }}  

            Rule: Stick with the above format, no other response is allowed. You should not ask any questions.  
        '''

        formatted_messages = []
        for msg in conversation_history:
            if isinstance(msg, dict) and 'message' in msg:
                # Skip messages containing card data or flight results
                if not isinstance(msg['message'], dict) and msg.get('type') != 'flight-result':
                    formatted_messages.append(msg['message'])
        
        conversation_text = "\n".join(formatted_messages)
        
        response = gpt_response(system_prompt, conversation_text)

        print("Response: ", response)
        is_valid, hotel_info = validate_task_info_response(response, "hotels")

        if not is_valid:
            print("Invalid response format, retrying...")
            continue

        print("Hotel info response:", response)

        if "not_available" in hotel_info['destination'] or "not_available" in hotel_info['date']:
            system_prompt = f'''
            Based on this user response:
            Create a clear question asking the user to provide the missing information.
            Only ask for the missing fields, one at a time.
            '''
                
            question = gpt_response(system_prompt, response)
            
            # Send question to user and wait for response
            await sio.emit('chat_response', {
                'status': 'success',
                'message': question,
                'requires_input': True,
                'input_type': 'hotel_info',
                'conversation_id': conversation_id
            })

            return "Hotel information is required"

        else:
            not_all_information_available = False
            hotel_info = eval(response)
            print("Complete hotel info:", hotel_info)

            destination = hotel_info['destination']
            date = hotel_info['date']

            task_metadata[conversation_id]['destination'] = destination
            task_metadata[conversation_id]['date'] = date

     

    try:
        url = f"https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city?cityCode={destination.upper()}"

        payload = {}
        headers = {
        'Authorization': f'Bearer {access_token}'
        }

        hotel_response = requests.request("GET", url, headers=headers, data=payload)

        print(hotel_response.text)

        hotel_data = hotel_response.json()

        task_metadata[conversation_id]['hotels']['completed'] = True
        task_metadata[conversation_id]['hotels']['data'] = hotel_data

        if isinstance(hotel_data, dict) and 'data' in hotel_data:
            await sio.emit('chat_response', {
                'status': 'success',
                'data': hotel_data['data'],
                'type': 'hotel-results',
                'message': 'Hotel search completed',
                'from': 'ai',
                'conversation_id': conversation_id
            })

            await sio.emit('chat_response', {
                'status': 'success',
                'message': "Hotel search is completed please select a hotel to book",
                'conversation_id': conversation_id
            })

        else:
            await sio.emit('chat_response', {
                'status': 'error',
                'message': 'No hotel data available, please try again',
                'type': 'hotel-results',
                'from': 'ai',
                'conversation_id': conversation_id
            })

        return "hotel search completed"
    except Exception as error:
        raise Exception(str(error))

async def search_transfers(conversation_id, origin="", destination=""):
    try:
        await sio.emit('chat_response', {
            'status': 'success',
            'message': "Now booking car from airport to hotel",
            'conversation_id': conversation_id
        })



        await sio.emit('chat_response', {
            'status': 'success',
            'message': "Car booking from airport to hotel is completed",
            'conversation_id': conversation_id
        })

        return "Car booking from airport to hotel is completed"
       
    except Exception as error:
        raise Exception(str(error))

async def search_activities(latitude="", longitude=""):
    try:
        return "Activity booking is completed"
    except Exception as error:
        raise Exception(str(error))
    

def gpt_response(system_prompt, user_prompt):
    # Initialize messages with system prompt
    messages = [{"role": "system", "content": system_prompt}]
    
    # Handle conversation history if user_prompt is a list of message objects
    if isinstance(user_prompt, list):
        if isinstance(user_prompt[0], dict) and 'role' in user_prompt[0]:
            # If it's already in the correct format with roles
            messages.extend(user_prompt)
        else:
            # If it's just a list of strings, join them as user messages
            messages.append({"role": "user", "content": "\n".join(user_prompt)})
    else:
        # Single string input
        messages.append({"role": "user", "content": user_prompt})

    response = client.chat.completions.create(
        model="gpt-4-0613",
        messages=messages,
        temperature=0.5,
        max_tokens=1000 
    )

    return response.choices[0].message.content

def generic_gpt_response(system_prompt, user_prompt = ""):

    response = client.chat.completions.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.5,
        max_tokens=1000 
    )

    return response.choices[0].message.content

def contains_generic(strings):
    return any("generic" in s.lower() for s in strings)


async def get_step_by_step_response(categories, sid, conversation_id):
    system_prompt = f'''
        Your responsibility is to write a step by step plan using categoriesto complete the user's request.
        
        Example:

        categories: ["Flight"]
        Response:
        I'll take a following steps to book a flight for you: \n
        1. I'll search for flights from origin to destination. \n
        2. I'll display the flights to you. \n
        3. I'll book the flight for you. \n

        categories: ["Flight", "Hotel"]
        Response:
        I'll take a following steps to book a flight and a hotel for you: \n
        1. I'll search for flights from origin to destination. \n
        2. I'll display the flights to you. \n
        3. I'll book the flight for you. \n
        4. I'll search for hotels in destination. \n
        5. I'll display the hotels to you. \n
        6. I'll book the hotel for you. \n


        Your response should be a step by step plan. like the example above only response nothing else. You should stick to flight booking if message is related to flight.
        You should stick to hotel booking if message is related to hotel. dont assume anything.


            
        '''

    step_by_step_response = gpt_response(system_prompt, categories);

    await sio.emit('chat_response', {
        'status': 'success',
        'message': step_by_step_response,
        'conversation_id': conversation_id,
        'from': 'ai',
        'type': 'step_by_step_response'
    })

    return step_by_step_response


async def identify_categories(message, conversation_history, sid, conversation_id):

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
        'message': ai_response,
        'conversation_id': conversation_id
    })

    return ai_response

async def process_task(task, conversation_history, sid, conversation_id, categories, task_metadata):
    task_lower = task.lower()
    print("Task: ", task_lower)
    
    if task_lower == "flights" and not task_metadata[conversation_id]['flights']['completed']:
        print("I am calling search flights")
        task_metadata[conversation_id]['current_task'] = "flights"
        await search_flights(conversation_history, sid, conversation_id, categories, task_metadata)
        return
        
    elif task_lower == "hotels" and not task_metadata[conversation_id]['hotels']['completed']:
        task_metadata[conversation_id]['current_task'] = "hotels"
        await search_hotels(conversation_history, sid, conversation_id, categories, task_metadata)
        return
    
    elif task_lower == "transports" and not task_metadata[conversation_id]['transports']['completed']:
        task_metadata[conversation_id]['current_task'] = "transports"
        await search_transfers(conversation_id)
        task_metadata[conversation_id]['transports']['completed'] = True
        return 
        
    elif task_lower == "experiences" and not task_metadata[conversation_id]['experiences']['completed']:
        task_metadata[conversation_id]['current_task'] = "experiences"
        await search_activities()
        task_metadata[conversation_id]['experiences']['completed'] = True
        return 
    
    return

def follow_up_response(context, user_message, conversation_id):

    system_prompt = f'''

        You are an AI assistant. Your responsibility is to user context {context}  to answer user's message

        if user message is for booking then respond with one word answer "booking_completed"

    '''

    response = gpt_response(system_prompt, user_message)

    if "booking" in response:
        response = "booking_completed"

    return response

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8000)