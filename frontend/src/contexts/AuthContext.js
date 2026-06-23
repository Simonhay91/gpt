import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);
  // Resolved permission set from backend. ["*"] means admin (all access).
  const [permissions, setPermissions] = useState([]);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchPermissions = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/user/permissions`);
      setPermissions(res.data.permissions || []);
    } catch {
      setPermissions([]);
    }
  }, []);

  const fetchUser = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`);
      setUser(response.data);
      localStorage.setItem('userEmail', response.data.email);
      // Fetch resolved permissions after user is loaded
      await fetchPermissions();
    } catch (error) {
      console.error('Failed to fetch user:', error);
      if (error.response?.status === 401) {
        logout();
      }
    } finally {
      setLoading(false);
    }
  };

  /**
   * Check whether the current user has a specific permission.
   * Admins always return true (they have ["*"]).
   * Usage: hasPermission('global_sources:create')
   */
  const hasPermission = useCallback((perm) => {
    return permissions.includes('*') || permissions.includes(perm);
  }, [permissions]);

  const login = async (email, password) => {
    const response = await axios.post(`${API}/auth/login`, { email, password });
    const { token: newToken, user: userData } = response.data;
    localStorage.setItem('token', newToken);
    localStorage.setItem('userEmail', userData.email);
    axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
    setToken(newToken);
    setUser(userData);
    // Fetch resolved permissions right after login
    try {
      const permRes = await axios.get(`${API}/user/permissions`, {
        headers: { Authorization: `Bearer ${newToken}` },
      });
      setPermissions(permRes.data.permissions || []);
    } catch {
      setPermissions([]);
    }
    return userData;
  };

  const register = async (email, password) => {
    const response = await axios.post(`${API}/auth/register`, { email, password });
    const { token: newToken, user: userData } = response.data;
    localStorage.setItem('token', newToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
    setToken(newToken);
    setUser(userData);
    return userData;
  };

  const changePassword = async (newPassword) => {
    await axios.post(`${API}/auth/change-password`, { new_password: newPassword });
    setUser(prev => ({ ...prev, mustChangePassword: false }));
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
    delete axios.defaults.headers.common['Authorization'];
    setToken(null);
    setUser(null);
    setPermissions([]);
  };

  return (
    <AuthContext.Provider value={{
      user, token, loading,
      permissions, hasPermission,
      login, register, logout, changePassword,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
