import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { Plus, MessageSquare, Trash2, Clock, ArrowRight, ArrowLeft, FolderOpen, Share2, Users, X, Shield, Eye, Edit, Settings } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Role configuration
const ROLES = {
  viewer: { label: 'Viewer', icon: Eye, color: 'text-blue-500', description: 'Только чтение' },
  editor: { label: 'Editor', icon: Edit, color: 'text-green-500', description: 'Создание чатов' },
  manager: { label: 'Manager', icon: Settings, color: 'text-orange-500', description: 'Управление источниками' }
};

const ProjectPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [project, setProject] = useState(null);
  const [chats, setChats] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newChatName, setNewChatName] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [userRole, setUserRole] = useState(null);  // Current user's role in this project
  
  // Share dialog
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [shareEmail, setShareEmail] = useState('');
  const [shareRole, setShareRole] = useState('viewer');  // Default role for new shares
  const [isSharing, setIsSharing] = useState(false);
  const [members, setMembers] = useState([]);
  const [isOwner, setIsOwner] = useState(false);
  const [allUsers, setAllUsers] = useState([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [selectedMemberForChats, setSelectedMemberForChats] = useState(null);
  const [chatVisibility, setChatVisibility] = useState({});
  const [isUpdatingVisibility, setIsUpdatingVisibility] = useState(false);
  const [isUpdatingRole, setIsUpdatingRole] = useState(null);

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
      
      // Check members and current user's role
      try {
        const membersRes = await axios.get(`${API}/projects/${projectId}/members`);
        setMembers(membersRes.data);
        
        // Find current user's role
        const currentUserMember = membersRes.data.find(m => m.email === user?.email);
        if (currentUserMember) {
          setUserRole(currentUserMember.role);
          setIsOwner(currentUserMember.role === 'owner');
        }
      } catch (e) {
        console.error('Failed to fetch members');
      }
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

  const shareProject = async () => {
    if (!shareEmail.trim()) {
      toast.error('Please enter an email');
      return;
    }
    
    setIsSharing(true);
    try {
      await axios.post(`${API}/projects/${projectId}/share`, { 
        email: shareEmail.trim(),
        role: shareRole 
      });
      toast.success(`Shared with ${shareEmail} as ${ROLES[shareRole]?.label || shareRole}`);
      setShareEmail('');
      setShareRole('viewer');
      // Refresh members
      const membersRes = await axios.get(`${API}/projects/${projectId}/members`);
      setMembers(membersRes.data);
    } catch (error) {
      const msg = error.response?.data?.detail || 'Failed to share';
      toast.error(msg);
    } finally {
      setIsSharing(false);
    }
  };

  const shareWithUser = async (email, role = 'viewer') => {
    setIsSharing(true);
    try {
      await axios.post(`${API}/projects/${projectId}/share`, { email, role });
      toast.success(`Shared with ${email} as ${ROLES[role]?.label || role}`);
      // Refresh members
      const membersRes = await axios.get(`${API}/projects/${projectId}/members`);
      setMembers(membersRes.data);
    } catch (error) {
      const msg = error.response?.data?.detail || 'Failed to share';
      toast.error(msg);
    } finally {
      setIsSharing(false);
    }
  };

  const updateMemberRole = async (userId, newRole) => {
    setIsUpdatingRole(userId);
    try {
      await axios.put(`${API}/projects/${projectId}/members/${userId}/role`, null, {
        params: { role: newRole }
      });
      toast.success(`Role updated to ${ROLES[newRole]?.label || newRole}`);
      // Refresh members
      const membersRes = await axios.get(`${API}/projects/${projectId}/members`);
      setMembers(membersRes.data);
    } catch (error) {
      const msg = error.response?.data?.detail || 'Failed to update role';
      toast.error(msg);
    } finally {
      setIsUpdatingRole(null);
    }
  };

  const fetchUsersForSharing = async () => {
    setIsLoadingUsers(true);
    try {
      const response = await axios.get(`${API}/users/list`);
      setAllUsers(response.data);
    } catch (error) {
      console.error('Failed to load users');
    } finally {
      setIsLoadingUsers(false);
    }
  };

  const openShareDialog = () => {
    fetchUsersForSharing();
    setShareDialogOpen(true);
  };

  const removeMember = async (userId) => {
    try {
      await axios.delete(`${API}/projects/${projectId}/share/${userId}`);
      setMembers(members.filter(m => m.id !== userId));
      toast.success('Member removed');
    } catch (error) {
      toast.error('Failed to remove member');
    }
  };

  const openChatVisibilityForMember = (member) => {
    setSelectedMemberForChats(member);
    // Initialize visibility state for this member
    const visibility = {};
    chats.forEach(chat => {
      // If sharedWithUsers is null/undefined, all members can see it (true)
      // If it's an array, check if member is in it
      const sharedWith = chat.sharedWithUsers;
      if (sharedWith === null || sharedWith === undefined) {
        visibility[chat.id] = true; // visible to all
      } else if (Array.isArray(sharedWith)) {
        visibility[chat.id] = sharedWith.includes(member.id);
      } else {
        visibility[chat.id] = true; // default to visible
      }
    });
    setChatVisibility(visibility);
  };

  const toggleChatVisibility = (chatId) => {
    setChatVisibility(prev => ({
      ...prev,
      [chatId]: !prev[chatId]
    }));
  };

  const saveChatVisibility = async () => {
    if (!selectedMemberForChats) return;
    
    setIsUpdatingVisibility(true);
    try {
      // For each chat, update visibility for this specific member
      for (const chat of chats) {
        const isVisible = chatVisibility[chat.id];
        
        // Get current sharedWithUsers or empty array
        let currentShared = chat.sharedWithUsers || [];
        
        // If chat was visible to all (null), convert to array of all member IDs first
        if (chat.sharedWithUsers === null || chat.sharedWithUsers === undefined) {
          // Get all shared member IDs (not owner)
          currentShared = members.filter(m => m.role !== 'owner').map(m => m.id);
        }
        
        let newSharedWith;
        if (isVisible) {
          // Add this member if not already present
          if (!currentShared.includes(selectedMemberForChats.id)) {
            newSharedWith = [...currentShared, selectedMemberForChats.id];
          } else {
            newSharedWith = currentShared;
          }
        } else {
          // Remove this member
          newSharedWith = currentShared.filter(id => id !== selectedMemberForChats.id);
        }
        
        await axios.put(`${API}/chats/${chat.id}/visibility`, { sharedWithUsers: newSharedWith });
      }
      
      // Refresh chats
      const chatsRes = await axios.get(`${API}/projects/${projectId}/chats`);
      setChats(chatsRes.data);
      
      toast.success('Chat visibility updated');
      setSelectedMemberForChats(null);
    } catch (error) {
      console.error('Error:', error);
      toast.error('Failed to update visibility');
    } finally {
      setIsUpdatingVisibility(false);
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
                  {chats.length} {chats.length === 1 ? 'chat' : 'chats'}
                  {members.length > 1 && (
                    <span className="ml-2 text-emerald-400">
                      • {members.length} members
                    </span>
                  )}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {/* Share Button */}
              <Dialog open={shareDialogOpen} onOpenChange={setShareDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" onClick={openShareDialog} data-testid="share-project-btn">
                    <Share2 className="mr-2 h-4 w-4" />
                    Share
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-xl w-[95vw]">
                  <DialogHeader>
                    <DialogTitle>Share Project</DialogTitle>
                    <DialogDescription>
                      Invite team members to collaborate on this project.
                    </DialogDescription>
                  </DialogHeader>
                  
                  {/* Add member by email */}
                  <div className="flex gap-2 pt-4">
                    <Input
                      placeholder="Enter email address"
                      value={shareEmail}
                      onChange={(e) => setShareEmail(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && shareProject()}
                      className="flex-1"
                      data-testid="share-email-input"
                    />
                    <select
                      value={shareRole}
                      onChange={(e) => setShareRole(e.target.value)}
                      className="w-28 px-2 py-1 rounded-md border border-input bg-background text-sm"
                      data-testid="share-role-select"
                    >
                      <option value="viewer">Viewer</option>
                      <option value="editor">Editor</option>
                      {isOwner && <option value="manager">Manager</option>}
                    </select>
                    <Button 
                      onClick={shareProject}
                      disabled={isSharing}
                      data-testid="share-btn"
                    >
                      {isSharing ? <div className="spinner" /> : 'Add'}
                    </Button>
                  </div>

                  {/* Role Legend */}
                  <div className="flex flex-wrap gap-3 pb-2 text-xs text-muted-foreground">
                    {Object.entries(ROLES).map(([key, { label, icon: Icon, color, description }]) => (
                      <div key={key} className="flex items-center gap-1">
                        <Icon className={`h-3 w-3 ${color}`} />
                        <span>{label}:</span>
                        <span className="opacity-70">{description}</span>
                      </div>
                    ))}
                  </div>
                  
                  {/* Available users to share with */}
                  {allUsers.length > 0 && (
                    <div className="space-y-2 mt-4">
                      <Label>Available Users</Label>
                      <div className="max-h-[150px] overflow-y-auto space-y-1">
                        {isLoadingUsers ? (
                          <div className="text-center py-2"><div className="spinner" /></div>
                        ) : (
                          allUsers
                            .filter(u => !members.find(m => m.id === u.id))
                            .map((u) => (
                              <div 
                                key={u.id} 
                                className="flex items-center justify-between py-2 px-3 bg-secondary/50 rounded-lg hover:bg-secondary cursor-pointer transition-colors"
                                onClick={() => !isSharing && shareWithUser(u.email, shareRole)}
                                data-testid={`share-user-${u.id}`}
                              >
                                <div className="flex items-center gap-3">
                                  <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-xs font-medium">
                                    {u.email?.charAt(0).toUpperCase()}
                                  </div>
                                  <span className="text-sm">{u.email}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="text-xs text-muted-foreground">{ROLES[shareRole]?.label}</span>
                                  <Plus className="h-4 w-4 text-muted-foreground" />
                                </div>
                              </div>
                            ))
                        )}
                        {!isLoadingUsers && allUsers.filter(u => !members.find(m => m.id === u.id)).length === 0 && (
                          <p className="text-sm text-muted-foreground text-center py-2">All users already have access</p>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Current members list */}
                  <div className="space-y-2 mt-4">
                    <Label>Members ({members.length})</Label>
                    <div className="space-y-2 max-h-[200px] overflow-y-auto">
                      {members.map((member) => {
                        const roleConfig = ROLES[member.role] || {};
                        const RoleIcon = roleConfig.icon || Shield;
                        
                        return (
                          <div key={member.id} className="flex items-center justify-between py-2 px-3 bg-secondary rounded-lg gap-2">
                            <div className="flex items-center gap-3 min-w-0 flex-1">
                              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                                {member.email?.charAt(0).toUpperCase()}
                              </div>
                              <div className="min-w-0">
                                <p className="text-sm font-medium truncate">{member.email}</p>
                                <div className="flex items-center gap-1">
                                  <RoleIcon className={`h-3 w-3 ${roleConfig.color || 'text-muted-foreground'}`} />
                                  <p className="text-xs text-muted-foreground capitalize">{member.role}</p>
                                </div>
                              </div>
                            </div>
                            {member.role !== 'owner' && isOwner && (
                              <div className="flex items-center gap-1 flex-shrink-0">
                                {/* Role selector */}
                                <select
                                  value={member.role}
                                  onChange={(e) => updateMemberRole(member.id, e.target.value)}
                                  disabled={isUpdatingRole === member.id}
                                  className="h-7 px-2 text-xs rounded border border-input bg-background"
                                  data-testid={`role-select-${member.id}`}
                                >
                                  <option value="viewer">Viewer</option>
                                  <option value="editor">Editor</option>
                                  <option value="manager">Manager</option>
                                </select>
                                {chats.length > 0 && (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-7 text-xs px-2"
                                    onClick={() => openChatVisibilityForMember(member)}
                                    data-testid={`manage-chats-${member.id}`}
                                  >
                                    <MessageSquare className="h-3 w-3 mr-1" />
                                    Chats
                                  </Button>
                                )}
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-destructive hover:text-destructive"
                                  onClick={() => removeMember(member.id)}
                                  data-testid={`remove-member-${member.id}`}
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
              
              {/* Chat Visibility Dialog */}
              <Dialog open={!!selectedMemberForChats} onOpenChange={(open) => !open && setSelectedMemberForChats(null)}>
                <DialogContent className="sm:max-w-lg">
                  <DialogHeader>
                    <DialogTitle>Chat Access</DialogTitle>
                    <DialogDescription>
                      Select which chats <span className="font-medium">{selectedMemberForChats?.email?.split('@')[0]}</span> can see.
                    </DialogDescription>
                  </DialogHeader>
                  
                  <div className="space-y-3 py-4 max-h-[300px] overflow-y-auto">
                    {chats.map((chat) => (
                      <div 
                        key={chat.id} 
                        className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-secondary/50 cursor-pointer transition-colors"
                        onClick={() => toggleChatVisibility(chat.id)}
                      >
                        <Checkbox
                          checked={chatVisibility[chat.id] || false}
                          onCheckedChange={() => toggleChatVisibility(chat.id)}
                          data-testid={`chat-visibility-${chat.id}`}
                        />
                        <MessageSquare className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm flex-1">{chat.name}</span>
                      </div>
                    ))}
                    {chats.length === 0 && (
                      <p className="text-sm text-muted-foreground text-center py-4">No chats in this project</p>
                    )}
                  </div>
                  
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setSelectedMemberForChats(null)}>
                      Cancel
                    </Button>
                    <Button onClick={saveChatVisibility} disabled={isUpdatingVisibility}>
                      {isUpdatingVisibility ? <div className="spinner mr-2" /> : null}
                      Save
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              
              {/* New Chat Button */}
              <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="btn-hover" data-testid="new-chat-btn">
                    <Plus className="mr-2 h-4 w-4" />
                    New Chat
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle>Create New Chat</DialogTitle>
                    <DialogDescription>
                      Start a new conversation in this project.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="chatName">Chat Name (optional)</Label>
                      <Input
                        id="chatName"
                        placeholder="New Chat"
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
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={createChat}
                      disabled={isCreating}
                      data-testid="confirm-create-chat-btn"
                    >
                      {isCreating ? <div className="spinner mr-2" /> : null}
                      Create Chat
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </div>

        {/* Chats List with 5px padding */}
        <div className="p-[5px]">
          {chats.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <div className="rounded-full bg-secondary p-4 mb-4">
                  <MessageSquare className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-semibold mb-2">No chats yet</h3>
                <p className="text-muted-foreground text-center mb-4">
                  Start a new conversation with the AI assistant
                </p>
                <Button onClick={() => setIsDialogOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Chat
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
                        <div className="rounded-lg bg-emerald-500/20 p-2">
                          <MessageSquare className="h-5 w-5 text-emerald-400" />
                        </div>
                        <div>
                          <h3 className="font-semibold">{chat.name || 'Untitled Chat'}</h3>
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
      </div>
    </DashboardLayout>
  );
};

export default ProjectPage;
