import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import ProjectMemoryModal from '../components/ProjectMemoryModal';
import ImageGenerator from '../components/ImageGenerator';
import AuthImage from '../components/AuthImage';
import { MessageBubble } from '../components/chat/MessageBubble';
import { SourcePanel } from '../components/chat/SourcePanel';
import { ChatInput } from '../components/chat/ChatInput';
import { toast } from 'sonner';
import {
  ArrowLeft, Loader2, FileText, File, Globe, ImageIcon,
  ChevronDown, Pencil, Check, X, FolderOpen,
  MessageSquare, Plus, Bot
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const THINKING_STEPS = [
  { icon: '📂', label: 'Reading sources...',         ms: 0    },
  { icon: '🔍', label: 'Searching relevant chunks...', ms: 1800 },
  { icon: '🧠', label: 'Thinking...',                 ms: 3800 },
  { icon: '✍️',  label: 'Writing answer...',           ms: 6000 },
];

const ThinkingSteps = ({ activeSourceIds, sourcesExplicitlySet, hasWebSearch }) => {
  const [stepIdx, setStepIdx] = useState(0);
  useEffect(() => {
    const timers = THINKING_STEPS.slice(1).map((s, i) =>
      setTimeout(() => setStepIdx(i + 1), s.ms)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  const noSources = sourcesExplicitlySet && activeSourceIds.length === 0;
  const steps = noSources
    ? THINKING_STEPS.filter(s => s.label !== 'Reading sources...' && s.label !== 'Searching relevant chunks...')
    : hasWebSearch
      ? THINKING_STEPS.map(s => s.label === 'Reading sources...' ? { ...s, label: 'Searching the web...' } : s)
      : THINKING_STEPS;

  const current = steps[Math.min(stepIdx, steps.length - 1)];

  return (
    <div className="flex gap-3 justify-start animate-slideIn">
      <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit">
        <Bot className="h-5 w-5 text-indigo-400" />
      </div>
      <div className="bg-secondary px-4 py-3 rounded-2xl rounded-bl-sm space-y-1.5 min-w-[200px]">
        {steps.map((s, i) => {
          const done = i < Math.min(stepIdx, steps.length - 1);
          const active = i === Math.min(stepIdx, steps.length - 1);
          return (
            <div key={i} className={`flex items-center gap-2 text-sm transition-all duration-300 ${active ? 'opacity-100' : done ? 'opacity-40' : 'opacity-20'}`}>
              <span className="text-base leading-none">{done ? '✅' : s.icon}</span>
              <span className={active ? 'text-foreground font-medium' : 'text-muted-foreground'}>{s.label}</span>
              {active && <span className="inline-flex gap-0.5 ml-1">{[0,1,2].map(d => <span key={d} className="w-1 h-1 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: `${d * 150}ms` }} />)}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const ChatPage = () => {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  // ── Core state ──
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [chat, setChat] = useState(null);
  const [projectSources, setProjectSources] = useState([]);
  const [activeSourceIds, setActiveSourceIds] = useState([]);
  const [sourcesExplicitlySet, setSourcesExplicitlySet] = useState(false);
  const sourcesJustLoaded = useRef(false); // prevents saving back to DB what we just loaded
  const [currentProjectName, setCurrentProjectName] = useState('');
  const [sourceMode, setSourceMode] = useState('all');
  const [generatedImages, setGeneratedImages] = useState([]);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);

  // ── Upload state ──
  const [isUploading, setIsUploading] = useState(false);
  const [isAddingUrl, setIsAddingUrl] = useState(false);
  const [urlInput, setUrlInput] = useState('');

  // ── Temp file (one-shot AI attachment) ──
  const [tempFile, setTempFile] = useState(null);        // { id, filename, fileType }
  const [isTempUploading, setIsTempUploading] = useState(false);
  const [pendingTempFile, setPendingTempFile] = useState(null); // shown after AI response for "save?" prompt
  const [isSavingTempFile, setIsSavingTempFile] = useState(false);

  // ── UI state ──
  const [showSourcePanel, setShowSourcePanel] = useState(false);
  const [showInfoBlock, setShowInfoBlock] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [expandedSources, setExpandedSources] = useState({});
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [showPlusMenu, setShowPlusMenu] = useState(false);

  // ── Chat name editing ──
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [isSavingName, setIsSavingName] = useState(false);

  // ── Message editing ──
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editedContent, setEditedContent] = useState('');

  // ── Move chat state ──
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [userProjects, setUserProjects] = useState([]);
  const [isMovingChat, setIsMovingChat] = useState(false);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [showCreateProject, setShowCreateProject] = useState(false);

  // ── Memory / context ──
  const [isSavingContext, setIsSavingContext] = useState(false);
  const [memoryModalOpen, setMemoryModalOpen] = useState(false);

  // ── Source viewer ──
  const [viewingSource, setViewingSource] = useState(null);
  const [sourceContent, setSourceContent] = useState(null);
  const [isLoadingSourceContent, setIsLoadingSourceContent] = useState(false);

  // ── Preview dialog ──
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewSource, setPreviewSource] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // ── Search ──
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

  // ── Refs ──
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const scrollAreaRef = useRef(null);
  const plusMenuRef = useRef(null);
  const nameInputRef = useRef(null);

  const isQuickChat = chat && !chat.projectId;

  // ── Effects ──
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

  // Auto-save context every 10 AI messages → saves to AI Profile (Settings → AI Profile)
  useEffect(() => {
    const assistantCount = messages.filter(m => m.role === 'assistant').length;
    if (assistantCount > 0 && assistantCount % 10 === 0 && !isSavingContext) {
      const dialogText = messages.map(m => `${m.role === 'user' ? 'Пользователь' : 'AI'}: ${m.content || ''}`).join('\n\n');
      axios.post(`${API}/chats/${chatId}/save-context`, { dialogText })
        .then(() => toast.success('Авто-сохранено → AI Profile (Settings → AI Profile)', { duration: 3000 }))
        .catch(() => toast.error('Авто-сохранение не удалось', { duration: 2000 }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length]);

  // Sync active sources with debounce — only when user has explicitly set them (not on initial load)
  useEffect(() => {
    if (!chatId || isLoading || !sourcesExplicitlySet) return;
    if (sourcesJustLoaded.current) {
      sourcesJustLoaded.current = false;
      return; // skip saving what we just loaded from DB
    }
    const timeout = setTimeout(async () => {
      try {
        await axios.post(`${API}/chats/${chatId}/active-sources`, { sourceIds: activeSourceIds });
      } catch { /* silent */ }
    }, 500);
    return () => clearTimeout(timeout);
  }, [activeSourceIds, chatId, isLoading, sourcesExplicitlySet]);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

  // ── Data fetching ──
  const fetchChatData = async () => {
    try {
      const chatRes = await axios.get(`${API}/chats/${chatId}`);
      setChat(chatRes.data);
      const dbActiveIds = chatRes.data.activeSourceIds;
      setSourceMode(chatRes.data.sourceMode || 'all');

      const messagesRes = await axios.get(`${API}/chats/${chatId}/messages`);
      setMessages(messagesRes.data.items || messagesRes.data);

      let allProjectSourceIds = [];
      if (chatRes.data.projectId) {
        const [sourcesRes, projRes] = await Promise.all([
          axios.get(`${API}/projects/${chatRes.data.projectId}/sources`),
          axios.get(`${API}/projects/${chatRes.data.projectId}`)
        ]);
        const projectSourceList = sourcesRes.data.items || sourcesRes.data;
        setProjectSources(projectSourceList);
        allProjectSourceIds = projectSourceList.map(s => s.id);
        setCurrentProjectName(projRes.data.name || '');
        const imagesRes = await axios.get(`${API}/projects/${chatRes.data.projectId}/images`);
        setGeneratedImages(imagesRes.data.items || imagesRes.data);
      } else {
        setProjectSources([]);
        setGeneratedImages([]);
      }

      // Set active sources AFTER loading project sources so SourcePanel shows the correct state:
      // null (never set) → show ALL project sources as checked, backend also uses all sources
      // []   (explicitly cleared) → show NONE checked, backend uses 0 sources
      // [ids] → show those specific sources checked
      if (dbActiveIds !== null && dbActiveIds !== undefined) {
        sourcesJustLoaded.current = true; // mark as loaded, skip debounce save
        setActiveSourceIds(dbActiveIds);
        setSourcesExplicitlySet(true);
      } else {
        // null = never set → show all project sources as active (consistent with backend behavior)
        setActiveSourceIds(allProjectSourceIds);
        setSourcesExplicitlySet(false);
      }
    } catch {
      toast.error('Failed to load chat');
      navigate('/dashboard');
    } finally {
      setIsLoading(false);
    }
  };

  // ── Source mode ──
  const updateSourceMode = async (newMode) => {
    try {
      await axios.put(`${API}/chats/${chatId}/source-mode`, { sourceMode: newMode });
      setSourceMode(newMode);
      toast.success(newMode === 'my' ? 'Using your sources only' : 'Using all sources');
    } catch { toast.error('Failed to update source mode'); }
  };

  // ── Grouped sources (memoized) ──
  const groupedSources = useMemo(() => {
    const groups = {
      pdf:   { label: 'PDF документы',   icon: FileText,  color: 'text-red-400',    sources: [] },
      doc:   { label: 'Документы Word',  icon: File,      color: 'text-blue-500',   sources: [] },
      excel: { label: 'Таблицы Excel',   icon: File,      color: 'text-green-500',  sources: [] },
      ppt:   { label: 'Презентации',     icon: File,      color: 'text-orange-500', sources: [] },
      url:   { label: 'Web URLs',        icon: Globe,     color: 'text-blue-400',   sources: [] },
      image: { label: 'Изображения',     icon: ImageIcon, color: 'text-purple-400', sources: [] },
      other: { label: 'Другие файлы',    icon: FileText,  color: 'text-gray-400',   sources: [] }
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
    return Object.entries(groups).filter(([, group]) => group.sources.length > 0);
  }, [projectSources]);

  // ── Source management ──
  const toggleSourceSelection = (sourceId) => {
    setSourcesExplicitlySet(true);
    setActiveSourceIds(prev => prev.includes(sourceId) ? prev.filter(id => id !== sourceId) : [...prev, sourceId]);
  };

  const toggleGroupSelection = (sources) => {
    setSourcesExplicitlySet(true);
    const sourceIds = sources.map(s => s.id);
    const allSelected = sourceIds.every(id => activeSourceIds.includes(id));
    if (allSelected) setActiveSourceIds(prev => prev.filter(id => !sourceIds.includes(id)));
    else setActiveSourceIds(prev => [...new Set([...prev, ...sourceIds])]);
  };

  const selectAllSources = () => { setSourcesExplicitlySet(true); setActiveSourceIds(projectSources.map(s => s.id)); };
  const deselectAllSources = () => { setSourcesExplicitlySet(true); setActiveSourceIds([]); };
  const resetSourcesToAll = async () => {
    setSourcesExplicitlySet(false);
    setActiveSourceIds([]);
    try {
      // Clear explicit selection from DB — null means "use all"
      await axios.post(`${API}/chats/${chatId}/active-sources`, { sourceIds: null });
    } catch { /* silent */ }
  };
  const toggleGroup = (groupKey) => setExpandedGroups(prev => ({ ...prev, [groupKey]: !prev[groupKey] }));

  const deleteSource = async (sourceId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this source?')) return;
    try {
      await axios.delete(`${API}/projects/${chat.projectId}/sources/${sourceId}`);
      setProjectSources(prev => prev.filter(s => s.id !== sourceId));
      setActiveSourceIds(prev => prev.filter(id => id !== sourceId));
      toast.success('Source deleted');
    } catch { toast.error('Failed to delete source'); }
  };

  const openPreview = async (source, e) => {
    e.stopPropagation();
    setPreviewLoading(true);
    setPreviewDialogOpen(true);
    try {
      const response = await axios.get(`${API}/projects/${chat.projectId}/sources/${source.id}/preview`);
      setPreviewSource(response.data);
    } catch {
      toast.error('Failed to load preview');
      setPreviewDialogOpen(false);
    } finally { setPreviewLoading(false); }
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
    } catch { toast.error('Failed to download file'); }
  };

  const saveToDepartment = async (source, e) => {
    e.stopPropagation();
    if (!user?.departments?.length) { toast.error('У вас нет департаментов для сохранения'); return; }
    try {
      const departmentId = user.departments[0];
      await axios.post(`${API}/department-sources/copy-from-project`, { sourceId: source.id, projectId: chat.projectId, departmentId });
      toast.success('Файл сохранен в источники департамента');
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed to save to department'); }
  };

  // ── File upload ──
  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const supportedExtensions = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md', '.png', '.jpg', '.jpeg'];
    const supportedMimeTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/plain', 'text/markdown', 'image/png', 'image/jpeg', 'image/jpg'];

    const validFiles = files.filter(file => {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!supportedExtensions.includes(ext) && !supportedMimeTypes.includes(file.type)) { toast.error(`${file.name}: Unsupported file type`); return false; }
      if (file.size > 10 * 1024 * 1024) { toast.error(`${file.name}: File size must be less than 10MB`); return false; }
      return true;
    });
    if (!validFiles.length) return;

    setIsUploading(true);

    const getFileBadge = (file) => {
      const ext = file.name.split('.').pop().toLowerCase();
      const typeMap = { pdf: 'pdf', docx: 'doc', doc: 'doc', pptx: 'ppt', ppt: 'ppt', xlsx: 'excel', xls: 'excel', csv: 'excel', png: 'image', jpg: 'image', jpeg: 'image', txt: 'text', md: 'text' };
      return { name: file.name, fileType: typeMap[ext] || 'file' };
    };

    try {
      if (validFiles.length > 1) {
        const formData = new FormData();
        validFiles.forEach(file => formData.append('files', file));
        const response = await axios.post(`${API}/projects/${chat.projectId}/sources/upload-multiple`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        const sourcesRes = await axios.get(`${API}/projects/${chat.projectId}/sources`);
        setProjectSources(sourcesRes.data);
        const uploaded = response.data.uploaded || [];
        const errors = response.data.errors || [];
        if (uploaded.length > 0) {
          toast.success(`Uploaded ${uploaded.length} file(s)`);
          const newIds = [...new Set([...activeSourceIds, ...uploaded.map(s => s.id)])];
          await axios.post(`${API}/chats/${chatId}/active-sources`, { sourceIds: newIds });
          setActiveSourceIds(newIds);
          setSourcesExplicitlySet(true);
          const badge = { name: validFiles.map(f => f.name).join(', '), fileType: 'file', multi: true };
          await sendMessage('Analyze this file and summarize the key points.', badge);
        }
        errors.forEach(err => toast.error(`${err.filename}: ${err.error}`));
      } else {
        const file = validFiles[0];
        const formData = new FormData();
        formData.append('file', file);
        const response = await axios.post(`${API}/projects/${chat.projectId}/sources/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        const uploadedSource = response.data;
        setProjectSources(prev => [...prev, uploadedSource]);
        toast.success(`Uploaded ${file.name} (${response.data.chunkCount} chunks extracted)`);
        const newIds = [...activeSourceIds, uploadedSource.id];
        await axios.post(`${API}/chats/${chatId}/active-sources`, { sourceIds: newIds });
        setActiveSourceIds(newIds);
        setSourcesExplicitlySet(true);
        await sendMessage('Analyze this file and summarize the key points.', getFileBadge(file));
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to upload file(s)');
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
      setSourcesExplicitlySet(true);
    } catch (error) { toast.error(error.response?.data?.detail || 'Failed to add URL'); }
    finally { setIsAddingUrl(false); }
  };

  const searchSources = async () => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) { toast.error('Введите минимум 2 символа'); return; }
    setIsSearching(true);
    setShowSearchResults(true);
    try {
      const response = await axios.post(`${API}/projects/${chat.projectId}/sources/search`, { query: searchQuery.trim(), limit: 20 });
      setSearchResults(response.data);
      if (response.data.length === 0) toast.info('Ничего не найдено');
    } catch { toast.error('Ошибка поиска'); }
    finally { setIsSearching(false); }
  };

  // ── Send message ──
  const sendMessage = async (contentOverride = null, fileBadge = null) => {

    const content = (contentOverride ?? input).trim();
if ((!content && !tempFile) || isSending) return;
const finalContent = content || "Analyze this file and summarize the key points.";

    const activeTempFile = tempFile;
    const tempUserMsg = {
      id: `temp-${Date.now()}`, chatId, role: 'user', content: finalContent,
      createdAt: new Date().toISOString(),
      ...(fileBadge ? { uploadedFile: fileBadge } : activeTempFile ? { uploadedFile: { name: activeTempFile.filename, fileType: activeTempFile.fileType, previewUrl: activeTempFile.previewUrl } } : {})
    };
    setMessages(prev => [...prev, tempUserMsg]);
    setInput('');
    setTempFile(null);
    setIsSending(true);

    try {
      // Send activeSourceIds only if user has explicitly interacted with checkboxes.
      // null means "use all accessible sources" (new chat / never touched).
      // []   means "user explicitly unchecked everything — no sources".
      const payload = {
        content: finalContent,
        activeSourceIds: sourcesExplicitlySet ? activeSourceIds : null,
        forceWebSearch: webSearchEnabled ? true : false,
      };
      if (activeTempFile) payload.temp_file_id = activeTempFile.id;
      const response = await axios.post(`${API}/chats/${chatId}/messages`, payload);
      const { user_message: userMsg, assistant_message: assistantMsg } = response.data;

      if (assistantMsg.autoIngestedUrls?.length > 0) {
        const sourcesRes = await axios.get(`${API}/projects/${chat.projectId}/sources`);
        setProjectSources(sourcesRes.data);
        const chatRes = await axios.get(`${API}/chats/${chatId}`);
        const refreshedIds = chatRes.data.activeSourceIds;
        if (refreshedIds !== null && refreshedIds !== undefined) {
          setActiveSourceIds(refreshedIds);
          setSourcesExplicitlySet(true);
        }
        toast.success(`Auto-ingested ${assistantMsg.autoIngestedUrls.length} URL(s) from your message`);
      }

      setMessages(prev => {
        const withoutTemp = prev.filter(m => m.id !== tempUserMsg.id);
        const realUserMsg = { ...tempUserMsg, id: userMsg.id, autoIngestedUrls: userMsg.autoIngestedUrls || null };
        return [...withoutTemp, realUserMsg, assistantMsg];
      });

      // Show "save to sources?" prompt after AI responds (only for project chats)
      if (activeTempFile && chat?.projectId) {
        setPendingTempFile({ ...activeTempFile, projectId: chat.projectId });
      }

      // Auto-rename on first message
      const isAutoName = chat?.name?.startsWith('Новый чат') || chat?.name === 'New Chat';
      const isFirst = messages.filter(m => m.role === 'user').length === 0;
      if (isAutoName && isFirst) {
        const shortName = content.trim().slice(0, 40) + (content.trim().length > 40 ? '...' : '');
        axios.put(`${API}/chats/${chatId}/rename`, { name: shortName })
          .then(res => setChat(prev => ({ ...prev, name: res.data.name || shortName })))
          .catch(() => {});
      }
    } catch {
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
      setInput(content);
      toast.error('Failed to send message');
    } finally { setIsSending(false); }
  };

  // ── Temp file: paperclip upload handler ──
  const handlePaperclipChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    let localPreviewUrl = null;
    const isImage = file.type.startsWith('image/');
    if (isImage) {
      localPreviewUrl = URL.createObjectURL(file);
    }

    setIsTempUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('chat_id', chatId);
      const res = await axios.post(`${API}/chat/upload-temp`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setTempFile({
        id: res.data.temp_file_id,
        filename: res.data.filename,
        fileType: res.data.file_type,
        previewUrl: localPreviewUrl,
      });
    } catch (err) {
      if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl);
      toast.error(err.response?.data?.detail || 'Не удалось загрузить файл');
    } finally {
      setIsTempUploading(false);
    }
  };

  const saveTempFileToSource = async () => {
    if (!pendingTempFile) return;
    setIsSavingTempFile(true);
    try {
      await axios.post(`${API}/chat/save-temp-to-source`, {
        temp_file_id: pendingTempFile.id,
        filename: pendingTempFile.filename,
        file_type: pendingTempFile.fileType,
        chat_id: chatId,
        project_id: pendingTempFile.projectId,
      });
      toast.success(`"${pendingTempFile.filename}" сохранён в источники проекта`);
      // Refresh sources
      const sourcesRes = await axios.get(`${API}/projects/${pendingTempFile.projectId}/sources`);
      setProjectSources(sourcesRes.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Не удалось сохранить в источники');
    } finally {
      setIsSavingTempFile(false);
      setPendingTempFile(null);
    }
  };

  // ── Message editing ──
  const startEditMessage = (message) => { setEditingMessageId(message.id); setEditedContent(message.content); };
  const cancelEditMessage = () => { setEditingMessageId(null); setEditedContent(''); };

  const saveEditedMessage = async (messageId) => {
    if (!editedContent.trim()) { toast.error('Сообщение не может быть пустым'); return; }
    try {
      const response = await axios.put(`${API}/chats/${chatId}/messages/${messageId}/edit`, { content: editedContent });
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === messageId);
        if (idx === -1) return prev;
        const updated = prev.slice(0, idx + 1);
        updated[idx] = response.data;
        return updated;
      });
      setEditingMessageId(null);
      setEditedContent('');
      toast.success('Сообщение обновлено');

      setIsSending(true);
      try {
        const aiResponse = await axios.post(`${API}/chats/${chatId}/messages?regen=true`, {
          content: editedContent,
          activeSourceIds: sourcesExplicitlySet ? activeSourceIds : null,
        });
        setMessages(prev => [...prev, aiResponse.data.assistant_message]);
        setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
      } catch { toast.error('Не удалось получить ответ AI'); }
      finally { setIsSending(false); }
    } catch (error) { toast.error(error.response?.data?.detail || 'Не удалось обновить сообщение'); }
  };

  // ── Source content viewer ──
  const viewSourceContent = async (sourceId, sourceName) => {
    setIsLoadingSourceContent(true);
    setViewingSource({ id: sourceId, name: sourceName });
    setSourceContent(null);
    try {
      const response = await axios.get(`${API}/sources/${sourceId}/chunks`);
      const fullContent = response.data.sort((a, b) => a.chunkIndex - b.chunkIndex).map(c => c.content || c.text).join('\n\n');
      setSourceContent(fullContent);
    } catch { toast.error('Не удалось загрузить содержимое'); setViewingSource(null); }
    finally { setIsLoadingSourceContent(false); }
  };

  // ── Project memory ──
  const saveToProjectMemory = async (messageContent) => {
    if (!chat?.projectId) { toast.error('Этот чат не привязан к проекту'); return; }
    try {
      const memRes = await axios.get(`${API}/projects/${chat.projectId}/memory`);
      const existing = memRes.data.project_memory || '';
      const separator = existing ? '\n\n---\n' : '';
      const updated = existing + separator + messageContent.trim();
      if (updated.length > 6000) { toast.error('Project Memory переполнена (макс. 6000 символов)'); return; }
      await axios.put(`${API}/projects/${chat.projectId}/memory`, { project_memory: updated });
      toast.success('Сохранено в Project Memory ✅');
    } catch (e) { toast.error(e.response?.data?.detail || 'Не удалось сохранить'); }
  };

  // ── Save context ──
  const saveContext = async () => {
    if (!messages.length) { toast.error('Нет сообщений для сохранения'); return; }
    setIsSavingContext(true);
    try {
      const dialogText = messages.map(m => `${m.role === 'user' ? 'Пользователь' : 'AI'}: ${m.content}`).join('\n\n');
      await axios.post(`${API}/chats/${chatId}/save-context`, { dialogText });
      toast.success('Контекст сохранен в AI Profile');
    } catch (error) { toast.error(error.response?.data?.detail || 'Не удалось сохранить контекст'); }
    finally { setIsSavingContext(false); }
  };

  // ── Download image ──
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
    } catch { toast.error('Failed to download image'); }
  };

  // ── Chat renaming ──
  const startEditingName = () => { setEditedName(chat?.name || 'Quick Chat'); setIsEditingName(true); setTimeout(() => nameInputRef.current?.focus(), 100); };
  const cancelEditingName = () => { setIsEditingName(false); setEditedName(''); };
  const saveNewName = async () => {
    if (!editedName.trim()) { toast.error('Name cannot be empty'); return; }
    setIsSavingName(true);
    try {
      const response = await axios.put(`${API}/chats/${chatId}/rename`, { name: editedName.trim() });
      setChat(response.data);
      setIsEditingName(false);
      toast.success('Chat renamed');
    } catch { toast.error('Failed to rename chat'); }
    finally { setIsSavingName(false); }
  };
  const handleNameKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); saveNewName(); }
    else if (e.key === 'Escape') { cancelEditingName(); }
  };

  // ── Move chat ──
  const fetchUserProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setUserProjects(response.data.items || response.data || []);
    } catch { /* silent */ }
  };
  const openMoveDialog = () => { fetchUserProjects(); setShowCreateProject(false); setNewProjectName(''); setMoveDialogOpen(true); };
  const moveChat = async (targetProjectId) => {
    setIsMovingChat(true);
    try {
      await axios.post(`${API}/chats/${chatId}/move`, { targetProjectId });
      toast.success('Chat moved to project');
      setMoveDialogOpen(false);
      window.location.reload();
    } catch { toast.error('Failed to move chat'); }
    finally { setIsMovingChat(false); }
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
    } catch { toast.error('Failed to create project'); }
    finally { setIsCreatingProject(false); }
  };

  const handleImageGenerated = (newImage) => {
    setGeneratedImages(prev => [newImage, ...prev]);
    setMessages(prev => [...prev, {
      id: `img-${newImage.id}`, chatId, role: 'assistant',
      content: `Generated image: "${newImage.prompt}"`,
      isGeneratedImage: true, imageData: newImage, createdAt: newImage.createdAt
    }]);
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

        {/* ── Header ── */}
        <div className="px-3 py-2 flex items-center gap-2 bg-transparent">
          {/* Back → Project name */}
          <button
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
            onClick={() => chat?.projectId ? navigate(`/projects/${chat.projectId}`) : navigate('/dashboard')}
            data-testid="back-from-chat-btn"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>{currentProjectName || 'Back'}</span>
          </button>

          {currentProjectName && <span className="text-muted-foreground text-sm">/</span>}

          {/* Chat name + edit */}
          <div className="flex-1 min-w-0">
            {isEditingName ? (
              <div className="flex items-center gap-1.5">
                <Input ref={nameInputRef} value={editedName} onChange={(e) => setEditedName(e.target.value)} onKeyDown={handleNameKeyDown} className="h-6 text-xs font-medium w-40" disabled={isSavingName} data-testid="chat-name-input" />
                <Button variant="ghost" size="icon" className="h-5 w-5" onClick={saveNewName} disabled={isSavingName} data-testid="save-chat-name-btn">
                  {isSavingName ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3 text-emerald-400" />}
                </Button>
                <Button variant="ghost" size="icon" className="h-5 w-5" onClick={cancelEditingName}><X className="h-3 w-3" /></Button>
              </div>
            ) : (
              <div className="flex items-center gap-1 min-w-0">
                <button className="text-sm font-medium truncate hover:text-muted-foreground transition-colors" onClick={startEditingName} data-testid="chat-name-display">
                  {isQuickChat ? (chat.name || 'Quick Chat') : (chat?.name || 'Untitled Chat')}
                </button>
                <Button variant="ghost" size="icon" className="h-5 w-5 opacity-30 hover:opacity-100 flex-shrink-0" onClick={startEditingName} data-testid="edit-chat-name-btn"><Pencil className="h-2.5 w-2.5" /></Button>
                <span className="text-xs text-muted-foreground flex-shrink-0">{messages.length} msg</span>
              </div>
            )}
          </div>

          {/* Source status — clickable */}
          {!isQuickChat && projectSources.length > 0 && (
            <button onClick={() => setShowSourcePanel(v => !v)} className="text-xs transition-colors flex-shrink-0">
              {!sourcesExplicitlySet && <span className="text-indigo-400 hover:text-indigo-300">all sources</span>}
              {sourcesExplicitlySet && activeSourceIds.length > 0 && <span className="text-indigo-400 hover:text-indigo-300">{activeSourceIds.length} source{activeSourceIds.length !== 1 ? 's' : ''} active</span>}
              {sourcesExplicitlySet && activeSourceIds.length === 0 && <span className="text-amber-400 hover:text-amber-300">no sources</span>}
            </button>
          )}

          {/* Sources icon */}
          {!isQuickChat && (
            <button
              onClick={() => setShowSourcePanel(v => !v)}
              className={`h-7 w-7 flex items-center justify-center rounded-lg hover:bg-secondary transition-colors flex-shrink-0 ${showSourcePanel ? 'text-indigo-400' : 'text-muted-foreground'}`}
              data-testid="toggle-source-panel-btn"
              title="Sources"
            >
              <FileText className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* ── Move Chat Dialog ── */}
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
                  <Input id="newProjectName" placeholder="My New Project" value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && createProjectAndMove()} disabled={isCreatingProject} data-testid="new-project-name-input" />
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
                    <Button onClick={() => setShowCreateProject(true)} data-testid="create-project-in-dialog-btn"><Plus className="mr-2 h-4 w-4" />Create Project</Button>
                  </div>
                ) : (
                  <>
                    {userProjects.filter(p => p.id !== chat?.projectId).map((project) => (
                      <Card key={project.id} className="cursor-pointer hover:border-indigo-500/50 transition-colors" onClick={() => moveChat(project.id)} data-testid={`move-to-project-${project.id}`}>
                        <CardContent className="py-3 flex items-center gap-3"><FolderOpen className="h-5 w-5 text-indigo-400" /><span className="font-medium">{project.name}</span></CardContent>
                      </Card>
                    ))}
                    {userProjects.filter(p => p.id !== chat?.projectId).length === 0 && (
                      <p className="text-center text-muted-foreground py-4">No other projects available.</p>
                    )}
                    <Card className="cursor-pointer hover:border-emerald-500/50 transition-colors border-dashed" onClick={() => setShowCreateProject(true)} data-testid="create-new-project-option">
                      <CardContent className="py-3 flex items-center gap-3"><Plus className="h-5 w-5 text-emerald-400" /><span className="font-medium text-emerald-400">Create New Project</span></CardContent>
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

        {/* ── Source Panel (left drawer) ── */}
        {!isQuickChat && (
          <>
            {/* Backdrop */}
            {showSourcePanel && (
              <div
                className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
                onClick={() => setShowSourcePanel(false)}
              />
            )}
            {/* Drawer — right side */}
            <div className={`fixed top-0 right-0 h-full z-40 w-[500px] bg-card border-l border-border shadow-2xl transition-transform duration-300 ease-in-out flex flex-col ${showSourcePanel ? 'translate-x-0' : 'translate-x-full'}`}>
              <SourcePanel
                projectSources={projectSources}
                activeSourceIds={activeSourceIds}
                sourcesExplicitlySet={sourcesExplicitlySet}
                currentProjectName={currentProjectName}
                currentUser={user}
                chat={chat}
                isUploading={isUploading}
                isAddingUrl={isAddingUrl}
                urlInput={urlInput}
                onUrlInputChange={setUrlInput}
                onAddUrl={handleAddUrl}
                onClose={() => setShowSourcePanel(false)}
                onToggleSource={toggleSourceSelection}
                onToggleGroupSelection={toggleGroupSelection}
                onSelectAll={selectAllSources}
                onDeselectAll={deselectAllSources}
                onResetToAll={resetSourcesToAll}
                expandedGroups={expandedGroups}
                onToggleGroup={toggleGroup}
                groupedSources={groupedSources}
                onDeleteSource={deleteSource}
                onPreview={openPreview}
                onDownload={downloadSource}
                onSaveToDept={saveToDepartment}
                searchQuery={searchQuery}
                onSearchQueryChange={setSearchQuery}
                onSearch={searchSources}
                isSearching={isSearching}
                showSearchResults={showSearchResults}
                searchResults={searchResults}
                onCloseSearch={() => { setShowSearchResults(false); setSearchResults([]); setSearchQuery(''); }}
                fileInputRef={fileInputRef}
                onFileInputChange={handleFileUpload}
                showInfoBlock={showInfoBlock}
                onCloseInfoBlock={() => setShowInfoBlock(false)}
              />
            </div>
          </>
        )}

        {/* ── Preview Dialog ── */}
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
                <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${previewSource?.quality === 'good' ? 'bg-green-500/10 text-green-600 dark:text-green-400' : previewSource?.quality === 'low' ? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400' : 'bg-secondary'}`}>
                  <span className={`w-2 h-2 rounded-full ${previewSource?.quality === 'good' ? 'bg-green-500' : previewSource?.quality === 'low' ? 'bg-yellow-500' : 'bg-red-500'}`}></span>
                  {previewSource?.qualityMessage || 'Текст извлечён'}
                </div>
                <ScrollArea className="max-h-[45vh] mt-3">
                  <pre className="text-sm whitespace-pre-wrap font-mono bg-secondary/50 p-4 rounded-lg">{previewSource?.text || 'No content'}</pre>
                </ScrollArea>
              </>
            )}
            <DialogFooter><Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>Close</Button></DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Hidden ImageGenerator — triggered from Plus menu */}
        {chat?.projectId && (
          <div className="hidden">
            <ImageGenerator projectId={chat.projectId} onImageGenerated={handleImageGenerated} />
          </div>
        )}

        {/* ── Messages Area ── */}
        <ScrollArea
          className="flex-1 px-6 py-4"
          ref={scrollAreaRef}
        >
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
                <MessageBubble
                  key={message.id}
                  message={message}
                  index={index}
                  messagesCount={messages.length}
                  isEditing={editingMessageId === message.id}
                  editedContent={editedContent}
                  onEditChange={setEditedContent}
                  onStartEdit={startEditMessage}
                  onCancelEdit={cancelEditMessage}
                  onSaveEdit={saveEditedMessage}
                  onSendMessage={sendMessage}
                  onViewSource={viewSourceContent}
                  onSaveToProjectMemory={saveToProjectMemory}
                  onDownloadImage={downloadImage}
                  expandedSources={expandedSources}
                  onToggleSourceExpansion={(id) => setExpandedSources(prev => ({ ...prev, [id]: !prev[id] }))}
                  chatId={chatId}
                  originalUserMessage={message.role === 'assistant' ? messages[index - 1]?.content : undefined}
                  chatHistory={messages.slice(0, index + 1)}
                />
              ))}
              {isSending && (
                <ThinkingSteps
                  activeSourceIds={activeSourceIds}
                  sourcesExplicitlySet={sourcesExplicitlySet}
                  hasWebSearch={webSearchEnabled}
                />
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* ── Scroll to bottom button ── */}
        {showScrollBtn && (
          <div className="fixed bottom-44 left-1/2 -translate-x-1/2 z-50">
            <button
              onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary text-primary-foreground text-xs font-medium shadow-lg hover:bg-primary/90 transition-all animate-bounce"
            >
              <ChevronDown className="h-3.5 w-3.5" />Scroll down
            </button>
          </div>
        )}

        {/* ── Chat Input ── */}
        <ChatInput
          input={input}
          onInputChange={setInput}
          onSend={() => sendMessage()}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
          isSending={isSending}
          isUploading={isUploading}
          isQuickChat={isQuickChat}
          activeSourceIds={activeSourceIds}
          sourcesExplicitlySet={sourcesExplicitlySet}
          chat={chat}
          messages={messages}
          isSavingContext={isSavingContext}
          onFileUpload={handleFileUpload}
          onShowSourcePanel={() => setShowSourcePanel(true)}
          onSaveContext={saveContext}
          onOpenMemory={() => setMemoryModalOpen(true)}
          onOpenMoveDialog={openMoveDialog}
          webSearchEnabled={webSearchEnabled}
          onToggleWebSearch={() => setWebSearchEnabled(v => !v)}
          textareaRef={textareaRef}
          plusMenuRef={plusMenuRef}
          showPlusMenu={showPlusMenu}
          onTogglePlusMenu={(val) => setShowPlusMenu(typeof val === 'function' ? val(showPlusMenu) : val)}
          tempFile={tempFile}
          isTempUploading={isTempUploading}
          onPaperclipChange={handlePaperclipChange}
          onRemoveTempFile={() => setTempFile(null)}
        />

        {/* ── Save temp file to sources prompt ── */}
        {pendingTempFile && (
          <div className="px-6 pb-3" data-testid="save-temp-file-prompt">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/25">
                <div className="flex items-center gap-2 text-sm text-amber-200 min-w-0">
                  <span className="flex-shrink-0">💾</span>
                  <span className="truncate">Сохранить <strong className="text-amber-100">"{pendingTempFile.filename}"</strong> в источники проекта?</span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={saveTempFileToSource}
                    disabled={isSavingTempFile}
                    className="border-amber-500/40 text-amber-200 hover:bg-amber-500/20 text-xs h-7"
                    data-testid="save-temp-file-btn"
                  >
                    {isSavingTempFile ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                    Сохранить
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setPendingTempFile(null)}
                    className="text-muted-foreground hover:text-foreground text-xs h-7"
                    data-testid="dismiss-save-temp-file-btn"
                  >
                    Нет
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Source content viewer modal ── */}
      <Dialog open={!!viewingSource} onOpenChange={() => { setViewingSource(null); setSourceContent(null); }}>
        <DialogContent className="sm:max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><FileText className="h-5 w-5 text-indigo-400" />{viewingSource?.name}</DialogTitle>
            <DialogDescription>Содержимое источника</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] pr-4">
            {isLoadingSourceContent ? (
              <div className="flex items-center justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
            ) : sourceContent ? (
              <div className="p-4 bg-secondary/30 rounded-lg">
                <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed">{sourceContent}</pre>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">Не удалось загрузить содержимое</div>
            )}
          </ScrollArea>
          <DialogFooter><Button variant="outline" onClick={() => { setViewingSource(null); setSourceContent(null); }}>Закрыть</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Project Memory Modal ── */}
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
