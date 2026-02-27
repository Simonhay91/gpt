import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { Sparkles, Save, Info } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MyGptPromptPage = () => {
  const { t, language } = useLanguage();
  const [userPrompt, setUserPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadUserPrompt();
  }, []);

  const loadUserPrompt = async () => {
    try {
      const response = await axios.get(`${API}/user/prompt`);
      setUserPrompt(response.data.customPrompt || '');
    } catch (error) {
      console.error('Failed to load prompt:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const saveUserPrompt = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/user/prompt`, { customPrompt: userPrompt.trim() || null });
      toast.success(t('prompt.saved'));
    } catch (error) {
      toast.error(t('prompt.saveFailed'));
    } finally {
      setIsSaving(false);
    }
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

  const placeholder = language === 'ru' 
    ? `Примеры:
• Всегда отвечай на русском
• Будь краток и по делу
• Используй примеры кода при объяснении технических концепций
• Форматируй ответы списками
• Объясняй как для новичка`
    : `Examples:
• Always respond in Russian
• Be concise and to the point
• Use code examples when explaining technical concepts
• Format responses with bullet points
• Explain things as if I'm a beginner`;

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-3xl" data-testid="my-gpt-prompt-page">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <Sparkles className="h-7 w-7 text-purple-500" />
            </div>
            {t('prompt.title')}
          </h1>
          <p className="text-muted-foreground mt-2">
            {t('prompt.subtitle')}
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
                    <p className="text-sm font-medium mb-2">{t('prompt.howItWorks')}</p>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>{t('prompt.howItWorksDesc1')}</p>
                      <p>{t('prompt.howItWorksDesc2')}</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Prompt Editor */}
            <Card>
              <CardHeader>
                <CardTitle>{t('prompt.customInstructions')}</CardTitle>
                <CardDescription>
                  {t('prompt.customInstructionsDesc')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="userPrompt">{t('prompt.yourInstructions')}</Label>
                  <Textarea
                    id="userPrompt"
                    placeholder={placeholder}
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    className="min-h-[200px] font-mono text-sm"
                    data-testid="user-prompt-textarea"
                  />
                </div>

                <div className="flex items-center justify-between pt-4">
                  <p className="text-xs text-muted-foreground">
                    {userPrompt.length} {t('prompt.characters')}
                  </p>
                  <Button
                    onClick={saveUserPrompt}
                    disabled={isSaving}
                    className="bg-purple-500 hover:bg-purple-600"
                    data-testid="save-prompt-btn"
                  >
                    {isSaving ? (
                      <div className="spinner mr-2" />
                    ) : (
                      <Save className="h-4 w-4 mr-2" />
                    )}
                    {t('prompt.savePrompt')}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Examples */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t('prompt.examplePrompts')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3">
                  {examples.map((example, i) => (
                    <button
                      key={i}
                      onClick={() => setUserPrompt(example)}
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

export default MyGptPromptPage;
