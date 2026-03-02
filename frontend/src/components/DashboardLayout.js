import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useLanguage } from '../contexts/LanguageContext';
import { Button } from './ui/button';
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
  Lock,
  Newspaper,
  Languages,
  FileSpreadsheet
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DashboardLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme, isDark } = useTheme();
  const { language, toggleLanguage, t } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  
  // Pending approvals count for managers
  const [pendingCount, setPendingCount] = useState(0);
  const [isManager, setIsManager] = useState(false);

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

  const navItems = [
    {
      name: t('nav.dashboard'),
      path: '/dashboard',
      icon: LayoutDashboard
    },
    {
      name: t('nav.techNews'),
      path: '/news',
      icon: Newspaper
    },
    {
      name: t('nav.mySources'),
      path: '/personal-sources',
      icon: Lock
    },
    {
      name: t('nav.myGptPrompt'),
      path: '/my-prompt',
      icon: Sparkles
    }
  ];

  if (user?.isAdmin) {
    navItems.push({
      name: t('nav.users'),
      path: '/admin/users',
      icon: Users
    });
    navItems.push({
      name: t('nav.departments'),
      path: '/admin/departments',
      icon: Building2,
      badge: pendingCount > 0 ? pendingCount : null
    });
    navItems.push({
      name: t('nav.globalSources'),
      path: '/admin/global-sources',
      icon: Globe2
    });
    navItems.push({
      name: t('nav.auditLogs'),
      path: '/admin/audit-logs',
      icon: ScrollText
    });
    navItems.push({
      name: t('nav.gptConfig'),
      path: '/admin/config',
      icon: Settings
    });
  } else {
    // Non-admin users: always show Departments link for managers
    navItems.push({
      name: t('nav.departments'),
      path: '/departments',
      icon: Building2,
      badge: pendingCount > 0 ? pendingCount : null
    });
    
    if (user?.canEditGlobalSources) {
      // Non-admin users with global sources permission
      navItems.push({
        name: t('nav.globalSources'),
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
          <span className="font-bold tracking-tight">PLANET KNOWLEDGE</span>
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
        </nav>

        {/* User Section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-border">
          {/* Language Toggle */}
          <div className="flex items-center justify-between mb-3 px-1">
            <span className="text-sm text-muted-foreground">{t('common.language')}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={toggleLanguage}
              className="gap-2 h-8"
              data-testid="language-toggle-btn"
            >
              <Languages className="h-4 w-4" />
              {language === 'ru' ? 'RU' : 'EN'}
            </Button>
          </div>

          {/* Theme Toggle */}
          <div className="flex items-center justify-between mb-4 px-1">
            <span className="text-sm text-muted-foreground">{t('nav.theme')}</span>
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
                  {t('nav.light')}
                </>
              ) : (
                <>
                  <Moon className="h-4 w-4" />
                  {t('nav.dark')}
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
                {user?.isAdmin ? `👑 ${t('role.administrator')}` : isManager ? `📋 ${t('role.manager')}` : t('role.user')}
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
            {t('nav.signOut')}
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
    </div>
  );
};

export default DashboardLayout;
