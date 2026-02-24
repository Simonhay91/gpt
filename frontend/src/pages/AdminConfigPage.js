import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { Settings, Bot, FileCode, Save, ArrowLeft, Shield, Clock } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminConfigPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [model, setModel] = useState('');
  const [developerPrompt, setDeveloperPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!user?.isAdmin) {
      toast.error('Admin access required');
      navigate('/dashboard');
      return;
    }
    fetchConfig();
  }, [user, navigate]);

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API}/admin/config`);
      setConfig(response.data);
      setModel(response.data.model);
      setDeveloperPrompt(response.data.developerPrompt);
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error('Admin access required');
        navigate('/dashboard');
      } else {
        toast.error('Failed to load configuration');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const saveConfig = async () => {
    setIsSaving(true);
    try {
      const response = await axios.put(`${API}/admin/config`, {
        model: model.trim(),
        developerPrompt: developerPrompt.trim()
      });
      setConfig(response.data);
      toast.success('Configuration saved successfully');
    } catch (error) {
      toast.error('Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
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
      <div className="p-6 lg:p-8" data-testid="admin-config-page">
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
          
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-indigo-500/20 p-3">
              <Settings className="h-6 w-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Admin Configuration</h1>
              <p className="text-muted-foreground mt-1 flex items-center gap-2">
                <Shield className="h-4 w-4" />
                Global GPT settings for all users
              </p>
            </div>
          </div>
        </div>

        {/* Config Info */}
        {config && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-6 bg-secondary/50 px-4 py-2 rounded-lg w-fit">
            <Clock className="h-4 w-4" />
            Last updated: {formatDate(config.updatedAt)}
          </div>
        )}

        {/* Tabs */}
        <Tabs defaultValue="model" className="max-w-3xl">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="model" data-testid="model-tab">
              <Bot className="mr-2 h-4 w-4" />
              Model Config
            </TabsTrigger>
            <TabsTrigger value="prompt" data-testid="prompt-tab">
              <FileCode className="mr-2 h-4 w-4" />
              System Prompt
            </TabsTrigger>
          </TabsList>

          <TabsContent value="model">
            <Card>
              <CardHeader>
                <CardTitle className="text-xl">Model Configuration</CardTitle>
                <CardDescription>
                  Set the OpenAI model used for all conversations
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="model">Model Name</Label>
                  <Input
                    id="model"
                    placeholder="gpt-4.1-mini"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="font-mono"
                    data-testid="model-input"
                  />
                  <p className="text-sm text-muted-foreground">
                    Common models: gpt-4.1-mini, gpt-4.1, gpt-4o, gpt-4.1-nano
                  </p>
                </div>

                <Button
                  onClick={saveConfig}
                  disabled={isSaving}
                  className="btn-hover"
                  data-testid="save-model-btn"
                >
                  {isSaving ? (
                    <div className="spinner mr-2" />
                  ) : (
                    <Save className="mr-2 h-4 w-4" />
                  )}
                  Save Changes
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="prompt">
            <Card>
              <CardHeader>
                <CardTitle className="text-xl">Developer/System Prompt</CardTitle>
                <CardDescription>
                  This prompt is sent with every request to define the AI's behavior
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="developerPrompt">System Prompt</Label>
                  <Textarea
                    id="developerPrompt"
                    placeholder="You are a helpful assistant..."
                    value={developerPrompt}
                    onChange={(e) => setDeveloperPrompt(e.target.value)}
                    className="min-h-[200px] font-mono text-sm"
                    data-testid="prompt-input"
                  />
                  <p className="text-sm text-muted-foreground">
                    This prompt shapes the AI's personality and behavior for all users
                  </p>
                </div>

                <Button
                  onClick={saveConfig}
                  disabled={isSaving}
                  className="btn-hover"
                  data-testid="save-prompt-btn"
                >
                  {isSaving ? (
                    <div className="spinner mr-2" />
                  ) : (
                    <Save className="mr-2 h-4 w-4" />
                  )}
                  Save Changes
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Warning */}
        <div className="mt-8 max-w-3xl">
          <Card className="border-amber-500/50 bg-amber-500/5">
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                <Shield className="h-5 w-5 text-amber-500 mt-0.5" />
                <div>
                  <h4 className="font-medium text-amber-500">Important</h4>
                  <p className="text-sm text-muted-foreground mt-1">
                    Changes to these settings will affect all users immediately. 
                    The model and system prompt are shared across all projects and chats.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default AdminConfigPage;
