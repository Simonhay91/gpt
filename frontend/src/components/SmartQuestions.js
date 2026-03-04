/**
 * SmartQuestions Component
 * Shows AI-generated question suggestions based on active sources
 */
import React, { useState } from 'react';
import { Lightbulb, Loader2, RefreshCw, X } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

export const SmartQuestions = ({ 
  chatId, 
  token, 
  hasActiveSources,
  onQuestionClick 
}) => {
  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [sourceNames, setSourceNames] = useState([]);
  const [isExpanded, setIsExpanded] = useState(false);

  const generateQuestions = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/chats/${chatId}/smart-questions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to generate questions');
      }
      
      const data = await response.json();
      setQuestions(data.questions || []);
      setSourceNames(data.sourceNames || []);
      setIsExpanded(true);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQuestionClick = (question) => {
    onQuestionClick(question);
    // Optionally collapse after click
    // setIsExpanded(false);
  };

  const handleClose = () => {
    setIsExpanded(false);
    setQuestions([]);
  };

  if (!hasActiveSources) {
    return null;
  }

  return (
    <div className="px-6 pb-2">
      <div className="max-w-3xl mx-auto">
        {!isExpanded ? (
          /* Collapsed state - just the button */
          <Button
            variant="outline"
            size="sm"
            onClick={generateQuestions}
            disabled={loading}
            className="gap-2 text-amber-500 border-amber-500/30 hover:bg-amber-500/10"
            data-testid="get-question-ideas-btn"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Генерирую идеи...
              </>
            ) : (
              <>
                <Lightbulb className="h-4 w-4" />
                Получить идеи вопросов
              </>
            )}
          </Button>
        ) : (
          /* Expanded state - show questions */
          <div className="p-4 bg-amber-500/5 border border-amber-500/20 rounded-lg animate-in slide-in-from-top duration-200">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-medium text-amber-500">
                  Идеи вопросов
                </span>
                {sourceNames.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    ({sourceNames.length} источников)
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={generateQuestions}
                  disabled={loading}
                  title="Обновить"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={handleClose}
                  title="Закрыть"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Questions as chips */}
            <div className="flex flex-wrap gap-2">
              {questions.map((question, idx) => (
                <button
                  key={idx}
                  onClick={() => handleQuestionClick(question)}
                  className="px-3 py-2 text-sm bg-background hover:bg-amber-500/10 
                           border border-border hover:border-amber-500/30 
                           rounded-full transition-colors text-left
                           max-w-full truncate"
                  data-testid={`smart-question-${idx}`}
                  title={question}
                >
                  {question}
                </button>
              ))}
            </div>

            {/* Source names */}
            {sourceNames.length > 0 && (
              <div className="mt-3 pt-3 border-t border-amber-500/10">
                <p className="text-xs text-muted-foreground">
                  Источники: {sourceNames.slice(0, 3).join(', ')}
                  {sourceNames.length > 3 && ` и ещё ${sourceNames.length - 3}`}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SmartQuestions;
