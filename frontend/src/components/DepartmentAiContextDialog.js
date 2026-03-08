import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { Sparkles, Save } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DepartmentAiContextDialog = ({ department, isOpen, onClose, language }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [aiContext, setAiContext] = useState({
    style: '',
    instruction: ''
  });

  useEffect(() => {
    if (isOpen && department) {
      loadAiContext();
    }
  }, [isOpen, department]);

  const loadAiContext = async () => {
    setIsLoading(true);
    try {
      const response = await axios.get(`${API}/departments/${department.id}/ai-context`);
      setAiContext({
        style: response.data.style || '',
        instruction: response.data.instruction || ''
      });
    } catch (error) {
      console.error('Failed to load AI context:', error);
      toast.error(language === 'ru' ? 'Ошибка загрузки' : 'Failed to load');
    } finally {
      setIsLoading(false);
    }
  };

  const saveAiContext = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/departments/${department.id}/ai-context`, aiContext);
      toast.success(language === 'ru' ? 'AI контекст сохранен' : 'AI context saved');
      onClose();
    } catch (error) {
      console.error('Failed to save AI context:', error);
      toast.error(language === 'ru' ? 'Ошибка сохранения' : 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  };

  if (!department) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-400" />
            {language === 'ru' ? `AI Контекст — ${department.name}` : `AI Context — ${department.name}`}
          </DialogTitle>
          <DialogDescription>
            {language === 'ru'
              ? 'Настройте, как AI будет взаимодействовать с сотрудниками этого отдела'
              : 'Configure how AI will interact with members of this department'}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="spinner" />
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {/* Style */}
            <div className="space-y-2">
              <Label htmlFor="style">
                {language === 'ru' ? 'Стиль отдела' : 'Department Style'}
              </Label>
              <Input
                id="style"
                placeholder={language === 'ru' ? 'Например: ориентированный на клиента' : 'E.g.: client-oriented'}
                value={aiContext.style}
                onChange={(e) => setAiContext({ ...aiContext, style: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                {language === 'ru'
                  ? 'Краткое описание стиля работы отдела'
                  : 'Brief description of department working style'}
              </p>
            </div>

            {/* Instruction */}
            <div className="space-y-2">
              <Label htmlFor="instruction">
                {language === 'ru' ? 'Инструкция для AI' : 'AI Instruction'}
              </Label>
              <Textarea
                id="instruction"
                placeholder={
                  language === 'ru'
                    ? 'Например: Всю техническую информацию подавай простым языком, ориентированным на клиента. Подчёркивай выгоды, а не характеристики.'
                    : 'E.g.: Present all technical information in simple, client-oriented language. Emphasize benefits, not features.'
                }
                value={aiContext.instruction}
                onChange={(e) => setAiContext({ ...aiContext, instruction: e.target.value })}
                className="min-h-[200px] font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                {language === 'ru'
                  ? 'Эта инструкция будет добавлена ко всем запросам сотрудников отдела'
                  : 'This instruction will be added to all requests from department members'}
              </p>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {language === 'ru' ? 'Отмена' : 'Cancel'}
          </Button>
          <Button
            onClick={saveAiContext}
            disabled={isSaving || isLoading}
            className="bg-purple-500 hover:bg-purple-600"
          >
            {isSaving ? (
              <div className="spinner mr-2" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            {language === 'ru' ? 'Сохранить' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default DepartmentAiContextDialog;
