import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useLanguage } from '../contexts/LanguageContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { LogIn, Mail, Lock, Globe, Sun, Moon, Languages } from 'lucide-react';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const { toggleTheme, isDark } = useTheme();
  const { language, toggleLanguage, t } = useLanguage();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      await login(email, password);
      toast.success(t('login.welcome'));
      navigate('/dashboard');
    } catch (error) {
      const message = error.response?.data?.detail || t('login.failed');
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Theme Toggle - Top Right */}
      <div className="fixed top-4 right-4 z-50 flex gap-2">
        <Button
          variant="outline"
          size="icon"
          onClick={toggleLanguage}
          className="h-10 w-10 rounded-full"
          data-testid="login-language-toggle"
        >
          <Languages className="h-5 w-5" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          onClick={toggleTheme}
          className="h-10 w-10 rounded-full"
          data-testid="login-theme-toggle"
        >
          {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
      </div>

      {/* Left side - Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-md animate-fadeIn">
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-2">
              <Globe className="h-6 w-6 text-indigo-500" />
              <span className="text-xl font-bold tracking-tight">PLANET KNOWLEDGE</span>
            </div>
            <p className="text-muted-foreground text-sm">
              {t('login.subtitle')}
            </p>
          </div>

          <Card className="border-border bg-card/50 backdrop-blur">
            <CardHeader className="space-y-1 pb-4">
              <CardTitle className="text-2xl font-bold tracking-tight">{t('login.title')}</CardTitle>
              <CardDescription>
                {t('login.subtitle')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-sm font-medium">
                    {t('login.email')}
                  </Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="pl-10 bg-background border-border"
                      required
                      data-testid="login-email-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" className="text-sm font-medium">
                    Password
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="password"
                      type="password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="pl-10 bg-background border-border"
                      required
                      data-testid="login-password-input"
                    />
                  </div>
                </div>

                <Button 
                  type="submit" 
                  className="w-full btn-hover"
                  disabled={isLoading}
                  data-testid="login-submit-btn"
                >
                  {isLoading ? (
                    <div className="spinner mr-2" />
                  ) : (
                    <LogIn className="mr-2 h-4 w-4" />
                  )}
                  Sign in
                </Button>
              </form>

              <div className="mt-6 text-center text-sm text-muted-foreground">
                Contact your administrator if you need an account
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Right side - Image */}
      <div className="hidden lg:flex flex-1 auth-background relative">
        <div className="absolute inset-0 bg-background/60 backdrop-blur-sm" />
        <div className="relative z-10 flex items-center justify-center w-full p-12">
          <div className="text-center max-w-md">
            <blockquote className="text-xl font-medium leading-relaxed text-foreground/90 mb-4">
              "One GPT configuration, infinite possibilities. Build isolated projects with shared intelligence."
            </blockquote>
            <p className="text-sm text-muted-foreground">— Planet Knowledge</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
