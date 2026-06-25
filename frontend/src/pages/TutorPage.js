import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { toast } from 'sonner';
import {
  GraduationCap, BookOpen, Clock, ArrowRight, Trash2, MessageSquare, RotateCcw
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatDate = (dateString) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('ru-RU', {
    day: 'numeric', month: 'short', year: 'numeric'
  });
};

const TutorPage = () => {
  const { language } = useLanguage();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [position, setPosition] = useState(null);
  const [books, setBooks] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [isStarting, setIsStarting] = useState(false);

  const ru = language === 'ru';

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = async () => {
    try {
      const [booksRes, lessonsRes] = await Promise.all([
        axios.get(`${API}/users/me/tutor-books`),
        axios.get(`${API}/quick-chats`, { params: { mode: 'tutor' } }),
      ]);
      setPosition(booksRes.data.position || null);
      setBooks(booksRes.data.items || []);
      const items = lessonsRes.data.items || lessonsRes.data;
      setLessons(Array.isArray(items) ? items : []);
    } catch (error) {
      toast.error(ru ? 'Не удалось загрузить Tutor' : 'Failed to load Tutor');
    } finally {
      setIsLoading(false);
    }
  };

  const startLesson = async () => {
    setIsStarting(true);
    try {
      const res = await axios.post(`${API}/quick-chats`, { name: ru ? 'Урок' : 'Lesson', mode: 'tutor' });
      navigate(`/chats/${res.data.id}`);
    } catch (error) {
      toast.error(ru ? 'Не удалось начать урок' : 'Failed to start lesson');
      setIsStarting(false);
    }
  };

  const openBookLesson = async (bookId) => {
    try {
      const res = await axios.get(`${API}/library/${bookId}/lesson-chat`);
      navigate(`/chats/${res.data.id}`);
    } catch (error) {
      toast.error(ru ? 'Не удалось открыть книгу' : 'Failed to open book');
    }
  };

  const resetProgress = async (bookId, e) => {
    e.stopPropagation();
    if (!window.confirm(ru ? 'Сбросить прогресс по этой книге?' : 'Reset progress for this book?')) return;
    try {
      await axios.delete(`${API}/users/me/tutor-memory/${bookId}`);
      setBooks(prev => prev.map(b => b.bookId === bookId
        ? { ...b, progressPercent: 0, summary: '', lastSession: null } : b));
      toast.success(ru ? 'Прогресс сброшен' : 'Progress reset');
    } catch {
      toast.error(ru ? 'Ошибка' : 'Error');
    }
  };

  const deleteLesson = async (chatId, e) => {
    e.stopPropagation();
    if (!window.confirm(ru ? 'Удалить этот урок?' : 'Delete this lesson?')) return;
    try {
      await axios.delete(`${API}/chats/${chatId}`);
      setLessons(prev => prev.filter(c => c.id !== chatId));
      toast.success(ru ? 'Урок удалён' : 'Lesson deleted');
    } catch {
      toast.error(ru ? 'Ошибка' : 'Error');
    }
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="tutor-page">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <GraduationCap className="h-8 w-8 text-sky-400" />
              Tutor
            </h1>
            <p className="text-muted-foreground mt-2">
              {ru
                ? 'Ваш персональный наставник. Учитесь по книгам своей должности — прогресс сохраняется между уроками.'
                : 'Your personal tutor. Learn from your position\'s books — progress is saved across lessons.'}
            </p>
          </div>
          <Button onClick={startLesson} disabled={isStarting} className="gap-2" data-testid="tutor-new-lesson-btn">
            {isStarting ? <div className="spinner" /> : <GraduationCap className="h-4 w-4" />}
            {ru ? 'Новый урок' : 'New lesson'}
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64"><div className="spinner" /></div>
        ) : (
          <div className="space-y-8">
            {/* Books with progress */}
            <div>
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-sky-400" />
                {ru ? 'Мои книги' : 'My books'}
              </h2>
              {!position ? (
                <Card className="border-dashed">
                  <CardContent className="py-8 text-center text-muted-foreground">
                    {ru
                      ? 'Должность не назначена. Обратитесь к администратору, чтобы получить книги для обучения.'
                      : 'No position assigned. Ask an admin to assign learning books.'}
                  </CardContent>
                </Card>
              ) : books.length === 0 ? (
                <Card className="border-dashed">
                  <CardContent className="py-8 text-center text-muted-foreground">
                    {ru
                      ? 'Для вашей должности пока нет книг в библиотеке.'
                      : 'No books assigned to your position yet.'}
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {books.map((b) => (
                    <Card
                      key={b.bookId}
                      className="card-hover cursor-pointer group"
                      onClick={() => openBookLesson(b.bookId)}
                    >
                      <CardContent className="py-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3 min-w-0">
                            <div className="rounded-lg bg-sky-500/15 p-2 flex-shrink-0">
                              <BookOpen className="h-5 w-5 text-sky-400" />
                            </div>
                            <div className="min-w-0">
                              <h3 className="font-semibold truncate">{b.bookTitle}</h3>
                              {b.summary ? (
                                <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">{b.summary}</p>
                              ) : (
                                <p className="text-sm text-muted-foreground mt-0.5">
                                  {ru ? 'Ещё не начато' : 'Not started yet'}
                                </p>
                              )}
                            </div>
                          </div>
                          {b.progressPercent > 0 && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 flex-shrink-0"
                              onClick={(e) => resetProgress(b.bookId, e)}
                              title={ru ? 'Сбросить прогресс' : 'Reset progress'}
                            >
                              <RotateCcw className="h-4 w-4 text-muted-foreground" />
                            </Button>
                          )}
                        </div>
                        {/* Progress bar */}
                        <div className="mt-3">
                          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                            <span>{ru ? 'Прогресс' : 'Progress'}</span>
                            <span>{b.progressPercent || 0}%</span>
                          </div>
                          <div className="h-2 rounded-full bg-secondary overflow-hidden">
                            <div
                              className="h-full bg-sky-500 transition-all"
                              style={{ width: `${Math.max(0, Math.min(100, b.progressPercent || 0))}%` }}
                            />
                          </div>
                          {b.lastSession && (
                            <p className="text-xs text-muted-foreground mt-1.5 flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {ru ? 'Последний урок: ' : 'Last lesson: '}{formatDate(b.lastSession)}
                            </p>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>

            {/* Recent lessons */}
            {lessons.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <MessageSquare className="h-5 w-5 text-emerald-400" />
                  {ru ? 'Мои уроки' : 'My lessons'}
                </h2>
                <div className="space-y-3">
                  {lessons.map((chat) => (
                    <Card
                      key={chat.id}
                      className="card-hover cursor-pointer group"
                      onClick={() => navigate(`/chats/${chat.id}`)}
                    >
                      <CardContent className="py-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="rounded-lg bg-emerald-500/15 p-2">
                              <GraduationCap className="h-5 w-5 text-emerald-400" />
                            </div>
                            <div>
                              <h3 className="font-semibold">{chat.name}</h3>
                              <div className="flex items-center gap-1 text-sm text-muted-foreground mt-1">
                                <Clock className="h-3 w-3" />
                                <span>{formatDate(chat.createdAt)}</span>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={(e) => deleteLesson(chat.id, e)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                            <ArrowRight className="h-4 w-4 text-muted-foreground" />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default TutorPage;
