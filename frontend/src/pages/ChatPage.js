import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
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
  Link,
  Globe,
  File,
  Quote,
  ImageIcon,
  Download,
  MessageSquare,
  MoveRight,
  FolderOpen,
  Pencil,
  Check,
  X,
  Copy,
  Search,
  Plus,
  Eye
} from 'lucide-react';
import { Label } from '../components/ui/label';
import DashboardLayout from '../components/DashboardLayout';
import ImageGenerator from '../components/ImageGenerator';
import AuthImage from '../components/AuthImage';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// URL regex pattern
const URL_REGEX = /(https?:\/\/[^\s<>"{}|\\^`[\]]+)/g;

// Function to render text with clickable URLs
const renderTextWithLinks = (text) => {
  if (!text) return null;
  
  const parts = text.split(URL_REGEX);
  
  return parts.map((part, index) => {
    if (URL_REGEX.test(part)) {
      // Reset regex lastIndex
      URL_REGEX.lastIndex = 0;
      return (
        <a
          key={index}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2 break-all"
          onClick={(e) => e.stopPropagation()}
        >
          {part}
        </a>
      );
    }
    return part;
  });
};

// File type icons
const getFileIcon = (mimeType, kind) => {
  if (kind === 'url') return <Globe className="h-5 w-5 text-blue-400" />;
  if (mimeType?.includes('pdf')) return <FileText className="h-5 w-5 text-red-400" />;
  if (mimeType?.includes('wordprocessingml')) return <File className="h-5 w-5 text-blue-500" />;
  if (mimeType?.includes('presentationml')) return <File className="h-5 w-5 text-orange-500" />;
  if (mimeType?.includes('spreadsheetml')) return <File className="h-5 w-5 text-green-500" />;
  if (mimeType?.includes('image')) return <ImageIcon className="h-5 w-5 text-purple-400" />;
  return <FileText className="h-5 w-5 text-gray-400" />;
};

const ChatPage = () => {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [chat, setChat] = useState(null);
  const [projectSources, setProjectSources] = useState([]);
  const [activeSourceIds, setActiveSourceIds] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [generatedImages, setGeneratedImages] = useState([]);
  const [isAddingUrl, setIsAddingUrl] = useState(false);
  const [showSourcePanel, setShowSourcePanel] = useState(false);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [userProjects, setUserProjects] = useState([]);
  const [isMovingChat, setIsMovingChat] = useState(false);
  
  // Create project in move dialog
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [showCreateProject, setShowCreateProject] = useState(false);
  
  // Rename chat state
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [isSavingName, setIsSavingName] = useState(false);
  const nameInputRef = useRef(null);
  
  // Preview dialog state
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewSource, setPreviewSource] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

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
      setActiveSourceIds(chatRes.data.activeSourceIds || []);
      
      // Get messages
      const messagesRes = await axios.get(`${API}/chats/${chatId}/messages`);
      setMessages(messagesRes.data);
      
      // Only fetch sources and images if chat belongs to a project
      if (chatRes.data.projectId) {
        const sourcesRes = await axios.get(`${API}/projects/${chatRes.data.projectId}/sources`);
        setProjectSources(sourcesRes.data);
        
        const imagesRes = await axios.get(`${API}/projects/${chatRes.data.projectId}/images`);
        setGeneratedImages(imagesRes.data);
      } else {
        // Quick chat - no sources
        setProjectSources([]);
        setGeneratedImages([]);
      }
    } catch (error) {
      toast.error('Failed to load chat');
      navigate('/dashboard');
    } finally {
      setIsLoading(false);
    }
  };

  // Check if this is a quick chat (no project)
  const isQuickChat = chat && !chat.projectId;

  const fetchUserProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setUserProjects(response.data);
    } catch (error) {
      console.error('Failed to load projects');
    }
  };

  const openMoveDialog = () => {
    fetchUserProjects();
    setShowCreateProject(false);
    setNewProjectName('');
    setMoveDialogOpen(true);
  };

  const createProjectAndMove = async () => {
    if (!newProjectName.trim()) {
      toast.error('Project name is required');
      return;
    }
    
    setIsCreatingProject(true);
    try {
      // Create project
      const response = await axios.post(`${API}/projects`, { name: newProjectName.trim() });
      const newProject = response.data;
      
      // Move chat to new project
      await axios.post(`${API}/chats/${chatId}/move`, { targetProjectId: newProject.id });
      toast.success('Project created and chat moved');
      setMoveDialogOpen(false);
      window.location.reload();
    } catch (error) {
      toast.error('Failed to create project');
    } finally {
      setIsCreatingProject(false);
    }
  };

  const moveChat = async (targetProjectId) => {
    setIsMovingChat(true);
    try {
      await axios.post(`${API}/chats/${chatId}/move`, { targetProjectId });
      toast.success('Chat moved to project');
      setMoveDialogOpen(false);
      // Reload chat data to reflect new project
      window.location.reload();
    } catch (error) {
      toast.error('Failed to move chat');
    } finally {
      setIsMovingChat(false);
    }
  };

  const startEditingName = () => {
    setEditedName(chat?.name || 'Quick Chat');
    setIsEditingName(true);
    setTimeout(() => nameInputRef.current?.focus(), 100);
  };

  const cancelEditingName = () => {
    setIsEditingName(false);
    setEditedName('');
  };

  const saveNewName = async () => {
    if (!editedName.trim()) {
      toast.error('Name cannot be empty');
      return;
    }
    
    setIsSavingName(true);
    try {
      const response = await axios.put(`${API}/chats/${chatId}/rename`, { name: editedName.trim() });
      setChat(response.data);
      setIsEditingName(false);
      toast.success('Chat renamed');
    } catch (error) {
      toast.error('Failed to rename chat');
    } finally {
      setIsSavingName(false);
    }
  };

  const handleNameKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveNewName();
    } else if (e.key === 'Escape') {
      cancelEditingName();
    }
  };

  const handleImageGenerated = (newImage) => {
    setGeneratedImages(prev => [newImage, ...prev]);
    
    // Add image as a system message in chat
    const imageMessage = {
      id: `img-${newImage.id}`,
      chatId,
      role: 'assistant',
      content: `Generated image: "${newImage.prompt}"`,
      isGeneratedImage: true,
      imageData: newImage,
      createdAt: newImage.createdAt
    };
    setMessages(prev => [...prev, imageMessage]);
  };

  const downloadImage = async (imageId) => {
    try {
      const response = await axios.get(`${API}/images/${imageId}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `generated_${imageId}.png`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error('Failed to download image');
    }
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const supportedMimeTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/plain',
      'text/markdown',
      'image/png',
      'image/jpeg',
      'image/jpg'
    ];
    
    const supportedExtensions = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md', '.png', '.jpg', '.jpeg'];

    // Filter valid files - check by extension OR mime type
    const validFiles = files.filter(file => {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      const isValidExt = supportedExtensions.includes(ext);
      const isValidMime = supportedMimeTypes.includes(file.type);
      
      if (!isValidExt && !isValidMime) {
        toast.error(`${file.name}: Unsupported file type. Use PDF, DOCX, PPTX, XLSX, TXT, MD, PNG, JPEG`);
        return false;
      }
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`${file.name}: File size must be less than 10MB`);
        return false;
      }
      return true;
    });

    if (validFiles.length === 0) return;

    setIsUploading(true);
    
    // Use multiple upload endpoint if more than one file
    if (validFiles.length > 1) {
      const formData = new FormData();
      validFiles.forEach(file => formData.append('files', file));
      
      try {
        const response = await axios.post(
          `${API}/projects/${chat.projectId}/sources/upload-multiple`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        
        // Refresh sources list
        const sourcesRes = await axios.get(`${API}/projects/${chat.projectId}/sources`);
        setProjectSources(sourcesRes.data);
        
        const uploaded = response.data.uploaded || [];
        const errors = response.data.errors || [];
        
        if (uploaded.length > 0) {
          toast.success(`Uploaded ${uploaded.length} file(s)`);
        }
        if (errors.length > 0) {
          errors.forEach(err => toast.error(`${err.filename}: ${err.error}`));
        }
      } catch (error) {
        const message = error.response?.data?.detail || 'Failed to upload files';
        toast.error(message);
      }
    } else {
      // Single file upload
      const file = validFiles[0];
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await axios.post(
          `${API}/projects/${chat.projectId}/sources/upload`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        );
        
        setProjectSources(prev => [...prev, response.data]);
        toast.success(`Uploaded ${file.name} (${response.data.chunkCount} chunks extracted)`);
      } catch (error) {
        const message = error.response?.data?.detail || 'Failed to upload file';
        toast.error(message);
      }
    }
    
    setIsUploading(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleAddUrl = async () => {
    const url = urlInput.trim();
    if (!url) {
      toast.error('Please enter a URL');
      return;
    }

    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      toast.error('URL must start with http:// or https://');
      return;
    }

    setIsAddingUrl(true);
    try {
      const response = await axios.post(
        `${API}/projects/${chat.projectId}/sources/url`,
        { url }
      );
      
      setProjectSources(prev => [...prev, response.data]);
      setUrlInput('');
      toast.success(`Added URL (${response.data.chunkCount} chunks extracted)`);
      
      // Auto-activate the URL source
      const newActiveIds = [...activeSourceIds, response.data.id];
      await updateActiveSources(newActiveIds);
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to add URL';
      toast.error(message);
    } finally {
      setIsAddingUrl(false);
    }
  };

  const deleteSource = async (sourceId, e) => {
    e.stopPropagation();
    
    if (!window.confirm('Are you sure you want to delete this source?')) {
      return;
    }

    try {
      await axios.delete(`${API}/projects/${chat.projectId}/sources/${sourceId}`);
      setProjectSources(prev => prev.filter(s => s.id !== sourceId));
      setActiveSourceIds(prev => prev.filter(id => id !== sourceId));
      toast.success('Source deleted');
    } catch (error) {
      toast.error('Failed to delete source');
    }
  };

  const openPreview = async (source, e) => {
    e.stopPropagation();
    setPreviewLoading(true);
    setPreviewDialogOpen(true);
    
    try {
      const response = await axios.get(`${API}/projects/${chat.projectId}/sources/${source.id}/preview`);
      setPreviewSource(response.data);
    } catch (error) {
      toast.error('Failed to load preview');
      setPreviewDialogOpen(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const downloadSource = async (source, e) => {
    e.stopPropagation();
    
    try {
      const response = await axios.get(
        `${API}/projects/${chat.projectId}/sources/${source.id}/download`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', source.originalName || 'file');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  const searchSources = async () => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      toast.error('Введите минимум 2 символа');
      return;
    }
    
    setIsSearching(true);
    setShowSearchResults(true);
    
    try {
      const response = await axios.post(`${API}/projects/${chat.projectId}/sources/search`, {
        query: searchQuery.trim(),
        limit: 20
      });
      setSearchResults(response.data);
      if (response.data.length === 0) {
        toast.info('Ничего не найдено');
      }
    } catch (error) {
      toast.error('Ошибка поиска');
    } finally {
      setIsSearching(false);
    }
  };

  const highlightMatch = (text, query) => {
    const regex = new RegExp(`(${query})`, 'gi');
    return text.replace(regex, '<mark class="bg-yellow-300 dark:bg-yellow-600 px-0.5 rounded">$1</mark>');
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
      
      // Check if URLs were auto-ingested
      if (response.data.autoIngestedUrls && response.data.autoIngestedUrls.length > 0) {
        // Refresh sources list to show newly ingested URLs
        const sourcesRes = await axios.get(`${API}/projects/${chat.projectId}/sources`);
        setProjectSources(sourcesRes.data);
        
        // Refresh chat to get updated active source IDs
        const chatRes = await axios.get(`${API}/chats/${chatId}`);
        setActiveSourceIds(chatRes.data.activeSourceIds || []);
        
        toast.success(`Auto-ingested ${response.data.autoIngestedUrls.length} URL(s) from your message`);
      }
      
      setMessages(prev => {
        const withoutTemp = prev.filter(m => m.id !== tempUserMsg.id);
        return [...withoutTemp, { ...tempUserMsg, id: `user-${Date.now()}`, autoIngestedUrls: response.data.autoIngestedUrls }, response.data];
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
    if (!bytes) return '';
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

  const getFileTypeLabel = (mimeType, kind) => {
    if (kind === 'url') return 'URL';
    if (mimeType?.includes('pdf')) return 'PDF';
    if (mimeType?.includes('wordprocessingml')) return 'DOCX';
    if (mimeType?.includes('presentationml')) return 'PPTX';
    if (mimeType?.includes('spreadsheetml')) return 'XLSX';
    if (mimeType?.includes('markdown')) return 'MD';
    if (mimeType?.includes('plain')) return 'TXT';
    if (mimeType?.includes('png')) return 'PNG';
    if (mimeType?.includes('jpeg') || mimeType?.includes('jpg')) return 'JPEG';
    return 'File';
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
              onClick={() => {
                // If chat belongs to a project, go to project page
                // Otherwise go to dashboard
                if (chat?.projectId) {
                  navigate(`/projects/${chat.projectId}`);
                } else {
                  navigate('/dashboard');
                }
              }}
              data-testid="back-from-chat-btn"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              {/* Editable Chat Name */}
              {isEditingName ? (
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-emerald-400" />
                  <Input
                    ref={nameInputRef}
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    onKeyDown={handleNameKeyDown}
                    className="h-8 w-48 text-sm font-semibold"
                    disabled={isSavingName}
                    data-testid="chat-name-input"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={saveNewName}
                    disabled={isSavingName}
                    data-testid="save-chat-name-btn"
                  >
                    {isSavingName ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4 text-emerald-400" />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={cancelEditingName}
                    disabled={isSavingName}
                  >
                    <X className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>
              ) : (
                <h1 className="font-semibold flex items-center gap-2">
                  {isQuickChat ? (
                    <>
                      <MessageSquare className="h-4 w-4 text-emerald-400" />
                      <span 
                        className="cursor-pointer hover:text-emerald-400 transition-colors"
                        onClick={startEditingName}
                        title="Click to rename"
                        data-testid="chat-name-display"
                      >
                        {chat.name || 'Quick Chat'}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-50 hover:opacity-100"
                        onClick={startEditingName}
                        data-testid="edit-chat-name-btn"
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                    </>
                  ) : (
                    'Chat'
                  )}
                </h1>
              )}
              <p className="text-sm text-muted-foreground">
                {messages.length} {messages.length === 1 ? 'message' : 'messages'}
                {!isQuickChat && activeSourceIds.length > 0 && (
                  <span className="ml-2 text-indigo-400">
                    • {activeSourceIds.length} source{activeSourceIds.length !== 1 ? 's' : ''} active
                  </span>
                )}
                {isQuickChat && (
                  <span className="ml-2 text-emerald-400">• Quick Chat</span>
                )}
              </p>
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center gap-2">
            {/* Move Chat Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={openMoveDialog}
              className="gap-2"
              data-testid="move-chat-btn"
            >
              <MoveRight className="h-4 w-4" />
              Move
            </Button>

            {/* Image Generator - only for project chats */}
            {chat && chat.projectId && (
              <ImageGenerator 
                projectId={chat.projectId} 
                onImageGenerated={handleImageGenerated}
              />
            )}
            
            {/* Source Panel Toggle - only for project chats */}
            {!isQuickChat && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSourcePanel(!showSourcePanel)}
                className="gap-2"
                data-testid="toggle-source-panel-btn"
              >
                <Paperclip className="h-4 w-4" />
                Sources
                {showSourcePanel ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
            )}
          </div>
        </div>

        {/* Move Chat Dialog */}
        <Dialog open={moveDialogOpen} onOpenChange={setMoveDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Move Chat to Project</DialogTitle>
              <DialogDescription>
                {showCreateProject 
                  ? "Create a new project and move this chat into it."
                  : "Select a project to move this chat into."
                }
                {chat?.projectId && !showCreateProject && " The chat will be removed from its current project."}
              </DialogDescription>
            </DialogHeader>
            
            {showCreateProject ? (
              // Create Project Form
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="newProjectName">Project Name</Label>
                  <Input
                    id="newProjectName"
                    placeholder="My New Project"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && createProjectAndMove()}
                    disabled={isCreatingProject}
                    data-testid="new-project-name-input"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => setShowCreateProject(false)}
                    disabled={isCreatingProject}
                  >
                    Back
                  </Button>
                  <Button
                    className="flex-1"
                    onClick={createProjectAndMove}
                    disabled={isCreatingProject || !newProjectName.trim()}
                    data-testid="create-and-move-btn"
                  >
                    {isCreatingProject ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                    Create & Move
                  </Button>
                </div>
              </div>
            ) : (
              // Project List
              <div className="space-y-2 py-4 max-h-[300px] overflow-y-auto">
                {userProjects.length === 0 ? (
                  <div className="text-center py-4">
                    <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                    <p className="text-muted-foreground mb-4">No projects yet</p>
                    <Button 
                      onClick={() => setShowCreateProject(true)}
                      data-testid="create-project-in-dialog-btn"
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Create Project
                    </Button>
                  </div>
                ) : (
                  <>
                    {userProjects
                      .filter(p => p.id !== chat?.projectId)
                      .map((project) => (
                        <Card
                          key={project.id}
                          className="cursor-pointer hover:border-indigo-500/50 transition-colors"
                          onClick={() => moveChat(project.id)}
                          data-testid={`move-to-project-${project.id}`}
                        >
                          <CardContent className="py-3 flex items-center gap-3">
                            <FolderOpen className="h-5 w-5 text-indigo-400" />
                            <span className="font-medium">{project.name}</span>
                          </CardContent>
                        </Card>
                      ))
                    }
                    {userProjects.filter(p => p.id !== chat?.projectId).length === 0 && (
                      <p className="text-center text-muted-foreground py-4">
                        No other projects available to move to.
                      </p>
                    )}
                    {/* Create new project option */}
                    <Card
                      className="cursor-pointer hover:border-emerald-500/50 transition-colors border-dashed"
                      onClick={() => setShowCreateProject(true)}
                      data-testid="create-new-project-option"
                    >
                      <CardContent className="py-3 flex items-center gap-3">
                        <Plus className="h-5 w-5 text-emerald-400" />
                        <span className="font-medium text-emerald-400">Create New Project</span>
                      </CardContent>
                    </Card>
                  </>
                )}
              </div>
            )}
            
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setMoveDialogOpen(false)}
                disabled={isMovingChat || isCreatingProject}
              >
                Cancel
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Source Panel - only for project chats */}
        {!isQuickChat && showSourcePanel && (
          <div className="border-b border-border bg-card/30 px-6 py-4" data-testid="source-panel">
            <div className="max-w-3xl mx-auto">
              {/* Upload and URL Input Row */}
              <div className="flex flex-wrap items-center gap-3 mb-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.png,.jpg,.jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,text/markdown,image/png,image/jpeg"
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
                  Upload Files
                </Button>
                
                <div className="flex-1 flex items-center gap-2 min-w-[200px]">
                  <Input
                    placeholder="https://example.com/article"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddUrl()}
                    className="h-9 text-sm"
                    data-testid="url-input"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAddUrl}
                    disabled={isAddingUrl || !urlInput.trim()}
                    className="gap-2 whitespace-nowrap"
                    data-testid="add-url-btn"
                  >
                    {isAddingUrl ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Link className="h-4 w-4" />
                    )}
                    Add URL
                  </Button>
                </div>
              </div>
              
              {/* Search in sources - NO GPT, NO TOKENS */}
              <div className="flex items-center gap-2 mb-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Поиск в документах (0 токенов)..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && searchSources()}
                    className="h-9 text-sm pl-9"
                    data-testid="search-sources-input"
                  />
                </div>
                <Button
                  variant="default"
                  size="sm"
                  onClick={searchSources}
                  disabled={isSearching || !searchQuery.trim()}
                  className="gap-2"
                  data-testid="search-sources-btn"
                >
                  {isSearching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  Найти
                </Button>
              </div>
              
              {/* Search Results */}
              {showSearchResults && (
                <div className="mb-4 border border-border rounded-lg p-3 bg-secondary/30">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Результаты поиска ({searchResults.length})</span>
                    <Button variant="ghost" size="sm" onClick={() => { setShowSearchResults(false); setSearchResults([]); setSearchQuery(''); }}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  {searchResults.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Ничего не найдено</p>
                  ) : (
                    <div className="space-y-2 max-h-[200px] overflow-y-auto">
                      {searchResults.map((result, idx) => (
                        <div key={idx} className="p-2 bg-background rounded border border-border">
                          <div className="flex items-center gap-2 mb-1">
                            <FileText className="h-3 w-3 text-muted-foreground" />
                            <span className="text-xs font-medium truncate">{result.sourceName}</span>
                            <span className="text-xs text-muted-foreground">({result.matchCount} совпадений)</span>
                          </div>
                          <p 
                            className="text-xs text-muted-foreground"
                            dangerouslySetInnerHTML={{ __html: highlightMatch(result.content, searchQuery) }}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="text-xs text-muted-foreground mb-3">
                Supported: PDF, DOCX, PPTX, XLSX, TXT, MD, PNG, JPEG files and web URLs (multiple files allowed)
              </div>

              {/* Sources List */}
              {projectSources.length === 0 ? (
                <div className="text-center py-6 text-muted-foreground">
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No sources uploaded yet</p>
                  <p className="text-xs mt-1">Upload files or add URLs to use as context</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[200px] overflow-y-auto">
                  {projectSources.map((source) => (
                    <div
                      key={source.id}
                      className="flex items-center gap-3 p-3 rounded-lg border border-indigo-500/50 bg-indigo-500/10 transition-colors"
                      data-testid={`source-item-${source.id}`}
                    >
                      <span className="inline-block w-2 h-2 rounded-full bg-indigo-500 flex-shrink-0"></span>
                      {getFileIcon(source.mimeType, source.kind)}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {source.originalName || source.url}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground mr-2">
                            {getFileTypeLabel(source.mimeType, source.kind)}
                          </span>
                          {source.sizeBytes ? `${formatFileSize(source.sizeBytes)} • ` : ''}
                          {source.chunkCount} chunks • {formatDate(source.createdAt)}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        {/* Preview button */}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 opacity-50 hover:opacity-100"
                          onClick={(e) => openPreview(source, e)}
                          title="Preview"
                          data-testid={`preview-source-${source.id}`}
                        >
                          <Eye className="h-4 w-4 text-blue-400" />
                        </Button>
                        {/* Download button - only for files */}
                        {source.kind === 'file' && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 opacity-50 hover:opacity-100"
                            onClick={(e) => downloadSource(source, e)}
                            title="Download"
                            data-testid={`download-source-${source.id}`}
                          >
                            <Download className="h-4 w-4 text-green-400" />
                          </Button>
                        )}
                        {/* Delete button */}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 opacity-50 hover:opacity-100"
                          onClick={(e) => deleteSource(source.id, e)}
                          data-testid={`delete-source-${source.id}`}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {projectSources.length > 0 && (
                <p className="text-xs text-muted-foreground mt-3 flex items-center gap-1">
                  <span className="inline-block w-2 h-2 rounded-full bg-indigo-500"></span>
                  All project sources are automatically used as context for AI responses
                </p>
              )}
            </div>
          </div>
        )}

        {/* Preview Dialog */}
        <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
          <DialogContent className="sm:max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                {previewSource?.name || 'Source Preview'}
              </DialogTitle>
              <DialogDescription>
                {previewSource?.chunkCount} chunks • {previewSource?.wordCount || 0} слов • {previewSource?.kind === 'url' ? 'URL' : previewSource?.mimeType}
              </DialogDescription>
            </DialogHeader>
            {previewLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <>
                {/* Quality indicator */}
                <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
                  previewSource?.quality === 'good' ? 'bg-green-500/10 text-green-600 dark:text-green-400' :
                  previewSource?.quality === 'low' ? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400' :
                  previewSource?.quality === 'poor' ? 'bg-red-500/10 text-red-600 dark:text-red-400' :
                  previewSource?.quality === 'empty' ? 'bg-red-500/10 text-red-600 dark:text-red-400' :
                  'bg-secondary'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${
                    previewSource?.quality === 'good' ? 'bg-green-500' :
                    previewSource?.quality === 'low' ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}></span>
                  {previewSource?.qualityMessage || 'Текст извлечён'}
                </div>
                
                <ScrollArea className="max-h-[45vh] mt-3">
                  <pre className="text-sm whitespace-pre-wrap font-mono bg-secondary/50 p-4 rounded-lg">
                    {previewSource?.text || 'No content'}
                  </pre>
                </ScrollArea>
              </>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Messages Area */}
        <ScrollArea className="flex-1 px-6 py-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="rounded-full bg-secondary p-4 mb-4">
                <Bot className="h-8 w-8 text-indigo-400" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Start a conversation</h3>
              <p className="text-muted-foreground max-w-md">
                {projectSources.length > 0 ? (
                  <span>
                    Select sources above, then ask questions about them.
                    <span className="block mt-2 text-indigo-400">
                      The AI will cite specific chunks from your documents.
                    </span>
                  </span>
                ) : (
                  <span>
                    Upload PDFs, DOCX, TXT files or add URLs to use as context.
                    <span className="block mt-2">
                      The AI will answer questions based on your sources.
                    </span>
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
                    {/* Show sender name for user messages in shared projects */}
                    {message.role === 'user' && message.senderName && (
                      <span className="text-xs text-muted-foreground px-2">
                        {message.senderName}
                      </span>
                    )}
                    
                    {/* Generated Image Display */}
                    {message.isGeneratedImage && message.imageData ? (
                      <div className="space-y-2">
                        <div className="relative rounded-lg overflow-hidden border border-indigo-500/30 max-w-md">
                          <AuthImage
                            imageId={message.imageData.id}
                            alt={message.imageData.prompt}
                            className="w-full h-auto"
                            data-testid={`generated-image-${message.imageData.id}`}
                          />
                          <div className="absolute top-2 right-2">
                            <Button
                              variant="secondary"
                              size="icon"
                              className="h-8 w-8 bg-black/50 hover:bg-black/70"
                              onClick={() => downloadImage(message.imageData.id)}
                              data-testid={`download-image-${message.imageData.id}`}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 px-2">
                          <ImageIcon className="h-3 w-3 text-indigo-400" />
                          <span className="text-xs text-muted-foreground truncate max-w-xs">
                            {message.imageData.prompt}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="group relative">
                        <div className={`px-4 py-3 rounded-2xl ${
                          message.role === 'user' 
                            ? 'bg-primary text-primary-foreground rounded-br-sm' 
                            : 'bg-secondary text-secondary-foreground rounded-bl-sm'
                        }`}>
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">
                            {renderTextWithLinks(message.content)}
                          </p>
                        </div>
                        
                        {/* Copy button for assistant messages */}
                        {message.role === 'assistant' && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="absolute -bottom-1 -right-1 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity bg-background border border-border shadow-sm"
                            onClick={async () => {
                              try {
                                await navigator.clipboard.writeText(message.content);
                                toast.success('Copied to clipboard');
                              } catch (err) {
                                // Fallback for environments where clipboard API is restricted
                                const textArea = document.createElement('textarea');
                                textArea.value = message.content;
                                textArea.style.position = 'fixed';
                                textArea.style.left = '-9999px';
                                document.body.appendChild(textArea);
                                textArea.select();
                                try {
                                  document.execCommand('copy');
                                  toast.success('Copied to clipboard');
                                } catch (e) {
                                  toast.error('Failed to copy');
                                }
                                document.body.removeChild(textArea);
                              }
                            }}
                            data-testid={`copy-message-${index}`}
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    )}
                    
                    {/* Auto-ingested URLs indicator for user messages */}
                    {message.role === 'user' && message.autoIngestedUrls?.length > 0 && (
                      <div className="mt-1 px-2">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">
                          <Globe className="h-3 w-3" />
                          {message.autoIngestedUrls.length} URL{message.autoIngestedUrls.length > 1 ? 's' : ''} auto-ingested
                        </span>
                      </div>
                    )}
                    
                    {/* Citations / Used Sources */}
                    {message.role === 'assistant' && !message.isGeneratedImage && (message.citations?.length > 0 || message.usedSources?.length > 0) && (
                      <div className="mt-2 px-2">
                        <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                          <Quote className="h-3 w-3" />
                          Sources used:
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {message.citations ? (
                            message.citations.map((citation, cidx) => {
                              const isGlobal = citation.sourceType === 'global';
                              const bgColor = isGlobal ? 'bg-emerald-500/10' : 'bg-indigo-500/10';
                              const textColor = isGlobal ? 'text-emerald-400' : 'text-indigo-400';
                              const borderColor = isGlobal ? 'border-emerald-500/20' : 'border-indigo-500/20';
                              const Icon = isGlobal ? Globe : FileText;
                              
                              return (
                                <span
                                  key={cidx}
                                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${bgColor} ${textColor} text-xs border ${borderColor}`}
                                  data-testid={`citation-${cidx}`}
                                  title={citation.textFragment || citation.sourceName}
                                >
                                  <Icon className="h-3 w-3" />
                                  <span className="font-medium">
                                    {isGlobal ? '🌐 ' : '📁 '}
                                    {citation.sourceName.length > 25 
                                      ? citation.sourceName.slice(0, 25) + '...' 
                                      : citation.sourceName}
                                  </span>
                                  {citation.chunks && (
                                    <span className="opacity-70">
                                      (chunks {Array.isArray(citation.chunks) 
                                        ? citation.chunks.map(c => c.index || c).join(', ')
                                        : citation.chunks})
                                    </span>
                                  )}
                                </span>
                              );
                            })
                          ) : message.usedSources?.map((source, sidx) => {
                            const isGlobal = source.sourceType === 'global';
                            const bgColor = isGlobal ? 'bg-emerald-500/10' : 'bg-indigo-500/10';
                            const textColor = isGlobal ? 'text-emerald-400' : 'text-indigo-400';
                            const borderColor = isGlobal ? 'border-emerald-500/20' : 'border-indigo-500/20';
                            const Icon = isGlobal ? Globe : FileText;
                            
                            return (
                              <span
                                key={sidx}
                                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${bgColor} ${textColor} text-xs border ${borderColor}`}
                                data-testid={`used-source-${sidx}`}
                              >
                                <Icon className="h-3 w-3" />
                                {isGlobal ? '🌐 ' : '📁 '}
                                {source.sourceName.length > 25 
                                  ? source.sourceName.slice(0, 25) + '...' 
                                  : source.sourceName}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    
                    {/* Cache indicator */}
                    {message.fromCache && (
                      <div className="mt-1 px-2">
                        <span className="inline-flex items-center gap-1 text-xs text-amber-500">
                          📦 Из кэша 
                          {message.cacheInfo?.similarity && (
                            <span className="opacity-70">({(message.cacheInfo.similarity * 100).toFixed(0)}%)</span>
                          )}
                        </span>
                      </div>
                    )}
                    
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
                activeSourceIds.length > 0 
                  ? "Ask a question about the selected sources..." 
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
