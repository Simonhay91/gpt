import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Plus, FolderOpen, Trash2, Clock, ArrowRight, Building2, Eye } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DashboardPage = () => {
  const { t } = useLanguage();
  const [projects, setProjects] = useState([]);
  const [overview, setOverview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [newProjectName, setNewProjectName] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [projectsRes, overviewRes] = await Promise.all([
        axios.get(`${API}/projects`),
        axios.get(`${API}/dashboard/overview`).catch(() => null),
      ]);
      // Handle paginated response
      setProjects(projectsRes.data.items || projectsRes.data);
      setOverview(overviewRes?.data || null);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

  // Cross-department / company overview (only for C-suite & department heads).
  const ownProjectIds = new Set(projects.map((p) => p.id));
  const showOverview =
    overview && overview.scope !== 'assigned' && (overview.projects || []).length > 0;
  const overviewExtraProjects = showOverview
    ? overview.projects.filter((p) => !ownProjectIds.has(p.id))
    : [];

  const createProject = async () => {
    if (!newProjectName.trim()) {
      toast.error('Project name is required');
      return;
    }

    setIsCreating(true);
    try {
      const response = await axios.post(`${API}/projects`, { name: newProjectName });
      setProjects([...projects, response.data]);
      setNewProjectName('');
      setIsDialogOpen(false);
      toast.success('Project created successfully');
    } catch (error) {
      toast.error('Failed to create project');
    } finally {
      setIsCreating(false);
    }
  };

  const deleteProject = async (projectId, e) => {
    e.stopPropagation();
    
    if (!window.confirm('Are you sure? This will delete all chats in this project.')) {
      return;
    }

    try {
      await axios.delete(`${API}/projects/${projectId}`);
      setProjects(projects.filter(p => p.id !== projectId));
      toast.success('Project deleted');
    } catch (error) {
      toast.error('Failed to delete project');
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="dashboard-page">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('dashboard.title')}</h1>
            <p className="text-muted-foreground mt-1">
              {t('dashboard.subtitle')}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {/* New Project Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button className="btn-hover" data-testid="create-project-btn">
                  <Plus className="mr-2 h-4 w-4" />
                  {t('dashboard.newProject')}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>{t('dashboard.createNewProject')}</DialogTitle>
                  <DialogDescription>
                    {t('dashboard.createProjectDesc')}
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">{t('dashboard.projectName')}</Label>
                    <Input
                      id="name"
                      placeholder="My Awesome Project"
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && createProject()}
                      data-testid="project-name-input"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                    data-testid="cancel-create-btn"
                  >
                    {t('action.cancel')}
                  </Button>
                  <Button
                    onClick={createProject}
                    disabled={isCreating}
                    data-testid="confirm-create-btn"
                  >
                    {isCreating ? <div className="spinner mr-2" /> : null}
                    {t('dashboard.createProject')}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="spinner" />
          </div>
        ) : (
          <div className="space-y-8">
            {/* Role-based Overview (C-suite: all departments / Dept head: their dept) */}
            {showOverview && (
              <div>
                <h2 className="text-xl font-semibold mb-1 flex items-center gap-2">
                  <Building2 className="h-5 w-5 text-sky-400" />
                  {overview.scope === 'all' ? 'Обзор всех отделов' : 'Проекты отдела'}
                  <span className="text-xs font-normal text-muted-foreground ml-1">
                    {overview.projects.length} проектов
                  </span>
                </h2>
                <p className="text-sm text-muted-foreground mb-4">
                  {overview.scope === 'all'
                    ? 'Все проекты компании (только для просмотра).'
                    : `Отделы: ${(overview.departmentNames || []).filter(Boolean).join(', ') || '—'}`}
                </p>
                {overviewExtraProjects.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Все эти проекты уже среди ваших ниже.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {overviewExtraProjects.map((p) => (
                      <Card
                        key={p.id}
                        className="card-hover cursor-pointer group border-sky-500/20"
                        onClick={() => navigate(`/projects/${p.id}`)}
                      >
                        <CardContent className="py-4">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="rounded-lg bg-sky-500/15 p-2 flex-shrink-0">
                                <FolderOpen className="h-5 w-5 text-sky-400" />
                              </div>
                              <div className="min-w-0">
                                <h3 className="font-semibold truncate">{p.name}</h3>
                                <p className="text-xs text-muted-foreground truncate">{p.ownerEmail}</p>
                              </div>
                            </div>
                            <Eye className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          </div>
                          <div className="flex items-center justify-between text-xs text-muted-foreground mt-3">
                            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatDate(p.createdAt)}</span>
                            <span>{p.memberCount} участн.</span>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Projects Section */}
            <div>
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <FolderOpen className="h-5 w-5 text-indigo-400" />
                {t('dashboard.projects')}
              </h2>
              
              {projects.length === 0 ? (
                <Card className="border-dashed card-hover cursor-pointer" onClick={() => setIsDialogOpen(true)} data-testid="empty-projects-card">
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <div className="rounded-full bg-secondary p-4 mb-4">
                      <FolderOpen className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <h3 className="text-lg font-semibold mb-2">{t('dashboard.noProjects')}</h3>
                    <p className="text-muted-foreground text-center mb-4">
                      {t('dashboard.createFirst')}
                    </p>
                    <Button variant="outline" data-testid="create-first-project-btn">
                      <Plus className="mr-2 h-4 w-4" />
                      {t('dashboard.createProject')}
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {projects.map((project, index) => (
                    <Card 
                      key={project.id}
                      className="card-hover cursor-pointer group"
                      onClick={() => navigate(`/projects/${project.id}`)}
                      style={{ animationDelay: `${index * 50}ms` }}
                      data-testid={`project-card-${project.id}`}
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <div className="rounded-lg bg-secondary p-2">
                              <FolderOpen className="h-5 w-5 text-indigo-400" />
                            </div>
                            <CardTitle className="text-lg">{project.name}</CardTitle>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className=" h-8 w-8"
                            onClick={(e) => deleteProject(project.id, e)}
                            data-testid={`delete-project-${project.id}`}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between text-sm text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Clock className="h-4 w-4" />
                            <span>{formatDate(project.createdAt)}</span>
                          </div>
                          <ArrowRight className="h-4 w-4 " />
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

      </div>
    </DashboardLayout>
  );
};

export default DashboardPage;
