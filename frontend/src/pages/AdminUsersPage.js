import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Plus, Users, Trash2, Copy, Eye, EyeOff, ArrowLeft, Coins, MessageSquare, Shield, HardDrive, FileText } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminUsersPage = () => {
  const [users, setUsers] = useState([]);
  const [sourceStats, setSourceStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [createdUser, setCreatedUser] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchUsers();
    fetchSourceStats();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/admin/users`);
      setUsers(response.data);
    } catch (error) {
      toast.error('Failed to load users');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSourceStats = async () => {
    try {
      const response = await axios.get(`${API}/admin/source-stats`);
      setSourceStats(response.data);
    } catch (error) {
      console.error('Failed to load source stats');
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

  const createUser = async () => {
    if (!newUserEmail.trim()) {
      toast.error('Email is required');
      return;
    }
    if (!newUserPassword.trim()) {
      toast.error('Password is required');
      return;
    }

    setIsCreating(true);
    try {
      const response = await axios.post(`${API}/admin/users`, { 
        email: newUserEmail, 
        password: newUserPassword 
      });
      setUsers([...users, { ...response.data, totalTokensUsed: 0, totalMessagesCount: 0 }]);
      setCreatedUser({ email: newUserEmail, password: newUserPassword });
      toast.success('User created successfully');
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to create user';
      toast.error(message);
    } finally {
      setIsCreating(false);
    }
  };

  const deleteUser = async (userId, userEmail) => {
    if (!window.confirm(`Are you sure you want to delete ${userEmail}? This will delete all their data.`)) {
      return;
    }

    try {
      await axios.delete(`${API}/admin/users/${userId}`);
      setUsers(users.filter(u => u.id !== userId));
      toast.success('User deleted');
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to delete user';
      toast.error(message);
    }
  };

  const copyCredentials = () => {
    if (createdUser) {
      const text = `Email: ${createdUser.email}\nPassword: ${createdUser.password}`;
      navigator.clipboard.writeText(text);
      toast.success('Credentials copied to clipboard');
    }
  };

  const resetDialog = () => {
    setNewUserEmail('');
    setNewUserPassword('');
    setCreatedUser(null);
    setShowPassword(false);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const formatNumber = (num) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="admin-users-page">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            className="mb-4 -ml-2"
            onClick={() => navigate('/dashboard')}
            data-testid="back-to-dashboard-btn"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Dashboard
          </Button>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-indigo-500/20 p-3">
                <Users className="h-6 w-6 text-indigo-400" />
              </div>
              <div>
                <h1 className="text-3xl font-bold tracking-tight">User Management</h1>
                <p className="text-muted-foreground mt-1">
                  {users.length} {users.length === 1 ? 'user' : 'users'} registered
                </p>
              </div>
            </div>
            
            <Dialog open={isDialogOpen} onOpenChange={(open) => {
              setIsDialogOpen(open);
              if (!open) resetDialog();
            }}>
              <DialogTrigger asChild>
                <Button className="btn-hover" data-testid="create-user-btn">
                  <Plus className="mr-2 h-4 w-4" />
                  Create User
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                {!createdUser ? (
                  <>
                    <DialogHeader>
                      <DialogTitle>Create New User</DialogTitle>
                      <DialogDescription>
                        Create a new user account and share the credentials with them.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <Input
                          id="email"
                          type="email"
                          placeholder="user@example.com"
                          value={newUserEmail}
                          onChange={(e) => setNewUserEmail(e.target.value)}
                          data-testid="new-user-email-input"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="password">Password</Label>
                        <div className="flex gap-2">
                          <div className="relative flex-1">
                            <Input
                              id="password"
                              type={showPassword ? "text" : "password"}
                              placeholder="Enter password"
                              value={newUserPassword}
                              onChange={(e) => setNewUserPassword(e.target.value)}
                              data-testid="new-user-password-input"
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
                          <Button
                            type="button"
                            variant="outline"
                            onClick={generatePassword}
                            data-testid="generate-password-btn"
                          >
                            Generate
                          </Button>
                        </div>
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
                        onClick={createUser}
                        disabled={isCreating}
                        data-testid="confirm-create-user-btn"
                      >
                        {isCreating ? <div className="spinner mr-2" /> : null}
                        Create User
                      </Button>
                    </DialogFooter>
                  </>
                ) : (
                  <>
                    <DialogHeader>
                      <DialogTitle>User Created Successfully</DialogTitle>
                      <DialogDescription>
                        Share these credentials with the new user.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="py-4 space-y-4">
                      <Card className="bg-emerald-500/10 border-emerald-500/20">
                        <CardContent className="pt-4">
                          <div className="space-y-3">
                            <div>
                              <Label className="text-xs text-muted-foreground">Email</Label>
                              <p className="font-mono text-sm">{createdUser.email}</p>
                            </div>
                            <div>
                              <Label className="text-xs text-muted-foreground">Password</Label>
                              <p className="font-mono text-sm">{createdUser.password}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={copyCredentials}
                        data-testid="copy-credentials-btn"
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        Copy Credentials
                      </Button>
                    </div>
                    <DialogFooter>
                      <Button onClick={() => {
                        setIsDialogOpen(false);
                        resetDialog();
                      }}>
                        Done
                      </Button>
                    </DialogFooter>
                  </>
                )}
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Users List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="spinner" />
          </div>
        ) : users.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="rounded-full bg-secondary p-4 mb-4">
                <Users className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-2">No users yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create your first user to get started
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {users.map((user, index) => (
              <Card 
                key={user.id}
                className="card-hover group"
                style={{ animationDelay: `${index * 50}ms` }}
                data-testid={`user-card-${user.id}`}
              >
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`rounded-lg p-2 ${user.isAdmin ? 'bg-amber-500/20' : 'bg-secondary'}`}>
                        {user.isAdmin ? (
                          <Shield className="h-5 w-5 text-amber-400" />
                        ) : (
                          <Users className="h-5 w-5 text-muted-foreground" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold">{user.email}</h3>
                          {user.isAdmin && (
                            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                              Admin
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Created {formatDate(user.createdAt)}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-6">
                      {/* Token Usage Stats */}
                      <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1 text-muted-foreground" title="Tokens used">
                          <Coins className="h-4 w-4 text-amber-400" />
                          <span>{formatNumber(user.totalTokensUsed)}</span>
                        </div>
                        <div className="flex items-center gap-1 text-muted-foreground" title="Messages sent">
                          <MessageSquare className="h-4 w-4 text-emerald-400" />
                          <span>{formatNumber(user.totalMessagesCount)}</span>
                        </div>
                      </div>
                      
                      {/* Delete Button */}
                      {!user.isAdmin && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                          onClick={() => deleteUser(user.id, user.email)}
                          data-testid={`delete-user-${user.id}`}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
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

export default AdminUsersPage;
