import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';
import { 
  ArrowLeft, 
  Globe2, 
  Upload, 
  Trash2, 
  FileText, 
  Eye, 
  Loader2,
  HardDrive,
  File,
  User,
  Search
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import SourceInsightsModal from '../components/SourceInsightsModal';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const GlobalSourcesPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sources, setSources] = useState([]);
  const [canEdit, setCanEdit] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  
  // Preview Dialog
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  const fetchSources = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/global-sources`);
      setSources(response.data.sources || []);
      setCanEdit(response.data.canEdit || false);
    } catch (error) {
      toast.error('Не удалось загрузить глобальные источники');
    } finally {
      setIsLoading(false);
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
        
        await axios.post(`${API}/global-sources/upload`, formData, {
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

  const handleDelete = async (sourceId, sourceName, uploadedBy) => {
    // Check if user can delete this source
    if (!user?.isAdmin && uploadedBy !== user?.id) {
      toast.error('Вы можете удалять только свои загрузки');
      return;
    }
    
    if (!window.confirm(`Удалить "${sourceName}"?`)) {
      return;
    }

    try {
      await axios.delete(`${API}/global-sources/${sourceId}`);
      toast.success('Источник удалён');
      setSources(sources.filter(s => s.id !== sourceId));
    } catch (error) {
      const message = error.response?.data?.detail || 'Не удалось удалить';
      toast.error(message);
    }
  };

  const handlePreview = async (sourceId) => {
    setIsLoadingPreview(true);
    setPreviewDialogOpen(true);
    
    try {
      const response = await axios.get(`${API}/global-sources/${sourceId}/preview`);
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
      year: 'numeric'
    });
  };

  const getSourceIcon = (source) => {
    if (source.kind === 'url') return <Globe2 className="h-4 w-4 text-blue-400" />;
    
    const mimeType = source.mimeType || '';
    if (mimeType.includes('pdf')) return <FileText className="h-4 w-4 text-red-400" />;
    if (mimeType.includes('csv')) return <FileText className="h-4 w-4 text-green-400" />;
    return <File className="h-4 w-4 text-muted-foreground" />;
  };

  const totalSize = sources.reduce((acc, s) => acc + (s.sizeBytes || 0), 0);

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="global-sources-page">
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
                  Общая база знаний для всех пользователей
                </p>
              </div>
            </div>
            
            {canEdit && (
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
            )}
          </div>
        </div>

        {/* Stats */}
        {sources.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
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
          </div>
        )}

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
              <p className="text-muted-foreground text-center">
                {canEdit 
                  ? 'Загрузите файлы, чтобы создать общую базу знаний'
                  : 'Администратор ещё не добавил источники'
                }
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {sources.map((source, index) => {
              const canDelete = user?.isAdmin || source.uploadedBy === user?.id;
              
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
                            {source.sizeBytes && (
                              <span>{formatBytes(source.sizeBytes)}</span>
                            )}
                            <span>• {source.chunkCount || 0} фрагментов</span>
                            <span>• {formatDate(source.createdAt)}</span>
                            {source.uploadedBy === user?.id && (
                              <span className="flex items-center gap-1 text-emerald-500">
                                <User className="h-3 w-3" /> Вы
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2 ml-4">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 "
                          onClick={() => handlePreview(source.id)}
                          data-testid={`preview-source-${source.id}`}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {canEdit && canDelete && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 "
                            onClick={() => handleDelete(source.id, source.originalName || source.url, source.uploadedBy)}
                            data-testid={`delete-source-${source.id}`}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {/* Preview Dialog */}
        <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
          <DialogContent className="sm:max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                {previewData?.name || 'Превью'}
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
                  {previewData.text || 'Нет текста'}
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

export default GlobalSourcesPage;
