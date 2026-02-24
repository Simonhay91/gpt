import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { 
  Send, 
  ArrowLeft, 
  Bot, 
  User, 
  Loader2, 
  Upload, 
  FileText, 
  Trash2, 
  ChevronDown, 
  ChevronUp,
  Paperclip,
  X
} from 'lucide-react';
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
  const [projectFiles, setProjectFiles] = useState([]);
  const [activeFileIds, setActiveFileIds] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [showFilePanel, setShowFilePanel] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchChatData();
  }, [chatId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchChatData = async () => {
    try {
      // Get chat details first
      const chatRes = await axios.get(`${API}/chats/${chatId}`);
      setChat(chatRes.data);
      setActiveFileIds(chatRes.data.activeFileIds || []);
      
      // Get messages
      const messagesRes = await axios.get(`${API}/chats/${chatId}/messages`);
      setMessages(messagesRes.data);
      
      // Get project files
      const filesRes = await axios.get(`${API}/projects/${chatRes.data.projectId}/files`);
      setProjectFiles(filesRes.data);
    } catch (error) {
      toast.error('Failed to load chat');
      navigate('/dashboard');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      toast.error('Only PDF files are allowed');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      toast.error('File size must be less than 10MB');
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(
        `${API}/projects/${chat.projectId}/files`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      
      setProjectFiles(prev => [...prev, response.data]);
      toast.success(`Uploaded ${file.name} (${response.data.chunkCount} chunks extracted)`);
      
      // Auto-activate the uploaded file
      const newActiveIds = [...activeFileIds, response.data.id];
      await updateActiveFiles(newActiveIds);
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to upload file';
      toast.error(message);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const updateActiveFiles = async (fileIds) => {
    try {
      await axios.post(`${API}/chats/${chatId}/active-files`, { fileIds });
      setActiveFileIds(fileIds);
    } catch (error) {
      toast.error('Failed to update active files');
    }
  };

  const toggleFileActive = async (fileId) => {
    const newActiveIds = activeFileIds.includes(fileId)
      ? activeFileIds.filter(id => id !== fileId)
      : [...activeFileIds, fileId];
    
    await updateActiveFiles(newActiveIds);
  };

  const deleteFile = async (fileId, e) => {
    e.stopPropagation();
    
    if (!window.confirm('Are you sure you want to delete this file?')) {
      return;
    }

    try {
      await axios.delete(`${API}/projects/${chat.projectId}/files/${fileId}`);
      setProjectFiles(prev => prev.filter(f => f.id !== fileId));
      setActiveFileIds(prev => prev.filter(id => id !== fileId));
      toast.success('File deleted');
    } catch (error) {
      toast.error('Failed to delete file');
    }
  };

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || isSending) return;

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
      
      setMessages(prev => {
        const withoutTemp = prev.filter(m => m.id !== tempUserMsg.id);
        return [...withoutTemp, { ...tempUserMsg, id: `user-${Date.now()}` }, response.data];
      });
    } catch (error) {
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
      setInput(content);
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

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
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
        <div className="border-b border-border px-6 py-4 flex items-center justify-between bg-card/50 backdrop-blur">
          <div className="flex items-center gap-4">
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
                {activeFileIds.length > 0 && (
                  <span className="ml-2 text-indigo-400">
                    • {activeFileIds.length} file{activeFileIds.length !== 1 ? 's' : ''} active
                  </span>
                )}
              </p>
            </div>
          </div>
          
          {/* File Panel Toggle */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilePanel(!showFilePanel)}
            className="gap-2"
            data-testid="toggle-file-panel-btn"
          >
            <Paperclip className="h-4 w-4" />
            Documents
            {showFilePanel ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>

        {/* File Panel */}
        {showFilePanel && (
          <div className="border-b border-border bg-card/30 px-6 py-4" data-testid="file-panel">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-muted-foreground">
                  Project Documents
                </h3>
                <div className="flex items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf"
                    onChange={handleFileUpload}
                    className="hidden"
                    data-testid="file-input"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="gap-2"
                    data-testid="upload-file-btn"
                  >
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    Upload PDF
                  </Button>
                </div>
              </div>

              {projectFiles.length === 0 ? (
                <div className="text-center py-6 text-muted-foreground">
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No documents uploaded yet</p>
                  <p className="text-xs mt-1">Upload a PDF to use as context in your conversation</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {projectFiles.map((file) => (
                    <div
                      key={file.id}
                      className={`flex items-center gap-3 p-3 rounded-lg border transition-colors cursor-pointer ${
                        activeFileIds.includes(file.id)
                          ? 'border-indigo-500/50 bg-indigo-500/10'
                          : 'border-border hover:border-border/80 bg-background/50'
                      }`}
                      onClick={() => toggleFileActive(file.id)}
                      data-testid={`file-item-${file.id}`}
                    >
                      <Checkbox
                        checked={activeFileIds.includes(file.id)}
                        onCheckedChange={() => toggleFileActive(file.id)}
                        data-testid={`file-checkbox-${file.id}`}
                      />
                      <FileText className={`h-5 w-5 flex-shrink-0 ${
                        activeFileIds.includes(file.id) ? 'text-indigo-400' : 'text-muted-foreground'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{file.originalName}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(file.sizeBytes)} • {file.chunkCount} chunks • {formatDate(file.createdAt)}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 hover:opacity-100"
                        onClick={(e) => deleteFile(file.id, e)}
                        data-testid={`delete-file-${file.id}`}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              
              {activeFileIds.length > 0 && (
                <p className="text-xs text-muted-foreground mt-3 flex items-center gap-1">
                  <span className="inline-block w-2 h-2 rounded-full bg-indigo-500"></span>
                  Selected files will be used as context for AI responses
                </p>
              )}
            </div>
          </div>
        )}

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
                {projectFiles.length > 0 ? (
                  <span className="block mt-2 text-indigo-400">
                    Tip: Select documents above to use them as context
                  </span>
                ) : (
                  <span className="block mt-2">
                    You can also upload PDFs to use as context
                  </span>
                )}
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
              placeholder={
                activeFileIds.length > 0 
                  ? "Ask a question about the selected documents..." 
                  : "Type your message... (Enter to send, Shift+Enter for new line)"
              }
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
