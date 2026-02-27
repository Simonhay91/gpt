import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { 
  ArrowLeft, 
  Globe2, 
  Upload, 
  Link, 
  Trash2, 
  FileText, 
  Eye, 
  Loader2,
  HardDrive,
  File,
  X,
  BarChart3,
  TrendingUp,
  Clock,
  Users
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminGlobalSourcesPage = () => {
  const navigate = useNavigate();
  const [sources, setSources] = useState([]);
  const [usageStats, setUsageStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isAddingUrl, setIsAddingUrl] = useState(false);
  const [activeTab, setActiveTab] = useState('sources'); // 'sources' or 'stats'
  
  // URL Dialog
  const [urlDialogOpen, setUrlDialogOpen] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  
  // Preview Dialog
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  const fetchSources = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/global-sources`);
      setSources(response.data);
    } catch (error) {
      toast.error('Не удалось загрузить глобальные источники');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchUsageStats = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/global-sources/stats`);
      setUsageStats(response.data);
    } catch (error) {
      console.error('Failed to fetch usage stats:', error);
    }
  }, []);
    }
  }, []);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    
    for (const file of files) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        
        await axios.post(`${API}/admin/global-sources/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        toast.success(`Файл "${file.name}" загружен`);
      } catch (error) {
        const message = error.response?.data?.detail || 'Ошибка загрузки';
        toast.error(`${file.name}: ${message}`);
      }
    }
    
    setIsUploading(false);
    fetchSources();
    event.target.value = '';
  };

  const handleAddUrl = async () => {
    if (!newUrl.trim()) {
      toast.error('Введите URL');
      return;
    }

    setIsAddingUrl(true);
    try {
      await axios.post(`${API}/admin/global-sources/url`, { url: newUrl.trim() });
      toast.success('URL добавлен');
      setUrlDialogOpen(false);
      setNewUrl('');
      fetchSources();
    } catch (error) {
      const message = error.response?.data?.detail || 'Не удалось добавить URL';
      toast.error(message);
    } finally {
      setIsAddingUrl(false);
    }
  };

  const handleDelete = async (sourceId, sourceName) => {
    if (!window.confirm(`Удалить "${sourceName}"? Это действие нельзя отменить.`)) {
      return;
    }

    try {
      await axios.delete(`${API}/admin/global-sources/${sourceId}`);
      toast.success('Источник удалён');
      setSources(sources.filter(s => s.id !== sourceId));
    } catch (error) {
      toast.error('Не удалось удалить источник');
    }
  };

  const handlePreview = async (sourceId) => {
    setIsLoadingPreview(true);
    setPreviewDialogOpen(true);
    
    try {
      const response = await axios.get(`${API}/admin/global-sources/${sourceId}/preview`);
      setPreviewData(response.data);
    } catch (error) {
      toast.error('Не удалось загрузить превью');
      setPreviewDialogOpen(false);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return bytes + ' B';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getSourceIcon = (source) => {
    if (source.kind === 'url') return <Globe2 className="h-4 w-4 text-blue-400" />;
    
    const mimeType = source.mimeType || '';
    if (mimeType.includes('pdf')) return <FileText className="h-4 w-4 text-red-400" />;
    if (mimeType.includes('word') || mimeType.includes('docx')) return <FileText className="h-4 w-4 text-blue-400" />;
    if (mimeType.includes('presentation') || mimeType.includes('pptx')) return <FileText className="h-4 w-4 text-orange-400" />;
    if (mimeType.includes('sheet') || mimeType.includes('xlsx')) return <FileText className="h-4 w-4 text-green-400" />;
    if (mimeType.includes('image')) return <FileText className="h-4 w-4 text-purple-400" />;
    return <File className="h-4 w-4 text-muted-foreground" />;
  };

  const totalSize = sources.reduce((acc, s) => acc + (s.sizeBytes || 0), 0);
  const totalChunks = sources.reduce((acc, s) => acc + (s.chunkCount || 0), 0);

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="admin-global-sources-page">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            className="mb-4 -ml-2"
            onClick={() => navigate('/dashboard')}
            data-testid="back-to-dashboard-btn"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Назад
          </Button>
          
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-emerald-500/20 p-3">
                <Globe2 className="h-6 w-6 text-emerald-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Глобальные источники</h1>
                <p className="text-muted-foreground mt-1">
                  Центральная база знаний для всех пользователей
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => setUrlDialogOpen(true)}
                data-testid="add-url-btn"
              >
                <Link className="mr-2 h-4 w-4" />
                Добавить URL
              </Button>
              
              <label>
                <Button asChild className="cursor-pointer" data-testid="upload-file-btn">
                  <span>
                    {isUploading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="mr-2 h-4 w-4" />
                    )}
                    Загрузить файл
                  </span>
                </Button>
                <input
                  type="file"
                  className="hidden"
                  multiple
                  accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.md,.png,.jpg,.jpeg"
                  onChange={handleFileUpload}
                  disabled={isUploading}
                />
              </label>
            </div>
          </div>
        </div>

        {/* Stats */}
        {sources.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{sources.length}</p>
                    <p className="text-sm text-muted-foreground">источников</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-3">
                  <HardDrive className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{formatBytes(totalSize)}</p>
                    <p className="text-sm text-muted-foreground">общий размер</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{totalChunks}</p>
                    <p className="text-sm text-muted-foreground">фрагментов текста</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Info Card */}
        <Card className="mb-6 border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="pt-4">
            <div className="flex items-start gap-3">
              <Globe2 className="h-5 w-5 text-emerald-500 mt-0.5" />
              <div>
                <h4 className="font-medium text-emerald-500">Как это работает</h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Глобальные источники автоматически доступны всем пользователям во всех проектах. 
                  Когда пользователь задаёт вопрос, GPT будет использовать как источники проекта, 
                  так и глобальные источники для формирования ответа.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Sources List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : sources.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="rounded-full bg-secondary p-4 mb-4">
                <Globe2 className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Нет глобальных источников</h3>
              <p className="text-muted-foreground text-center mb-4 max-w-md">
                Загрузите файлы или добавьте URL, чтобы создать общую базу знаний для всех пользователей
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {sources.map((source, index) => (
              <Card 
                key={source.id}
                className="card-hover group"
                style={{ animationDelay: `${index * 50}ms` }}
                data-testid={`source-card-${source.id}`}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1 min-w-0">
                      <div className="rounded-lg bg-secondary p-2">
                        {getSourceIcon(source)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-semibold truncate">
                          {source.originalName || source.url || 'Без названия'}
                        </h3>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                          <span>{source.kind === 'url' ? 'URL' : 'Файл'}</span>
                          {source.sizeBytes && (
                            <span>• {formatBytes(source.sizeBytes)}</span>
                          )}
                          <span>• {source.chunkCount || 0} фрагментов</span>
                          <span className="hidden sm:inline">• {formatDate(source.createdAt)}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2 ml-4">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handlePreview(source.id)}
                        data-testid={`preview-source-${source.id}`}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handleDelete(source.id, source.originalName || source.url)}
                        data-testid={`delete-source-${source.id}`}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Add URL Dialog */}
        <Dialog open={urlDialogOpen} onOpenChange={setUrlDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Добавить URL</DialogTitle>
              <DialogDescription>
                Введите URL веб-страницы для извлечения текста и добавления в глобальную базу знаний
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="url">URL адрес</Label>
                <Input
                  id="url"
                  type="url"
                  placeholder="https://example.com/article"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  data-testid="url-input"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setUrlDialogOpen(false)}
              >
                Отмена
              </Button>
              <Button
                onClick={handleAddUrl}
                disabled={isAddingUrl}
                data-testid="confirm-add-url-btn"
              >
                {isAddingUrl ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Link className="mr-2 h-4 w-4" />
                )}
                Добавить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Preview Dialog */}
        <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
          <DialogContent className="sm:max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                {previewData?.name || 'Превью источника'}
              </DialogTitle>
              {previewData && (
                <DialogDescription>
                  {previewData.chunkCount} фрагментов • {previewData.wordCount} слов
                </DialogDescription>
              )}
            </DialogHeader>
            
            {isLoadingPreview ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : previewData ? (
              <div className="max-h-[50vh] overflow-y-auto">
                <pre className="whitespace-pre-wrap text-sm bg-secondary/50 p-4 rounded-lg">
                  {previewData.text || 'Нет текста для отображения'}
                </pre>
              </div>
            ) : null}
            
            <DialogFooter>
              <Button onClick={() => setPreviewDialogOpen(false)}>
                Закрыть
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default AdminGlobalSourcesPage;
