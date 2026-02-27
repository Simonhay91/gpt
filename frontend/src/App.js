import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { LanguageProvider } from './contexts/LanguageContext';
import './App.css';

// Pages
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ProjectPage from './pages/ProjectPage';
import ChatPage from './pages/ChatPage';
import AdminConfigPage from './pages/AdminConfigPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminUserDetailPage from './pages/AdminUserDetailPage';
import AdminGlobalSourcesPage from './pages/AdminGlobalSourcesPage';
import GlobalSourcesPage from './pages/GlobalSourcesPage';
// Enterprise Knowledge Architecture Pages
import AdminDepartmentsPage from './pages/AdminDepartmentsPage';
import AdminAuditLogsPage from './pages/AdminAuditLogsPage';
import PersonalSourcesPage from './pages/PersonalSourcesPage';
import DepartmentSourcesPage from './pages/DepartmentSourcesPage';
import MyDepartmentsPage from './pages/MyDepartmentsPage';
import NewsPage from './pages/NewsPage';
import MyGptPromptPage from './pages/MyGptPromptPage';

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="spinner" />
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

// Public Route (redirect if logged in)
const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="spinner" />
      </div>
    );
  }
  
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

// Admin Route
const AdminRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="spinner" />
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  if (!user.isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={
        <PublicRoute>
          <LoginPage />
        </PublicRoute>
      } />
      
      {/* Protected Routes */}
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <DashboardPage />
        </ProtectedRoute>
      } />
      <Route path="/projects/:projectId" element={
        <ProtectedRoute>
          <ProjectPage />
        </ProtectedRoute>
      } />
      <Route path="/chats/:chatId" element={
        <ProtectedRoute>
          <ChatPage />
        </ProtectedRoute>
      } />
      
      {/* Admin Routes */}
      <Route path="/admin/config" element={
        <AdminRoute>
          <AdminConfigPage />
        </AdminRoute>
      } />
      <Route path="/admin/users" element={
        <AdminRoute>
          <AdminUsersPage />
        </AdminRoute>
      } />
      <Route path="/admin/users/:userId" element={
        <AdminRoute>
          <AdminUserDetailPage />
        </AdminRoute>
      } />
      <Route path="/admin/global-sources" element={
        <AdminRoute>
          <AdminGlobalSourcesPage />
        </AdminRoute>
      } />
      <Route path="/admin/departments" element={
        <AdminRoute>
          <AdminDepartmentsPage />
        </AdminRoute>
      } />
      <Route path="/admin/departments/:departmentId/sources" element={
        <AdminRoute>
          <DepartmentSourcesPage />
        </AdminRoute>
      } />
      <Route path="/departments/:departmentId/sources" element={
        <ProtectedRoute>
          <DepartmentSourcesPage />
        </ProtectedRoute>
      } />
      <Route path="/departments" element={
        <ProtectedRoute>
          <MyDepartmentsPage />
        </ProtectedRoute>
      } />
      <Route path="/admin/audit-logs" element={
        <AdminRoute>
          <AdminAuditLogsPage />
        </AdminRoute>
      } />
      
      {/* User Global Sources Route */}
      <Route path="/global-sources" element={
        <ProtectedRoute>
          <GlobalSourcesPage />
        </ProtectedRoute>
      } />
      
      {/* Personal Sources Route */}
      <Route path="/personal-sources" element={
        <ProtectedRoute>
          <PersonalSourcesPage />
        </ProtectedRoute>
      } />
      
      {/* News Route */}
      <Route path="/news" element={
        <ProtectedRoute>
          <NewsPage />
        </ProtectedRoute>
      } />
      
      {/* My GPT Prompt Route */}
      <Route path="/my-prompt" element={
        <ProtectedRoute>
          <MyGptPromptPage />
        </ProtectedRoute>
      } />
      
      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppRoutes />
          <Toaster 
            position="top-right"
            toastOptions={{
              style: {
                background: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                color: 'hsl(var(--foreground))'
              }
            }}
          />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
