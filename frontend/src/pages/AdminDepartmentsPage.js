import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { 
  Building2, Plus, Users, Shield, Trash2, UserPlus, 
  ChevronRight, Settings, FileText, Crown
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminDepartmentsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [departments, setDepartments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newDeptName, setNewDeptName] = useState('');
  const [newDeptDescription, setNewDeptDescription] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [selectedDept, setSelectedDept] = useState(null);
  const [allUsers, setAllUsers] = useState([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);

  useEffect(() => {
    fetchDepartments();
  }, []);

  const fetchDepartments = async () => {
    try {
      const response = await axios.get(`${API}/departments`);
      setDepartments(response.data);
    } catch (error) {
      toast.error('Failed to load departments');
    } finally {
      setIsLoading(false);
    }
  };

  const createDepartment = async () => {
    if (!newDeptName.trim()) {
      toast.error('Name is required');
      return;
    }
    
    setIsCreating(true);
    try {
      const response = await axios.post(`${API}/departments`, {
        name: newDeptName.trim(),
        description: newDeptDescription.trim()
      });
      setDepartments([...departments, response.data]);
      setNewDeptName('');
      setNewDeptDescription('');
      setIsCreateDialogOpen(false);
      toast.success('Department created');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create department');
    } finally {
      setIsCreating(false);
    }
  };

  const deleteDepartment = async (deptId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this department? This cannot be undone.')) return;
    
    try {
      await axios.delete(`${API}/departments/${deptId}`);
      setDepartments(departments.filter(d => d.id !== deptId));
      toast.success('Department deleted');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete');
    }
  };

  const openMembersDialog = async (dept) => {
    setSelectedDept(dept);
    setIsLoadingUsers(true);
    try {
      const [deptRes, usersRes] = await Promise.all([
        axios.get(`${API}/departments/${dept.id}`),
        axios.get(`${API}/users/list`)
      ]);
      setSelectedDept(deptRes.data);
      setAllUsers(usersRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setIsLoadingUsers(false);
    }
  };

  const addMember = async (userId, isManager = false) => {
    try {
      await axios.post(`${API}/departments/${selectedDept.id}/members`, {
        userId,
        isManager
      });
      toast.success('Member added');
      // Refresh department
      const deptRes = await axios.get(`${API}/departments/${selectedDept.id}`);
      setSelectedDept(deptRes.data);
      fetchDepartments();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add member');
    }
  };

  const removeMember = async (userId) => {
    try {
      await axios.delete(`${API}/departments/${selectedDept.id}/members/${userId}`);
      toast.success('Member removed');
      const deptRes = await axios.get(`${API}/departments/${selectedDept.id}`);
      setSelectedDept(deptRes.data);
      fetchDepartments();
    } catch (error) {
      toast.error('Failed to remove member');
    }
  };

  const toggleManager = async (userId, isManager) => {
    try {
      await axios.put(`${API}/departments/${selectedDept.id}/members/${userId}/manager`, {
        isManager
      });
      toast.success(isManager ? 'Promoted to manager' : 'Demoted from manager');
      const deptRes = await axios.get(`${API}/departments/${selectedDept.id}`);
      setSelectedDept(deptRes.data);
      fetchDepartments();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update');
    }
  };

  if (!user?.isAdmin) {
    navigate('/dashboard');
    return null;
  }

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="admin-departments-page">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <Building2 className="h-8 w-8 text-indigo-400" />
              Отделы
            </h1>
            <p className="text-muted-foreground mt-2">
              Управление отделами и иерархией знаний
            </p>
          </div>
          
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-department-btn">
                <Plus className="mr-2 h-4 w-4" />
                Создать отдел
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Новый отдел</DialogTitle>
                <DialogDescription>
                  Создайте отдел для организации базы знаний
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Название</Label>
                  <Input
                    value={newDeptName}
                    onChange={(e) => setNewDeptName(e.target.value)}
                    placeholder="Engineering"
                    data-testid="dept-name-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Описание</Label>
                  <Input
                    value={newDeptDescription}
                    onChange={(e) => setNewDeptDescription(e.target.value)}
                    placeholder="Инженерный отдел"
                    data-testid="dept-description-input"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                  Отмена
                </Button>
                <Button onClick={createDepartment} disabled={isCreating}>
                  {isCreating ? <div className="spinner mr-2" /> : null}
                  Создать
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {/* Departments Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="spinner" />
          </div>
        ) : departments.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">Нет отделов</h3>
              <p className="text-muted-foreground text-center mb-4">
                Создайте первый отдел для организации базы знаний
              </p>
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Создать отдел
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {departments.map((dept) => (
              <Card 
                key={dept.id} 
                className="card-hover cursor-pointer group"
                onClick={() => openMembersDialog(dept)}
                data-testid={`dept-card-${dept.id}`}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-indigo-500/20 p-2">
                        <Building2 className="h-5 w-5 text-indigo-400" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{dept.name}</CardTitle>
                        {dept.description && (
                          <CardDescription className="mt-1">
                            {dept.description}
                          </CardDescription>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="opacity-0 group-hover:opacity-100 h-8 w-8"
                      onClick={(e) => deleteDepartment(dept.id, e)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      <span>{dept.memberCount || 0} участников</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Crown className="h-4 w-4 text-amber-500" />
                      <span>{dept.managerCount || 0} менеджеров</span>
                    </div>
                  </div>
                  {dept.sourceCount > 0 && (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground mt-2">
                      <FileText className="h-4 w-4" />
                      <span>{dept.sourceCount} источников</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Members Dialog */}
        <Dialog open={!!selectedDept} onOpenChange={(open) => !open && setSelectedDept(null)}>
          <DialogContent className="sm:max-w-xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                {selectedDept?.name}
              </DialogTitle>
              <DialogDescription>
                Управление участниками отдела
              </DialogDescription>
            </DialogHeader>
            
            {isLoadingUsers ? (
              <div className="flex justify-center py-8">
                <div className="spinner" />
              </div>
            ) : (
              <div className="space-y-4">
                {/* Current Members */}
                <div>
                  <Label className="text-sm font-medium">
                    Участники ({selectedDept?.members?.length || 0})
                  </Label>
                  <div className="mt-2 space-y-2 max-h-[200px] overflow-y-auto">
                    {selectedDept?.members?.length === 0 ? (
                      <p className="text-sm text-muted-foreground py-2">Нет участников</p>
                    ) : (
                      selectedDept?.members?.map((member) => (
                        <div 
                          key={member.userId} 
                          className="flex items-center justify-between py-2 px-3 bg-secondary rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium">
                              {member.email?.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className="text-sm font-medium">{member.email}</p>
                              {member.isManager && (
                                <div className="flex items-center gap-1 text-xs text-amber-500">
                                  <Crown className="h-3 w-3" />
                                  Manager
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs"
                              onClick={() => toggleManager(member.userId, !member.isManager)}
                            >
                              {member.isManager ? 'Demote' : 'Promote'}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive"
                              onClick={() => removeMember(member.userId)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Add Members */}
                <div>
                  <Label className="text-sm font-medium">Добавить участника</Label>
                  <div className="mt-2 space-y-1 max-h-[150px] overflow-y-auto">
                    {allUsers
                      .filter(u => !selectedDept?.members?.find(m => m.userId === u.id))
                      .map((u) => (
                        <div 
                          key={u.id} 
                          className="flex items-center justify-between py-2 px-3 bg-secondary/50 rounded-lg hover:bg-secondary cursor-pointer"
                          onClick={() => addMember(u.id, false)}
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-xs font-medium">
                              {u.email?.charAt(0).toUpperCase()}
                            </div>
                            <span className="text-sm">{u.email}</span>
                          </div>
                          <UserPlus className="h-4 w-4 text-muted-foreground" />
                        </div>
                      ))}
                    {allUsers.filter(u => !selectedDept?.members?.find(m => m.userId === u.id)).length === 0 && (
                      <p className="text-sm text-muted-foreground text-center py-2">
                        Все пользователи уже добавлены
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default AdminDepartmentsPage;
