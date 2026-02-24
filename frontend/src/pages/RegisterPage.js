import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { UserPlus, Mail, Lock, Sparkles } from 'lucide-react';

const RegisterPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    setIsLoading(true);
    
    try {
      await register(email, password);
      toast.success('Account created successfully!');
      navigate('/dashboard');
    } catch (error) {
      const message = error.response?.data?.detail || 'Registration failed';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="register-page">
      {/* Left side - Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-md animate-fadeIn">
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-6 w-6 text-indigo-500" />
              <span className="text-xl font-bold tracking-tight">SHARED GPT</span>
            </div>
            <p className="text-muted-foreground text-sm">
              Create your account to get started
            </p>
          </div>

          <Card className="border-border bg-card/50 backdrop-blur">
            <CardHeader className="space-y-1 pb-4">
              <CardTitle className="text-2xl font-bold tracking-tight">Create account</CardTitle>
              <CardDescription>
                Enter your details to create your account
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-sm font-medium">
                    Email
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
                      data-testid="register-email-input"
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
                      data-testid="register-password-input"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword" className="text-sm font-medium">
                    Confirm Password
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="confirmPassword"
                      type="password"
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="pl-10 bg-background border-border"
                      required
                      data-testid="register-confirm-password-input"
                    />
                  </div>
                </div>

                <Button 
                  type="submit" 
                  className="w-full btn-hover"
                  disabled={isLoading}
                  data-testid="register-submit-btn"
                >
                  {isLoading ? (
                    <div className="spinner mr-2" />
                  ) : (
                    <UserPlus className="mr-2 h-4 w-4" />
                  )}
                  Create account
                </Button>
              </form>

              <div className="mt-6 text-center text-sm">
                <span className="text-muted-foreground">Already have an account? </span>
                <Link 
                  to="/login" 
                  className="text-primary hover:underline font-medium"
                  data-testid="register-login-link"
                >
                  Sign in
                </Link>
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
              "Organize your AI conversations into isolated projects. Share the power, keep the context."
            </blockquote>
            <p className="text-sm text-muted-foreground">— Shared Project GPT</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
