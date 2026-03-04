import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { 
  FileText, Upload, Trash2, Share, Clock, Database,
  Lock, History, ChevronRight, Building2, FolderOpen, Eye, Search
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import SourceInsightsModal from '../components/SourceInsightsModal';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PersonalSourcesPage = () => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [sources, setSources] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedSource, setSelectedSource] = useState(null);
  const [versions, setVersions] = useState([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  
  // Publish dialog
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [publishTarget, setPublishTarget] = useState({ level: 'project', id: '' });
  const [projects, setProjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [isPublishing, setIsPublishing] = useState(false);
  
  // Preview dialog
  const [previewSource, setPreviewSource] = useState(null);
  const [previewContent, setPreviewContent] = useState('');
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  
  // Insights modal
  const [insightsSource, setInsightsSource] = useState(null);

  useEffect(() => {
    fetchSources();
    fetchTargets();
  }, []);

  const fetchSources = async () => {
    try {
      const response = await axios.get(`${API}/personal-sources`);
      setSources(response.data);
    } catch (error) {
      toast.error(t('common.error'));
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTargets = async () => {
    try {
      const [projectsRes, deptsRes] = await Promise.all([
        axios.get(`${API}/projects`),
        axios.get(`${API}/users/me/departments`)
      ]);
      setProjects(projectsRes.data);
      setDepartments(deptsRes.data.filter(d => d.isManager));
    } catch (error) {
      console.error('Failed to load targets');
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API}/personal-sources/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSources([response.data, ...sources]);
      toast.success('Source uploaded');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const deleteSource = async (sourceId) => {
    if (!window.confirm('Delete this source? This cannot be undone.')) return;

    try {
      await axios.delete(`${API}/personal-sources/${sourceId}`);
      setSources(sources.filter(s => s.id !== sourceId));
      toast.success('Source deleted');
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const openPreview = async (source) => {
    setPreviewSource(source);
    setIsLoadingPreview(true);
    setPreviewContent('');
    
    try {
      const response = await axios.get(`${API}/personal-sources/${source.id}/preview`);
      setPreviewContent(response.data.content || response.data.extractedText || 'No content available');
    } catch (error) {
      setPreviewContent('Failed to load preview');
      toast.error('Failed to load preview');
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const openVersionsDialog = async (source) => {
    setSelectedSource(source);
    setIsLoadingVersions(true);
    try {
      const response = await axios.get(`${API}/sources/${source.id}/versions`);
      setVersions(response.data);
    } catch (error) {
      toast.error('Failed to load versions');
    } finally {
      setIsLoadingVersions(false);
    }
  };

  const openPublishDialog = (source) => {
    setSelectedSource(source);
    setPublishTarget({ level: 'project', id: projects[0]?.id || '' });
    setPublishDialogOpen(true);
  };

  const publishSource = async () => {
    if (!publishTarget.id) {
      toast.error('Select a target');
      return;
    }

    setIsPublishing(true);
    try {
      const response = await axios.post(`${API}/personal-sources/${selectedSource.id}/publish`, {
        targetLevel: publishTarget.level,
        targetId: publishTarget.id
      });
      toast.success(response.data.message);
      if (response.data.requiresApproval) {
        toast.info('Requires manager approval');
      }
      setPublishDialogOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Publish failed');
    } finally {
      setIsPublishing(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatBytes = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="personal-sources-page">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <Lock className="h-8 w-8 text-violet-400" />
                {t('personal.title')}
              </h1>
              <p className="text-muted-foreground mt-2">
                {t('personal.subtitle')}
              </p>
            </div>
            
            <div className="relative">
              <input
                type="file"
                id="file-upload"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileUpload}
                disabled={isUploading}
                accept=".pdf,.docx,.txt,.md,.pptx,.xlsx,.csv,.png,.jpg,.jpeg"
              />
              <Button disabled={isUploading} data-testid="upload-btn">
                {isUploading ? (
                  <div className="spinner mr-2" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                {t('personal.upload')}
              </Button>
            </div>
          </div>
        </div>

        {/* Info Banner */}
        <Card className="mb-6 border-violet-500/30 bg-violet-500/5">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <Lock className="h-5 w-5 text-violet-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium">{t('personal.infoTitle')}</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('personal.infoDesc')}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Sources List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="spinner" />
          </div>
        ) : sources.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">{t('personal.noSources')}</h3>
              <p className="text-muted-foreground text-center mb-4">
                {t('personal.uploadDesc')}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {sources.map((source) => (
              <Card 
                key={source.id} 
                className="card-hover group"
                data-testid={`source-card-${source.id}`}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="rounded-lg bg-violet-500/20 p-2">
                        <FileText className="h-5 w-5 text-violet-400" />
                      </div>
                      <div>
                        <h3 className="font-semibold">{source.originalName}</h3>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                          <span>{formatBytes(source.sizeBytes)}</span>
                          <span>•</span>
                          <span>{source.chunkCount} chunks</span>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDate(source.createdAt)}
                          </span>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <Database className="h-3 w-3" />
                            v{source.version}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openPreview(source)}
                        data-testid={`preview-btn-${source.id}`}
                      >
                        <Eye className="h-4 w-4 mr-1" />
                        Просмотр
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openVersionsDialog(source)}
                        data-testid={`versions-btn-${source.id}`}
                        className=""
                      >
                        <History className="h-4 w-4 mr-1" />
                        История
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openPublishDialog(source)}
                        data-testid={`publish-btn-${source.id}`}
                        className=""
                      >
                        <Share className="h-4 w-4 mr-1" />
                        Опубликовать
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive "
                        onClick={() => deleteSource(source.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Versions Dialog */}
        <Dialog open={!!selectedSource && !publishDialogOpen} onOpenChange={(open) => !open && setSelectedSource(null)}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                История версий
              </DialogTitle>
              <DialogDescription>
                {selectedSource?.originalName}
              </DialogDescription>
            </DialogHeader>
            
            {isLoadingVersions ? (
              <div className="flex justify-center py-8">
                <div className="spinner" />
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {versions.map((version) => (
                  <div 
                    key={version.id}
                    className={`p-3 rounded-lg border ${version.isActive ? 'border-emerald-500 bg-emerald-500/10' : 'border-border'}`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">Version {version.version}</span>
                          {version.isActive && (
                            <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">
                              Active
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {version.changeDescription || 'No description'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {version.createdByEmail} • {formatDate(version.createdAt)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Publish Dialog */}
        <Dialog open={publishDialogOpen} onOpenChange={setPublishDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Share className="h-5 w-5" />
                Опубликовать источник
              </DialogTitle>
              <DialogDescription>
                Создаст копию в выбранном месте
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Уровень</Label>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant={publishTarget.level === 'project' ? 'default' : 'outline'}
                    className="w-full"
                    onClick={() => setPublishTarget({ ...publishTarget, level: 'project', id: projects[0]?.id || '' })}
                  >
                    <FolderOpen className="h-4 w-4 mr-2" />
                    Проект
                  </Button>
                  <Button
                    variant={publishTarget.level === 'department' ? 'default' : 'outline'}
                    className="w-full"
                    onClick={() => setPublishTarget({ ...publishTarget, level: 'department', id: departments[0]?.id || '' })}
                    disabled={departments.length === 0}
                  >
                    <Building2 className="h-4 w-4 mr-2" />
                    Отдел
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label>
                  {publishTarget.level === 'project' ? 'Проект' : 'Отдел'}
                </Label>
                <select
                  className="w-full px-3 py-2 rounded-md border border-input bg-background"
                  value={publishTarget.id}
                  onChange={(e) => setPublishTarget({ ...publishTarget, id: e.target.value })}
                >
                  {publishTarget.level === 'project' 
                    ? projects.map(p => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))
                    : departments.map(d => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))
                  }
                </select>
              </div>

              {publishTarget.level === 'department' && (
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                  <p className="text-sm text-amber-400">
                    ⚠️ Публикация в отдел требует одобрения менеджера
                  </p>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setPublishDialogOpen(false)}>
                Отмена
              </Button>
              <Button onClick={publishSource} disabled={isPublishing || !publishTarget.id}>
                {isPublishing ? <div className="spinner mr-2" /> : null}
                Опубликовать
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Preview Dialog */}
        <Dialog open={!!previewSource} onOpenChange={(open) => !open && setPreviewSource(null)}>
          <DialogContent className="sm:max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-violet-400" />
                Просмотр содержимого
              </DialogTitle>
              <DialogDescription>
                {previewSource?.originalName}
              </DialogDescription>
            </DialogHeader>
            
            {isLoadingPreview ? (
              <div className="flex justify-center py-8">
                <div className="spinner" />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-4 text-sm text-muted-foreground border-b pb-3">
                  <span>{formatBytes(previewSource?.sizeBytes || 0)}</span>
                  <span>•</span>
                  <span>{previewSource?.chunkCount || 0} chunks</span>
                  <span>•</span>
                  <span>v{previewSource?.version || 1}</span>
                </div>
                <div className="bg-muted/50 rounded-lg p-4 max-h-[400px] overflow-y-auto">
                  <pre className="whitespace-pre-wrap text-sm font-mono">
                    {previewContent}
                  </pre>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setPreviewSource(null)}>
                Закрыть
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default PersonalSourcesPage;
