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
  Users,
  Database,
  Zap,
  RefreshCw
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminGlobalSourcesPage = () => {
  const navigate = useNavigate();
  const [sources, setSources] = useState([]);
  const [usageStats, setUsageStats] = useState(null);
  const [cacheStats, setCacheStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isAddingUrl, setIsAddingUrl] = useState(false);
  const [isClearingCache, setIsClearingCache] = useState(false);
  const [activeTab, setActiveTab] = useState('sources'); // 'sources', 'stats', or 'cache'
  
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

  const fetchCacheStats = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/cache/stats`);
      setCacheStats(response.data);
    } catch (error) {
      console.error('Failed to fetch cache stats:', error);
    }
  }, []);

  useEffect(() => {
    fetchSources();
    fetchUsageStats();
  }, [fetchSources, fetchUsageStats]);

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

        {/* Stats Summary */}
        {sources.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
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
                  <TrendingUp className="h-5 w-5 text-emerald-500" />
                  <div>
                    <p className="text-2xl font-bold">{usageStats?.totalUsageCount || 0}</p>
                    <p className="text-sm text-muted-foreground">использований</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-3">
                  <BarChart3 className="h-5 w-5 text-blue-500" />
                  <div>
                    <p className="text-2xl font-bold">{usageStats?.sourcesUsedCount || 0}/{sources.length}</p>
                    <p className="text-sm text-muted-foreground">используются</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <Button
            variant={activeTab === 'sources' ? 'default' : 'outline'}
            onClick={() => setActiveTab('sources')}
          >
            <FileText className="mr-2 h-4 w-4" />
            Источники
          </Button>
          <Button
            variant={activeTab === 'stats' ? 'default' : 'outline'}
            onClick={() => setActiveTab('stats')}
          >
            <BarChart3 className="mr-2 h-4 w-4" />
            Статистика
          </Button>
        </div>

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

        {/* Tab Content */}
        {activeTab === 'stats' ? (
          /* Statistics Tab */
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Использование источников
                </CardTitle>
                <CardDescription>
                  Статистика того, как GPT использует глобальные источники в ответах
                </CardDescription>
              </CardHeader>
              <CardContent>
                {usageStats?.sources?.length > 0 ? (
                  <div className="space-y-3">
                    {usageStats.sources.map((stat, index) => (
                      <div 
                        key={stat.sourceId}
                        className="flex items-center justify-between p-3 bg-secondary/30 rounded-lg"
                      >
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                            stat.usageCount > 0 ? 'bg-emerald-500/20 text-emerald-500' : 'bg-secondary text-muted-foreground'
                          }`}>
                            {index + 1}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-medium truncate">{stat.sourceName}</p>
                            <div className="flex items-center gap-3 text-sm text-muted-foreground">
                              <span>{stat.chunkCount} фрагментов</span>
                              <span>•</span>
                              <span>{formatBytes(stat.sizeBytes)}</span>
                            </div>
                          </div>
                        </div>
                        <div className="text-right ml-4">
                          <p className={`text-lg font-bold ${stat.usageCount > 0 ? 'text-emerald-500' : 'text-muted-foreground'}`}>
                            {stat.usageCount}
                          </p>
                          <p className="text-xs text-muted-foreground">использований</p>
                          {stat.lastUsedAt && (
                            <p className="text-xs text-muted-foreground mt-1">
                              <Clock className="inline h-3 w-3 mr-1" />
                              {formatDate(stat.lastUsedAt)}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
                    <p>Пока нет данных об использовании</p>
                    <p className="text-sm">Статистика появится после того, как пользователи начнут задавать вопросы</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Recent Users */}
            {usageStats?.sources?.some(s => s.recentUsers?.length > 0) && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5" />
                    Последние пользователи
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {usageStats.sources
                      .filter(s => s.recentUsers?.length > 0)
                      .slice(0, 5)
                      .map(stat => (
                        <div key={stat.sourceId} className="p-2 bg-secondary/20 rounded">
                          <p className="font-medium text-sm">{stat.sourceName}</p>
                          <div className="flex flex-wrap gap-2 mt-1">
                            {stat.recentUsers.map((user, i) => (
                              <span key={i} className="text-xs bg-secondary px-2 py-1 rounded">
                                {user.email}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          /* Sources Tab */
          <>
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
                {sources.map((source, index) => {
                  const usage = usageStats?.sources?.find(s => s.sourceId === source.id);
                  return (
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
                                {usage?.usageCount > 0 && (
                                  <span className="text-emerald-500">• {usage.usageCount} использований</span>
                                )}
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
                  );
                })}
              </div>
            )}
          </>
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
