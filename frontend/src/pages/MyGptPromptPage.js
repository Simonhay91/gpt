import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { Sparkles, Save, Info } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MyGptPromptPage = () => {
  const [userPrompt, setUserPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadUserPrompt();
  }, []);

  const loadUserPrompt = async () => {
    try {
      const response = await axios.get(`${API}/user/prompt`);
      setUserPrompt(response.data.customPrompt || '');
    } catch (error) {
      console.error('Failed to load prompt:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const saveUserPrompt = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/user/prompt`, { customPrompt: userPrompt.trim() || null });
      toast.success('Custom prompt saved successfully');
    } catch (error) {
      toast.error('Failed to save prompt');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-3xl" data-testid="my-gpt-prompt-page">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/20">
              <Sparkles className="h-7 w-7 text-purple-500" />
            </div>
            My GPT Prompt
          </h1>
          <p className="text-muted-foreground mt-2">
            Customize how AI responds to you across all conversations
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="spinner" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Info Card */}
            <Card className="border-purple-500/30 bg-purple-500/5">
              <CardContent className="py-4">
                <div className="flex items-start gap-3">
                  <Info className="h-5 w-5 text-purple-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium mb-2">How it works</p>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>Your custom prompt is added to every conversation to personalize AI responses.</p>
                      <p>This is <strong>private</strong> and only affects your conversations.</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Prompt Editor */}
            <Card>
              <CardHeader>
                <CardTitle>Custom Instructions</CardTitle>
                <CardDescription>
                  Tell the AI how you want it to respond. This will be included in every chat.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="userPrompt">Your instructions</Label>
                  <Textarea
                    id="userPrompt"
                    placeholder="Examples:
• Always respond in Russian
• Be concise and to the point
• Use code examples when explaining technical concepts
• Format responses with bullet points
• Explain things as if I'm a beginner"
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    className="min-h-[200px] font-mono text-sm"
                    data-testid="user-prompt-textarea"
                  />
                </div>

                <div className="flex items-center justify-between pt-4">
                  <p className="text-xs text-muted-foreground">
                    {userPrompt.length} characters
                  </p>
                  <Button
                    onClick={saveUserPrompt}
                    disabled={isSaving}
                    className="bg-purple-500 hover:bg-purple-600"
                    data-testid="save-prompt-btn"
                  >
                    {isSaving ? (
                      <div className="spinner mr-2" />
                    ) : (
                      <Save className="h-4 w-4 mr-2" />
                    )}
                    Save Prompt
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Examples */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Example prompts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3">
                  {[
                    "Always respond in Russian. Be concise.",
                    "I'm a senior developer. Skip basic explanations, focus on advanced concepts.",
                    "Format all code with comments. Use TypeScript when possible.",
                    "I work in finance. Use relevant terminology and examples.",
                    "Explain things step by step. I'm learning programming."
                  ].map((example, i) => (
                    <button
                      key={i}
                      onClick={() => setUserPrompt(example)}
                      className="text-left p-3 rounded-lg border border-border hover:border-purple-500/50 hover:bg-purple-500/5 transition-colors text-sm"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default MyGptPromptPage;
