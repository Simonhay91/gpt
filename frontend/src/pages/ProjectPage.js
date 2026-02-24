import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Plus, MessageSquare, Trash2, Clock, ArrowRight, ArrowLeft, FolderOpen } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ProjectPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [chats, setChats] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newChatName, setNewChatName] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    fetchProjectAndChats();
  }, [projectId]);

  const fetchProjectAndChats = async () => {
    try {
      const [projectRes, chatsRes] = await Promise.all([
        axios.get(`${API}/projects/${projectId}`),
        axios.get(`${API}/projects/${projectId}/chats`)
      ]);
      setProject(projectRes.data);
      setChats(chatsRes.data);
    } catch (error) {
      toast.error('Failed to load project');
      navigate('/dashboard');
    } finally {
      setIsLoading(false);
    }
  };

  const createChat = async () => {
    setIsCreating(true);
    try {
      const response = await axios.post(`${API}/projects/${projectId}/chats`, { 
        name: newChatName.trim() || 'New Chat' 
      });
      setChats([...chats, response.data]);
      setNewChatName('');
      setIsDialogOpen(false);
      toast.success('Chat created');
      // Navigate to the new chat
      navigate(`/chats/${response.data.id}`);
    } catch (error) {
      toast.error('Failed to create chat');
    } finally {
      setIsCreating(false);
    }
  };

  const deleteChat = async (chatId, e) => {
    e.stopPropagation();
    
    if (!window.confirm('Are you sure? This will delete all messages in this chat.')) {
      return;
    }

    try {
      await axios.delete(`${API}/chats/${chatId}`);
      setChats(chats.filter(c => c.id !== chatId));
      toast.success('Chat deleted');
    } catch (error) {
      toast.error('Failed to delete chat');
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="spinner" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="project-page">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            className="mb-4 -ml-2"
            onClick={() => navigate('/dashboard')}
            data-testid="back-to-dashboard-btn"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Projects
          </Button>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-secondary p-3">
                <FolderOpen className="h-6 w-6 text-indigo-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight">{project?.name}</h1>
                <p className="text-muted-foreground mt-1">
                  {chats.length} {chats.length === 1 ? 'chat' : 'chats'} in this project
                </p>
              </div>
            </div>
            
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button className="btn-hover" data-testid="create-chat-btn">
                  <Plus className="mr-2 h-4 w-4" />
                  New Chat
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Create New Chat</DialogTitle>
                  <DialogDescription>
                    Start a new conversation within this project.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="chatName">Chat Name (optional)</Label>
                    <Input
                      id="chatName"
                      placeholder="e.g., Feature Discussion"
                      value={newChatName}
                      onChange={(e) => setNewChatName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && createChat()}
                      data-testid="chat-name-input"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                    data-testid="cancel-chat-btn"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={createChat}
                    disabled={isCreating}
                    data-testid="confirm-chat-btn"
                  >
                    {isCreating ? <div className="spinner mr-2" /> : null}
                    Create
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Chats List */}
        {chats.length === 0 ? (
          <Card className="border-dashed card-hover cursor-pointer" onClick={() => setIsDialogOpen(true)} data-testid="empty-chats-card">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="rounded-full bg-secondary p-4 mb-4">
                <MessageSquare className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-2">No chats yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Start your first conversation in this project
              </p>
              <Button variant="outline" data-testid="create-first-chat-btn">
                <Plus className="mr-2 h-4 w-4" />
                Start Chat
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {chats.map((chat, index) => (
              <Card 
                key={chat.id}
                className="card-hover cursor-pointer group"
                onClick={() => navigate(`/chats/${chat.id}`)}
                style={{ animationDelay: `${index * 50}ms` }}
                data-testid={`chat-card-${chat.id}`}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="rounded-lg bg-secondary p-2">
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
                        onClick={(e) => deleteChat(chat.id, e)}
                        data-testid={`delete-chat-${chat.id}`}
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
        )}
      </div>
    </DashboardLayout>
  );
};

export default ProjectPage;
