import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import ProjectMemoryModal from '../components/ProjectMemoryModal';
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
  ChevronRight,
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
  Eye,
  Save,
  Target,
  Globe2,
  Lightbulb,
  TrendingUp,
  Info,
  Database,
  Building2,
  Brain
} from 'lucide-react';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import DashboardLayout from '../components/DashboardLayout';
import ImageGenerator from '../components/ImageGenerator';
import ExcelAssistant from '../components/ExcelAssistant';
import AuthImage from '../components/AuthImage';
import SmartQuestions from '../components/SmartQuestions';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const URL_REGEX = /(https?:\/\/[^\s<>"{}|\\^`[\]]+)/g;

const renderTextWithLinks = (text) => {
  if (!text) return null;
  
  const urlPattern = /https?:\/\/[^\s<>"{}|\\^`[\]]+/g;
  const parts = [];
  let lastIndex = 0;
  let match;
  
  while ((match = urlPattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const url = match[0];
    parts.push(
      React.createElement('a', {
        key: match.index,
        href: url,
        target: '_blank',
        rel: 'noopener noreferrer',
        className: 'text-indigo-400 hover:text-indigo-300 underline underline-offset-2 break-all',
        onClick: (e) => e.stopPropagation()
      }, url)
    );
    lastIndex = match.index + url.length;
  }
  
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  
  return parts.length > 0 ? parts : text;
};


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
  const { currentUser } = useAuth();
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
  
  const token = localStorage.getItem('token') || axios.defaults.headers.common['Authorization']?.replace('Bearer ', '');
  
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [showCreateProject, setShowCreateProject] = useState(false);
  
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [isSavingName, setIsSavingName] = useState(false);
  const nameInputRef = useRef(null);
  
  const [sourceMode, setSourceMode] = useState('all');
  const [currentProjectName, setCurrentProjectName] = useState('');
  
  const [expandedSources, setExpandedSources] = useState({});
  const [viewingSource, setViewingSource] = useState(null);
  const [sourceContent, setSourceContent] = useState(null);
  const [isLoadingSourceContent, setIsLoadingSourceContent] = useState(false);
  
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewSource, setPreviewSource] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);
  
  const [expandedGroups, setExpandedGroups] = useState({});
  const [showInfoBlock, setShowInfoBlock] = useState(false);
  const [isSavingContext, setIsSavingContext] = useState(false);
  const [memoryModalOpen, setMemoryModalOpen] = useState(false);
  
  // Edit message state
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editedContent, setEditedContent] = useState("");
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const scrollAreaRef = useRef(null);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const plusMenuRef = useRef(null);

  useEffect(() => { fetchChatData(); }, [chatId]);
  useEffect(() => { scrollToBottom(); }, [messages]);

  useEffect(() => {
    const scrollContainer = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]');
    if (!scrollContainer) return;
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
      setShowScrollBtn(scrollHeight - scrollTop - clientHeight > 200);
    };
    scrollContainer.addEventListener('scroll', handleScroll);
    return () => scrollContainer.removeEventListener('scroll', handleScroll);
  }, [isLoading]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target)) {
        setShowPlusMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Auto-save context every 10 messages (silently)
  useEffect(() => {
    const assistantCount = messages.filter(m => m.role === 'assistant').length;
    if (assistantCount > 0 && assistantCount % 10 === 0 && !isSavingContext) {
      const dialogText = messages
        .map(msg => `${msg.role === 'user' ? 'Пользователь' : 'AI'}: ${msg.content || ''}`)
        .join('\n\n');
      axios.post(`${API}/chats/${chatId}/save-context`, { dialogText })
        .then(() => toast.success('Контекст авто-сохранён', { duration: 2000 }))
        .catch(() => {});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchChatData = async () => {
    try {
      const chatRes = await axios.get(`${API}/chats/${chatId}`);
      setChat(chatRes.data);
      setActiveSourceIds(chatRes.data.activeSourceIds || []);
      setSourceMode(chatRes.data.sourceMode || 'all');
      
      const messagesRes = await axios.get(`${API}/chats/${chatId}/messages`);
      setMessages(messagesRes.data.items || messagesRes.data);
      
      if (chatRes.data.projectId) {
        const [sourcesRes, projRes] = await Promise.all([
          axios.get(`${API}/projects/${chatRes.data.projectId}/sources`),
          axios.get(`${API}/projects/${chatRes.data.projectId}`)
        ]);
        setProjectSources(sourcesRes.data.items || sourcesRes.data);
        setCurrentProjectName(projRes.data.name || '');
        const imagesRes = await axios.get(`${API}/projects/${chatRes.data.projectId}/images`);
        setGeneratedImages(imagesRes.data.items || imagesRes.data);
      } else {
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

  const isQuickChat = chat && !chat.projectId;

  const updateSourceMode = async (newMode) => {
    try {
      await axios.put(`${API}/chats/${chatId}/source-mode`, { sourceMode: newMode });
      setSourceMode(newMode);
      toast.success(newMode === 'my' ? 'Using your sources only' : 'Using all sources');
    } catch (error) {
      toast.error('Failed to update source mode');
    }
  };

  const fetchUserProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setUserProjects(response.data.items || response.data || []);
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
    if (!newProjectName.trim()) { toast.error('Project name is required'); return; }
    setIsCreatingProject(true);
    try {
      const response = await axios.post(`${API}/projects`, { name: newProjectName.trim() });
      await axios.post(`${API}/chats/${chatId}/move`, { targetProjectId: response.data.id });
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
    if (!editedName.trim()) { toast.error('Name cannot be empty'); return; }
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
    if (e.key === 'Enter') { e.preventDefault(); saveNewName(); }
    else if (e.key === 'Escape') { cancelEditingName(); }
  };

  const handleImageGenerated = (newImage) => {
    setGeneratedImages(prev => [newImage, ...prev]);
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
      const response = await axios.get(`${API}/images/${imageId}`, { responseType: 'blob' });
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
      'text/plain', 'text/markdown', 'image/png', 'image/jpeg', 'image/jpg'
    ];
    const supportedExtensions = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md', '.png', '.jpg', '.jpeg'];

    const validFiles = files.filter(file => {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!supportedExtensions.includes(ext) && !supportedMimeTypes.includes(file.type)) {
        toast.error(`${file.name}: Unsupported file type`);
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

    if (validFiles.length > 1) {
      const formData = new FormData();
      validFiles.forEach(file => formData.append('files', file));
      try {
        const response = await axios.post(`${API}/projects/${chat.projectId}/sources/upload-multiple`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        const sourcesRes = await axios.get(`${API}/projects/${chat.projectId}/sources`);
        setProjectSources(sourcesRes.data);
        const uploaded = response.data.uploaded || [];
        const errors = response.data.errors || [];
        if (uploaded.length > 0) toast.success(`Uploaded ${uploaded.length} file(s)`);
        errors.forEach(err => toast.error(`${err.filename}: ${err.error}`));
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Failed to upload files');
      }
    } else {
      const file = validFiles[0];
      const formData = new FormData();
      formData.append('file', file);
      try {
        const response = await axios.post(`${API}/projects/${chat.projectId}/sources/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        setProjectSources(prev => [...prev, response.data]);
        toast.success(`Uploaded ${file.name} (${response.data.chunkCount} chunks extracted)`);
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Failed to upload file');
      }
    }

    setIsUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleAddUrl = async () => {
    const url = urlInput.trim();
    if (!url) { toast.error('Please enter a URL'); return; }
    if (!url.startsWith('http://') && !url.startsWith('https://')) { toast.error('URL must start with http:// or https://'); return; }

    setIsAddingUrl(true);
    try {
      const response = await axios.post(`${API}/projects/${chat.projectId}/sources/url`, { url });
      setProjectSources(prev => [...prev, response.data]);
      setUrlInput('');
      toast.success(`Added URL (${response.data.chunkCount} chunks extracted)`);
      const newActiveIds = [...activeSourceIds, response.data.id];
      await axios.post(`${API}/chats/${chatId}/active-sources`, { sourceIds: newActiveIds });
      setActiveSourceIds(newActiveIds);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add URL');
    } finally {
      setIsAddingUrl(false);
    }
  };

  const deleteSource = async (sourceId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this source?')) return;
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
      const response = await axios.get(`${API}/projects/${chat.projectId}/sources/${source.id}/download`, { responseType: 'blob' });
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

  const saveToDepartment = async (source, e) => {
    e.stopPropagation();
    if (!currentUser?.departments || currentUser.departments.length === 0) {
      toast.error('У вас нет департаментов для сохранения');
      return;
    }
    try {
      const departmentId = currentUser.departments[0];
      await axios.post(`${API}/department-sources/copy-from-project`, { sourceId: source.id, projectId: chat.projectId, departmentId });
      toast.success('Файл сохранен в источники департамента');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save to department');
    }
  };

  const searchSources = async () => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) { toast.error('Введите минимум 2 символа'); return; }
    setIsSearching(true);
    setShowSearchResults(true);
    try {
      const response = await axios.post(`${API}/projects/${chat.projectId}/sources/search`, { query: searchQuery.trim(), limit: 20 });
      setSearchResults(response.data);
      if (response.data.length === 0) toast.info('Ничего не найдено');
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

  const sendMessage = async (contentOverride) => {
    const content = (contentOverride ?? input).trim();
    if (!content || isSending) return;

    const tempUserMsg = { id: `temp-${Date.now()}`, chatId, role: 'user', content, createdAt: new Date().toISOString() };
    setMessages(prev => [...prev, tempUserMsg]);
    setInput('');
    setIsSending(true);

    try {
      const response = await axios.post(`${API}/chats/${chatId}/messages`, { content });
      const { user_message: userMsg, assistant_message: assistantMsg } = response.data;
      if (assistantMsg.autoIngestedUrls && assistantMsg.autoIngestedUrls.length > 0) {
        const sourcesRes = await axios.get(`${API}/projects/${chat.projectId}/sources`);
        setProjectSources(sourcesRes.data);
        const chatRes = await axios.get(`${API}/chats/${chatId}`);
        setActiveSourceIds(chatRes.data.activeSourceIds || []);
        toast.success(`Auto-ingested ${assistantMsg.autoIngestedUrls.length} URL(s) from your message`);
      }
      setMessages(prev => {
        const withoutTemp = prev.filter(m => m.id !== tempUserMsg.id);
        const realUserMsg = { ...tempUserMsg, id: userMsg.id, autoIngestedUrls: userMsg.autoIngestedUrls || null };
        return [...withoutTemp, realUserMsg, assistantMsg];
      });

      // Auto-rename chat after first message if name is auto-generated
      const isAutoName = chat?.name?.startsWith('Новый чат') || chat?.name === 'New Chat';
      const isFirst = messages.filter(m => m.role === 'user').length === 0;
      if (isAutoName && isFirst) {
        const shortName = content.trim().slice(0, 40) + (content.trim().length > 40 ? '...' : '');
        axios.put(`${API}/chats/${chatId}/rename`, { name: shortName })
          .then(res => setChat(prev => ({ ...prev, name: res.data.name || shortName })))
          .catch(() => {});
      }
    } catch (error) {
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
      setInput(content);
      toast.error('Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const formatTime = (dateString) => new Date(dateString).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  const formatFileSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const toggleSourceExpansion = (messageId) => {
    setExpandedSources(prev => ({ ...prev, [messageId]: !prev[messageId] }));
  };

  const viewSourceContent = async (sourceId, sourceName) => {
    setIsLoadingSourceContent(true);
    setViewingSource({ id: sourceId, name: sourceName });
    setSourceContent(null);
    try {
      const response = await axios.get(`${API}/sources/${sourceId}/chunks`);
      const fullContent = response.data
        .sort((a, b) => a.chunkIndex - b.chunkIndex)
        .map(chunk => chunk.content || chunk.text)
        .join('\n\n');
      setSourceContent(fullContent);
    } catch (error) {
      toast.error('Не удалось загрузить содержимое');
      setViewingSource(null);
    } finally {
      setIsLoadingSourceContent(false);
    }
  };

  const closeSourceModal = () => { setViewingSource(null); setSourceContent(null); };

  const saveContext = async () => {
    if (messages.length === 0) {
      toast.error('Нет сообщений для сохранения');
      return;
    }

    setIsSavingContext(true);
    try {
      // Prepare dialog text
      const dialogText = messages
        .map(msg => `${msg.role === 'user' ? 'Пользователь' : 'AI'}: ${msg.content}`)
        .join('\n\n');

      // Send to AI for summarization
      const response = await axios.post(`${API}/chats/${chatId}/save-context`, {
        dialogText
      });

      const contextSummary = response.data.summary;
      
      // Show toast notification
      const toastElement = document.createElement('div');
      toastElement.className = 'fixed bottom-6 left-1/2 transform -translate-x-1/2 bg-emerald-600 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-2 z-50 animate-slide-up';
      toastElement.innerHTML = `
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        <span>Контекст сохранен в AI Profile</span>
      `;
      document.body.appendChild(toastElement);
      
      setTimeout(() => {
        toastElement.remove();
      }, 3000);

    } catch (error) {
      const message = error.response?.data?.detail || 'Не удалось сохранить контекст';
      toast.error(message);
    } finally {
      setIsSavingContext(false);
    }
  };

  const startEditMessage = (message) => {
    setEditingMessageId(message.id);
    setEditedContent(message.content);
  };

  const cancelEditMessage = () => {
    setEditingMessageId(null);
    setEditedContent("");
  };

  const saveEditedMessage = async (messageId) => {
    if (!editedContent.trim()) {
      toast.error('Сообщение не может быть пустым');
      return;
    }

    try {
      const response = await axios.put(`${API}/chats/${chatId}/messages/${messageId}/edit`, {
        content: editedContent
      });

      // Use functional update to avoid stale closure — only remove NEXT messages
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === messageId);
        if (idx === -1) return prev;
        const updated = prev.slice(0, idx + 1);   // keep 0..idx (previous + edited)
        updated[idx] = response.data;              // replace edited with server response
        return updated;
      });

      setEditingMessageId(null);
      setEditedContent("");
      toast.success('Сообщение обновлено');

      // Get new AI response
      setIsSending(true);
      try {
        const aiResponse = await axios.post(`${API}/chats/${chatId}/messages`, {
          content: editedContent
        });
        const { user_message: editedUserMsg, assistant_message: newAssistantMsg } = aiResponse.data;
        setMessages(prev => [...prev, { ...editedUserMsg, content: editedContent }, newAssistantMsg]);
        setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);

        // Auto-rename chat after first exchange if name is auto-generated
        const isAutoName = chat?.name?.startsWith('Новый чат') || chat?.name === 'New Chat';
        const isFirstMessage = messages.filter(m => m.role === 'user').length === 1;
        if (isAutoName && isFirstMessage) {
          const shortName = content.trim().slice(0, 40) + (content.trim().length > 40 ? '...' : '');
          axios.put(`${API}/chats/${chatId}/rename`, { name: shortName })
            .then(res => setChat(prev => ({ ...prev, name: res.data.name || shortName })))
            .catch(() => {});
        }
      } catch (aiError) {
        console.error('Failed to get AI response:', aiError);
        toast.error('Не удалось получить ответ AI');
      } finally {
        setIsSending(false);
      }

    } catch (error) {
      const message = error.response?.data?.detail || 'Не удалось обновить сообщение';
      toast.error(message);
    }
  };

  const groupedSources = React.useMemo(() => {
    const groups = {
      pdf: { label: 'PDF документы', icon: FileText, color: 'text-red-400', sources: [] },
      doc: { label: 'Документы Word', icon: File, color: 'text-blue-500', sources: [] },
      excel: { label: 'Таблицы Excel', icon: File, color: 'text-green-500', sources: [] },
      ppt: { label: 'Презентации', icon: File, color: 'text-orange-500', sources: [] },
      url: { label: 'Web URLs', icon: Globe, color: 'text-blue-400', sources: [] },
      image: { label: 'Изображения', icon: ImageIcon, color: 'text-purple-400', sources: [] },
      other: { label: 'Другие файлы', icon: FileText, color: 'text-gray-400', sources: [] }
    };
    projectSources.forEach(source => {
      if (source.kind === 'url') groups.url.sources.push(source);
      else if (source.mimeType?.includes('pdf')) groups.pdf.sources.push(source);
      else if (source.mimeType?.includes('wordprocessingml')) groups.doc.sources.push(source);
      else if (source.mimeType?.includes('spreadsheetml')) groups.excel.sources.push(source);
      else if (source.mimeType?.includes('presentationml')) groups.ppt.sources.push(source);
      else if (source.mimeType?.includes('image')) groups.image.sources.push(source);
      else groups.other.sources.push(source);
    });
    return Object.entries(groups).filter(([_, group]) => group.sources.length > 0);
  }, [projectSources]);

  const toggleGroup = (groupKey) => setExpandedGroups(prev => ({ ...prev, [groupKey]: !prev[groupKey] }));
  const toggleSourceSelection = (sourceId) => setActiveSourceIds(prev => prev.includes(sourceId) ? prev.filter(id => id !== sourceId) : [...prev, sourceId]);
  const toggleGroupSelection = (sources) => {
    const sourceIds = sources.map(s => s.id);
    const allSelected = sourceIds.every(id => activeSourceIds.includes(id));
    if (allSelected) setActiveSourceIds(prev => prev.filter(id => !sourceIds.includes(id)));
    else setActiveSourceIds(prev => [...new Set([...prev, ...sourceIds])]);
  };
  const selectAllSources = () => setActiveSourceIds(projectSources.map(s => s.id));
  const deselectAllSources = () => setActiveSourceIds([]);

  useEffect(() => {
    if (!chatId || isLoading) return;
    const syncActiveSources = async () => {
      try {
        await axios.post(`${API}/chats/${chatId}/active-sources`, { sourceIds: activeSourceIds });
      } catch (error) {
        console.error('Failed to sync active sources:', error);
      }
    };
    const timeoutId = setTimeout(syncActiveSources, 500);
    return () => clearTimeout(timeoutId);
  }, [activeSourceIds, chatId, isLoading]);

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
              onClick={() => chat?.projectId ? navigate(`/projects/${chat.projectId}`) : navigate('/dashboard')}
              data-testid="back-from-chat-btn"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
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
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={saveNewName} disabled={isSavingName} data-testid="save-chat-name-btn">
                    {isSavingName ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4 text-emerald-400" />}
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={cancelEditingName} disabled={isSavingName}>
                    <X className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>
              ) : (
                <h1 className="font-semibold flex items-center gap-2">
                  {isQuickChat ? (
                    <>
                      <MessageSquare className="h-4 w-4 text-emerald-400" />
                      <span className="cursor-pointer hover:text-emerald-400 transition-colors" onClick={startEditingName} title="Click to rename" data-testid="chat-name-display">
                        {chat.name || 'Quick Chat'}
                      </span>
                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-50 hover:opacity-100" onClick={startEditingName} data-testid="edit-chat-name-btn">
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
                  <span className="ml-2 text-indigo-400">• {activeSourceIds.length} source{activeSourceIds.length !== 1 ? 's' : ''} active</span>
                )}
                {isQuickChat && <span className="ml-2 text-emerald-400">• Quick Chat</span>}
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {/* Source Mode Toggle */}
            <div className="flex items-center gap-1 bg-muted/50 rounded-lg p-1">
              <Button
                variant={sourceMode === 'my' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => updateSourceMode('my')}
                className={`gap-1.5 h-8 ${sourceMode === 'my' ? 'bg-violet-600 hover:bg-violet-700' : ''}`}
                data-testid="source-mode-my"
              >
                <Target className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">My Sources</span>
              </Button>
              <Button
                variant={sourceMode === 'all' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => updateSourceMode('all')}
                className={`gap-1.5 h-8 ${sourceMode === 'all' ? 'bg-emerald-600 hover:bg-emerald-700' : ''}`}
                data-testid="source-mode-all"
              >
                <Globe2 className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">All Sources</span>
              </Button>
            </div>

            {/* Move Chat Button */}
            <Button variant="outline" size="sm" onClick={openMoveDialog} className="gap-2" data-testid="move-chat-btn">
              <MoveRight className="h-4 w-4" />
              Move
            </Button>

            {/* Project Memory Button - only for project chats */}
            {!isQuickChat && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setMemoryModalOpen(true)}
                disabled={messages.length === 0}
                className="gap-2"
                data-testid="memory-btn"
                title="Сохранить в Project Memory"
              >
                <Brain className="h-4 w-4 text-violet-400" />
                <span className="hidden sm:inline">Memory</span>
              </Button>
            )}

            {/* Image Generator - only for project chats */}
            {chat && chat.projectId && (
              <ImageGenerator projectId={chat.projectId} onImageGenerated={handleImageGenerated} />
            )}

            {/* Source Panel Toggle - only for project chats */}
            {!isQuickChat && (
              <Button variant="outline" size="sm" onClick={() => setShowSourcePanel(!showSourcePanel)} className="gap-2" data-testid="toggle-source-panel-btn">
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
                {showCreateProject ? "Create a new project and move this chat into it." : "Select a project to move this chat into."}
                {chat?.projectId && !showCreateProject && " The chat will be removed from its current project."}
              </DialogDescription>
            </DialogHeader>
            {showCreateProject ? (
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
                  <Button variant="outline" className="flex-1" onClick={() => setShowCreateProject(false)} disabled={isCreatingProject}>Back</Button>
                  <Button className="flex-1" onClick={createProjectAndMove} disabled={isCreatingProject || !newProjectName.trim()} data-testid="create-and-move-btn">
                    {isCreatingProject ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                    Create & Move
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2 py-4 max-h-[300px] overflow-y-auto">
                {userProjects.length === 0 ? (
                  <div className="text-center py-4">
                    <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                    <p className="text-muted-foreground mb-4">No projects yet</p>
                    <Button onClick={() => setShowCreateProject(true)} data-testid="create-project-in-dialog-btn">
                      <Plus className="mr-2 h-4 w-4" />Create Project
                    </Button>
                  </div>
                ) : (
                  <>
                    {userProjects.filter(p => p.id !== chat?.projectId).map((project) => (
                      <Card key={project.id} className="cursor-pointer hover:border-indigo-500/50 transition-colors" onClick={() => moveChat(project.id)} data-testid={`move-to-project-${project.id}`}>
                        <CardContent className="py-3 flex items-center gap-3">
                          <FolderOpen className="h-5 w-5 text-indigo-400" />
                          <span className="font-medium">{project.name}</span>
                        </CardContent>
                      </Card>
                    ))}
                    {userProjects.filter(p => p.id !== chat?.projectId).length === 0 && (
                      <p className="text-center text-muted-foreground py-4">No other projects available.</p>
                    )}
                    <Card className="cursor-pointer hover:border-emerald-500/50 transition-colors border-dashed" onClick={() => setShowCreateProject(true)} data-testid="create-new-project-option">
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
              <Button variant="outline" onClick={() => setMoveDialogOpen(false)} disabled={isMovingChat || isCreatingProject}>Cancel</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Source Panel */}
        {!isQuickChat && showSourcePanel && (
          <div className="border-b border-border bg-card/30 px-6 py-4" data-testid="source-panel">
            <div className="max-w-3xl mx-auto">
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
                <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={isUploading} className="gap-2" data-testid="upload-file-btn">
                  {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  Upload Files
                </Button>
                <div className="flex-1 flex items-center gap-2 min-w-[200px]">
                  <Input placeholder="https://example.com/article" value={urlInput} onChange={(e) => setUrlInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleAddUrl()} className="h-9 text-sm" data-testid="url-input" />
                  <Button variant="outline" size="sm" onClick={handleAddUrl} disabled={isAddingUrl || !urlInput.trim()} className="gap-2 whitespace-nowrap" data-testid="add-url-btn">
                    {isAddingUrl ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link className="h-4 w-4" />}
                    Add URL
                  </Button>
                </div>
              </div>

              <div className="flex items-center gap-2 mb-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input placeholder="Поиск в документах (0 токенов)..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && searchSources()} className="h-9 text-sm pl-9" data-testid="search-sources-input" />
                </div>
                <Button variant="default" size="sm" onClick={searchSources} disabled={isSearching || !searchQuery.trim()} className="gap-2" data-testid="search-sources-btn">
                  {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Найти
                </Button>
              </div>

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
                          <p className="text-xs text-muted-foreground" dangerouslySetInnerHTML={{ __html: highlightMatch(result.content, searchQuery) }} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="text-xs text-muted-foreground mb-3">
                Supported: PDF, DOCX, PPTX, XLSX, TXT, MD, PNG, JPEG files and web URLs (multiple files allowed)
              </div>

              {projectSources.length > 0 && showInfoBlock && (
                <div className="mb-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 relative">
                  <button onClick={() => setShowInfoBlock(false)} className="absolute top-2 right-2 p-1 hover:bg-blue-500/20 rounded transition-colors">
                    <X className="h-4 w-4 text-blue-400" />
                  </button>
                  <div className="flex items-start gap-3 pr-8">
                    <Info className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1 text-sm text-blue-200/90 space-y-2">
                      <p className="font-medium text-blue-300">Как работают источники в AI-чате:</p>
                      <ul className="space-y-1.5 text-xs">
                        <li className="flex items-start gap-2"><Database className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" /><span><strong className="text-blue-300">Иерархия:</strong> Личные → Проектные → Департамент → Глобальные</span></li>
                        <li className="flex items-start gap-2"><Target className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" /><span><strong className="text-blue-300">Активные источники:</strong> Только выбранные источники используются для генерации ответов</span></li>
                        <li className="flex items-start gap-2"><Lightbulb className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" /><span><strong className="text-blue-300">Влияние на ответы:</strong> AI ищет информацию в активных источниках и формирует ответ на основе найденного контекста</span></li>
                        <li className="flex items-start gap-2"><ChevronRight className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" /><span><strong className="text-blue-300">Режимы:</strong> "Только проектные" использует только источники проекта, "Все источники" включает доступные на всех уровнях</span></li>
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {projectSources.length === 0 ? (
                <div className="text-center py-6 text-muted-foreground">
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Источники не загружены</p>
                  <p className="text-xs mt-1">Загрузите файлы или добавьте URL для контекста</p>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-border">
                    <span className="text-xs text-muted-foreground">Выбрано: {activeSourceIds.length} из {projectSources.length}</span>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={selectAllSources} data-testid="select-all-sources">Все</Button>
                      <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={deselectAllSources} data-testid="deselect-all-sources">Сбросить</Button>
                    </div>
                  </div>
                  <div className="max-h-[280px] overflow-y-auto space-y-1">
                    {groupedSources.map(([groupKey, group]) => {
                      const GroupIcon = group.icon;
                      const isExpanded = expandedGroups[groupKey];
                      const groupSourceIds = group.sources.map(s => s.id);
                      const selectedInGroup = groupSourceIds.filter(id => activeSourceIds.includes(id)).length;
                      const allSelected = selectedInGroup === group.sources.length;
                      const someSelected = selectedInGroup > 0 && selectedInGroup < group.sources.length;
                      return (
                        <div key={groupKey} className="rounded-lg border border-border overflow-hidden">
                          <div className="flex items-center gap-2 p-2 bg-secondary/30 cursor-pointer hover:bg-secondary/50 transition-colors" onClick={() => toggleGroup(groupKey)}>
                            <Checkbox checked={allSelected} ref={someSelected ? (el) => { if (el) el.indeterminate = true; } : undefined} onCheckedChange={() => toggleGroupSelection(group.sources)} onClick={(e) => e.stopPropagation()} className="data-[state=checked]:bg-indigo-500" data-testid={`group-checkbox-${groupKey}`} />
                            {isExpanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                            <GroupIcon className={`h-4 w-4 ${group.color}`} />
                            <span className="text-sm font-medium flex-1">{group.label}</span>
                            <span className="text-xs text-muted-foreground">{selectedInGroup}/{group.sources.length}</span>
                          </div>
                          {isExpanded && (
                            <div className="border-t border-border">
                              {group.sources.map((source) => {
                                const isSelected = activeSourceIds.includes(source.id);
                                return (
                                  <div key={source.id} className={`flex items-center gap-2 p-2 pl-8 transition-colors ${isSelected ? 'bg-indigo-500/10' : 'hover:bg-secondary/20'}`} data-testid={`source-item-${source.id}`}>
                                    <Checkbox checked={isSelected} onCheckedChange={() => toggleSourceSelection(source.id)} className="data-[state=checked]:bg-indigo-500" data-testid={`source-checkbox-${source.id}`} />
                                    {getFileIcon(source.mimeType, source.kind)}
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm truncate">{source.originalName || source.url}</p>
                                      <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
                                        <p className="text-xs text-muted-foreground">{source.sizeBytes ? `${formatFileSize(source.sizeBytes)} • ` : ''}{source.chunkCount} chunks</p>
                                        {currentProjectName && (
                                          <span className="inline-flex items-center gap-0.5 text-xs text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded-full border border-indigo-500/20" data-testid={`source-project-badge-${source.id}`}>
                                            <FolderOpen className="h-2.5 w-2.5 flex-shrink-0" />
                                            <span className="truncate max-w-[90px]">{currentProjectName}</span>
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-1">
                                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); openPreview(source, e); }} title="Просмотр" data-testid={`preview-source-${source.id}`}><Eye className="h-3.5 w-3.5 text-blue-400" /></Button>
                                      {source.kind === 'file' && <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); downloadSource(source, e); }} title="Скачать" data-testid={`download-source-${source.id}`}><Download className="h-3.5 w-3.5 text-green-400" /></Button>}
                                      {source.level === 'project' && currentUser?.departments?.length > 0 && <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); saveToDepartment(source, e); }} title="Сохранить в источники департамента" data-testid={`save-to-dept-${source.id}`}><Building2 className="h-3.5 w-3.5 text-amber-400" /></Button>}
                                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); deleteSource(source.id, e); }} data-testid={`delete-source-${source.id}`}><Trash2 className="h-3.5 w-3.5 text-destructive" /></Button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {projectSources.length > 0 && (
                <p className="text-xs text-muted-foreground mt-3 flex items-center gap-1">
                  <span className="inline-block w-2 h-2 rounded-full bg-indigo-500"></span>
                  Выбранные источники используются как контекст для AI ответов
                </p>
              )}
            </div>
          </div>
        )}

        {/* Preview Dialog */}
        <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
          <DialogContent className="sm:max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><FileText className="h-5 w-5" />{previewSource?.name || 'Source Preview'}</DialogTitle>
              <DialogDescription>{previewSource?.chunkCount} chunks • {previewSource?.wordCount || 0} слов • {previewSource?.kind === 'url' ? 'URL' : previewSource?.mimeType}</DialogDescription>
            </DialogHeader>
            {previewLoading ? (
              <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
            ) : (
              <>
                <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${previewSource?.quality === 'good' ? 'bg-green-500/10 text-green-600 dark:text-green-400' : previewSource?.quality === 'low' ? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400' : previewSource?.quality === 'poor' || previewSource?.quality === 'empty' ? 'bg-red-500/10 text-red-600 dark:text-red-400' : 'bg-secondary'}`}>
                  <span className={`w-2 h-2 rounded-full ${previewSource?.quality === 'good' ? 'bg-green-500' : previewSource?.quality === 'low' ? 'bg-yellow-500' : 'bg-red-500'}`}></span>
                  {previewSource?.qualityMessage || 'Текст извлечён'}
                </div>
                <ScrollArea className="max-h-[45vh] mt-3">
                  <pre className="text-sm whitespace-pre-wrap font-mono bg-secondary/50 p-4 rounded-lg">{previewSource?.text || 'No content'}</pre>
                </ScrollArea>
              </>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Messages Area */}
        <ScrollArea className="flex-1 px-6 py-4" ref={scrollAreaRef}>
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="rounded-full bg-secondary p-4 mb-4"><Bot className="h-8 w-8 text-indigo-400" /></div>
              <h3 className="text-lg font-semibold mb-2">Start a conversation</h3>
              <p className="text-muted-foreground max-w-md">
                {projectSources.length > 0 ? (
                  <span>Select sources above, then ask questions about them.<span className="block mt-2 text-indigo-400">The AI will cite specific chunks from your documents.</span></span>
                ) : (
                  <span>Upload PDFs, DOCX, TXT files or add URLs to use as context.<span className="block mt-2">The AI will answer questions based on your sources.</span></span>
                )}
              </p>
            </div>
          ) : (
            <div className="space-y-6 max-w-3xl mx-auto">
              {messages.map((message, index) => (
                <div key={message.id} className={`flex gap-4 animate-slideIn ${message.role === 'user' ? 'justify-end' : 'justify-start'}`} style={{ animationDelay: `${index * 30}ms` }} data-testid={`message-${message.role}-${index}`}>
                  {message.role === 'assistant' && (
                    <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit"><Bot className="h-5 w-5 text-indigo-400" /></div>
                  )}
                  <div className={`flex flex-col gap-1 max-w-[80%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                    {message.role === 'user' && message.senderName && (
                      <span className="text-xs text-muted-foreground px-2">{message.senderName}</span>
                    )}
                    {message.isGeneratedImage && message.imageData ? (
                      <div className="space-y-2">
                        <div className="relative rounded-lg overflow-hidden border border-indigo-500/30 max-w-md">
                          <AuthImage imageId={message.imageData.id} alt={message.imageData.prompt} className="w-full h-auto" data-testid={`generated-image-${message.imageData.id}`} />
                          <div className="absolute top-2 right-2">
                            <Button variant="secondary" size="icon" className="h-8 w-8 bg-black/50 hover:bg-black/70" onClick={() => downloadImage(message.imageData.id)} data-testid={`download-image-${message.imageData.id}`}>
                              <Download className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 px-2">
                          <ImageIcon className="h-3 w-3 text-indigo-400" />
                          <span className="text-xs text-muted-foreground truncate max-w-xs">{message.imageData.prompt}</span>
                        </div>
                      </div>
                    ) : (
                      <div className={`group relative ${editingMessageId === message.id ? '' : ''}`}>
                        {editingMessageId === message.id ? (
                          // Edit mode — match message bubble width
                          <div className="space-y-2">
                            <textarea
                              value={editedContent}
                              onChange={(e) => {
                                setEditedContent(e.target.value);
                                e.target.style.height = 'auto';
                                e.target.style.height = e.target.scrollHeight + 'px';
                              }}
                              ref={(el) => { if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px'; } }}
                              style={{
                                width: `${Math.min(Math.max(
                                  Math.max(...editedContent.split('\n').map(l => l.length)) * 8.5 + 40,
                                  200
                                ), 560)}px`
                              }}
                              className="px-4 py-3 rounded-2xl bg-primary/10 text-foreground border border-primary/20 focus:border-primary focus:outline-none resize-none overflow-hidden block"
                              autoFocus
                            />
                            <div className="flex gap-2 justify-end">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={cancelEditMessage}
                              >
                                <X className="h-4 w-4 mr-1" />
                                Cancel
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => saveEditedMessage(message.id)}
                              >
                                <Check className="h-4 w-4 mr-1" />
                                Save
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className={`px-4 py-3 rounded-2xl ${message.role === 'user' ? 'bg-primary text-primary-foreground rounded-br-sm' : 'bg-secondary text-secondary-foreground rounded-bl-sm'}`}>
                              <p className="whitespace-pre-wrap text-sm leading-relaxed">{renderTextWithLinks(message.content)}</p>
                            </div>
                            {message.role === 'user' && (
                              <div className="absolute -bottom-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 bg-background border border-border shadow-sm"
                                  onClick={() => startEditMessage(message)}
                                  title="Edit message"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            )}
                            {message.role === 'assistant' && (
                              <div className="absolute -bottom-1 -right-1 flex gap-1">
                                <Button variant="ghost" size="icon" className="h-7 w-7 bg-background border border-border shadow-sm"
                                  onClick={async () => {
                                    try {
                                      await axios.post(`${API}/save-to-knowledge`, { content: message.content, chatId });
                                      toast.success('Saved to Knowledge ✅');
                                    } catch (err) { toast.error('Failed to save'); }
                                  }}
                                  title="Save to Knowledge" data-testid={`save-message-${index}`}>
                                  <Save className="h-3.5 w-3.5 text-green-500" />
                                </Button>
                                <Button variant="ghost" size="icon" className="h-7 w-7 bg-background border border-border shadow-sm"
                                  onClick={async () => {
                                    try {
                                      await navigator.clipboard.writeText(message.content);
                                      toast.success('Copied to clipboard');
                                    } catch (err) {
                                      const textArea = document.createElement('textarea');
                                      textArea.value = message.content;
                                      textArea.style.position = 'fixed';
                                      textArea.style.left = '-9999px';
                                      document.body.appendChild(textArea);
                                      textArea.select();
                                      try { document.execCommand('copy'); toast.success('Copied to clipboard'); }
                                      catch (e) { toast.error('Failed to copy'); }
                                      document.body.removeChild(textArea);
                                    }
                                  }}
                                  data-testid={`copy-message-${index}`}>
                                  <Copy className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                    {message.role === 'user' && message.autoIngestedUrls?.length > 0 && (
                      <div className="mt-1 px-2">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">
                          <Globe className="h-3 w-3" />
                          {message.autoIngestedUrls.length} URL{message.autoIngestedUrls.length > 1 ? 's' : ''} auto-ingested
                        </span>
                      </div>
                    )}
                    {message.role === 'assistant' && message.competitorInfo && (
                      <div className="mt-2 px-2">
                        <div className="flex items-center gap-2 p-2 rounded-lg bg-orange-500/10 border border-orange-500/20">
                          <TrendingUp className="h-4 w-4 text-orange-400" />
                          <div className="flex-1">
                            <p className="text-xs font-medium text-orange-400">🔍 Competitor Data Used</p>
                            <p className="text-xs text-muted-foreground">{message.competitorInfo.competitor_name} - {message.competitorInfo.product_title}</p>
                          </div>
                        </div>
                      </div>
                    )}
                    {message.role === 'assistant' && !message.isGeneratedImage && (message.citations?.length > 0 || message.usedSources?.length > 0) && (
                      <div className="mt-2 px-2">
                        <button onClick={() => toggleSourceExpansion(message.id)} className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1 px-2 rounded hover:bg-secondary/50" data-testid={`toggle-sources-${index}`}>
                          <Quote className="h-3 w-3" />
                          <span className="font-medium">Sources ({(message.citations || message.usedSources)?.length})</span>
                          {expandedSources[message.id] ? <ChevronUp className="h-3 w-3 ml-auto" /> : <ChevronDown className="h-3 w-3 ml-auto" />}
                        </button>
                        {expandedSources[message.id] && (
                          <div className="flex flex-wrap gap-2 mt-2 animate-slideIn">
                            {message.citations ? message.citations.map((citation, cidx) => {
                              const isGlobal = citation.sourceType === 'global';
                              const bgColor = isGlobal ? 'bg-emerald-500/10' : 'bg-indigo-500/10';
                              const textColor = isGlobal ? 'text-emerald-400' : 'text-indigo-400';
                              const borderColor = isGlobal ? 'border-emerald-500/20' : 'border-indigo-500/20';
                              const Icon = isGlobal ? Globe : FileText;
                              return (
                                <button key={cidx} onClick={() => viewSourceContent(citation.sourceId, citation.sourceName)} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${bgColor} ${textColor} text-xs border ${borderColor} hover:opacity-80 transition-opacity cursor-pointer`} data-testid={`citation-${cidx}`} title={`Нажмите для просмотра: ${citation.sourceName}`}>
                                  <Icon className="h-3 w-3" />
                                  <span className="font-medium">{isGlobal ? '🌐 ' : '📁 '}{citation.sourceName.length > 25 ? citation.sourceName.slice(0, 25) + '...' : citation.sourceName}</span>
                                  {citation.chunks && <span className="opacity-70">(chunks {Array.isArray(citation.chunks) ? citation.chunks.map(c => c.index || c).join(', ') : citation.chunks})</span>}
                                </button>
                              );
                            }) : message.usedSources?.map((source, sidx) => {
                              const isGlobal = source.sourceType === 'global';
                              const bgColor = isGlobal ? 'bg-emerald-500/10' : 'bg-indigo-500/10';
                              const textColor = isGlobal ? 'text-emerald-400' : 'text-indigo-400';
                              const borderColor = isGlobal ? 'border-emerald-500/20' : 'border-indigo-500/20';
                              const Icon = isGlobal ? Globe : FileText;
                              return (
                                <button key={sidx} onClick={() => viewSourceContent(source.sourceId, source.sourceName)} className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${bgColor} ${textColor} text-xs border ${borderColor} hover:opacity-80 transition-opacity cursor-pointer`} data-testid={`used-source-${sidx}`} title={`Нажмите для просмотра: ${source.sourceName}`}>
                                  <Icon className="h-3 w-3" />
                                  {isGlobal ? '🌐 ' : '📁 '}{source.sourceName.length > 25 ? source.sourceName.slice(0, 25) + '...' : source.sourceName}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* Web Sources Section */}
                    {message.role === 'assistant' && message.web_sources?.length > 0 && (
                      <div className="mt-2 px-2">
                        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-2">
                          <Globe2 className="h-3 w-3" />
                          <span>🌐 Web Sources</span>
                        </div>
                        <div className="flex flex-col gap-1.5">
                          {message.web_sources.map((webSource, idx) => (
                            <a
                              key={idx}
                              href={webSource.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-start gap-2 px-3 py-2 rounded-md bg-blue-500/10 text-blue-400 text-xs border border-blue-500/20 hover:bg-blue-500/20 transition-colors"
                            >
                              <Link className="h-3 w-3 flex-shrink-0 mt-0.5" />
                              <div className="flex-1">
                                <div className="font-medium">{webSource.title}</div>
                                <div className="text-xs opacity-70 truncate">{webSource.url}</div>
                              </div>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Fetched URL Content Indicator */}
                    {message.role === 'assistant' && message.fetchedUrls?.length > 0 && (
                      <div className="mt-2 px-2">
                        <div className="flex flex-wrap gap-1.5" data-testid="fetched-urls-indicator">
                          {message.fetchedUrls.map((url, idx) => {
                            let hostname = url;
                            try { hostname = new URL(url).hostname; } catch {}
                            return (
                              <a
                                key={idx}
                                href={url}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={url}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-sky-500/10 text-sky-400 text-xs border border-sky-500/20 hover:bg-sky-500/20 transition-colors"
                                data-testid={`fetched-url-badge-${idx}`}
                              >
                                <Link className="h-3 w-3 flex-shrink-0" />
                                <span className="truncate max-w-[160px]">URL прочитан: {hostname}</span>
                              </a>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Excel Result Block */}
                    {message.role === 'assistant' && message.excel_preview && message.excel_file_id && (
                      <div className="mt-2 px-2" data-testid={`excel-result-block-${index}`}>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              const response = await axios.get(
                                `${process.env.REACT_APP_BACKEND_URL}/api/excel/download/${message.excel_file_id}`,
                                { responseType: 'blob' }
                              );
                              const url = window.URL.createObjectURL(new Blob([response.data]));
                              const link = document.createElement('a');
                              link.href = url;
                              link.setAttribute('download', 'result.xlsx');
                              document.body.appendChild(link);
                              link.click();
                              link.remove();
                              window.URL.revokeObjectURL(url);
                            } catch (err) {
                              toast.error('Не удалось скачать файл');
                            }
                          }}
                          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-green-500/30 bg-green-500/10 hover:bg-green-500/20 text-green-400 text-xs font-medium transition-colors"
                          title="Файл удаляется после первого скачивания"
                          data-testid={`excel-download-chat-${index}`}
                        >
                          <Download className="h-3.5 w-3.5" />
                          Скачать Excel ({message.excel_preview.total_rows} строк)
                        </button>
                      </div>
                    )}
                    
                    {/* Clarifying Questions Section */}
                    {message.role === 'assistant' && message.clarifying_question && message.clarifying_options?.length > 0 && (
                      <div className="mt-3 px-2">
                        <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-300 dark:border-amber-500/20">
                          <div className="flex items-start gap-2 mb-3">
                            <MessageSquare className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                            <p className="text-sm font-medium text-amber-800 dark:text-amber-300">{message.clarifying_question}</p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {message.clarifying_options.map((option, idx) => (
                              <Button
                                key={idx}
                                variant="outline"
                                size="sm"
                                onClick={() => sendMessage(option)}
                                className="bg-amber-100 dark:bg-amber-500/20 border-amber-400 dark:border-amber-500/30 text-amber-800 dark:text-amber-200 hover:bg-amber-200 dark:hover:bg-amber-500/30 hover:text-amber-900 dark:hover:text-amber-100"
                              >
                                {option}
                              </Button>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {message.fromCache && (
                      <div className="mt-1 px-2">
                        <span className="inline-flex items-center gap-1 text-xs text-amber-500">
                          📦 Из кэша {message.cacheInfo?.similarity && <span className="opacity-70">({(message.cacheInfo.similarity * 100).toFixed(0)}%)</span>}
                        </span>
                      </div>
                    )}
                    <span className="text-xs text-muted-foreground px-1">{formatTime(message.createdAt)}</span>
                  </div>
                  {message.role === 'user' && (
                    <div className="flex-shrink-0 rounded-full bg-emerald-500/20 p-2 h-fit"><User className="h-5 w-5 text-emerald-400" /></div>
                  )}
                </div>
              ))}
              {isSending && (
                <div className="flex gap-4 justify-start animate-slideIn">
                  <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit"><Bot className="h-5 w-5 text-indigo-400" /></div>
                  <div className="bg-secondary px-4 py-3 rounded-2xl rounded-bl-sm"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* Smart Question Suggestions — hidden */}
        {/* <SmartQuestions
          chatId={chatId}
          token={token}
          hasActiveSources={true}
          onQuestionClick={(question) => {
            setInput(question);
            setTimeout(() => {
              const btn = document.querySelector('[data-testid="send-message-btn"]');
              if (btn && !btn.disabled) btn.click();
            }, 100);
          }}
        /> */}

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <div className="fixed bottom-44 left-1/2 -translate-x-1/2 z-50">
            <button
              onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary text-primary-foreground text-xs font-medium shadow-lg hover:bg-primary/90 transition-all animate-bounce"
            >
              <ChevronDown className="h-3.5 w-3.5" />
              Scroll down
            </button>
          </div>
        )}

        {/* Input Area */}
        <div className="border-t border-border px-6 py-4 bg-card/50 backdrop-blur">
          <div className="max-w-3xl mx-auto space-y-2">
            {/* Textarea + Send row */}
            <div className="flex gap-3 items-end">
              {/* Plus button inside chat field */}
              {!isQuickChat && (
                <div className="relative flex-shrink-0 self-end mb-0.5" ref={plusMenuRef}>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.md,.png,.jpg,.jpeg"
                    onChange={(e) => { handleFileUpload(e); setShowPlusMenu(false); }}
                    className="hidden"
                    id="chat-input-file"
                  />
                  <button
                    onClick={() => setShowPlusMenu(prev => !prev)}
                    disabled={isUploading}
                    className="flex items-center justify-center h-9 w-9 rounded-full border border-border bg-background hover:bg-secondary transition-colors disabled:opacity-50"
                    data-testid="chat-plus-btn"
                  >
                    {isUploading
                      ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                      : <Plus className="h-4 w-4 text-muted-foreground" />}
                  </button>

                  {showPlusMenu && (
                    <div className="absolute bottom-11 left-0 z-50 w-52 rounded-xl border border-border bg-card shadow-xl overflow-hidden">
                      <button
                        className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                        onClick={() => { document.getElementById('chat-input-file').click(); setShowPlusMenu(false); }}
                      >
                        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-indigo-500/15">
                          <Upload className="h-4 w-4 text-indigo-400" />
                        </div>
                        <div>
                          <p className="font-medium">Upload File</p>
                          <p className="text-xs text-muted-foreground">PDF, DOCX, XLSX, IMG</p>
                        </div>
                      </button>

                      <button
                        className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                        onClick={() => { setShowSourcePanel(true); setShowPlusMenu(false); }}
                      >
                        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-blue-500/15">
                          <Link className="h-4 w-4 text-blue-400" />
                        </div>
                        <div>
                          <p className="font-medium">Add URL</p>
                          <p className="text-xs text-muted-foreground">Web page or article</p>
                        </div>
                      </button>

                      {chat?.projectId && (
                        <button
                          className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                          onClick={() => { setShowPlusMenu(false); document.querySelector('[data-testid="generate-image-btn"]')?.click(); }}
                        >
                          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-purple-500/15">
                            <ImageIcon className="h-4 w-4 text-purple-400" />
                          </div>
                          <div>
                            <p className="font-medium">Generate Image</p>
                            <p className="text-xs text-muted-foreground">AI image generation</p>
                          </div>
                        </button>
                      )}

                      <button
                        className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                        onClick={() => { saveContext(); setShowPlusMenu(false); }}
                        disabled={isSavingContext || messages.length === 0}
                      >
                        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-emerald-500/15">
                          <Save className="h-4 w-4 text-emerald-400" />
                        </div>
                        <div>
                          <p className="font-medium">Save Context</p>
                          <p className="text-xs text-muted-foreground">Save to AI Profile</p>
                        </div>
                      </button>

                      {!isQuickChat && (
                        <button
                          className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                          onClick={() => { setMemoryModalOpen(true); setShowPlusMenu(false); }}
                          disabled={messages.length === 0}
                        >
                          <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-violet-500/15">
                            <Brain className="h-4 w-4 text-violet-400" />
                          </div>
                          <div>
                            <p className="font-medium">Project Memory</p>
                            <p className="text-xs text-muted-foreground">Save to memory</p>
                          </div>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              <Textarea
                ref={textareaRef}
                placeholder={activeSourceIds.length > 0 ? "Ask a question about the selected sources..." : "Type your message... (Enter to send, Shift+Enter for new line)"}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                className="min-h-[60px] max-h-[200px] resize-none bg-background flex-1"
                disabled={isSending}
                data-testid="chat-input"
              />
              <Button onClick={() => sendMessage()} disabled={!input.trim() || isSending} className="btn-hover self-end" data-testid="send-message-btn">
                {isSending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Source Content Viewer Modal */}
      <Dialog open={!!viewingSource} onOpenChange={closeSourceModal}>
        <DialogContent className="sm:max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><FileText className="h-5 w-5 text-indigo-400" />{viewingSource?.name}</DialogTitle>
            <DialogDescription>Содержимое источника</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] pr-4">
            {isLoadingSourceContent ? (
              <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
            ) : sourceContent ? (
              <div className="space-y-4">
                <div className="p-4 bg-secondary/30 rounded-lg">
                  <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed">{sourceContent}</pre>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">Не удалось загрузить содержимое</div>
            )}
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={closeSourceModal}>Закрыть</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Project Memory Modal */}
      {!isQuickChat && (
        <ProjectMemoryModal
          open={memoryModalOpen}
          onClose={() => setMemoryModalOpen(false)}
          chatId={chatId}
          projectId={chat?.projectId}
          messages={messages}
        />
      )}
    </DashboardLayout>
  );
};

export default ChatPage;