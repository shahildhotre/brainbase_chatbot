"use client";

// import Hero from "@/components/hero";
// import ConnectSupabaseSteps from "@/components/tutorial/connect-supabase-steps";
// import SignUpUserSteps from "@/components/tutorial/sign-up-user-steps";
// import { hasEnvVars } from "@/utils/supabase/check-env-vars";

// import Image from "next/image";
import { use, useState, useEffect, useRef } from "react";
import { createClient } from "@/utils/supabase/client";
import { io } from "socket.io-client";
import {Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle} from "@/components/ui/sheet";

// Initialize socket connection with explicit configuration
const socket = io('http://localhost:8000', {
  transports: ['websocket'],
  reconnection: true,
});

// Add these interfaces at the top of the file
interface FlightPrice {
  total: string;
}

interface MessageType {
  type?: string;
  data?: FlightData[];
  message: string;
  from: 'user' | 'ai';
  conversation_id?: string;
  parent_conversation_id?: string;
}

interface FlightLinks {
  flightDates: string;
  flightOffers: string;
}

interface FlightData {
  type: string;
  id: string;
  source: string;
  itineraries: {
    duration: string;
    segments: {
      departure: {
        iataCode: string;
        terminal?: string;
        at: string;
      };
      arrival: {
        iataCode: string;
        terminal?: string;
        at: string;
      };
      carrierCode: string;
      number: string;
    }[];
  }[];
  price: {
    currency: string;
    total: string;
    base: string;
    grandTotal: string;
  };
}

interface HotelData {
  chainCode: string;
  iataCode: string;
  name: string;
  hotelId: string;
  geoCode: {
    latitude: number;
    longitude: number;
  };
  address: {
    countryCode: string;
  };
}

// Add this interface with other interfaces
interface StepByStepState {
  isOpen: boolean;
  content: string;
}

// Add this component above the Home component
const FlightCard = ({ flight, messages, setMessages, saveToSupabase }: { flight: FlightData, messages: MessageType[], setMessages: (messages: any) => void, saveToSupabase: (message: string, from: 'user' | 'ai', type: string|null, data: any|null, conversation_id?: string) => void  }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [sheetMessage, setSheetMessage] = useState("");
  
  // Get the parent conversation ID from the most recent flight search message
  const parentConversationId = messages
    .filter(msg => msg.type === 'flight-results')
    .pop()?.conversation_id || 'main_chat';

  // Create child conversation ID with parent reference
  const conversationId = useRef(
    `child_${flight.itineraries[0].segments[0].departure.iataCode}-` +
    `${flight.itineraries[0].segments[0].arrival.iataCode}_` +
    `${new Date(flight.itineraries[0].segments[0].departure.at).toISOString().split('T')[0]}_` +
    `${flight.itineraries[0].segments[0].carrierCode}${flight.itineraries[0].segments[0].number}`
  );

  const handleSheetSend = async () => {
    if (!sheetMessage.trim()) return;
    
    const newMessage = {
      message: sheetMessage,
      from: 'user' as "user"|"ai",
      conversation_id: conversationId.current,
      parent_conversation_id: parentConversationId
    } as MessageType;

    // Get only relevant messages for this conversation
    const relevantMessages = messages.filter(msg => msg.conversation_id === conversationId.current);

    // Send message to backend with context including both flight and hotel details
    socket.emit('chat_message', {
      messages: [...relevantMessages, newMessage],
      context: {
        flightDetails: flight || null,
        conversation_id: conversationId.current,
        parent_conversation_id: parentConversationId
      }
    });

    setMessages((prev: MessageType[]) => [...prev, newMessage]);
    setSheetMessage("");
    
    await saveToSupabase(sheetMessage, 'user', null, null, conversationId.current);
  };

  return (
    <>
      <div 
        className="bg-white rounded-lg shadow-md p-4 mb-4 cursor-pointer hover:shadow-lg transition-shadow"
        onClick={() => setIsOpen(true)}
      >
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-lg font-semibold text-blue-600">
            {flight.itineraries[0].segments[0].departure.iataCode} → {flight.itineraries[0].segments[0].arrival.iataCode}
          </h3>
          <span className="text-xl font-bold text-blue-600">${flight.price.total}</span>
        </div>
        <div className="text-sm text-gray-600">
          <p>Departure: {new Date(flight.itineraries[0].segments[0].departure.at).toLocaleString()}</p>
          <p>Arrival: {new Date(flight.itineraries[0].segments[0].arrival.at).toLocaleString()}</p>
          <p>Airline: {flight.itineraries[0].segments[0].carrierCode} {flight.itineraries[0].segments[0].number}</p>
          <p>Duration: {flight.itineraries[0].duration}</p>
        </div>
      </div>

      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetContent>
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto">
              <SheetHeader>
                <SheetTitle>Flight Details</SheetTitle>
                <div className="space-y-4 mt-4 text-gray-600">
                  <div>
                    <h3 className="text-lg font-semibold">Route</h3>
                    <p>{flight.itineraries[0].segments[0].departure.iataCode} → {flight.itineraries[0].segments[0].arrival.iataCode}</p>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">Times</h3>
                    <p>Departure: {new Date(flight.itineraries[0].segments[0].departure.at).toLocaleString()}</p>
                    <p>Arrival: {new Date(flight.itineraries[0].segments[0].arrival.at).toLocaleString()}</p>
                    <p>Duration: {flight.itineraries[0].duration}</p>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">Airline</h3>
                    <p>Carrier: {flight.itineraries[0].segments[0].carrierCode}</p>
                    <p>Flight: {flight.itineraries[0].segments[0].carrierCode} {flight.itineraries[0].segments[0].number}</p>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">Price</h3>
                    <p className="text-xl font-bold text-blue-600">${flight.price.total}</p>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">Additional Details</h3>
                    {flight.itineraries[0].segments[0].departure.terminal && (
                      <p>Departure Terminal: {flight.itineraries[0].segments[0].departure.terminal}</p>
                    )}
                    {flight.itineraries[0].segments[0].arrival.terminal && (
                      <p>Arrival Terminal: {flight.itineraries[0].segments[0].arrival.terminal}</p>
                    )}
                  </div>
                </div>
              </SheetHeader>

              {/* Chat Section */}
              <div className="mt-6">
                <div className="space-y-4">
                  {messages.filter((msg: MessageType) => msg.conversation_id === conversationId.current).map((msg, index) => (
                    <div 
                      key={index} 
                      className={`flex items-start ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div 
                        className={`rounded-lg p-3 max-w-[70%] ${
                          msg.from === 'user' 
                            ? 'bg-gray-200 text-gray-800' 
                            : 'bg-blue-500 text-white'
                        }`}
                      >
                        <p>{msg.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Input Area - Fixed at bottom */}
            <div className="border-t mt-4 pt-4 bg-white">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={sheetMessage}
                  onChange={(e) => setSheetMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSheetSend();
                    }
                  }}
                  placeholder="Ask about this flight..."
                  className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button 
                  onClick={handleSheetSend} 
                  className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition-colors"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
};

// Add HotelCard component
const HotelCard = ({ hotel, messages, setMessages, saveToSupabase }: { 
  hotel: HotelData, 
  messages: MessageType[], 
  setMessages: (messages: any) => void, 
  saveToSupabase: (message: string, from: 'user' | 'ai', type: string|null, data: any|null, conversation_id?: string) => void  
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [sheetMessage, setSheetMessage] = useState("");
  
  // Get the parent conversation ID from the most recent hotel search message
  const parentConversationId = messages
    .filter(msg => msg.type === 'hotel-results')
    .pop()?.conversation_id || 'main_chat';

  // Create child conversation ID with parent reference
  const conversationId = useRef(
    `child_hotel_${hotel.hotelId}_${hotel.iataCode}`
  );


  const handleSheetSend = async () => {
    if (!sheetMessage.trim()) return;
    
    const newMessage = {
      message: sheetMessage,
      from: 'user' as "user"|"ai",
      conversation_id: conversationId.current,
      parent_conversation_id: parentConversationId
    } as MessageType;

    // Get only relevant messages for this conversation
    const relevantMessages = messages.filter(msg => msg.conversation_id === conversationId.current);

    // Send message to backend with context including hotel details
    socket.emit('chat_message', {
      messages: [...relevantMessages, newMessage],
      context: {
        hotelDetails: hotel,
        conversation_id: conversationId.current,
        parent_conversation_id: parentConversationId
      }
    });

    setMessages((prev: MessageType[]) => [...prev, newMessage]);
    setSheetMessage("");
    
    await saveToSupabase(sheetMessage, 'user', null, null, conversationId.current);
  };

  return (
    <>
      <div 
        className="bg-white rounded-lg shadow-md p-4 mb-4 cursor-pointer hover:shadow-lg transition-shadow"
        onClick={() => setIsOpen(true)}
      >
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-lg font-semibold text-blue-600">
            {hotel.name}
          </h3>
        </div>
        <div className="text-sm text-gray-600">
          <p>Location: {hotel.iataCode}</p>
          <p>Chain: {hotel.chainCode}</p>
        </div>
      </div>

      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetContent>
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto">
              <SheetHeader>
                <SheetTitle>Hotel Details</SheetTitle>
                <div className="space-y-4 mt-4 text-gray-600">
                  <div>
                    <h3 className="text-lg font-semibold">Hotel Name</h3>
                    <p>{hotel.name}</p>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">Location</h3>
                    <p>Airport Code: {hotel.iataCode}</p>
                    <p>Coordinates: {hotel.geoCode.latitude}, {hotel.geoCode.longitude}</p>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">Chain</h3>
                    <p>{hotel.chainCode}</p>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">Country</h3>
                    <p>{hotel.address?.countryCode || 'Not specified'}</p>
                  </div>
                </div>
              </SheetHeader>

              {/* Chat Section */}
              <div className="mt-6">
                <div className="space-y-4">
                  {messages.filter((msg: MessageType) => msg.conversation_id === conversationId.current).map((msg, index) => (
                    <div 
                      key={index} 
                      className={`flex items-start ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div 
                        className={`rounded-lg p-3 max-w-[70%] ${
                          msg.from === 'user' 
                            ? 'bg-gray-200 text-gray-800' 
                            : 'bg-blue-500 text-white'
                        }`}
                      >
                        <p>{msg.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Input Area */}
            <div className="border-t mt-4 pt-4 bg-white">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={sheetMessage}
                  onChange={(e) => setSheetMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSheetSend();
                    }
                  }}
                  placeholder="Ask about this hotel..."
                  className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button 
                  onClick={handleSheetSend} 
                  className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition-colors"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
};

export default function Home() {
  const [message, setMessage] = useState<string>("");
  const [messages, setMessages] = useState<MessageType[]>([
    {message: "Hello! How can I help you today?", from: 'ai'}
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mainConversationId = useRef('main_chat');

  // Add this new state
  const [stepByStep, setStepByStep] = useState<StepByStepState>({
    isOpen: false,
    content: ''
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Socket.IO event handlers
    socket.on('connect', () => {
      console.log('Connected to Socket.IO server');
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from Socket.IO server');
    });

    socket.on('error', (error) => {
      console.error('Socket error:', error);
    });

    socket.on('chat_response', (response: any) => {
      console.log('Received response:', response);
      if (!response || !response.message) {
        console.error('Invalid response format:', response);
        return;
      }

      // Add step-by-step handling
      if (response.type === 'step_by_step_response') {
        setStepByStep({
          isOpen: true,
          content: response.message
        });
      }

      // Add AI response to messages and save to Supabase
      const aiMessage = response.message;
      const aiData = response.data as FlightData[];
      const aiType = response.type;
      const aiConversationId = response.conversation_id;
      setMessages(prev => [...prev, {message: aiMessage, from: 'ai', type: aiType, data: aiData, conversation_id: aiConversationId}]);
      saveToSupabase(aiMessage, 'ai', aiType, aiData, aiConversationId);
    });

    // Fetch existing messages from Supabase
    fetchMessages();

    // Cleanup socket connection on component unmount
    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('error');
      // socket.off('chat_response');
      socket.disconnect();
    };
  }, []);

  const saveToSupabase = async (
    message: string, 
    from: 'user' | 'ai', 
    type: string|null, 
    data: any|null, 
    conversation_id?: string
  ) => {
    const supabase = createClient();
    await supabase.from('brainbase_chathistory').insert({
      message, 
      from, 
      type, 
      data,
      conversation_id
    });
  };

  const fetchMessages = async () => {
    const supabase = createClient();
    const {data, error} = await supabase
      .from('brainbase_chathistory')
      .select('*')
      .order('created_at', {ascending: true});

    // console.log("data: ", data);
    
    if (error) {
      console.error(error);
    } else {
      setMessages(data as MessageType[]);
    }
  };

  const handleSend = async () => {
    if (!message.trim()) return;
    
    const newMessage = {
      message, 
      from: 'user' as "user"|"ai",
      conversation_id: mainConversationId.current
    };

    // Send message to backend
    socket.emit('chat_message', {
      messages: [...messages, newMessage],
      context: {
        conversation_id: mainConversationId.current
      }
    });

    setMessages(prev => [...prev, newMessage]);
    
    setMessage("");
    await saveToSupabase(message, 'user', null, null, mainConversationId.current);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Add Sidebar */}
      {stepByStep.isOpen && (
        <div className="fixed left-0 top-0 h-full w-64 bg-white shadow-lg p-4 overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold">Trip Planning Steps</h2>
            <button 
              onClick={() => setStepByStep(prev => ({ ...prev, isOpen: false }))}
              className="text-gray-500 hover:text-gray-700"
            >
              ×
            </button>
          </div>
          <div className="prose">
            {stepByStep.content.split('\n').map((line, index) => (
              <p key={index}>{line}</p>
            ))}
          </div>
        </div>
      )}

      {/* Existing layout */}
      <header className="bg-white shadow p-4">
        <h1 className="text-xl font-bold text-gray-800">BrainBase Chatbot</h1>
      </header>

      {/* Add margin-left when sidebar is open */}
      <div className={`flex-1 overflow-y-auto p-4 ${stepByStep.isOpen ? 'ml-64' : ''}`}>
        <div className="space-y-4">
          {/* Bot's initial message */}
          <div className="flex items-start">
            <div className="bg-blue-500 text-white rounded-lg p-3 max-w-[70%]">
              <p>Hello! How can I help you today?</p>
            </div>
          </div>

          {/* Messages */}
          {messages.map((msg, index) => (
            msg.conversation_id === mainConversationId.current && (
              <div 
                key={index} 
                className={`flex items-start ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div 
                  className={`rounded-lg p-3 max-w-[70%] ${
                    msg.from === 'user' 
                      ? 'bg-gray-200 text-gray-800' 
                      : 'bg-blue-500 text-white'
                  }`}
                >
                  {msg.data && Array.isArray(msg.data) && (msg.type === 'flight-results' || msg.type === 'hotel-results') ? (
                    <div className="space-y-2">
                      {msg.data.slice(0, 10).map((item: FlightData | HotelData, idx: number) => (
                        'type' in item ? (
                          <FlightCard key={idx} flight={item as FlightData} messages={messages} setMessages={setMessages} saveToSupabase={saveToSupabase} />
                        ) : (
                          <HotelCard key={idx} hotel={item as HotelData} messages={messages} setMessages={setMessages} saveToSupabase={saveToSupabase} />
                        )
                      ))}
                    </div>
                  ) : (
                    <p>{msg.message}</p>
                  )}
                </div>
              </div>
            )
          ))}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Add margin-left to input area when sidebar is open */}
      <div className={`bg-white border-t p-4 ${stepByStep.isOpen ? 'ml-64' : ''}`}>
        <div className="flex space-x-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type your message..."
            className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button onClick={handleSend} className="bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition-colors">
            Send
          </button>
        </div>
      </div>
    </div>
  );
}