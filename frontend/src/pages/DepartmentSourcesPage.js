import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { 
  Building2, Upload, FileText, Trash2, Clock, Database,
  ArrowLeft, CheckCircle, XCircle, AlertCircle, Send,
  Eye, History, Download, Image, FileSpreadsheet
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  draft: { 
    label: 'Черновик', 
    color: 'text-gray-400 bg-gray-500/20', 
    icon: AlertCircle,
    cardBorder: 'border-gray-500/50',
    needsAction: true
  },
  pending: { 
    label: '⏳ Ждёт одобрения', 
    color: 'text-amber-400 bg-amber-500/30', 
    icon: Clock,
    cardBorder: 'border-amber-500 border-2',
    needsAction: true
  },
  approved: { 
    label: 'Одобрено', 
    color: 'text-blue-400 bg-blue-500/20', 
    icon: CheckCircle,
    cardBorder: 'border-blue-500/50',
    needsAction: false
  },
  active: { 
    label: '✓ Активно', 
    color: 'text-emerald-400 bg-emerald-500/20', 
    icon: CheckCircle,
    cardBorder: 'border-emerald-500/30',
    needsAction: false
  },
};

const DepartmentSourcesPage = () => {
  const { departmentId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const [department, setDepartment] = useState(null);
  const [sources, setSources] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isManager, setIsManager] = useState(false);
  
  // Approval dialog
  const [selectedSource, setSelectedSource] = useState(null);
  const [approvalAction, setApprovalAction] = useState(null);
  const [approvalComment, setApprovalComment] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Versions dialog
  const [versionsDialogOpen, setVersionsDialogOpen] = useState(false);
  const [versions, setVersions] = useState([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  
  // Preview dialog
  const [previewSource, setPreviewSource] = useState(null);
  const [previewContent, setPreviewContent] = useState('');
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  useEffect(() => {
    fetchData();
  }, [departmentId]);

  const fetchData = async () => {
    try {
      const [deptRes, sourcesRes] = await Promise.all([
        axios.get(`${API}/departments/${departmentId}`),
        axios.get(`${API}/departments/${departmentId}/sources`)
      ]);
      setDepartment(deptRes.data);
      setSources(sourcesRes.data);
      
      // Check if current user is manager
      const managers = deptRes.data.managers || [];
      setIsManager(user?.isAdmin || managers.includes(user?.id));
    } catch (error) {
      toast.error('Не удалось загрузить данные');
      if (error.response?.status === 404) {
        navigate('/admin/departments');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(
        `${API}/departments/${departmentId}/sources/upload`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      setSources([response.data, ...sources]);
      toast.success('Источник загружен (статус: черновик)');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка загрузки');
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const deleteSource = async (sourceId) => {
    if (!window.confirm('Удалить этот источник?')) return;

    try {
      await axios.delete(`${API}/sources/${sourceId}`);
      setSources(sources.filter(s => s.id !== sourceId));
      toast.success('Источник удалён');
    } catch (error) {
      toast.error('Не удалось удалить');
    }
  };

  const openApprovalDialog = (source, action) => {
    setSelectedSource(source);
    setApprovalAction(action);
    setApprovalComment('');
  };

  const processApproval = async () => {
    if (!selectedSource || !approvalAction) return;

    setIsProcessing(true);
    try {
      await axios.post(`${API}/sources/${selectedSource.id}/approval`, {
        action: approvalAction,
        comment: approvalComment
      });
      
      const actionLabels = {
        submit: 'отправлен на проверку',
        approve: 'одобрен',
        activate: 'активирован',
        reject: 'отклонён'
      };
      toast.success(`Источник ${actionLabels[approvalAction]}`);
      
      // Refresh sources
      const res = await axios.get(`${API}/departments/${departmentId}/sources`);
      setSources(res.data);
      
      setSelectedSource(null);
      setApprovalAction(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка');
    } finally {
      setIsProcessing(false);
    }
  };

  const openVersionsDialog = async (source) => {
    setSelectedSource(source);
    setVersionsDialogOpen(true);
    setIsLoadingVersions(true);
    
    try {
      const res = await axios.get(`${API}/sources/${source.id}/versions`);
      setVersions(res.data);
    } catch (error) {
      toast.error('Не удалось загрузить версии');
    } finally {
      setIsLoadingVersions(false);
    }
  };

  const openPreview = async (source) => {
    setPreviewSource(source);
    setIsLoadingPreview(true);
    setPreviewContent('');
    
    try {
      const res = await axios.get(`${API}/sources/${source.id}/preview`);
      setPreviewContent(res.data.content || 'Нет содержимого');
    } catch (error) {
      setPreviewContent('Не удалось загрузить preview');
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const getFileIcon = (mimeType) => {
    if (mimeType?.includes('image')) return Image;
    if (mimeType?.includes('spreadsheet') || mimeType?.includes('csv')) return FileSpreadsheet;
    return FileText;
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
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getAvailableActions = (source) => {
    const actions = [];
    const status = source.status || 'active';
    
    if (isManager) {
      if (status === 'draft') {
        actions.push({ action: 'submit', label: 'На проверку', icon: Send });
        actions.push({ action: 'approve', label: 'Одобрить', icon: CheckCircle });
      }
      if (status === 'pending') {
        actions.push({ action: 'approve', label: 'Одобрить', icon: CheckCircle });
        actions.push({ action: 'reject', label: 'Отклонить', icon: XCircle });
      }
      if (status === 'approved') {
        actions.push({ action: 'activate', label: 'Активировать', icon: CheckCircle });
      }
    }
    
    return actions;
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="spinner" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="department-sources-page">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            className="mb-4"
            onClick={() => navigate('/admin/departments')}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к отделам
          </Button>
          
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <Building2 className="h-8 w-8 text-indigo-400" />
                {department?.name}
              </h1>
              <p className="text-muted-foreground mt-2">
                База знаний отдела • {sources.length} источников
              </p>
            </div>
            
            {isManager && (
              <div className="relative">
                <input
                  type="file"
                  id="dept-file-upload"
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  onChange={handleFileUpload}
                  disabled={isUploading}
                  accept=".pdf,.docx,.txt,.md,.pptx,.xlsx,.csv,.png,.jpg,.jpeg"
                />
                <Button disabled={isUploading} data-testid="upload-dept-source-btn">
                  {isUploading ? (
                    <div className="spinner mr-2" />
                  ) : (
                    <Upload className="mr-2 h-4 w-4" />
                  )}
                  Загрузить
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Approval Workflow Info */}
        <Card className="mb-6 border-indigo-500/30 bg-indigo-500/5">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-indigo-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium">Workflow одобрения</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Источники отдела проходят проверку: <span className="text-gray-400">Черновик</span> → 
                  <span className="text-amber-400"> На проверке</span> → 
                  <span className="text-blue-400"> Одобрено</span> → 
                  <span className="text-emerald-400"> Активно</span>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Sources List */}
        {sources.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">Нет источников</h3>
              <p className="text-muted-foreground text-center mb-4">
                {isManager 
                  ? 'Загрузите документы для базы знаний отдела'
                  : 'Менеджер ещё не добавил источники'
                }
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {sources.map((source) => {
              const statusConfig = STATUS_CONFIG[source.status] || STATUS_CONFIG.active;
              const StatusIcon = statusConfig.icon;
              const actions = getAvailableActions(source);

              return (
                <Card key={source.id} className="card-hover group" data-testid={`dept-source-${source.id}`}>
                  <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="rounded-lg bg-indigo-500/20 p-2">
                          <FileText className="h-5 w-5 text-indigo-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold">{source.originalName}</h3>
                            <span className={`text-xs px-2 py-0.5 rounded flex items-center gap-1 ${statusConfig.color}`}>
                              <StatusIcon className="h-3 w-3" />
                              {statusConfig.label}
                            </span>
                          </div>
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
                          {source.createdByEmail && (
                            <p className="text-xs text-muted-foreground mt-1">
                              Загрузил: {source.createdByEmail}
                            </p>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        {/* Approval Actions */}
                        {actions.map(({ action, label, icon: Icon }) => (
                          <Button
                            key={action}
                            variant="outline"
                            size="sm"
                            onClick={() => openApprovalDialog(source, action)}
                          >
                            <Icon className="h-4 w-4 mr-1" />
                            {label}
                          </Button>
                        ))}
                        
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openVersionsDialog(source)}
                        >
                          <History className="h-4 w-4 mr-1" />
                          История
                        </Button>
                        
                        {isManager && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive"
                            onClick={() => deleteSource(source.id)}
                          >
                            <Trash2 className="h-4 w-4" />
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

        {/* Approval Dialog */}
        <Dialog 
          open={!!approvalAction} 
          onOpenChange={(open) => !open && setApprovalAction(null)}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>
                {approvalAction === 'submit' && 'Отправить на проверку'}
                {approvalAction === 'approve' && 'Одобрить источник'}
                {approvalAction === 'activate' && 'Активировать источник'}
                {approvalAction === 'reject' && 'Отклонить источник'}
              </DialogTitle>
              <DialogDescription>
                {selectedSource?.originalName}
              </DialogDescription>
            </DialogHeader>
            
            {(approvalAction === 'reject') && (
              <div className="space-y-2 py-4">
                <Label>Причина отклонения</Label>
                <Textarea
                  value={approvalComment}
                  onChange={(e) => setApprovalComment(e.target.value)}
                  placeholder="Укажите причину..."
                  className="min-h-[100px]"
                />
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setApprovalAction(null)}>
                Отмена
              </Button>
              <Button 
                onClick={processApproval} 
                disabled={isProcessing}
                variant={approvalAction === 'reject' ? 'destructive' : 'default'}
              >
                {isProcessing ? <div className="spinner mr-2" /> : null}
                Подтвердить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Versions Dialog */}
        <Dialog open={versionsDialogOpen} onOpenChange={setVersionsDialogOpen}>
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
                          <span className="font-medium">Версия {version.version}</span>
                          {version.isActive && (
                            <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded">
                              Активная
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {version.changeDescription || 'Нет описания'}
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
      </div>
    </DashboardLayout>
  );
};

export default DepartmentSourcesPage;
