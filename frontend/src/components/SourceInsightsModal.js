/**
 * SourceInsightsModal Component
 * Displays AI-generated insights (summary + suggested questions) for a source
 */
import React, { useState } from 'react';
import { 
  Search, 
  Loader2, 
  Save, 
  X, 
  Lightbulb,
  MessageSquare,
  CheckCircle
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

export const SourceInsightsModal = ({ 
  isOpen, 
  onClose, 
  sourceId, 
  sourceName,
  token 
}) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [insights, setInsights] = useState(null);
  const [saved, setSaved] = useState(false);

  const analyzeSource = async () => {
    setLoading(true);
    setSaved(false);
    try {
      const response = await fetch(`${API}/api/sources/${sourceId}/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Analysis failed');
      }
      
      const data = await response.json();
      setInsights(data);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const saveInsights = async () => {
    if (!insights) return;
    
    setSaving(true);
    try {
      const response = await fetch(`${API}/api/sources/${sourceId}/save-insights`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          summary: insights.summary,
          suggestedQuestions: insights.suggestedQuestions
        })
      });
      
      if (!response.ok) throw new Error('Failed to save');
      
      setSaved(true);
      toast.success('Insights saved!');
    } catch (error) {
      toast.error('Failed to save insights');
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    setInsights(null);
    setSaved(false);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Search className="h-5 w-5 text-indigo-500" />
            Анализ источника
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Source Name */}
          <div className="p-3 bg-secondary/50 rounded-lg">
            <span className="text-sm text-muted-foreground">Источник:</span>
            <p className="font-medium truncate">{sourceName}</p>
          </div>

          {/* Analyze Button */}
          {!insights && (
            <div className="flex justify-center py-8">
              <Button 
                onClick={analyzeSource} 
                disabled={loading}
                size="lg"
                className="gap-2"
                data-testid="analyze-source-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Анализирую...
                  </>
                ) : (
                  <>
                    <Search className="h-5 w-5" />
                    Анализировать источник
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Results */}
          {insights && (
            <div className="space-y-4 animate-in fade-in duration-300">
              {/* Summary */}
              <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="h-4 w-4 text-indigo-400" />
                  <span className="font-medium text-indigo-400">Краткое содержание</span>
                </div>
                <p className="text-sm leading-relaxed">{insights.summary}</p>
              </div>

              {/* Suggested Questions */}
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="h-4 w-4 text-emerald-400" />
                  <span className="font-medium text-emerald-400">Предлагаемые вопросы</span>
                </div>
                <div className="space-y-2">
                  {insights.suggestedQuestions.map((question, idx) => (
                    <div 
                      key={idx}
                      className="flex items-start gap-2 p-2 bg-background/50 rounded-md text-sm"
                    >
                      <span className="text-emerald-500 font-medium">{idx + 1}.</span>
                      <span>{question}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={analyzeSource} disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : '🔄 Обновить'}
                </Button>
                <Button 
                  onClick={saveInsights} 
                  disabled={saving || saved}
                  className="gap-2"
                  data-testid="save-insights-btn"
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : saved ? (
                    <>
                      <CheckCircle className="h-4 w-4" />
                      Сохранено
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      Сохранить
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SourceInsightsModal;
