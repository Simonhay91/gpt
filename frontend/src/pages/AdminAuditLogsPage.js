import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { 
  ScrollText, User, FileText, Building2, Settings,
  Filter, RefreshCw, ChevronDown, CheckCircle, XCircle,
  Plus, Trash2, Edit, Share, RotateCcw, ChevronLeft, ChevronRight
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_ICONS = {
  create: { icon: Plus, color: 'text-emerald-400', bg: 'bg-emerald-500/20' },
  update: { icon: Edit, color: 'text-blue-400', bg: 'bg-blue-500/20' },
  delete: { icon: Trash2, color: 'text-red-400', bg: 'bg-red-500/20' },
  approve: { icon: CheckCircle, color: 'text-emerald-400', bg: 'bg-emerald-500/20' },
  reject: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/20' },
  publish: { icon: Share, color: 'text-violet-400', bg: 'bg-violet-500/20' },
  restore: { icon: RotateCcw, color: 'text-amber-400', bg: 'bg-amber-500/20' },
};

const ENTITY_ICONS = {
  source: FileText,
  department: Building2,
  user: User,
  config: Settings,
};

const LEVEL_COLORS = {
  personal: 'text-violet-400 bg-violet-500/20',
  project: 'text-blue-400 bg-blue-500/20',
  department: 'text-indigo-400 bg-indigo-500/20',
  global: 'text-emerald-400 bg-emerald-500/20',
};

const AdminAuditLogsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useLanguage();
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState({
    entity: '',
    action: '',
    level: '',
    limit: 50
  });
  const [showFilters, setShowFilters] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    if (user?.isAdmin) {
      fetchLogs();
    }
  }, [user]);

  const fetchLogs = async (page = 1) => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.entity) params.append('entity', filters.entity);
      if (filters.action) params.append('action', filters.action);
      if (filters.level) params.append('level', filters.level);
      params.append('limit', filters.limit.toString());
      const offset = (page - 1) * filters.limit;
      params.append('offset', offset.toString());
      
      const response = await axios.get(`${API}/admin/audit-logs?${params}`);
      setLogs(response.data);
      setCurrentPage(page);
      // Check if there are more pages by checking if we got full limit
      setHasMore(response.data.length === filters.limit);
    } catch (error) {
      toast.error(t('common.error'));
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const renderChanges = (changes) => {
    if (!changes || Object.keys(changes).length === 0) return null;
    
    return (
      <div className="mt-2 text-xs space-y-1">
        {Object.entries(changes).map(([field, change]) => (
          <div key={field} className="flex items-center gap-2">
            <span className="text-muted-foreground">{field}:</span>
            {typeof change === 'object' && change.old !== undefined ? (
              <>
                <span className="text-red-400 line-through">{String(change.old)}</span>
                <span>→</span>
                <span className="text-emerald-400">{String(change.new)}</span>
              </>
            ) : (
              <span className="text-muted-foreground">{JSON.stringify(change)}</span>
            )}
          </div>
        ))}
      </div>
    );
  };

  if (!user?.isAdmin) {
    navigate('/dashboard');
    return null;
  }

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="audit-logs-page">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <ScrollText className="h-8 w-8 text-emerald-400" />
                {t('audit.title')}
              </h1>
              <p className="text-muted-foreground mt-2">
                {t('audit.subtitle')}
              </p>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => setShowFilters(!showFilters)}
              >
                <Filter className="h-4 w-4 mr-2" />
                {t('audit.filter')}
                <ChevronDown className={`h-4 w-4 ml-2 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
              </Button>
              <Button onClick={fetchLogs} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                {t('news.refresh')}
              </Button>
            </div>
          </div>

          {/* Filters */}
          {showFilters && (
            <Card className="mt-4">
              <CardContent className="py-4">
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <Label className="text-sm">Entity</Label>
                    <select
                      className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                      value={filters.entity}
                      onChange={(e) => setFilters({ ...filters, entity: e.target.value })}
                    >
                      <option value="">{t('audit.all')}</option>
                      <option value="source">Источники</option>
                      <option value="department">Отделы</option>
                      <option value="user">Пользователи</option>
                      <option value="config">Конфиг</option>
                    </select>
                  </div>
                  <div>
                    <Label className="text-sm">Действие</Label>
                    <select
                      className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                      value={filters.action}
                      onChange={(e) => setFilters({ ...filters, action: e.target.value })}
                    >
                      <option value="">Все</option>
                      <option value="create">Создание</option>
                      <option value="update">Изменение</option>
                      <option value="delete">Удаление</option>
                      <option value="approve">Одобрение</option>
                      <option value="reject">Отклонение</option>
                      <option value="publish">Публикация</option>
                      <option value="restore">Восстановление</option>
                    </select>
                  </div>
                  <div>
                    <Label className="text-sm">Уровень</Label>
                    <select
                      className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                      value={filters.level}
                      onChange={(e) => setFilters({ ...filters, level: e.target.value })}
                    >
                      <option value="">Все</option>
                      <option value="personal">Personal</option>
                      <option value="project">Project</option>
                      <option value="department">Department</option>
                      <option value="global">Global</option>
                    </select>
                  </div>
                  <div>
                    <Label className="text-sm">Количество</Label>
                    <select
                      className="w-full mt-1 px-3 py-2 rounded-md border border-input bg-background text-sm"
                      value={filters.limit}
                      onChange={(e) => setFilters({ ...filters, limit: parseInt(e.target.value) })}
                    >
                      <option value="25">25</option>
                      <option value="50">50</option>
                      <option value="100">100</option>
                      <option value="200">200</option>
                    </select>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <Button size="sm" onClick={() => {
                    setCurrentPage(1);
                    fetchLogs(1);
                  }}>
                    Применить
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Logs List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="spinner" />
          </div>
        ) : logs.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <ScrollText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">Нет записей</h3>
              <p className="text-muted-foreground">
                Журнал аудита пуст или не соответствует фильтрам
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {logs.map((log) => {
              const actionConfig = ACTION_ICONS[log.action] || ACTION_ICONS.update;
              const ActionIcon = actionConfig.icon;
              const EntityIcon = ENTITY_ICONS[log.entity] || FileText;
              const levelColor = LEVEL_COLORS[log.level] || '';

              return (
                <Card key={log.id} className="overflow-hidden" data-testid={`audit-log-${log.id}`}>
                  <CardContent className="py-3">
                    <div className="flex items-start gap-4">
                      {/* Action Icon */}
                      <div className={`rounded-lg p-2 ${actionConfig.bg}`}>
                        <ActionIcon className={`h-4 w-4 ${actionConfig.color}`} />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium capitalize">{log.action}</span>
                          <span className="text-muted-foreground">•</span>
                          <span className="flex items-center gap-1 text-sm">
                            <EntityIcon className="h-3 w-3" />
                            {log.entity}
                          </span>
                          {log.entityName && (
                            <>
                              <span className="text-muted-foreground">•</span>
                              <span className="text-sm font-medium truncate max-w-[200px]">
                                {log.entityName}
                              </span>
                            </>
                          )}
                          {log.level && (
                            <span className={`text-xs px-2 py-0.5 rounded capitalize ${levelColor}`}>
                              {log.level}
                            </span>
                          )}
                        </div>
                        
                        {renderChanges(log.changes)}
                        
                        <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            {log.userEmail}
                          </span>
                          <span>{formatDate(log.timestamp)}</span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default AdminAuditLogsPage;
