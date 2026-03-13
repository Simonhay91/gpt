import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { 
  ArrowLeft, 
  User, 
  Coins, 
  MessageSquare, 
  FolderOpen, 
  FileText, 
  Clock, 
  Save,
  Settings,
  Globe2
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminUserDetailPage = () => {
  const { userId } = useParams();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [userDetails, setUserDetails] = useState(null);
  const [userPrompt, setUserPrompt] = useState('');
  const [userModel, setUserModel] = useState('');
  const [canEditGlobal, setCanEditGlobal] = useState(false);
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  const [isSavingModel, setIsSavingModel] = useState(false);
  const [isSavingGlobalPerm, setIsSavingGlobalPerm] = useState(false);

  const gptModels = [
    { value: '', label: 'По умолчанию (глобальная настройка)' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini (экономичная)' },
    { value: 'gpt-4.1', label: 'GPT-4.1 (стандарт)' },
    { value: 'gpt-4o', label: 'GPT-4o (премиум)' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo (большие документы)' }
  ];

  useEffect(() => {
    fetchUserDetails();
  }, [userId]);

  const fetchUserDetails = async () => {
    try {
      const response = await axios.get(`${API}/admin/users/${userId}/details`);
      setUserDetails(response.data);
      setUserPrompt(response.data.prompt || '');
      setUserModel(response.data.gptModel || '');
      setCanEditGlobal(response.data.user?.canEditGlobalSources || false);
    } catch (error) {
      toast.error('Failed to load user details');
      navigate('/admin/users');
    } finally {
      setIsLoading(false);
    }
  };

  const savePrompt = async () => {
    setIsSavingPrompt(true);
    try {
      await axios.put(`${API}/admin/users/${userId}/prompt`, { prompt: userPrompt });
      toast.success('Prompt saved');
    } catch (error) {
      toast.error('Failed to save prompt');
    } finally {
      setIsSavingPrompt(false);
    }
  };

  const saveModel = async () => {
    setIsSavingModel(true);
    try {
      await axios.put(`${API}/admin/users/${userId}/gpt-model`, { model: userModel || null });
      toast.success('Model saved');
    } catch (error) {
      toast.error('Failed to save model');
    } finally {
      setIsSavingModel(false);
    }
  };

  const toggleGlobalPermission = async () => {
    setIsSavingGlobalPerm(true);
    try {
      await axios.put(`${API}/admin/users/${userId}/global-permission`, { 
        canEditGlobalSources: !canEditGlobal 
      });
      setCanEditGlobal(!canEditGlobal);
      toast.success(canEditGlobal ? 'Разрешение отозвано' : 'Разрешение выдано');
    } catch (error) {
      toast.error('Ошибка сохранения');
    } finally {
      setIsSavingGlobalPerm(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatNumber = (num) => {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="spinner h-8 w-8" />
        </div>
      </DashboardLayout>
    );
  }

  if (!userDetails) {
    return (
      <DashboardLayout>
        <div className="p-8 text-center">
          <p className="text-muted-foreground">User not found</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 md:p-8 max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/users')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xl font-bold">
              {userDetails.user.email?.charAt(0).toUpperCase()}
            </div>
            <div>
              <h1 className="text-2xl font-bold">{userDetails.user.email}</h1>
              <p className="text-sm text-muted-foreground">
                Зарегистрирован: {formatDate(userDetails.user.createdAt)}
              </p>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Coins className="h-8 w-8 text-amber-400" />
                <div>
                  <p className="text-2xl font-bold">{formatNumber(userDetails.tokenUsage.totalTokens)}</p>
                  <p className="text-xs text-muted-foreground">Токенов</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <MessageSquare className="h-8 w-8 text-emerald-400" />
                <div>
                  <p className="text-2xl font-bold">{formatNumber(userDetails.tokenUsage.totalMessages)}</p>
                  <p className="text-xs text-muted-foreground">Сообщений</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <FolderOpen className="h-8 w-8 text-blue-400" />
                <div>
                  <p className="text-2xl font-bold">{userDetails.projects.length}</p>
                  <p className="text-xs text-muted-foreground">Проектов</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <FileText className="h-8 w-8 text-purple-400" />
                <div>
                  <p className="text-2xl font-bold">
                    {userDetails.projects.reduce((sum, p) => sum + (p.sourceCount || 0), 0)}
                  </p>
                  <p className="text-xs text-muted-foreground">Файлов</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Left Column - Settings */}
          <div className="space-y-6">
            {/* GPT Model */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  GPT Модель
                </CardTitle>
                <CardDescription>
                  Индивидуальная модель для этого пользователя
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <select
                  value={userModel}
                  onChange={(e) => setUserModel(e.target.value)}
                  className="w-full p-2 rounded-md border border-input bg-background"
                >
                  {gptModels.map(m => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
                <Button onClick={saveModel} disabled={isSavingModel} className="w-full">
                  {isSavingModel ? <div className="spinner mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                  Сохранить модель
                </Button>
              </CardContent>
            </Card>

            {/* Global Sources Permission */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe2 className="h-5 w-5" />
                  Глобальные источники
                </CardTitle>
                <CardDescription>
                  Разрешение редактировать общую базу знаний
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                  <div>
                    <p className="font-medium">Может редактировать</p>
                    <p className="text-sm text-muted-foreground">
                      {canEditGlobal ? 'Пользователь может загружать и удалять свои файлы' : 'Только просмотр'}
                    </p>
                  </div>
                  <Button 
                    variant={canEditGlobal ? "destructive" : "default"}
                    size="sm"
                    onClick={toggleGlobalPermission}
                    disabled={isSavingGlobalPerm}
                  >
                    {isSavingGlobalPerm ? (
                      <div className="spinner h-4 w-4" />
                    ) : canEditGlobal ? (
                      'Отозвать'
                    ) : (
                      'Выдать'
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* User Prompt */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User className="h-5 w-5" />
                  Промпт пользователя
                </CardTitle>
                <CardDescription>
                  Пользовательские инструкции для GPT
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  placeholder="Промпт не задан"
                  className="min-h-[150px] font-mono text-sm"
                />
                <Button onClick={savePrompt} disabled={isSavingPrompt} className="w-full">
                  {isSavingPrompt ? <div className="spinner mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                  Сохранить промпт
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Projects & Activity */}
          <div className="space-y-6">
            {/* Projects */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FolderOpen className="h-5 w-5" />
                  Проекты ({userDetails.projects.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                {userDetails.projects.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">Нет проектов</p>
                ) : (
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {userDetails.projects.map(project => (
                      <div key={project.id} className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg">
                        <div>
                          <p className="font-medium text-sm">{project.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {project.chatCount} чатов • {project.sourceCount} файлов
                          </p>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(project.createdAt).split(',')[0]}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default AdminUserDetailPage;
