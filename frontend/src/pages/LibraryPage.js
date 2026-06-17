import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import {
  Library, Upload, Trash2, Building2, Clock, Eye, Download,
  FileText, Loader2, Share2, Globe2, Search, Pencil
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatBytes = (bytes) => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDate = (dateString) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('ru-RU', {
    day: 'numeric', month: 'short', year: 'numeric'
  });
};

const LibraryPage = () => {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [departments, setDepartments] = useState([]);   // departments the user can share to
  const [search, setSearch] = useState('');

  // Upload dialog
  const [uploadOpen, setUploadOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDesc, setUploadDesc] = useState('');
  const [uploadTags, setUploadTags] = useState('');
  const [uploadDeptIds, setUploadDeptIds] = useState([]);
  const [uploadGlobal, setUploadGlobal] = useState(false);

  // Share dialog
  const [shareItem, setShareItem] = useState(null);
  const [shareDeptIds, setShareDeptIds] = useState([]);
  const [shareGlobal, setShareGlobal] = useState(false);
  const [isSharing, setIsSharing] = useState(false);

  // Edit dialog
  const [editItem, setEditItem] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editTags, setEditTags] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  // Preview dialog
  const [previewItem, setPreviewItem] = useState(null);
  const [previewContent, setPreviewContent] = useState('');
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  const canManage = useMemo(
    () => user?.isAdmin || departments.length > 0,
    [user, departments]
  );

  useEffect(() => {
    fetchItems();
    fetchDepartments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchItems = async () => {
    try {
      const res = await axios.get(`${API}/library`, { params: { manage: false } });
      setItems(res.data || []);
    } catch {
      toast.error('Не удалось загрузить библиотеку');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDepartments = async () => {
    try {
      if (user?.isAdmin) {
        const res = await axios.get(`${API}/departments`);
        setDepartments(res.data || []);
      } else {
        const res = await axios.get(`${API}/users/me/departments`);
        setDepartments((res.data || []).filter(d => d.isManager));
      }
    } catch {
      setDepartments([]);
    }
  };

  const toggleId = (list, setList, id) => {
    setList(list.includes(id) ? list.filter(x => x !== id) : [...list, id]);
  };

  // ── Upload ──
  const openUpload = () => {
    setUploadFile(null);
    setUploadTitle('');
    setUploadDesc('');
    setUploadTags('');
    setUploadDeptIds([]);
    setUploadGlobal(false);
    setUploadOpen(true);
  };

  const submitUpload = async () => {
    if (!uploadFile) { toast.error('Выберите файл'); return; }
    if (!uploadGlobal && uploadDeptIds.length === 0) {
      toast.error('Выберите хотя бы один департамент');
      return;
    }
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('title', uploadTitle || uploadFile.name);
    formData.append('description', uploadDesc);
    formData.append('tags', JSON.stringify(uploadTags.split(',').map(t => t.trim()).filter(Boolean)));
    formData.append('departmentIds', JSON.stringify(uploadDeptIds));
    formData.append('isGlobal', uploadGlobal ? 'true' : 'false');
    try {
      await axios.post(`${API}/library/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Книга добавлена в библиотеку');
      setUploadOpen(false);
      await fetchItems();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Не удалось загрузить');
    } finally {
      setIsUploading(false);
    }
  };

  // ── Share ──
  const openShare = (item) => {
    setShareItem(item);
    setShareDeptIds(item.sharedDepartments || []);
    setShareGlobal(!!item.isGlobalLibrary);
  };

  const submitShare = async () => {
    setIsSharing(true);
    try {
      await axios.post(`${API}/library/${shareItem.id}/share`, {
        departmentIds: shareDeptIds,
        isGlobal: shareGlobal,
      });
      toast.success('Доступ обновлён');
      setShareItem(null);
      await fetchItems();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Не удалось обновить доступ');
    } finally {
      setIsSharing(false);
    }
  };

  // ── Edit ──
  const openEdit = (item) => {
    setEditItem(item);
    setEditTitle(item.title || '');
    setEditDesc(item.description || '');
    setEditTags((item.tags || []).join(', '));
  };

  const submitEdit = async () => {
    setIsSavingEdit(true);
    try {
      await axios.put(`${API}/library/${editItem.id}`, {
        title: editTitle,
        description: editDesc,
        tags: editTags.split(',').map(t => t.trim()).filter(Boolean),
      });
      toast.success('Сохранено');
      setEditItem(null);
      await fetchItems();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Не удалось сохранить');
    } finally {
      setIsSavingEdit(false);
    }
  };

  // ── Delete ──
  const deleteItem = async (item) => {
    if (!window.confirm(`Удалить «${item.title || item.originalName}»? Это действие необратимо.`)) return;
    try {
      await axios.delete(`${API}/library/${item.id}`);
      toast.success('Удалено');
      setItems(items.filter(i => i.id !== item.id));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Не удалось удалить');
    }
  };

  // ── Download ──
  const downloadItem = async (item) => {
    try {
      const res = await axios.get(`${API}/library/${item.id}/download`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = item.originalName || item.title || 'download';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error('Не удалось скачать');
    }
  };

  // ── Preview ──
  const openPreview = async (item) => {
    setPreviewItem(item);
    setIsLoadingPreview(true);
    setPreviewContent('');
    try {
      const res = await axios.get(`${API}/library/${item.id}/preview`);
      setPreviewContent(res.data.content || 'Нет содержимого');
    } catch {
      setPreviewContent('Не удалось загрузить просмотр');
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const canManageItem = (item) =>
    user?.isAdmin || item.ownerId === user?.id ||
    (item.sharedDepartments || []).some(did => departments.some(d => d.id === did));

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(it =>
      (it.title || '').toLowerCase().includes(q) ||
      (it.description || '').toLowerCase().includes(q) ||
      (it.originalName || '').toLowerCase().includes(q) ||
      (it.tags || []).some(t => t.toLowerCase().includes(q))
    );
  }, [items, search]);

  const DeptCheckboxList = ({ selected, onToggle }) => (
    <div className="space-y-1.5 max-h-[180px] overflow-y-auto rounded-md border border-border p-2">
      {departments.length === 0 ? (
        <p className="text-sm text-muted-foreground p-2">Нет доступных департаментов</p>
      ) : departments.map(d => (
        <label key={d.id} className="flex items-center gap-2 p-1.5 rounded hover:bg-secondary/40 cursor-pointer">
          <Checkbox
            checked={selected.includes(d.id)}
            onCheckedChange={() => onToggle(d.id)}
            className="data-[state=checked]:bg-indigo-500"
          />
          <Building2 className="h-4 w-4 text-amber-400" />
          <span className="text-sm">{d.name}</span>
        </label>
      ))}
    </div>
  );

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="library-page">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <Library className="h-8 w-8 text-indigo-400" />
              Библиотека
            </h1>
            <p className="text-muted-foreground mt-2">
              Общие документы, доступные в чате. Одну книгу можно открыть сразу нескольким департаментам.
            </p>
          </div>
          {canManage && (
            <Button onClick={openUpload} data-testid="library-upload-btn" className="gap-2">
              <Upload className="h-4 w-4" />
              Загрузить
            </Button>
          )}
        </div>

        {/* Search */}
        <div className="relative mb-6 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Поиск по библиотеке..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64"><div className="spinner" /></div>
        ) : filteredItems.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Library className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">Библиотека пуста</h3>
              <p className="text-muted-foreground text-center">
                {canManage ? 'Загрузите первую книгу, чтобы поделиться ею с департаментами.' : 'Пока нет доступных вам документов.'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredItems.map(item => (
              <Card key={item.id} className="card-hover group" data-testid={`library-item-${item.id}`}>
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 min-w-0">
                      <div className="rounded-lg bg-indigo-500/20 p-2 flex-shrink-0">
                        <FileText className="h-5 w-5 text-indigo-400" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold truncate">{item.title || item.originalName}</h3>
                        {item.description && (
                          <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">{item.description}</p>
                        )}
                        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1.5 flex-wrap">
                          <span>{formatBytes(item.sizeBytes)}</span>
                          <span>•</span>
                          <span>{item.chunkCount} chunks</span>
                          <span>•</span>
                          <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatDate(item.createdAt)}</span>
                        </div>
                        {/* Shared department badges */}
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {item.isGlobalLibrary && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                              <Globe2 className="h-3 w-3" /> Все департаменты
                            </span>
                          )}
                          {(item.sharedDepartmentNames || []).map(d => (
                            <span key={d.id} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border bg-amber-500/10 text-amber-400 border-amber-500/20">
                              <Building2 className="h-3 w-3" /> {d.name}
                            </span>
                          ))}
                          {(item.tags || []).map((tag, i) => (
                            <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs border bg-secondary text-muted-foreground border-border">
                              #{tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Button variant="outline" size="sm" onClick={() => openPreview(item)} title="Просмотр">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => downloadItem(item)} title="Скачать">
                        <Download className="h-4 w-4" />
                      </Button>
                      {canManageItem(item) && (
                        <>
                          <Button variant="outline" size="sm" onClick={() => openShare(item)} title="Поделиться с департаментами">
                            <Share2 className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => openEdit(item)} title="Редактировать">
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="text-destructive" onClick={() => deleteItem(item)} title="Удалить">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Upload Dialog */}
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Upload className="h-5 w-5" /> Загрузить в библиотеку</DialogTitle>
              <DialogDescription>Файл будет доступен в чате выбранным департаментам.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>Файл</Label>
                <Input
                  type="file"
                  accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.md,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const f = e.target.files?.[0] || null;
                    setUploadFile(f);
                    if (f && !uploadTitle) setUploadTitle(f.name);
                  }}
                />
              </div>
              <div className="space-y-2">
                <Label>Название</Label>
                <Input value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} placeholder="Название книги" />
              </div>
              <div className="space-y-2">
                <Label>Описание</Label>
                <Input value={uploadDesc} onChange={(e) => setUploadDesc(e.target.value)} placeholder="Краткое описание (необязательно)" />
              </div>
              <div className="space-y-2">
                <Label>Теги (через запятую)</Label>
                <Input value={uploadTags} onChange={(e) => setUploadTags(e.target.value)} placeholder="договор, hr, инструкция" />
              </div>
              {user?.isAdmin && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox checked={uploadGlobal} onCheckedChange={() => setUploadGlobal(v => !v)} className="data-[state=checked]:bg-emerald-500" />
                  <Globe2 className="h-4 w-4 text-emerald-400" />
                  <span className="text-sm">Доступно всем департаментам</span>
                </label>
              )}
              {!uploadGlobal && (
                <div className="space-y-2">
                  <Label>Департаменты</Label>
                  <DeptCheckboxList selected={uploadDeptIds} onToggle={(id) => toggleId(uploadDeptIds, setUploadDeptIds, id)} />
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setUploadOpen(false)} disabled={isUploading}>Отмена</Button>
              <Button onClick={submitUpload} disabled={isUploading} className="gap-2">
                {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                Загрузить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Share Dialog */}
        <Dialog open={!!shareItem} onOpenChange={(open) => !open && setShareItem(null)}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Share2 className="h-5 w-5" /> Поделиться с департаментами</DialogTitle>
              <DialogDescription>{shareItem?.title || shareItem?.originalName}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              {user?.isAdmin && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox checked={shareGlobal} onCheckedChange={() => setShareGlobal(v => !v)} className="data-[state=checked]:bg-emerald-500" />
                  <Globe2 className="h-4 w-4 text-emerald-400" />
                  <span className="text-sm">Доступно всем департаментам</span>
                </label>
              )}
              {!shareGlobal && (
                <div className="space-y-2">
                  <Label>Департаменты</Label>
                  <DeptCheckboxList selected={shareDeptIds} onToggle={(id) => toggleId(shareDeptIds, setShareDeptIds, id)} />
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShareItem(null)} disabled={isSharing}>Отмена</Button>
              <Button onClick={submitShare} disabled={isSharing} className="gap-2">
                {isSharing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Share2 className="h-4 w-4" />}
                Сохранить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit Dialog */}
        <Dialog open={!!editItem} onOpenChange={(open) => !open && setEditItem(null)}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Pencil className="h-5 w-5" /> Редактировать</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>Название</Label>
                <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Описание</Label>
                <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Теги (через запятую)</Label>
                <Input value={editTags} onChange={(e) => setEditTags(e.target.value)} />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditItem(null)} disabled={isSavingEdit}>Отмена</Button>
              <Button onClick={submitEdit} disabled={isSavingEdit} className="gap-2">
                {isSavingEdit ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Сохранить
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Preview Dialog */}
        <Dialog open={!!previewItem} onOpenChange={(open) => !open && setPreviewItem(null)}>
          <DialogContent className="sm:max-w-2xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Eye className="h-5 w-5 text-indigo-400" /> {previewItem?.title || previewItem?.originalName}</DialogTitle>
            </DialogHeader>
            {isLoadingPreview ? (
              <div className="flex justify-center py-8"><div className="spinner" /></div>
            ) : (
              <div className="bg-muted/50 rounded-lg p-4 max-h-[55vh] overflow-y-auto">
                <pre className="whitespace-pre-wrap text-sm font-mono">{previewContent}</pre>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setPreviewItem(null)}>Закрыть</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default LibraryPage;
