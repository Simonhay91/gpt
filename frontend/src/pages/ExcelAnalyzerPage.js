import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { 
  FileSpreadsheet, Upload, Send, Loader2, Trash2, 
  Table, MessageSquare, Sparkles, Download, X, FileText
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ExcelAnalyzerPage = () => {
  const { t, language } = useLanguage();
  const [session, setSession] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [question, setQuestion] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [messages, setMessages] = useState([]);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const validTypes = [
      'text/csv',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel'
    ];
    
    if (!validTypes.includes(file.type)) {
      toast.error(language === 'ru' ? 'Только Excel и CSV файлы' : 'Only Excel and CSV files allowed');
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API}/analyzer/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setSession(response.data);
      setMessages([]);
      toast.success(language === 'ru' ? 'Файл загружен!' : 'File uploaded!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const askQuestion = async () => {
    if (!question.trim() || !session) return;

    const userQuestion = question.trim();
    setQuestion('');
    setMessages(prev => [...prev, { role: 'user', content: userQuestion }]);
    setIsAsking(true);

    try {
      const response = await axios.post(`${API}/analyzer/ask`, {
        session_id: session.session_id,
        question: userQuestion
      });
      
      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Analysis failed');
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: language === 'ru' ? 'Ошибка анализа. Попробуйте ещё раз.' : 'Analysis failed. Please try again.' 
      }]);
    } finally {
      setIsAsking(false);
    }
  };

  const closeSession = async () => {
    if (!session) return;
    
    try {
      await axios.delete(`${API}/analyzer/session/${session.session_id}`);
    } catch (e) {}
    
    setSession(null);
    setMessages([]);
  };

  const exportToExcel = async () => {
    if (!session) return;
    
    try {
      const response = await axios.get(
        `${API}/analyzer/session/${session.session_id}/export/excel`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `analysis_${session.file_name.split('.')[0]}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success(language === 'ru' ? 'Excel файл скачан!' : 'Excel file downloaded!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Export failed');
    }
  };

  const exportToPdf = async () => {
    if (!session) return;
    
    try {
      const response = await axios.get(
        `${API}/analyzer/session/${session.session_id}/export/pdf`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `analysis_${session.file_name.split('.')[0]}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success(language === 'ru' ? 'PDF файл скачан!' : 'PDF file downloaded!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Export failed');
    }
  };

  const quickQuestions = language === 'ru' ? [
    "Покажи общую статистику по данным",
    "Найди дубликаты",
    "Какие есть уникальные значения в первой колонке?",
    "Посчитай сумму по числовым колонкам",
    "Найди пустые значения"
  ] : [
    "Show summary statistics",
    "Find duplicates",
    "What are unique values in first column?",
    "Calculate sum for numeric columns",
    "Find empty values"
  ];

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 h-[calc(100vh-4rem)] flex flex-col" data-testid="excel-analyzer-page">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/20">
              <FileSpreadsheet className="h-7 w-7 text-green-500" />
            </div>
            Excel/CSV Analyzer
            <span className="text-sm font-normal text-emerald-500 bg-emerald-500/10 px-2 py-1 rounded-full">
              Gemini AI
            </span>
          </h1>
          <p className="text-muted-foreground mt-2">
            {language === 'ru' 
              ? 'Загрузите Excel или CSV файл и задавайте вопросы по данным'
              : 'Upload Excel or CSV file and ask questions about your data'}
          </p>
        </div>

        {!session ? (
          /* Upload State */
          <Card className="flex-1 flex flex-col items-center justify-center border-dashed">
            <CardContent className="text-center py-12">
              <div className="rounded-full bg-green-500/20 p-6 mb-6 inline-block">
                <FileSpreadsheet className="h-12 w-12 text-green-500" />
              </div>
              <h3 className="text-xl font-semibold mb-2">
                {language === 'ru' ? 'Загрузите файл для анализа' : 'Upload a file to analyze'}
              </h3>
              <p className="text-muted-foreground mb-6 max-w-md">
                {language === 'ru' 
                  ? 'Поддерживаются Excel (.xlsx) и CSV файлы до 10MB'
                  : 'Supports Excel (.xlsx) and CSV files up to 10MB'}
              </p>
              
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".csv,.xlsx,.xls"
                onChange={handleFileUpload}
              />
              
              <Button 
                size="lg"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="bg-green-500 hover:bg-green-600"
              >
                {isUploading ? (
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-5 w-5" />
                )}
                {language === 'ru' ? 'Выбрать файл' : 'Choose File'}
              </Button>
            </CardContent>
          </Card>
        ) : (
          /* Analysis State */
          <div className="flex-1 flex flex-col min-h-0">
            {/* File Info Bar */}
            <Card className="mb-4 border-green-500/30 bg-green-500/5">
              <CardContent className="py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <FileSpreadsheet className="h-5 w-5 text-green-500" />
                    <div>
                      <p className="font-medium">{session.file_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {session.total_rows} {language === 'ru' ? 'строк' : 'rows'} • {session.columns?.length} {language === 'ru' ? 'колонок' : 'columns'}
                      </p>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={closeSession}>
                    <X className="h-4 w-4 mr-1" />
                    {language === 'ru' ? 'Закрыть' : 'Close'}
                  </Button>
                </div>
                
                {/* Column names */}
                <div className="mt-2 flex flex-wrap gap-1">
                  {session.columns?.slice(0, 8).map((col, i) => (
                    <span key={i} className="text-xs bg-secondary px-2 py-0.5 rounded">
                      {col}
                    </span>
                  ))}
                  {session.columns?.length > 8 && (
                    <span className="text-xs text-muted-foreground">
                      +{session.columns.length - 8} more
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Preview Table */}
            {session.preview && messages.length === 0 && (
              <Card className="mb-4">
                <CardHeader className="py-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Table className="h-4 w-4" />
                    Preview
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-secondary">
                      <tr>
                        {session.preview[0]?.map((cell, i) => (
                          <th key={i} className="px-3 py-2 text-left font-medium whitespace-nowrap">
                            {cell}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {session.preview.slice(1, 6).map((row, rowIdx) => (
                        <tr key={rowIdx} className="border-t border-border">
                          {row.map((cell, cellIdx) => (
                            <td key={cellIdx} className="px-3 py-2 whitespace-nowrap max-w-[200px] truncate">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}

            {/* Quick Questions */}
            {messages.length === 0 && (
              <div className="mb-4">
                <p className="text-sm text-muted-foreground mb-2">
                  {language === 'ru' ? 'Быстрые вопросы:' : 'Quick questions:'}
                </p>
                <div className="flex flex-wrap gap-2">
                  {quickQuestions.map((q, i) => (
                    <Button 
                      key={i} 
                      variant="outline" 
                      size="sm"
                      onClick={() => setQuestion(q)}
                      className="text-xs"
                    >
                      {q}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
              {messages.map((msg, i) => (
                <div 
                  key={i} 
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    msg.role === 'user' 
                      ? 'bg-green-500 text-white' 
                      : 'bg-secondary'
                  }`}>
                    {msg.role === 'assistant' && (
                      <div className="flex items-center gap-2 mb-2 text-green-500">
                        <Sparkles className="h-4 w-4" />
                        <span className="text-xs font-medium">Gemini AI</span>
                      </div>
                    )}
                    <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                  </div>
                </div>
              ))}
              
              {isAsking && (
                <div className="flex justify-start">
                  <div className="bg-secondary rounded-lg px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-green-500" />
                      <span className="text-sm text-muted-foreground">
                        {language === 'ru' ? 'Анализирую...' : 'Analyzing...'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="flex gap-2">
              <Input
                placeholder={language === 'ru' ? 'Задайте вопрос о данных...' : 'Ask a question about your data...'}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && askQuestion()}
                disabled={isAsking}
                className="flex-1"
              />
              <Button 
                onClick={askQuestion}
                disabled={isAsking || !question.trim()}
                className="bg-green-500 hover:bg-green-600"
              >
                {isAsking ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default ExcelAnalyzerPage;
