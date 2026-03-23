import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Loader2, Brain, Sparkles, CheckCircle2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MAX_CHARS = 6000;
const WARN_CHARS = 4800;

const ProjectMemoryModal = ({ open, onClose, chatId, projectId, messages }) => {
  const [step, setStep] = useState('extracting');
  const [points, setPoints] = useState([]);
  const [selected, setSelected] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [existingMemory, setExistingMemory] = useState('');
  const [previewText, setPreviewText] = useState('');

  useEffect(() => {
    if (open) {
      setStep('extracting');
      setPoints([]);
      setSelected([]);
      extractPoints();
      loadExistingMemory();
    }
  }, [open]);

  useEffect(() => {
    const selectedPoints = points.filter((_, i) => selected.includes(i));
    const newPart = selectedPoints.map(p => `• ${p}`).join('\n');
    const combined = existingMemory
      ? `${existingMemory}\n\n[Обновлено]\n${newPart}`
      : newPart;
    setPreviewText(combined);
  }, [selected, points, existingMemory]);

  const loadExistingMemory = async () => {
    try {
      const res = await axios.get(`${API}/projects/${projectId}/memory`);
      setExistingMemory(res.data.project_memory || '');
    } catch (e) {
      setExistingMemory('');
    }
  };

const extractPoints = async () => {
  try {
    const dialogText = messages
      .slice(-30)
      .map(m => `${m.role === 'user' ? 'User' : 'AI'}: ${m.content || ''}`)
      .filter(line => line.length > 10)
      .join('\n\n');

    if (!dialogText || dialogText.length < 20) {
      setPoints([]);
      setStep('selecting');
      return;
    }

    const response = await axios.post(`${API}/chats/${chatId}/extract-memory-points`, {
      dialogText
    });

    const pts = response.data.points || [];
    setPoints(pts);
    setStep('selecting');
  } catch (e) {
    console.error('extractPoints error:', e);
    setPoints([]);
    setStep('error');
  }
};

  const togglePoint = (idx) => {
    setSelected(prev =>
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    );
  };

  const handleSave = async () => {
    if (selected.length === 0) {
      toast.error('Выберите хотя бы 1 пункт');
      return;
    }
    if (previewText.length > MAX_CHARS) {
      toast.error('Слишком длинно — уберите несколько пунктов');
      return;
    }

    setIsSaving(true);
    try {
      await axios.put(`${API}/projects/${projectId}/memory`, {
        project_memory: previewText
      });
      toast.success('Project Memory сохранён ✅');
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Не удалось сохранить');
    } finally {
      setIsSaving(false);
    }
  };

  const charCount = previewText.length;
  const tokenApprox = Math.round(charCount / 4);
  const isOverLimit = charCount > MAX_CHARS;
  const isNearLimit = charCount > WARN_CHARS;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-violet-400" />
            Project Memory
          </DialogTitle>
          <DialogDescription>
            Выберите ключевые моменты из разговора, чтобы AI помнил их в следующих чатах
          </DialogDescription>
        </DialogHeader>

        {step === 'extracting' ? (
          <div className="flex flex-col items-center justify-center py-10 gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
            <p className="text-sm text-muted-foreground">Извлечение ключевых моментов...</p>
          </div>
        ) : step === 'error' ? (
          <div className="text-center py-6 space-y-3">
            <p className="text-sm text-red-400">Ошибка при обращении к AI. Проверьте соединение.</p>
            <Button variant="outline" size="sm" onClick={() => { setStep('extracting'); extractPoints(); }}>
              Повторить
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {points.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground text-sm">
                Разговор слишком короткий — ничего не извлечено
              </div>
            ) : (
              <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
                <p className="text-xs text-muted-foreground mb-2">
                  Выберите что сохранить ({selected.length}/{points.length})
                </p>
                {points.map((point, idx) => (
                  <div
                    key={idx}
                    onClick={() => togglePoint(idx)}
                    className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selected.includes(idx)
                        ? 'border-violet-500/50 bg-violet-500/10'
                        : 'border-border hover:border-violet-500/30 hover:bg-secondary/50'
                    }`}
                  >
                    <CheckCircle2 className={`h-4 w-4 mt-0.5 flex-shrink-0 transition-colors ${
                      selected.includes(idx) ? 'text-violet-400' : 'text-muted-foreground/30'
                    }`} />
                    <span className="text-sm leading-relaxed">{point}</span>
                  </div>
                ))}
              </div>
            )}

            {selected.length > 0 && (
              <div className={`flex items-center justify-between text-xs px-1 ${
                isOverLimit ? 'text-red-400' : isNearLimit ? 'text-amber-400' : 'text-muted-foreground'
              }`}>
                <span>{charCount} символов</span>
                <span className={`font-medium ${isOverLimit ? 'text-red-400' : ''}`}>
                  ~{tokenApprox} / 1500 токенов
                </span>
              </div>
            )}

            {isOverLimit && (
              <p className="text-xs text-red-400 px-1">
                ⚠️ Лимит превышен — уберите несколько пунктов
              </p>
            )}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || step === 'extracting' || selected.length === 0 || isOverLimit}
            className="gap-2 bg-violet-600 hover:bg-violet-700"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Сохранить в Memory
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ProjectMemoryModal;