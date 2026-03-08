import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { Sparkles, Save, Info, User } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AiSettingsPage = () => {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [departments, setDepartments] = useState([]);
  
  const [formData, setFormData] = useState({
    display_name: '',
    position: '',
    department_id: '',
    preferred_language: 'ru',
    response_style: 'formal',
    custom_instruction: ''
  });

  useEffect(() => {
    loadAiProfile();
    loadDepartments();
  }, []);

  const loadDepartments = async () => {
    try {
      const response = await axios.get(`${API}/departments`);
      setDepartments(response.data.items || []);
    } catch (error) {
      console.error('Failed to load departments:', error);
    }
  };

  const loadAiProfile = async () => {
    try {
      const response = await axios.get(`${API}/users/me/ai-profile`);
      setFormData({
        display_name: response.data.display_name || user?.email?.split('@')[0] || '',
        position: response.data.position || '',
        department_id: response.data.department_id || '',
        preferred_language: response.data.preferred_language || 'ru',
        response_style: response.data.response_style || 'formal',
        custom_instruction: response.data.custom_instruction || ''
      });
    } catch (error) {
      console.error('Failed to load AI profile:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const saveAiProfile = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/users/me/ai-profile`, formData);
      toast.success(language === 'ru' ? 'AI настройки сохранены' : 'AI settings saved');
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка сохранения' : 'Failed to save');
      console.error('Save error:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const examples = language === 'ru' ? [
    "Всегда отвечай на русском. Будь краток.",
    "Я senior разработчик. Пропускай базовые объяснения, фокусируйся на продвинутых концепциях.",
    "Форматируй код с комментариями. Используй TypeScript когда возможно.",
    "Я работаю в финансах. Используй соответствующую терминологию и примеры.",
    "Объясняй пошагово. Я учусь программированию."
  ] : [
    "Always respond in Russian. Be concise.",
    "I'm a senior developer. Skip basic explanations, focus on advanced concepts.",
    "Format all code with comments. Use TypeScript when possible.",
    "I work in finance. Use relevant terminology and examples.",
    "Explain things step by step. I'm learning programming."
  ];

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-3xl" data-testid="ai-settings-page">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <Sparkles className="h-7 w-7 text-purple-500" />
            </div>
            {language === 'ru' ? 'AI Настройки' : 'AI Settings'}
          </h1>
          <p className="text-muted-foreground mt-2">
            {language === 'ru' 
              ? 'Настройте, как AI должен взаимодействовать с вами' 
              : 'Configure how AI should interact with you'}
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="spinner" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Info Card */}
            <Card className="border-purple-500/30 bg-purple-500/5">
              <CardContent className="py-4">
                <div className="flex items-start gap-3">
                  <Info className="h-5 w-5 text-purple-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium mb-2">
                      {language === 'ru' ? 'Как это работает?' : 'How it works?'}
                    </p>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>
                        {language === 'ru'
                          ? 'AI будет учитывать ваш профиль и предпочтения при генерации ответов.'
                          : 'AI will consider your profile and preferences when generating responses.'}
                      </p>
                      <p>
                        {language === 'ru'
                          ? 'Все настройки применяются ко всем вашим чатам.'
                          : 'All settings apply to all your chats.'}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Profile Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User className="h-5 w-5" />
                  {language === 'ru' ? 'Профиль' : 'Profile'}
                </CardTitle>
                <CardDescription>
                  {language === 'ru'
                    ? 'Информация о вас для персонализации ответов'
                    : 'Information about you for personalized responses'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Display Name */}
                <div className="space-y-2">
                  <Label htmlFor="display_name">
                    {language === 'ru' ? 'Отображаемое имя' : 'Display Name'}
                  </Label>
                  <Input
                    id="display_name"
                    placeholder={language === 'ru' ? 'Иван Петров' : 'John Doe'}
                    value={formData.display_name}
                    onChange={(e) => handleChange('display_name', e.target.value)}
                  />
                </div>

                {/* Position */}
                <div className="space-y-2">
                  <Label htmlFor="position">
                    {language === 'ru' ? 'Должность' : 'Position'}
                  </Label>
                  <Input
                    id="position"
                    placeholder={language === 'ru' ? 'Менеджер по продажам' : 'Sales Manager'}
                    value={formData.position}
                    onChange={(e) => handleChange('position', e.target.value)}
                  />
                </div>

                {/* Department */}
                <div className="space-y-2">
                  <Label htmlFor="department_id">
                    {language === 'ru' ? 'Отдел' : 'Department'}
                  </Label>
                  <Select
                    value={formData.department_id}
                    onValueChange={(value) => handleChange('department_id', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={language === 'ru' ? 'Выберите отдел' : 'Select department'} />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.map((dept) => (
                        <SelectItem key={dept.id} value={dept.id}>
                          {dept.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Preferred Language */}
                <div className="space-y-2">
                  <Label htmlFor="preferred_language">
                    {language === 'ru' ? 'Предпочитаемый язык' : 'Preferred Language'}
                  </Label>
                  <Select
                    value={formData.preferred_language}
                    onValueChange={(value) => handleChange('preferred_language', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ru">Русский</SelectItem>
                      <SelectItem value="en">English</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Response Style */}
                <div className="space-y-2">
                  <Label htmlFor="response_style">
                    {language === 'ru' ? 'Стиль ответов' : 'Response Style'}
                  </Label>
                  <Select
                    value={formData.response_style}
                    onValueChange={(value) => handleChange('response_style', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="formal">
                        {language === 'ru' ? 'Формальный' : 'Formal'}
                      </SelectItem>
                      <SelectItem value="casual">
                        {language === 'ru' ? 'Неформальный' : 'Casual'}
                      </SelectItem>
                      <SelectItem value="technical">
                        {language === 'ru' ? 'Технический' : 'Technical'}
                      </SelectItem>
                      <SelectItem value="simple">
                        {language === 'ru' ? 'Простой' : 'Simple'}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Custom Instructions */}
            <Card>
              <CardHeader>
                <CardTitle>
                  {language === 'ru' ? 'Дополнительная инструкция' : 'Custom Instructions'}
                </CardTitle>
                <CardDescription>
                  {language === 'ru'
                    ? 'Специальные указания для AI'
                    : 'Special instructions for AI'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="custom_instruction">
                    {language === 'ru' ? 'Ваши инструкции' : 'Your Instructions'}
                  </Label>
                  <Textarea
                    id="custom_instruction"
                    placeholder={language === 'ru' 
                      ? 'Например: Всегда отвечай на русском. Будь краток и по делу.'
                      : 'E.g.: Always respond in Russian. Be concise.'}
                    value={formData.custom_instruction}
                    onChange={(e) => handleChange('custom_instruction', e.target.value)}
                    className="min-h-[150px] font-mono text-sm"
                    data-testid="custom-instruction-textarea"
                  />
                </div>

                <div className="flex items-center justify-between pt-4">
                  <p className="text-xs text-muted-foreground">
                    {formData.custom_instruction.length} {language === 'ru' ? 'символов' : 'characters'}
                  </p>
                  <Button
                    onClick={saveAiProfile}
                    disabled={isSaving}
                    className="bg-purple-500 hover:bg-purple-600"
                    data-testid="save-ai-settings-btn"
                  >
                    {isSaving ? (
                      <div className="spinner mr-2" />
                    ) : (
                      <Save className="h-4 w-4 mr-2" />
                    )}
                    {language === 'ru' ? 'Сохранить настройки' : 'Save Settings'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Examples */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  {language === 'ru' ? 'Примеры инструкций' : 'Example Instructions'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3">
                  {examples.map((example, i) => (
                    <button
                      key={i}
                      onClick={() => handleChange('custom_instruction', example)}
                      className="text-left p-3 rounded-lg border border-border hover:border-purple-500/50 hover:bg-purple-500/5 transition-colors text-sm"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default AiSettingsPage;
