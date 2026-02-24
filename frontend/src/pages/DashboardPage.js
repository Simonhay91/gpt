import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Plus, FolderOpen, Trash2, Clock, ArrowRight, MessageSquare, Settings, MoveRight, Sparkles } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DashboardPage = () => {
  const [projects, setProjects] = useState([]);
  const [quickChats, setQuickChats] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newProjectName, setNewProjectName] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isCreatingQuickChat, setIsCreatingQuickChat] = useState(false);
  
  // User prompt state
  const [userPrompt, setUserPrompt] = useState('');
  const [isPromptDialogOpen, setIsPromptDialogOpen] = useState(false);
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  
  // Move chat state
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [chatToMove, setChatToMove] = useState(null);
  const [isMovingChat, setIsMovingChat] = useState(false);
  
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [projectsRes, quickChatsRes, promptRes] = await Promise.all([
        axios.get(`${API}/projects`),
        axios.get(`${API}/quick-chats`),
        axios.get(`${API}/user/prompt`)
      ]);
      setProjects(projectsRes.data);
      setQuickChats(quickChatsRes.data);
      setUserPrompt(promptRes.data.customPrompt || '');
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

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

  const createQuickChat = async () => {
    setIsCreatingQuickChat(true);
    try {
      const response = await axios.post(`${API}/quick-chats`, { name: 'Quick Chat' });
      toast.success('Quick chat created');
      navigate(`/chats/${response.data.id}`);
    } catch (error) {
      toast.error('Failed to create quick chat');
    } finally {
      setIsCreatingQuickChat(false);
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

  const deleteQuickChat = async (chatId, e) => {
    e.stopPropagation();
    
    if (!window.confirm('Are you sure? This will delete all messages in this chat.')) {
      return;
    }

    try {
      await axios.delete(`${API}/chats/${chatId}`);
      setQuickChats(quickChats.filter(c => c.id !== chatId));
      toast.success('Chat deleted');
    } catch (error) {
      toast.error('Failed to delete chat');
    }
  };

  const openMoveDialog = (chat, e) => {
    e.stopPropagation();
    setChatToMove(chat);
    setMoveDialogOpen(true);
  };

  const moveChat = async (targetProjectId) => {
    if (!chatToMove) return;
    
    setIsMovingChat(true);
    try {
      await axios.post(`${API}/chats/${chatToMove.id}/move`, { targetProjectId });
      setQuickChats(quickChats.filter(c => c.id !== chatToMove.id));
      setMoveDialogOpen(false);
      setChatToMove(null);
      toast.success('Chat moved to project');
    } catch (error) {
      toast.error('Failed to move chat');
    } finally {
      setIsMovingChat(false);
    }
  };

  const saveUserPrompt = async () => {
    setIsSavingPrompt(true);
    try {
      await axios.put(`${API}/user/prompt`, { customPrompt: userPrompt.trim() || null });
      toast.success('Custom prompt saved');
      setIsPromptDialogOpen(false);
    } catch (error) {
      toast.error('Failed to save prompt');
    } finally {
      setIsSavingPrompt(false);
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
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground mt-1">
              Manage your AI conversations and projects
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {/* User Prompt Settings */}
            <Dialog open={isPromptDialogOpen} onOpenChange={setIsPromptDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="gap-2" data-testid="user-prompt-btn">
                  <Sparkles className="h-4 w-4" />
                  My GPT Prompt
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                  <DialogTitle>Your Custom GPT Prompt</DialogTitle>
                  <DialogDescription>
                    This prompt will be added to every conversation to customize AI responses for you.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="userPrompt">Custom Instructions</Label>
                    <Textarea
                      id="userPrompt"
                      placeholder="e.g., Always respond in Russian. Be concise. Use code examples when possible."
                      value={userPrompt}
                      onChange={(e) => setUserPrompt(e.target.value)}
                      className="min-h-[150px]"
                      data-testid="user-prompt-input"
                    />
                    <p className="text-xs text-muted-foreground">
                      This prompt is private and only affects your conversations.
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setIsPromptDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={saveUserPrompt}
                    disabled={isSavingPrompt}
                    data-testid="save-prompt-btn"
                  >
                    {isSavingPrompt ? <div className="spinner mr-2" /> : null}
                    Save Prompt
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Quick Chat Button */}
            <Button 
              variant="secondary" 
              onClick={createQuickChat}
              disabled={isCreatingQuickChat}
              className="gap-2"
              data-testid="quick-chat-btn"
            >
              {isCreatingQuickChat ? <div className="spinner" /> : <MessageSquare className="h-4 w-4" />}
              New Chat
            </Button>
            
            {/* New Project Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button className="btn-hover" data-testid="create-project-btn">
                  <Plus className="mr-2 h-4 w-4" />
                  New Project
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Create New Project</DialogTitle>
                  <DialogDescription>
                    Create a new project to organize your AI conversations with sources.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Project Name</Label>
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
                    Cancel
                  </Button>
                  <Button
                    onClick={createProject}
                    disabled={isCreating}
                    data-testid="confirm-create-btn"
                  >
                    {isCreating ? <div className="spinner mr-2" /> : null}
                    Create
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
            {/* Quick Chats Section */}
            {quickChats.length > 0 && (
              <div>
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <MessageSquare className="h-5 w-5 text-emerald-400" />
                  My Chats
                </h2>
                <div className="space-y-3">
                  {quickChats.map((chat, index) => (
                    <Card 
                      key={chat.id}
                      className="card-hover cursor-pointer group"
                      onClick={() => navigate(`/chats/${chat.id}`)}
                      style={{ animationDelay: `${index * 50}ms` }}
                      data-testid={`quick-chat-card-${chat.id}`}
                    >
                      <CardContent className="py-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="rounded-lg bg-emerald-500/20 p-2">
                              <MessageSquare className="h-5 w-5 text-emerald-400" />
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
                              className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                              onClick={(e) => openMoveDialog(chat, e)}
                              title="Move to project"
                              data-testid={`move-chat-${chat.id}`}
                            >
                              <MoveRight className="h-4 w-4 text-indigo-400" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                              onClick={(e) => deleteQuickChat(chat.id, e)}
                              data-testid={`delete-quick-chat-${chat.id}`}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                            <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Projects Section */}
            <div>
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <FolderOpen className="h-5 w-5 text-indigo-400" />
                Projects
              </h2>
              
              {projects.length === 0 ? (
                <Card className="border-dashed card-hover cursor-pointer" onClick={() => setIsDialogOpen(true)} data-testid="empty-projects-card">
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <div className="rounded-full bg-secondary p-4 mb-4">
                      <FolderOpen className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <h3 className="text-lg font-semibold mb-2">No projects yet</h3>
                    <p className="text-muted-foreground text-center mb-4">
                      Create a project to organize chats with file sources
                    </p>
                    <Button variant="outline" data-testid="create-first-project-btn">
                      <Plus className="mr-2 h-4 w-4" />
                      Create Project
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
                            className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
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
                          <ArrowRight className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Move Chat Dialog */}
        <Dialog open={moveDialogOpen} onOpenChange={setMoveDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Move Chat to Project</DialogTitle>
              <DialogDescription>
                Select a project to move "{chatToMove?.name}" into.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2 py-4 max-h-[300px] overflow-y-auto">
              {projects.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">
                  No projects available. Create a project first.
                </p>
              ) : (
                projects.map((project) => (
                  <Card
                    key={project.id}
                    className="cursor-pointer hover:border-indigo-500/50 transition-colors"
                    onClick={() => moveChat(project.id)}
                    data-testid={`move-to-project-${project.id}`}
                  >
                    <CardContent className="py-3 flex items-center gap-3">
                      <FolderOpen className="h-5 w-5 text-indigo-400" />
                      <span className="font-medium">{project.name}</span>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setMoveDialogOpen(false)}
                disabled={isMovingChat}
              >
                Cancel
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default DashboardPage;
