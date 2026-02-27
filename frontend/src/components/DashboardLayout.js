import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { toast } from 'sonner';
import axios from 'axios';
import { 
  LayoutDashboard, 
  Settings, 
  LogOut, 
  Globe, 
  Globe2,
  Menu, 
  X,
  ChevronRight,
  Users,
  Sun,
  Moon,
  Sparkles,
  Building2,
  ScrollText,
  Lock
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DashboardLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme, isDark } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  
  // Pending approvals count for managers
  const [pendingCount, setPendingCount] = useState(0);
  const [isManager, setIsManager] = useState(false);
  
  // User Prompt State
  const [isPromptDialogOpen, setIsPromptDialogOpen] = useState(false);
  const [userPrompt, setUserPrompt] = useState('');
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  const [promptLoaded, setPromptLoaded] = useState(false);

  // Fetch pending approvals count for managers
  useEffect(() => {
    const fetchPendingCount = async () => {
      try {
        const response = await axios.get(`${API}/departments/pending-count`);
        setPendingCount(response.data.count || 0);
        setIsManager(response.data.isManager || false);
      } catch (error) {
        // Silently fail - user might not be a manager
        setPendingCount(0);
        setIsManager(false);
      }
    };
    
    if (user) {
      fetchPendingCount();
      // Refresh every 60 seconds
      const interval = setInterval(fetchPendingCount, 60000);
      return () => clearInterval(interval);
    }
  }, [user]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const loadUserPrompt = async () => {
    if (promptLoaded) return;
    try {
      const response = await axios.get(`${API}/user/prompt`);
      setUserPrompt(response.data.customPrompt || '');
      setPromptLoaded(true);
    } catch (error) {
      console.error('Failed to load prompt');
    }
  };

  const openPromptDialog = () => {
    loadUserPrompt();
    setIsPromptDialogOpen(true);
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

  const navItems = [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: LayoutDashboard
    },
    {
      name: 'My Sources',
      path: '/personal-sources',
      icon: Lock
    }
  ];

  if (user?.isAdmin) {
    navItems.push({
      name: 'Users',
      path: '/admin/users',
      icon: Users
    });
    navItems.push({
      name: 'Departments',
      path: '/admin/departments',
      icon: Building2,
      badge: pendingCount > 0 ? pendingCount : null
    });
    navItems.push({
      name: 'Global Sources',
      path: '/admin/global-sources',
      icon: Globe2
    });
    navItems.push({
      name: 'Audit Logs',
      path: '/admin/audit-logs',
      icon: ScrollText
    });
    navItems.push({
      name: 'GPT Config',
      path: '/admin/config',
      icon: Settings
    });
  } else {
    // Non-admin users: show Departments link if they are managers
    if (isManager) {
      navItems.push({
        name: 'Departments',
        path: '/departments',
        icon: Building2,
        badge: pendingCount > 0 ? pendingCount : null
      });
    }
    
    if (user?.canEditGlobalSources) {
      // Non-admin users with global sources permission
      navItems.push({
        name: 'Global Sources',
        path: '/global-sources',
        icon: Globe2
      });
    }
  }

  const isActive = (path) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  return (
    <div className="min-h-screen bg-background" data-testid="dashboard-layout">
      {/* Mobile Menu Button */}
      <div className="lg:hidden fixed top-4 left-4 z-50">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          data-testid="mobile-menu-btn"
        >
          {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>
      </div>

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-card/80 backdrop-blur-xl border-r border-border
        transform transition-transform duration-300 ease-in-out
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:translate-x-0
      `} data-testid="sidebar">
        {/* Logo */}
        <div className="h-16 flex items-center gap-2 px-6 border-b border-border">
          <Globe className="h-5 w-5 text-indigo-500" />
          <span className="font-bold tracking-tight">PLANET GPT</span>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                  transition-all duration-200
                  ${active 
                    ? 'bg-primary text-primary-foreground' 
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  }
                `}
                data-testid={`nav-${item.name.toLowerCase().replace(' ', '-')}`}
              >
                <Icon className="h-4 w-4" />
                <span className="flex-1">{item.name}</span>
                {item.badge && (
                  <span className="bg-amber-500 text-white text-xs font-bold px-2 py-0.5 rounded-full min-w-[20px] text-center">
                    {item.badge}
                  </span>
                )}
                {active && !item.badge && <ChevronRight className="h-4 w-4 ml-auto" />}
              </Link>
            );
          })}
          
          {/* My GPT Prompt Button */}
          <button
            onClick={openPromptDialog}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium w-full
              text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-all duration-200"
            data-testid="nav-my-gpt-prompt"
          >
            <Sparkles className="h-4 w-4" />
            My GPT Prompt
          </button>
        </nav>

        {/* User Section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-border">
          {/* Theme Toggle */}
          <div className="flex items-center justify-between mb-4 px-1">
            <span className="text-sm text-muted-foreground">Theme</span>
            <Button
              variant="outline"
              size="sm"
              onClick={toggleTheme}
              className="gap-2 h-8"
              data-testid="theme-toggle-btn"
            >
              {isDark ? (
                <>
                  <Sun className="h-4 w-4" />
                  Light
                </>
              ) : (
                <>
                  <Moon className="h-4 w-4" />
                  Dark
                </>
              )}
            </Button>
          </div>

          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white font-medium">
              {user?.email?.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.email}</p>
              <p className="text-xs text-muted-foreground">
                {user?.isAdmin ? '👑 Administrator' : pendingCount > 0 ? '📋 Manager' : 'User'}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start text-muted-foreground hover:text-foreground"
            onClick={handleLogout}
            data-testid="logout-btn"
          >
            <LogOut className="mr-2 h-4 w-4" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-30 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="lg:pl-64 min-h-screen">
        <div className="h-16 lg:hidden" /> {/* Spacer for mobile */}
        {children}
      </main>

      {/* My GPT Prompt Dialog */}
      <Dialog open={isPromptDialogOpen} onOpenChange={setIsPromptDialogOpen}>
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
    </div>
  );
};

export default DashboardLayout;
