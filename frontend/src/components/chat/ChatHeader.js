/**
 * ChatHeader Component
 * Displays chat title, navigation, and source mode selector
 */
import React from 'react';
import { 
  Menu, 
  ArrowLeft, 
  FolderOpen, 
  MoreVertical, 
  Edit2, 
  Trash2, 
  Move, 
  FileText,
  Loader2,
  ChevronDown
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

export const ChatHeader = ({
  chat,
  isQuickChat,
  isDeleting,
  showSourcePanel,
  setShowSourcePanel,
  setMoveDialogOpen,
  setRenameDialogOpen,
  deleteChat,
  toggleSidebar,
  sourceMode,
  onSourceModeChange,
  isChangingSourceMode
}) => {
  const navigate = useNavigate();

  return (
    <div className="border-b border-border px-4 py-3 flex items-center justify-between bg-card/50 backdrop-blur">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={toggleSidebar} className="lg:hidden">
          <Menu className="h-5 w-5" />
        </Button>
        
        {/* Back to project button */}
        {chat?.projectId && (
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => navigate(`/projects/${chat.projectId}`)}
            className="gap-2 text-muted-foreground hover:text-foreground"
            data-testid="back-to-project-btn"
          >
            <ArrowLeft className="h-4 w-4" />
            <FolderOpen className="h-4 w-4" />
          </Button>
        )}
        
        <div className="flex flex-col">
          <h1 className="font-semibold truncate max-w-[300px]" data-testid="chat-title">
            {chat?.name || 'Chat'}
          </h1>
          {isQuickChat && (
            <span className="text-xs text-amber-500">Quick Chat</span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Source Mode Selector */}
        <Select 
          value={sourceMode} 
          onValueChange={onSourceModeChange}
          disabled={isChangingSourceMode}
        >
          <SelectTrigger 
            className="w-[180px] h-9 text-sm"
            data-testid="source-mode-select"
          >
            {isChangingSourceMode ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SelectValue placeholder="Source Mode" />
            )}
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">
              <div className="flex items-center gap-2">
                <span>🌐</span>
                <span>Все источники</span>
              </div>
            </SelectItem>
            <SelectItem value="my">
              <div className="flex items-center gap-2">
                <span>📁</span>
                <span>Мои источники</span>
              </div>
            </SelectItem>
          </SelectContent>
        </Select>

        {/* Toggle Source Panel - only for project chats */}
        {!isQuickChat && (
          <Button 
            variant={showSourcePanel ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowSourcePanel(!showSourcePanel)}
            className="gap-2"
            data-testid="toggle-sources-btn"
          >
            <FileText className="h-4 w-4" />
            Sources
          </Button>
        )}

        {/* Chat Actions Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" data-testid="chat-menu-btn">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem 
              onClick={() => setRenameDialogOpen(true)}
              data-testid="rename-chat-menu-item"
            >
              <Edit2 className="h-4 w-4 mr-2" />
              Rename
            </DropdownMenuItem>
            
            <DropdownMenuItem 
              onClick={() => setMoveDialogOpen(true)}
              data-testid="move-chat-menu-item"
            >
              <Move className="h-4 w-4 mr-2" />
              {isQuickChat ? 'Move to Project' : 'Move to Another Project'}
            </DropdownMenuItem>
            
            <DropdownMenuSeparator />
            
            <DropdownMenuItem 
              onClick={deleteChat}
              disabled={isDeleting}
              className="text-destructive focus:text-destructive"
              data-testid="delete-chat-menu-item"
            >
              {isDeleting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Delete Chat
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};

export default ChatHeader;
