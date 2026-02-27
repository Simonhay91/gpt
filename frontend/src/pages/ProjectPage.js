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
import { Plus, MessageSquare, Trash2, Clock, ArrowRight, ArrowLeft, FolderOpen, Share2, Users, X } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';

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
  
  // Share dialog
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [shareEmail, setShareEmail] = useState('');
  const [isSharing, setIsSharing] = useState(false);
  const [members, setMembers] = useState([]);
  const [isOwner, setIsOwner] = useState(false);
  const [allUsers, setAllUsers] = useState([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [selectedMemberForChats, setSelectedMemberForChats] = useState(null);
  const [chatVisibility, setChatVisibility] = useState({});  // {chatId: boolean}
  const [isUpdatingVisibility, setIsUpdatingVisibility] = useState(false);

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
      
      // Check if current user is owner (we'll know from the API response)
      // Fetch members to determine ownership
      try {
        const membersRes = await axios.get(`${API}/projects/${projectId}/members`);
        setMembers(membersRes.data);
        // Current user is owner if they have owner role
        const currentUserEmail = localStorage.getItem('userEmail');
        const ownerMember = membersRes.data.find(m => m.role === 'owner');
        setIsOwner(ownerMember?.email === currentUserEmail);
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
      await axios.post(`${API}/projects/${projectId}/share`, { email: shareEmail.trim() });
      toast.success(`Shared with ${shareEmail}`);
      setShareEmail('');
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

  const shareWithUser = async (email) => {
    setIsSharing(true);
    try {
      await axios.post(`${API}/projects/${projectId}/share`, { email });
      toast.success(`Shared with ${email}`);
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
      // If sharedWithUsers is null, all members can see it
      // If it's an array, check if member is in it
      const sharedWith = chat.sharedWithUsers;
      visibility[chat.id] = sharedWith === null || sharedWith === undefined || sharedWith.includes(member.id);
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
      // For each chat, update its sharedWithUsers
      for (const chat of chats) {
        const isVisible = chatVisibility[chat.id];
        const currentShared = chat.sharedWithUsers || [];
        
        let newSharedWith;
        if (isVisible) {
          // Add member to sharedWithUsers (or set to null if all should see)
          if (currentShared.length === 0 && chat.sharedWithUsers === null) {
            // Already visible to all, no change needed
            continue;
          }
          newSharedWith = [...new Set([...currentShared, selectedMemberForChats.id])];
        } else {
          // Remove member from sharedWithUsers
          if (chat.sharedWithUsers === null) {
            // Was visible to all, now need to set to all members except this one
            const otherMembers = members.filter(m => m.role !== 'owner' && m.id !== selectedMemberForChats.id);
            newSharedWith = otherMembers.map(m => m.id);
          } else {
            newSharedWith = currentShared.filter(id => id !== selectedMemberForChats.id);
          }
        }
        
        await axios.put(`${API}/chats/${chat.id}/visibility`, { sharedWithUsers: newSharedWith });
      }
      
      // Refresh chats
      const chatsRes = await axios.get(`${API}/projects/${projectId}/chats`);
      setChats(chatsRes.data);
      
      toast.success('Chat visibility updated');
      setSelectedMemberForChats(null);
    } catch (error) {
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
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle>Share Project</DialogTitle>
                    <DialogDescription>
                      Invite team members to collaborate on this project.
                    </DialogDescription>
                  </DialogHeader>
                  
                  {/* Add member by email */}
                  <div className="flex gap-2 py-4">
                    <Input
                      placeholder="Enter email address"
                      value={shareEmail}
                      onChange={(e) => setShareEmail(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && shareProject()}
                      data-testid="share-email-input"
                    />
                    <Button 
                      onClick={shareProject}
                      disabled={isSharing}
                      data-testid="share-btn"
                    >
                      {isSharing ? <div className="spinner" /> : 'Add'}
                    </Button>
                  </div>
                  
                  {/* Available users to share with */}
                  {allUsers.length > 0 && (
                    <div className="space-y-2 mb-4">
                      <Label>Available Users</Label>
                      <div className="max-h-[150px] overflow-y-auto space-y-1">
                        {isLoadingUsers ? (
                          <div className="text-center py-2"><div className="spinner" /></div>
                        ) : (
                          allUsers
                            .filter(u => !members.find(m => m.id === u.id))
                            .map((user) => (
                              <div 
                                key={user.id} 
                                className="flex items-center justify-between py-2 px-3 bg-secondary/50 rounded-lg hover:bg-secondary cursor-pointer transition-colors"
                                onClick={() => !isSharing && shareWithUser(user.email)}
                                data-testid={`share-user-${user.id}`}
                              >
                                <div className="flex items-center gap-3">
                                  <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-xs font-medium">
                                    {user.email?.charAt(0).toUpperCase()}
                                  </div>
                                  <span className="text-sm">{user.email}</span>
                                </div>
                                <Plus className="h-4 w-4 text-muted-foreground" />
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
                  <div className="space-y-2">
                    <Label>Members ({members.length})</Label>
                    {members.map((member) => (
                      <div key={member.id} className="flex items-center justify-between py-2 px-3 bg-secondary rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-sm font-medium">
                            {member.email?.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="text-sm font-medium">{member.email}</p>
                            <p className="text-xs text-muted-foreground capitalize">{member.role}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          {member.role !== 'owner' && isOwner && chats.length > 0 && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-8 text-xs"
                              onClick={() => openChatVisibilityForMember(member)}
                              data-testid={`manage-chats-${member.id}`}
                            >
                              <MessageSquare className="h-3 w-3 mr-1" />
                              Chats
                            </Button>
                          )}
                          {member.role !== 'owner' && isOwner && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => removeMember(member.id)}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </DialogContent>
              </Dialog>
              
              {/* Chat Visibility Dialog */}
              <Dialog open={!!selectedMemberForChats} onOpenChange={(open) => !open && setSelectedMemberForChats(null)}>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle>Chat Access for {selectedMemberForChats?.email}</DialogTitle>
                    <DialogDescription>
                      Select which chats this user can see in the project.
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
