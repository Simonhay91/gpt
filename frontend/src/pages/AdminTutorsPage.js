import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Plus, GraduationCap, Trash2, Copy, Eye, EyeOff, ArrowLeft, Coins, MessageSquare, KeyRound } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminTutorsPage = () => {
  const [tutors, setTutors] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [createdUser, setCreatedUser] = useState(null);
  const [resetPasswordUser, setResetPasswordUser] = useState(null);
  const [isResetting, setIsResetting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTutors();
  }, []);

  const fetchTutors = async () => {
    try {
      const response = await axios.get(`${API}/admin/tutors`);
      setTutors(response.data || []);
    } catch (error) {
      toast.error('Не удалось загрузить тьюторов');
    } finally {
      setIsLoading(false);
    }
  };

  const generatePassword = () => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
    let password = '';
    for (let i = 0; i < 12; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setNewUserPassword(password);
  };

  const createTutor = async () => {
    if (!newUserEmail.trim()) {
      toast.error('Email обязателен');
      return;
    }
    if (!newUserPassword.trim()) {
      toast.error('Пароль обязателен');
      return;
    }

    setIsCreating(true);
    try {
      // Step 1: create the user
      const createRes = await axios.post(`${API}/admin/users`, {
        email: newUserEmail,
        password: newUserPassword,
      });
      const newUserId = createRes.data.id;

      // Step 2: assign Tutor position
      await axios.put(`${API}/admin/users/${newUserId}/position`, { position: 'Tutor' });

      setCreatedUser({ email: newUserEmail, password: newUserPassword });
      await fetchTutors();
      toast.success('Тьютор создан');
    } catch (error) {
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map(e => e.msg || String(e)).join(', ')
        : (detail || 'Не удалось создать тьютора');
      toast.error(message);
    } finally {
      setIsCreating(false);
    }
  };

  const deleteTutor = async (userId, userEmail) => {
    if (!window.confirm(`Удалить ${userEmail}? Все данные будут удалены.`)) return;
    try {
      await axios.delete(`${API}/admin/users/${userId}`);
      setTutors(tutors.filter(u => u.id !== userId));
      toast.success('Тьютор удалён');
    } catch (error) {
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map(e => e.msg || String(e)).join(', ')
        : (detail || 'Не удалось удалить');
      toast.error(message);
    }
  };

  const copyCredentials = () => {
    if (createdUser) {
      navigator.clipboard.writeText(`Email: ${createdUser.email}\nPassword: ${createdUser.password}`);
      toast.success('Скопировано');
    }
  };

  const resetDialog = () => {
    setNewUserEmail('');
    setNewUserPassword('');
    setCreatedUser(null);
    setShowPassword(false);
  };

  const handleResetPassword = async (userId) => {
    setIsResetting(true);
    try {
      const res = await axios.post(`${API}/admin/users/${userId}/reset-password`);
      setResetPasswordUser(res.data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map(x => x.msg || String(x)).join(', ')
        : (detail || 'Не удалось сбросить пароль');
      toast.error(message);
    } finally {
      setIsResetting(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const formatNumber = (num) => {
    const n = Number(num);
    if (!n || isNaN(n)) return '0';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toLocaleString('ru-RU');
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            className="mb-4 -ml-2"
            onClick={() => navigate('/dashboard')}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            На главную
          </Button>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-indigo-500/20 p-3">
                <GraduationCap className="h-6 w-6 text-indigo-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Тьюторы</h1>
                <p className="text-muted-foreground mt-1">
                  {tutors.length} {tutors.length === 1 ? 'тьютор' : tutors.length >= 2 && tutors.length <= 4 ? 'тьютора' : 'тьюторов'}
                </p>
              </div>
            </div>

            <Dialog open={isDialogOpen} onOpenChange={(open) => {
              setIsDialogOpen(open);
              if (!open) resetDialog();
            }}>
              <DialogTrigger asChild>
                <Button className="btn-hover">
                  <Plus className="mr-2 h-4 w-4" />
                  Создать тьютора
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                {!createdUser ? (
                  <>
                    <DialogHeader>
                      <DialogTitle>Создать тьютора</DialogTitle>
                      <DialogDescription>
                        Новый пользователь будет создан с должностью «Тьютор».
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="tutor-email">Email</Label>
                        <Input
                          id="tutor-email"
                          type="email"
                          placeholder="tutor@example.com"
                          value={newUserEmail}
                          onChange={(e) => setNewUserEmail(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="tutor-password">Пароль</Label>
                        <div className="flex gap-2">
                          <div className="relative flex-1">
                            <Input
                              id="tutor-password"
                              type={showPassword ? 'text' : 'password'}
                              placeholder="Введите пароль"
                              value={newUserPassword}
                              onChange={(e) => setNewUserPassword(e.target.value)}
                            />
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                              onClick={() => setShowPassword(!showPassword)}
                            >
                              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                          </div>
                          <Button type="button" variant="outline" onClick={generatePassword}>
                            Сгенерировать
                          </Button>
                        </div>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                        Отмена
                      </Button>
                      <Button onClick={createTutor} disabled={isCreating}>
                        {isCreating ? <div className="spinner mr-2" /> : null}
                        Создать
                      </Button>
                    </DialogFooter>
                  </>
                ) : (
                  <>
                    <DialogHeader>
                      <DialogTitle>Тьютор создан</DialogTitle>
                      <DialogDescription>
                        Передайте эти данные новому тьютору.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-4">
                      <Card className="bg-emerald-500/10 border-emerald-500/20">
                        <CardContent className="pt-4 space-y-3">
                          <div>
                            <Label className="text-xs text-muted-foreground">Email</Label>
                            <p className="font-mono text-sm">{createdUser.email}</p>
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">Пароль</Label>
                            <p className="font-mono text-sm">{createdUser.password}</p>
                          </div>
                        </CardContent>
                      </Card>
                      <Button variant="outline" className="w-full" onClick={copyCredentials}>
                        <Copy className="mr-2 h-4 w-4" />
                        Скопировать данные
                      </Button>
                    </div>
                    <DialogFooter>
                      <Button onClick={() => { setIsDialogOpen(false); resetDialog(); }}>
                        Готово
                      </Button>
                    </DialogFooter>
                  </>
                )}
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="spinner" />
          </div>
        ) : tutors.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="rounded-full bg-secondary p-4 mb-4">
                <GraduationCap className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Тьюторов пока нет</h3>
              <p className="text-muted-foreground text-center">
                Создайте первого тьютора с помощью кнопки выше
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {tutors.map((tutor, index) => (
              <Card
                key={tutor.id}
                className="card-hover group"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="rounded-lg bg-indigo-500/20 p-2">
                        <GraduationCap className="h-5 w-5 text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="font-semibold">{tutor.email}</h3>
                        <p className="text-sm text-muted-foreground">
                          Создан {formatDate(tutor.createdAt)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1 text-muted-foreground" title="Токенов использовано">
                          <Coins className="h-4 w-4 text-amber-400" />
                          <span>{formatNumber(tutor.totalTokensUsed)}</span>
                        </div>
                        <div className="flex items-center gap-1 text-muted-foreground" title="Сообщений отправлено">
                          <MessageSquare className="h-4 w-4 text-emerald-400" />
                          <span>{formatNumber(tutor.totalMessagesCount)}</span>
                        </div>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1"
                        onClick={() => handleResetPassword(tutor.id)}
                        disabled={isResetting}
                        title="Сбросить пароль"
                      >
                        <KeyRound className="h-3.5 w-3.5" />
                        Сброс
                      </Button>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/admin/users/${tutor.id}`)}
                      >
                        Подробнее
                      </Button>

                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => deleteTutor(tutor.id, tutor.email)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Reset Password Dialog */}
      {resetPasswordUser && (
        <Dialog open={!!resetPasswordUser} onOpenChange={() => setResetPasswordUser(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Новый пароль сгенерирован</DialogTitle>
              <DialogDescription>
                Передайте этот пароль <strong>{resetPasswordUser.email}</strong>. При следующем входе будет предложено его изменить.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-2">
                <span className="font-mono text-sm flex-1">{resetPasswordUser.new_password}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={() => { navigator.clipboard.writeText(resetPasswordUser.new_password); toast.success('Скопировано!'); }}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => setResetPasswordUser(null)}>Готово</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </DashboardLayout>
  );
};

export default AdminTutorsPage;
