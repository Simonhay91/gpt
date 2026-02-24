import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { Send, ArrowLeft, Bot, User, Loader2 } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ChatPage = () => {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [chat, setChat] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    fetchMessages();
  }, [chatId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchMessages = async () => {
    try {
      const response = await axios.get(`${API}/chats/${chatId}/messages`);
      setMessages(response.data);
      
      // Get chat info from URL or make additional request if needed
      // For now, we'll extract project info from the first call's response if needed
    } catch (error) {
      toast.error('Failed to load chat');
      navigate('/dashboard');
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || isSending) return;

    // Optimistic update - add user message immediately
    const tempUserMsg = {
      id: `temp-${Date.now()}`,
      chatId,
      role: 'user',
      content,
      createdAt: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, tempUserMsg]);
    setInput('');
    setIsSending(true);

    try {
      const response = await axios.post(`${API}/chats/${chatId}/messages`, { content });
      
      // Replace temp message with real one and add assistant response
      setMessages(prev => {
        const withoutTemp = prev.filter(m => m.id !== tempUserMsg.id);
        // Find the user message in the response (it was saved server-side)
        return [...withoutTemp, { ...tempUserMsg, id: `user-${Date.now()}` }, response.data];
      });
    } catch (error) {
      // Remove optimistic update on error
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
      setInput(content); // Restore input
      toast.error('Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (dateString) => {
    return new Date(dateString).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
          <div className="spinner" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-4rem)]" data-testid="chat-page">
        {/* Chat Header */}
        <div className="border-b border-border px-6 py-4 flex items-center gap-4 bg-card/50 backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            data-testid="back-from-chat-btn"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="font-semibold">Chat</h1>
            <p className="text-sm text-muted-foreground">
              {messages.length} {messages.length === 1 ? 'message' : 'messages'}
            </p>
          </div>
        </div>

        {/* Messages Area */}
        <ScrollArea className="flex-1 px-6 py-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="rounded-full bg-secondary p-4 mb-4">
                <Bot className="h-8 w-8 text-indigo-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Start a conversation</h3>
              <p className="text-muted-foreground max-w-md">
                Send a message to begin chatting with the AI assistant.
                All messages are isolated to this chat.
              </p>
            </div>
          ) : (
            <div className="space-y-6 max-w-3xl mx-auto">
              {messages.map((message, index) => (
                <div
                  key={message.id}
                  className={`flex gap-4 animate-slideIn ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                  style={{ animationDelay: `${index * 30}ms` }}
                  data-testid={`message-${message.role}-${index}`}
                >
                  {message.role === 'assistant' && (
                    <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit">
                      <Bot className="h-5 w-5 text-indigo-400" />
                    </div>
                  )}
                  
                  <div className={`flex flex-col gap-1 max-w-[80%] ${
                    message.role === 'user' ? 'items-end' : 'items-start'
                  }`}>
                    <div className={`px-4 py-3 rounded-2xl ${
                      message.role === 'user' 
                        ? 'bg-primary text-primary-foreground rounded-br-sm' 
                        : 'bg-secondary text-secondary-foreground rounded-bl-sm'
                    }`}>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">
                        {message.content}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground px-1">
                      {formatTime(message.createdAt)}
                    </span>
                  </div>

                  {message.role === 'user' && (
                    <div className="flex-shrink-0 rounded-full bg-emerald-500/20 p-2 h-fit">
                      <User className="h-5 w-5 text-emerald-400" />
                    </div>
                  )}
                </div>
              ))}
              
              {isSending && (
                <div className="flex gap-4 justify-start animate-slideIn">
                  <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit">
                    <Bot className="h-5 w-5 text-indigo-400" />
                  </div>
                  <div className="bg-secondary px-4 py-3 rounded-2xl rounded-bl-sm">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* Input Area */}
        <div className="border-t border-border px-6 py-4 bg-card/50 backdrop-blur">
          <div className="max-w-3xl mx-auto flex gap-4">
            <Textarea
              ref={textareaRef}
              placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="min-h-[60px] max-h-[200px] resize-none bg-background"
              disabled={isSending}
              data-testid="chat-input"
            />
            <Button
              onClick={sendMessage}
              disabled={!input.trim() || isSending}
              className="btn-hover self-end"
              data-testid="send-message-btn"
            >
              {isSending ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default ChatPage;
