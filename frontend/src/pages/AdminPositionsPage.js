import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Plus, Briefcase, Trash2, ArrowLeft, Pencil } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminPositionsPage = () => {
  const [positions, setPositions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  // Create dialog
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newValue, setNewValue] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  // Edit dialog
  const [editPosition, setEditPosition] = useState(null); // { id, value, label }
  const [editLabel, setEditLabel] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchPositions();
  }, []);

  const fetchPositions = async () => {
    try {
      const res = await axios.get(`${API}/admin/positions`);
      setPositions(res.data || []);
    } catch {
      toast.error('Не удалось загрузить должности');
    } finally {
      setIsLoading(false);
    }
  };

  const createPosition = async () => {
    const value = newValue.trim();
    const label = newLabel.trim();
    if (!value || !label) {
      toast.error('Заполните оба поля');
      return;
    }
    setIsCreating(true);
    try {
      const res = await axios.post(`${API}/admin/positions`, { value, label });
      setPositions(prev => [...prev, res.data]);
      setIsCreateOpen(false);
      setNewValue('');
      setNewLabel('');
      toast.success('Должность создана');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Ошибка создания');
    } finally {
      setIsCreating(false);
    }
  };

  const saveEdit = async () => {
    const label = editLabel.trim();
    if (!label) { toast.error('Название обязательно'); return; }
    setIsSaving(true);
    try {
      const res = await axios.put(`${API}/admin/positions/${editPosition.id}`, { label });
      setPositions(prev => prev.map(p => p.id === editPosition.id ? res.data : p));
      setEditPosition(null);
      toast.success('Сохранено');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setIsSaving(false);
    }
  };

  const deletePosition = async (pos) => {
    if (!window.confirm(`Удалить должность «${pos.label}»?`)) return;
    try {
      await axios.delete(`${API}/admin/positions/${pos.id}`);
      setPositions(prev => prev.filter(p => p.id !== pos.id));
      toast.success('Должность удалена');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Ошибка удаления');
    }
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        {/* Header */}
        <div className="mb-8">
          <Button variant="ghost" className="mb-4 -ml-2" onClick={() => navigate('/dashboard')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            На главную
          </Button>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-indigo-500/20 p-3">
                <Briefcase className="h-6 w-6 text-indigo-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Должности</h1>
                <p className="text-muted-foreground mt-1">
                  {positions.length} {positions.length === 1 ? 'должность' : positions.length >= 2 && positions.length <= 4 ? 'должности' : 'должностей'}
                </p>
              </div>
            </div>

            {/* Create dialog */}
            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
              <DialogTrigger asChild>
                <Button className="btn-hover">
                  <Plus className="mr-2 h-4 w-4" />
                  Добавить должность
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Новая должность</DialogTitle>
                  <DialogDescription>
                    Введите технический ключ и название для отображения.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="pos-value">Ключ (value)</Label>
                    <Input
                      id="pos-value"
                      placeholder="SalesManager"
                      value={newValue}
                      onChange={e => setNewValue(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">Латинские буквы без пробелов, напр. «SalesManager»</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="pos-label">Название</Label>
                    <Input
                      id="pos-label"
                      placeholder="Менеджер по продажам"
                      value={newLabel}
                      onChange={e => setNewLabel(e.target.value)}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Отмена</Button>
                  <Button onClick={createPosition} disabled={isCreating}>
                    {isCreating ? <div className="spinner mr-2" /> : null}
                    Создать
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="spinner" />
          </div>
        ) : positions.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="rounded-full bg-secondary p-4 mb-4">
                <Briefcase className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Должностей пока нет</h3>
              <p className="text-muted-foreground">Добавьте первую должность кнопкой выше</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-base text-muted-foreground font-normal">
                Эти должности отображаются в библиотеке и в карточке пользователя
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-border">
                {positions.map(pos => (
                  <div key={pos.id} className="flex items-center justify-between px-6 py-4">
                    <div>
                      <p className="font-semibold">{pos.label}</p>
                      <p className="text-xs text-muted-foreground font-mono">{pos.value}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => { setEditPosition(pos); setEditLabel(pos.label); }}
                      >
                        <Pencil className="h-3.5 w-3.5 mr-1" />
                        Изменить
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => deletePosition(pos)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Edit dialog */}
      <Dialog open={!!editPosition} onOpenChange={open => { if (!open) setEditPosition(null); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Изменить должность</DialogTitle>
            <DialogDescription>
              Ключ <span className="font-mono text-foreground">{editPosition?.value}</span> нельзя изменить — только название.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Название</Label>
              <Input
                value={editLabel}
                onChange={e => setEditLabel(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditPosition(null)}>Отмена</Button>
            <Button onClick={saveEdit} disabled={isSaving}>
              {isSaving ? <div className="spinner mr-2" /> : null}
              Сохранить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
};

export default AdminPositionsPage;
