import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';
import {
  Send,
  ArrowLeft,
  Bot,
  User,
  Loader2,
  FileText,
  ChevronDown,
  ChevronUp,
  Paperclip,
  Globe,
  Quote,
  ImageIcon,
  Download,
  MessageSquare,
  MoveRight,
  Pencil,
  Check,
  X,
  Copy,
  Save,
  Target,
  Globe2,
  TrendingUp,
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import ImageGenerator from '../components/ImageGenerator';
import AuthImage from '../components/AuthImage';
import SmartQuestions from '../components/SmartQuestions';
import { SourcePanel } from '../components/chat/SourcePanel';
import { MoveDialog } from '../components/chat/MoveDialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const URL_REGEX = /(https?:\/\/[^\s<>"{}|\\^`[\]]+)/g;

const renderTextWithLinks = (text) => {
  if (!text) return null;
  const parts = text.split(URL_REGEX);
  return parts.map((part, index) => {
    if (URL_REGEX.test(part)) {
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

const ChatPage = () => {
  const { chatId } = useParams();
  const navigate = useNavigate();

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [chat, setChat] = useState(null);
  const [projectSources, setProjectSources] = useState([]);
  const [activeSourceIds, setActiveSourceIds] = useState([]);
  const [generatedImages, setGeneratedImages] = useState([]);
  const [showSourcePanel, setShowSourcePanel] = useState(false);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);

  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [isSavingName, setIsSavingName] = useState(false);
  const nameInputRef = useRef(null);

  const [sourceMode, setSourceMode] = useState('all');

  const [expandedSources, setExpandedSources] = useState({});
  const [viewingSource, setViewingSource] = useState(null);
  const [sourceContent, setSourceContent] = useState(null);
  const [isLoadingSourceContent, setIsLoadingSourceContent] = useState(false);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // ─── Data fetching ─────────────────────────────────────────────────────────

  useEffect(() => { fetchChatData(); }, [chatId]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const fetchChatData = async () => {
    try {
      const chatRes = await axios.get(`${API}/chats/${chatId}`);
      setChat(chatRes.data);
      setActiveSourceIds(chatRes.data.activeSourceIds || []);
      setSourceMode(chatRes.data.sourceMode || 'all');

      const messagesRes = await axios.get(`${API}/chats/${chatId}/messages`);
      setMessages(messagesRes.data.items || messagesRes.data);

      if (chatRes.data.projectId) {
        const sourcesRes = await axios.get(`${API}/projects/${chatRes.data.projectId}/sources`);
        setProjectSources(sourcesRes.data.items || sourcesRes.data);

        const imagesRes = await axios.get(`${API}/projects/${chatRes.data.projectId}/images`);
        setGeneratedImages(imagesRes.data.items || imagesRes.data);
      } else {
        setProjectSources([]);
        setGeneratedImages([]);
      }
    } catch {
      toast.error('Failed to load chat');
      navigate('/dashboard');
    } finally {
      setIsLoading(false);
    }
  };

  const isQuickChat = chat && !chat.projectId;

  // ─── Active sources sync ───────────────────────────────────────────────────

  useEffect(() => {
    if (!chatId || isLoading) return;
    const timeoutId = setTimeout(async () => {
      try {
        await axios.put(`${API}/chats/${chatId}/active-sources`, { sourceIds: activeSourceIds });
      } catch {
        console.error('Failed to sync active sources');
      }
    }, 500);
    return () => clearTimeout(timeoutId);
  }, [activeSourceIds, chatId, isLoading]);

  // ─── Source mode ───────────────────────────────────────────────────────────

  const updateSourceMode = async (newMode) => {
    try {
      await axios.put(`${API}/chats/${chatId}/source-mode`, { sourceMode: newMode });
      setSourceMode(newMode);
      toast.success(newMode === 'my' ? 'Using your sources only' : 'Using all sources');
    } catch {
      toast.error('Failed to update source mode');
    }
  };

  // ─── Chat name editing ─────────────────────────────────────────────────────

  const startEditingName = () => {
    setEditedName(chat?.name || 'Quick Chat');
    setIsEditingName(true);
    setTimeout(() => nameInputRef.current?.focus(), 100);
  };

  const cancelEditingName = () => { setIsEditingName(false); setEditedName(''); };

  const saveNewName = async () => {
    if (!editedName.trim()) { toast.error('Name cannot be empty'); return; }
    setIsSavingName(true);
    try {
      const response = await axios.put(`${API}/chats/${chatId}/rename`, { name: editedName.trim() });
      setChat(response.data);
      setIsEditingName(false);
      toast.success('Chat renamed');
    } catch {
      toast.error('Failed to rename chat');
    } finally {
      setIsSavingName(false);
    }
  };

  const handleNameKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); saveNewName(); }
    else if (e.key === 'Escape') { cancelEditingName(); }
  };

  // ─── Images ────────────────────────────────────────────────────────────────

  const handleImageGenerated = (newImage) => {
    setGeneratedImages((prev) => [newImage, ...prev]);
    setMessages((prev) => [...prev, {
      id: `img-${newImage.id}`,
      chatId,
      role: 'assistant',
      content: `Generated image: "${newImage.prompt}"`,
      isGeneratedImage: true,
      imageData: newImage,
      createdAt: newImage.createdAt,
    }]);
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
    } catch {
      toast.error('Failed to download image');
    }
  };

  // ─── Messaging ─────────────────────────────────────────────────────────────

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || isSending) return;

    const tempUserMsg = {
      id: `temp-${Date.now()}`,
      chatId,
      role: 'user',
      content,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setInput('');
    setIsSending(true);

    try {
      const response = await axios.post(`${API}/chats/${chatId}/messages`, { content });

      if (response.data.autoIngestedUrls?.length > 0) {
        const sourcesRes = await axios.get(`${API}/projects/${chat.projectId}/sources`);
        setProjectSources(sourcesRes.data.items || sourcesRes.data);
        const chatRes = await axios.get(`${API}/chats/${chatId}`);
        setActiveSourceIds(chatRes.data.activeSourceIds || []);
        toast.success(`Auto-ingested ${response.data.autoIngestedUrls.length} URL(s) from your message`);
      }

      setMessages((prev) => {
        const withoutTemp = prev.filter((m) => m.id !== tempUserMsg.id);
        return [
          ...withoutTemp,
          { ...tempUserMsg, id: `user-${Date.now()}`, autoIngestedUrls: response.data.autoIngestedUrls },
          response.data,
        ];
      });
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
      setInput(content);
      toast.error('Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  // ─── Citations / source content ────────────────────────────────────────────

  const toggleSourceExpansion = (messageId) => {
    setExpandedSources((prev) => ({ ...prev, [messageId]: !prev[messageId] }));
  };

  const viewSourceContent = async (sourceId, sourceName) => {
    setIsLoadingSourceContent(true);
    setViewingSource({ id: sourceId, name: sourceName });
    setSourceContent(null);
    try {
      const response = await axios.get(`${API}/sources/${sourceId}/chunks`);
      const fullContent = response.data
        .sort((a, b) => a.chunkIndex - b.chunkIndex)
        .map((chunk) => chunk.content || chunk.text)
        .join('\n\n');
      setSourceContent(fullContent);
    } catch {
      toast.error('Не удалось загрузить содержимое');
      setViewingSource(null);
    } finally {
      setIsLoadingSourceContent(false);
    }
  };

  const closeSourceModal = () => { setViewingSource(null); setSourceContent(null); };

  // ─── Helpers ───────────────────────────────────────────────────────────────

  const formatTime = (dateString) =>
    new Date(dateString).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  // ─── Loading state ─────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
          <div className="spinner" />
        </div>
      </DashboardLayout>
    );
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-4rem)]" data-testid="chat-page">

        {/* Header */}
        <div className="border-b border-border px-6 py-4 flex items-center justify-between bg-card/50 backdrop-blur">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate(chat?.projectId ? `/projects/${chat.projectId}` : '/dashboard')}
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
                      <span
                        className="cursor-pointer hover:text-emerald-400 transition-colors"
                        onClick={startEditingName}
                        title="Click to rename"
                        data-testid="chat-name-display"
                      >
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
                  <span className="ml-2 text-indigo-400">
                    • {activeSourceIds.length} source{activeSourceIds.length !== 1 ? 's' : ''} active
                  </span>
                )}
                {isQuickChat && <span className="ml-2 text-emerald-400">• Quick Chat</span>}
              </p>
            </div>
          </div>

          {/* Header actions */}
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

            <Button variant="outline" size="sm" onClick={() => setMoveDialogOpen(true)} className="gap-2" data-testid="move-chat-btn">
              <MoveRight className="h-4 w-4" />
              Move
            </Button>

            {chat?.projectId && (
              <ImageGenerator projectId={chat.projectId} onImageGenerated={handleImageGenerated} />
            )}

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

        {/* Move dialog */}
        <MoveDialog
          open={moveDialogOpen}
          onOpenChange={setMoveDialogOpen}
          chatId={chatId}
          currentProjectId={chat?.projectId}
          onMoved={() => window.location.reload()}
        />

        {/* Source Panel */}
        {!isQuickChat && showSourcePanel && (
          <SourcePanel
            projectId={chat?.projectId}
            sources={projectSources}
            activeSourceIds={activeSourceIds}
            onSourcesChange={setProjectSources}
            onActiveSourcesChange={setActiveSourceIds}
          />
        )}

        {/* Messages */}
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
                    <span className="block mt-2">The AI will answer questions based on your sources.</span>
                  </span>
                )}
              </p>
            </div>
          ) : (
            <div className="space-y-6 max-w-3xl mx-auto">
              {messages.map((message, index) => (
                <div
                  key={message.id}
                  className={`flex gap-4 animate-slideIn ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  style={{ animationDelay: `${index * 30}ms` }}
                  data-testid={`message-${message.role}-${index}`}
                >
                  {message.role === 'assistant' && (
                    <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit">
                      <Bot className="h-5 w-5 text-indigo-400" />
                    </div>
                  )}

                  <div className={`flex flex-col gap-1 max-w-[80%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                    {message.role === 'user' && message.senderName && (
                      <span className="text-xs text-muted-foreground px-2">{message.senderName}</span>
                    )}

                    {/* Generated image */}
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

                        {message.role === 'assistant' && (
                          <div className="absolute -bottom-1 -right-1 flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 bg-background border border-border shadow-sm"
                              onClick={async () => {
                                try {
                                  await axios.post(`${API}/save-to-knowledge`, { content: message.content, chatId });
                                  toast.success('Saved to Knowledge ✅');
                                } catch {
                                  toast.error('Failed to save');
                                }
                              }}
                              title="Save to Knowledge"
                              data-testid={`save-message-${index}`}
                            >
                              <Save className="h-3.5 w-3.5 text-green-500" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 bg-background border border-border shadow-sm"
                              onClick={async () => {
                                try {
                                  await navigator.clipboard.writeText(message.content);
                                  toast.success('Copied to clipboard');
                                } catch {
                                  const ta = document.createElement('textarea');
                                  ta.value = message.content;
                                  ta.style.position = 'fixed';
                                  ta.style.left = '-9999px';
                                  document.body.appendChild(ta);
                                  ta.select();
                                  try {
                                    document.execCommand('copy');
                                    toast.success('Copied to clipboard');
                                  } catch {
                                    toast.error('Failed to copy');
                                  }
                                  document.body.removeChild(ta);
                                }
                              }}
                              data-testid={`copy-message-${index}`}
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Auto-ingested URLs indicator */}
                    {message.role === 'user' && message.autoIngestedUrls?.length > 0 && (
                      <div className="mt-1 px-2">
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">
                          <Globe className="h-3 w-3" />
                          {message.autoIngestedUrls.length} URL{message.autoIngestedUrls.length > 1 ? 's' : ''} auto-ingested
                        </span>
                      </div>
                    )}

                    {/* Competitor data indicator */}
                    {message.role === 'assistant' && message.competitorInfo && (
                      <div className="mt-2 px-2">
                        <div className="flex items-center gap-2 p-2 rounded-lg bg-orange-500/10 border border-orange-500/20">
                          <TrendingUp className="h-4 w-4 text-orange-400" />
                          <div className="flex-1">
                            <p className="text-xs font-medium text-orange-400">🔍 Competitor Data Used</p>
                            <p className="text-xs text-muted-foreground">
                              {message.competitorInfo.competitor_name} - {message.competitorInfo.product_title}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Citations – collapsible */}
                    {message.role === 'assistant' && !message.isGeneratedImage &&
                      (message.citations?.length > 0 || message.usedSources?.length > 0) && (
                      <div className="mt-2 px-2">
                        <button
                          onClick={() => toggleSourceExpansion(message.id)}
                          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1 px-2 rounded hover:bg-secondary/50"
                          data-testid={`toggle-sources-${index}`}
                        >
                          <Quote className="h-3 w-3" />
                          <span className="font-medium">
                            Sources ({(message.citations || message.usedSources)?.length})
                          </span>
                          {expandedSources[message.id]
                            ? <ChevronUp className="h-3 w-3 ml-auto" />
                            : <ChevronDown className="h-3 w-3 ml-auto" />}
                        </button>

                        {expandedSources[message.id] && (
                          <div className="flex flex-wrap gap-2 mt-2 animate-slideIn">
                            {(message.citations || message.usedSources)?.map((item, cidx) => {
                              const isGlobal = item.sourceType === 'global';
                              return (
                                <button
                                  key={cidx}
                                  onClick={() => viewSourceContent(item.sourceId, item.sourceName)}
                                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs border hover:opacity-80 transition-opacity cursor-pointer ${
                                    isGlobal
                                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                      : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
                                  }`}
                                  data-testid={`citation-${cidx}`}
                                  title={`Нажмите для просмотра: ${item.sourceName}`}
                                >
                                  {isGlobal
                                    ? <Globe className="h-3 w-3" />
                                    : <FileText className="h-3 w-3" />}
                                  <span className="font-medium">
                                    {isGlobal ? '🌐 ' : '📁 '}
                                    {item.sourceName?.length > 25
                                      ? item.sourceName.slice(0, 25) + '...'
                                      : item.sourceName}
                                  </span>
                                  {item.chunks && (
                                    <span className="opacity-70">
                                      (chunks {Array.isArray(item.chunks)
                                        ? item.chunks.map((c) => c.index || c).join(', ')
                                        : item.chunks})
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Cache indicator */}
                    {message.fromCache && (
                      <div className="mt-1 px-2">
                        <span className="inline-flex items-center gap-1 text-xs text-amber-500">
                          📦 Из кэша
                          {message.cacheInfo?.similarity && (
                            <span className="opacity-70">
                              ({(message.cacheInfo.similarity * 100).toFixed(0)}%)
                            </span>
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

        {/* Smart question suggestions */}
        <SmartQuestions
          chatId={chatId}
          token={localStorage.getItem('token') || axios.defaults.headers.common['Authorization']?.replace('Bearer ', '')}
          hasActiveSources={true}
          onQuestionClick={(question) => {
            setInput(question);
            setTimeout(() => {
              const btn = document.querySelector('[data-testid="send-message-btn"]');
              if (btn && !btn.disabled) btn.click();
            }, 100);
          }}
        />

        {/* Input area */}
        <div className="border-t border-border px-6 py-4 bg-card/50 backdrop-blur">
          <div className="max-w-3xl mx-auto flex gap-4">
            <Textarea
              ref={textareaRef}
              placeholder={
                activeSourceIds.length > 0
                  ? 'Ask a question about the selected sources...'
                  : 'Type your message... (Enter to send, Shift+Enter for new line)'
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
              {isSending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
            </Button>
          </div>
        </div>
      </div>

      {/* Source content viewer modal */}
      <Dialog open={!!viewingSource} onOpenChange={closeSourceModal}>
        <DialogContent className="sm:max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-indigo-400" />
              {viewingSource?.name}
            </DialogTitle>
            <DialogDescription>Содержимое источника</DialogDescription>
          </DialogHeader>

          <ScrollArea className="max-h-[60vh] pr-4">
            {isLoadingSourceContent ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : sourceContent ? (
              <div className="p-4 bg-secondary/30 rounded-lg">
                <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed">{sourceContent}</pre>
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
    </DashboardLayout>
  );
};

export default ChatPage;
