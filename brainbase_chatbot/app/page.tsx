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
}

interface FlightLinks {
  flightDates: string;
  flightOffers: string;
}

interface FlightData {
  type: string;
  origin: string;
  destination: string;
  departureDate: string;
  returnDate: string;
  price: FlightPrice;
  links: FlightLinks;
}

// Add this component above the Home component
const FlightCard = ({ flight }: { flight: FlightData }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <div 
        className="bg-white rounded-lg shadow-md p-4 mb-4 cursor-pointer hover:shadow-lg transition-shadow"
        onClick={() => setIsOpen(true)}
      >
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-lg font-semibold">{flight.origin} → {flight.destination}</h3>
          <span className="text-xl font-bold text-blue-600">${flight.price.total}</span>
        </div>
        <div className="text-sm text-gray-600">
          <p>Departure: {new Date(flight.departureDate).toLocaleDateString()}</p>
          <p>Return: {new Date(flight.returnDate).toLocaleDateString()}</p>
        </div>
      </div>

      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Flight Details</SheetTitle>
            <SheetDescription>
              <div className="space-y-4 mt-4">
                <div>
                  <h3 className="text-lg font-semibold">Route</h3>
                  <p>{flight.origin} → {flight.destination}</p>
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Dates</h3>
                  <p>Departure: {new Date(flight.departureDate).toLocaleDateString()}</p>
                  <p>Return: {new Date(flight.returnDate).toLocaleDateString()}</p>
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Price</h3>
                  <p className="text-xl font-bold text-blue-600">${flight.price.total}</p>
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Links</h3>
                  <a 
                    href={flight.links.flightOffers} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline block"
                  >
                    View Flight Offer
                  </a>
                  <a 
                    href={flight.links.flightDates} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline block"
                  >
                    View Flight Dates
                  </a>
                </div>
              </div>
            </SheetDescription>
          </SheetHeader>
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
      // Add AI response to messages and save to Supabase
      const aiMessage = response.message;
      const aiData = response.data as FlightData[];
      const aiType = response.type;
      setMessages(prev => [...prev, {message: aiMessage, from: 'ai', type: aiType, data: aiData}]);
      saveToSupabase(aiMessage, 'ai', aiType, aiData);
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

  const saveToSupabase = async (message: string, from: 'user' | 'ai', type: string|null, data: any|null) => {
    const supabase = createClient();
    await supabase.from('brainbase_chathistory').insert({message, from, type, data});
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
    
    const newMessage = {message, from: 'user' as "user"|"ai"};

    // Send message to backend
    socket.emit('chat_message', {
      messages: [...messages, newMessage]
    });

    setMessages(prev => [...prev, newMessage]);
    
    setMessage("");
    await saveToSupabase(message, 'user', null, null);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow p-4">
        <h1 className="text-xl font-bold text-gray-800">BrainBase Chatbot</h1>
      </header>

      {/* Chat Container */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-4">
          {/* Bot's initial message */}
          <div className="flex items-start">
            <div className="bg-blue-500 text-white rounded-lg p-3 max-w-[70%]">
              <p>Hello! How can I help you today?</p>
            </div>
          </div>

          {/* Messages */}
          {messages.map((msg, index) => (
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
                {msg.data && Array.isArray(msg.data) && msg.type === 'flight-results' ? (
                  <div className="space-y-2">
                    {msg.data.map((flight: FlightData, idx: number) => (
                      <FlightCard key={idx} flight={flight} />
                    ))}
                  </div>
                ) : (
                  <p>{msg.message}</p>
                )}
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-white border-t p-4">
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