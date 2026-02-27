import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Building2, FileText, Users, Crown, AlertCircle } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MyDepartmentsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [departments, setDepartments] = useState([]);
  const [pendingCounts, setPendingCounts] = useState({});
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [deptsRes, pendingRes] = await Promise.all([
        axios.get(`${API}/users/me/departments`),
        axios.get(`${API}/departments/pending-count`)
      ]);
      
      setDepartments(deptsRes.data);
      
      // Create map of departmentId -> pending count
      const counts = {};
      for (const item of pendingRes.data.departments || []) {
        counts[item.departmentId] = item.count;
      }
      setPendingCounts(counts);
    } catch (error) {
      toast.error('Не удалось загрузить данные');
    } finally {
      setIsLoading(false);
    }
  };

  // Filter to only show departments where user is manager
  const managedDepartments = departments.filter(d => d.isManager);

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <div className="spinner" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="my-departments-page">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Building2 className="h-8 w-8 text-indigo-400" />
            Мои отделы
          </h1>
          <p className="text-muted-foreground mt-2">
            Отделы где вы являетесь менеджером
          </p>
        </div>

        {managedDepartments.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">Нет отделов</h3>
              <p className="text-muted-foreground text-center">
                Вы не являетесь менеджером ни одного отдела
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {managedDepartments.map((dept) => {
              const pending = pendingCounts[dept.id] || 0;
              
              return (
                <Card key={dept.id} className="card-hover" data-testid={`my-dept-${dept.id}`}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="rounded-lg bg-indigo-500/20 p-2">
                          <Building2 className="h-5 w-5 text-indigo-400" />
                        </div>
                        <div>
                          <CardTitle className="text-lg">{dept.name}</CardTitle>
                          <div className="flex items-center gap-1 text-xs text-amber-500 mt-1">
                            <Crown className="h-3 w-3" />
                            Manager
                          </div>
                        </div>
                      </div>
                      {pending > 0 && (
                        <div className="flex items-center gap-1 bg-amber-500/20 text-amber-500 px-2 py-1 rounded-full text-xs font-medium">
                          <AlertCircle className="h-3 w-3" />
                          {pending} ожидают
                        </div>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Button
                      className="w-full"
                      onClick={() => navigate(`/departments/${dept.id}/sources`)}
                    >
                      <FileText className="h-4 w-4 mr-2" />
                      Управление источниками
                      {pending > 0 && (
                        <span className="ml-2 bg-amber-500 text-white text-xs px-2 py-0.5 rounded-full">
                          {pending}
                        </span>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default MyDepartmentsPage;
