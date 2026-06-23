import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';
import {
  Shield, Plus, Trash2, Save, Lock, ChevronRight,
  ChevronDown, Loader2, Edit2, ArrowLeft, Users
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Human-readable labels for resources and actions
const RESOURCE_LABELS = {
  users:           'Users',
  roles:           'Roles',
  global_sources:  'Global Sources',
  product_catalog: 'Product Catalog',
  departments:     'Departments',
  competitors:     'Competitors',
  library:         'Library',
  news:            'News',
  reports:         'Reports',
  audit_logs:      'Audit Logs',
  config:          'Config',
  oem_datasheet:   'OEM Datasheet',
  project_memory:  'Project Memory',
  chats:           'Chats',
  sources:         'Sources',
  cache:           'Cache',
  backfill:        'Backfill',
};

const ACTION_LABELS = {
  read:           'Read',
  create:         'Create',
  update:         'Update',
  delete:         'Delete',
  approve:        'Approve',
  assign:         'Assign',
  import:         'Import',
  manage:         'Manage',
  reset_password: 'Reset Password',
  run:            'Run',
  clear:          'Clear',
};

const ROLE_COLORS = {
  role_super_admin: 'text-amber-400 bg-amber-500/15 border-amber-500/30',
  role_manager:     'text-blue-400 bg-blue-500/15 border-blue-500/30',
  role_editor:      'text-emerald-400 bg-emerald-500/15 border-emerald-500/30',
  role_viewer:      'text-slate-400 bg-slate-500/15 border-slate-500/30',
  role_base:        'text-purple-400 bg-purple-500/15 border-purple-500/30',
};

const AdminRolesPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [roles, setRoles]           = useState([]);
  const [registry, setRegistry]     = useState({});  // { resource: [action, ...] }
  const [isLoading, setIsLoading]   = useState(true);
  const [selectedRole, setSelectedRole] = useState(null);   // role being edited in matrix
  const [editPerms, setEditPerms]   = useState(new Set());  // checked permissions for editor
  const [isSaving, setIsSaving]     = useState(false);
  const [expandedRoles, setExpandedRoles] = useState(new Set());

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName]       = useState('');
  const [newDesc, setNewDesc]       = useState('');
  const [isCreating, setIsCreating] = useState(false);

  // Delete confirm
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting]     = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [rolesRes, regRes] = await Promise.all([
        axios.get(`${API}/admin/roles`),
        axios.get(`${API}/admin/permissions/registry`),
      ]);
      setRoles(rolesRes.data || []);
      setRegistry(regRes.data || {});
    } catch {
      toast.error('Failed to load roles');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Open the permissions matrix for a role
  const openMatrix = (role) => {
    setSelectedRole(role);
    setEditPerms(new Set(role.permissions || []));
    // Auto-expand
    setExpandedRoles(prev => new Set([...prev, role.id]));
  };

  const togglePerm = (perm) => {
    if (selectedRole?.isSystem && selectedRole?.id === 'role_super_admin') return;
    setEditPerms(prev => {
      const next = new Set(prev);
      next.has(perm) ? next.delete(perm) : next.add(perm);
      return next;
    });
  };

  const toggleAllResource = (resource, actions) => {
    if (selectedRole?.isSystem && selectedRole?.id === 'role_super_admin') return;
    const perms = actions.map(a => `${resource}:${a}`);
    const allChecked = perms.every(p => editPerms.has(p));
    setEditPerms(prev => {
      const next = new Set(prev);
      if (allChecked) perms.forEach(p => next.delete(p));
      else            perms.forEach(p => next.add(p));
      return next;
    });
  };

  const savePermissions = async () => {
    if (!selectedRole) return;
    setIsSaving(true);
    try {
      const body = { permissions: [...editPerms] };
      const res = await axios.put(`${API}/admin/roles/${selectedRole.id}`, body);
      setRoles(prev => prev.map(r => r.id === selectedRole.id ? res.data : r));
      setSelectedRole(res.data);
      toast.success('Permissions saved');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  };

  const createRole = async () => {
    if (!newName.trim()) { toast.error('Name required'); return; }
    setIsCreating(true);
    try {
      const res = await axios.post(`${API}/admin/roles`, {
        name: newName.trim(),
        description: newDesc.trim(),
        permissions: [],
      });
      setRoles(prev => [...prev, res.data]);
      setCreateOpen(false);
      setNewName(''); setNewDesc('');
      toast.success('Role created');
      openMatrix(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create');
    } finally {
      setIsCreating(false);
    }
  };

  const deleteRole = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await axios.delete(`${API}/admin/roles/${deleteTarget.id}`);
      setRoles(prev => prev.filter(r => r.id !== deleteTarget.id));
      if (selectedRole?.id === deleteTarget.id) setSelectedRole(null);
      setDeleteTarget(null);
      toast.success('Role deleted');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    } finally {
      setIsDeleting(false);
    }
  };

  const toggleExpand = (roleId) => {
    setExpandedRoles(prev => {
      const next = new Set(prev);
      next.has(roleId) ? next.delete(roleId) : next.add(roleId);
      return next;
    });
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </DashboardLayout>
    );
  }

  const isSuperAdmin = selectedRole?.id === 'role_super_admin';
  const isReadOnly   = selectedRole?.isSystem && isSuperAdmin;

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate('/admin/users')}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Shield className="h-6 w-6 text-indigo-400" />
                Roles & Permissions
              </h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                Create roles, assign permissions, then assign roles to users
              </p>
            </div>
          </div>
          <Button onClick={() => setCreateOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            New Role
          </Button>
        </div>

        <div className="grid lg:grid-cols-5 gap-6">

          {/* Left — Roles list */}
          <div className="lg:col-span-2 space-y-3">
            {roles.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">No roles found</p>
            )}
            {roles.map(role => {
              const colorClass = ROLE_COLORS[role.id] || 'text-indigo-400 bg-indigo-500/15 border-indigo-500/30';
              const isSelected = selectedRole?.id === role.id;
              return (
                <Card
                  key={role.id}
                  className={`cursor-pointer transition-all border ${
                    isSelected
                      ? 'ring-2 ring-indigo-500 border-indigo-500/50'
                      : 'hover:border-border/80'
                  }`}
                  onClick={() => openMatrix(role)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-3 min-w-0">
                        <span className={`mt-0.5 text-xs font-semibold px-2 py-0.5 rounded-full border shrink-0 ${colorClass}`}>
                          {role.isSystem ? <Lock className="h-3 w-3 inline mr-1" /> : null}
                          {role.isSystem ? 'System' : 'Custom'}
                        </span>
                        <div className="min-w-0">
                          <p className="font-semibold text-sm truncate">{role.name}</p>
                          {role.description && (
                            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{role.description}</p>
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {role.permissions?.includes('*')
                              ? 'All permissions (*)'
                              : `${role.permissions?.length || 0} permissions`}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={(e) => { e.stopPropagation(); openMatrix(role); }}
                          title="Edit permissions"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </Button>
                        {!role.isSystem && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-red-400 hover:text-red-400 hover:bg-red-500/10"
                            onClick={(e) => { e.stopPropagation(); setDeleteTarget(role); }}
                            title="Delete role"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Right — Permissions matrix */}
          <div className="lg:col-span-3">
            {!selectedRole ? (
              <Card className="h-full flex items-center justify-center min-h-[300px]">
                <CardContent className="text-center text-muted-foreground">
                  <Shield className="h-12 w-12 mx-auto mb-3 opacity-20" />
                  <p className="text-sm">Select a role to view and edit its permissions</p>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader className="pb-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        {selectedRole.isSystem && <Lock className="h-4 w-4 text-muted-foreground" />}
                        {selectedRole.name}
                      </CardTitle>
                      {selectedRole.description && (
                        <CardDescription className="mt-1">{selectedRole.description}</CardDescription>
                      )}
                    </div>
                    {!isReadOnly && (
                      <Button onClick={savePermissions} disabled={isSaving} size="sm" className="gap-2 shrink-0">
                        {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                        Save
                      </Button>
                    )}
                  </div>
                  {isSuperAdmin && (
                    <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs text-amber-400">
                      Super Admin always has full access (*) — permissions cannot be changed.
                    </div>
                  )}
                  {selectedRole.isSystem && !isSuperAdmin && (
                    <div className="mt-3 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-xs text-blue-400">
                      This is a system role. You can customize its permissions — changes will survive server restarts.
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  {isSuperAdmin ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <Shield className="h-10 w-10 mx-auto mb-2 text-amber-400/60" />
                      <p className="text-sm">Wildcard permission — access to everything</p>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {Object.entries(registry).map(([resource, actions]) => {
                        const allChecked = actions.every(a => editPerms.has(`${resource}:${a}`));
                        const someChecked = actions.some(a => editPerms.has(`${resource}:${a}`));
                        const isExpanded = expandedRoles.has(`matrix_${resource}`);

                        return (
                          <div key={resource} className="border border-border/50 rounded-lg overflow-hidden">
                            {/* Resource header row */}
                            <div
                              className="flex items-center gap-3 px-4 py-2.5 bg-secondary/30 cursor-pointer hover:bg-secondary/50 transition-colors"
                              onClick={() => setExpandedRoles(prev => {
                                const next = new Set(prev);
                                const key = `matrix_${resource}`;
                                next.has(key) ? next.delete(key) : next.add(key);
                                return next;
                              })}
                            >
                              <Checkbox
                                checked={allChecked}
                                className={`data-[state=checked]:bg-indigo-500 ${someChecked && !allChecked ? 'opacity-60' : ''}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (!isReadOnly) toggleAllResource(resource, actions);
                                }}
                                disabled={isReadOnly}
                              />
                              <span className="font-medium text-sm flex-1">
                                {RESOURCE_LABELS[resource] || resource}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {actions.filter(a => editPerms.has(`${resource}:${a}`)).length}/{actions.length}
                              </span>
                              {isExpanded
                                ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                : <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              }
                            </div>

                            {/* Action checkboxes */}
                            {isExpanded && (
                              <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-3 gap-2 bg-background/40">
                                {actions.map(action => {
                                  const perm = `${resource}:${action}`;
                                  return (
                                    <label
                                      key={perm}
                                      className={`flex items-center gap-2 p-1.5 rounded hover:bg-secondary/40 ${isReadOnly ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                                    >
                                      <Checkbox
                                        checked={editPerms.has(perm)}
                                        onCheckedChange={() => !isReadOnly && togglePerm(perm)}
                                        disabled={isReadOnly}
                                        className="data-[state=checked]:bg-indigo-500"
                                      />
                                      <span className="text-sm">{ACTION_LABELS[action] || action}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Create role dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" /> New Role
            </DialogTitle>
            <DialogDescription>
              Create a custom role and then assign permissions to it.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Role name *</Label>
              <Input
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="e.g. Content Editor"
                onKeyDown={e => e.key === 'Enter' && createRole()}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={newDesc}
                onChange={e => setNewDesc(e.target.value)}
                placeholder="Short description of this role"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={isCreating}>
              Cancel
            </Button>
            <Button onClick={createRole} disabled={isCreating || !newName.trim()} className="gap-2">
              {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={open => !open && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-400">
              <Trash2 className="h-5 w-5" /> Delete role
            </DialogTitle>
            <DialogDescription>
              Delete <strong>{deleteTarget?.name}</strong>? Users assigned this role will revert to <strong>Base User</strong>.
              This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={deleteRole} disabled={isDeleting} className="gap-2">
              {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
};

export default AdminRolesPage;
