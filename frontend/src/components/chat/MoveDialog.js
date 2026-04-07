/**
 * MoveDialog Component
 * Dialog for moving a chat to a different project (or a newly created one)
 */
import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { FolderOpen, Loader2, Plus } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Card, CardContent } from '../ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const MoveDialog = ({
  open,
  onOpenChange,
  chatId,
  currentProjectId,
  onMoved,
}) => {
  const [projects, setProjects] = useState([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

  const fetchProjects = async () => {
    setIsLoadingProjects(true);
    try {
      const response = await axios.get(`${API}/projects`);
      setProjects(response.data.items || response.data || []);
    } catch {
      console.error('Failed to load projects');
    } finally {
      setIsLoadingProjects(false);
    }
  };

  const handleOpenChange = (value) => {
    if (value) {
      setShowCreateForm(false);
      setNewProjectName('');
      fetchProjects();
    }
    onOpenChange(value);
  };

  const moveChat = async (targetProjectId) => {
    setIsMoving(true);
    try {
      await axios.post(`${API}/chats/${chatId}/move`, { targetProjectId });
      toast.success('Chat moved to project');
      onOpenChange(false);
      onMoved?.();
    } catch {
      toast.error('Failed to move chat');
    } finally {
      setIsMoving(false);
    }
  };

  const createProjectAndMove = async () => {
    if (!newProjectName.trim()) { toast.error('Project name is required'); return; }
    setIsCreating(true);
    try {
      const response = await axios.post(`${API}/projects`, { name: newProjectName.trim() });
      await axios.post(`${API}/chats/${chatId}/move`, { targetProjectId: response.data.id });
      toast.success('Project created and chat moved');
      onOpenChange(false);
      onMoved?.();
    } catch {
      toast.error('Failed to create project');
    } finally {
      setIsCreating(false);
    }
  };

  const otherProjects = projects.filter((p) => p.id !== currentProjectId);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Move Chat to Project</DialogTitle>
          <DialogDescription>
            {showCreateForm
              ? 'Create a new project and move this chat into it.'
              : 'Select a project to move this chat into.'}
            {currentProjectId && !showCreateForm &&
              ' The chat will be removed from its current project.'}
          </DialogDescription>
        </DialogHeader>

        {showCreateForm ? (
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="newProjectName">Project Name</Label>
              <Input
                id="newProjectName"
                placeholder="My New Project"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createProjectAndMove()}
                disabled={isCreating}
                data-testid="new-project-name-input"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowCreateForm(false)}
                disabled={isCreating}
              >
                Back
              </Button>
              <Button
                className="flex-1"
                onClick={createProjectAndMove}
                disabled={isCreating || !newProjectName.trim()}
                data-testid="create-and-move-btn"
              >
                {isCreating
                  ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  : <Plus className="mr-2 h-4 w-4" />}
                Create & Move
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-2 py-4 max-h-[300px] overflow-y-auto">
            {isLoadingProjects ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : otherProjects.length === 0 ? (
              <div className="text-center py-4">
                <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground mb-4">No projects yet</p>
                <Button
                  onClick={() => setShowCreateForm(true)}
                  data-testid="create-project-in-dialog-btn"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Create Project
                </Button>
              </div>
            ) : (
              <>
                {otherProjects.map((project) => (
                  <Card
                    key={project.id}
                    className="cursor-pointer hover:border-indigo-500/50 transition-colors"
                    onClick={() => moveChat(project.id)}
                    data-testid={`move-to-project-${project.id}`}
                  >
                    <CardContent className="py-3 flex items-center gap-3">
                      <FolderOpen className="h-5 w-5 text-indigo-400" />
                      <span className="font-medium">{project.name}</span>
                      {isMoving && <Loader2 className="h-4 w-4 animate-spin ml-auto" />}
                    </CardContent>
                  </Card>
                ))}

                <Card
                  className="cursor-pointer hover:border-emerald-500/50 transition-colors border-dashed"
                  onClick={() => setShowCreateForm(true)}
                  data-testid="create-new-project-option"
                >
                  <CardContent className="py-3 flex items-center gap-3">
                    <Plus className="h-5 w-5 text-emerald-400" />
                    <span className="font-medium text-emerald-400">Create New Project</span>
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isMoving || isCreating}
          >
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MoveDialog;
