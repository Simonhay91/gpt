import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { 
  Newspaper, ExternalLink, MessageSquare, ArrowUp, Clock,
  TrendingUp, Sparkles, RefreshCw, Zap
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const NewsPage = () => {
  const { t } = useLanguage();
  const [stories, setStories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('top');
  const [fetchedAt, setFetchedAt] = useState(null);

  useEffect(() => {
    fetchNews(activeTab);
  }, [activeTab]);

  const fetchNews = async (type) => {
    setIsLoading(true);
    try {
      const response = await axios.get(`${API}/news/${type}?limit=30`);
      setStories(response.data.stories || []);
      setFetchedAt(response.data.fetchedAt);
    } catch (error) {
      console.error('Failed to fetch news:', error);
      setStories([]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTimeAgo = (timestamp) => {
    const seconds = Math.floor(Date.now() / 1000 - timestamp);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const getDomain = (url) => {
    if (!url) return 'news.ycombinator.com';
    try {
      return new URL(url).hostname.replace('www.', '');
    } catch {
      return 'news.ycombinator.com';
    }
  };

  const tabs = [
    { id: 'top', label: t('news.top'), icon: TrendingUp },
    { id: 'best', label: t('news.best'), icon: Sparkles },
    { id: 'new', label: t('news.new'), icon: Zap },
  ];

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8" data-testid="news-page">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <div className="p-2 rounded-lg bg-orange-500/20">
                  <Newspaper className="h-7 w-7 text-orange-500" />
                </div>
                {t('news.title')}
              </h1>
              <p className="text-muted-foreground mt-2">
                {t('news.subtitle')}
              </p>
            </div>
            
            <Button 
              variant="outline" 
              onClick={() => fetchNews(activeTab)}
              disabled={isLoading}
              data-testid="refresh-news-btn"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              {t('news.refresh')}
            </Button>
          </div>

          {/* Tabs */}
          <div className="flex gap-2 mt-6">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <Button
                  key={tab.id}
                  variant={activeTab === tab.id ? 'default' : 'outline'}
                  onClick={() => setActiveTab(tab.id)}
                  className={activeTab === tab.id ? 'bg-orange-500 hover:bg-orange-600' : ''}
                  data-testid={`news-tab-${tab.id}`}
                >
                  <Icon className="h-4 w-4 mr-2" />
                  {tab.label}
                </Button>
              );
            })}
          </div>
        </div>

        {/* Loading */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="spinner" />
          </div>
        ) : stories.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Newspaper className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">{t('news.noStories')}</h3>
              <p className="text-muted-foreground text-center">
                {t('news.tryRefresh')}
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Stories List */}
            <div className="space-y-3">
              {stories.map((story, index) => (
                <Card 
                  key={story.id} 
                  className="card-hover group"
                  data-testid={`news-story-${story.id}`}
                >
                  <CardContent className="py-4">
                    <div className="flex gap-4">
                      {/* Rank */}
                      <div className="flex-shrink-0 w-8 text-center">
                        <span className="text-lg font-bold text-muted-foreground">
                          {index + 1}
                        </span>
                      </div>
                      
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start gap-2">
                          <a
                            href={story.url || story.hnUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-semibold hover:text-orange-500 transition-colors line-clamp-2"
                          >
                            {story.title}
                          </a>
                          <ExternalLink className="h-4 w-4 flex-shrink-0 text-muted-foreground " />
                        </div>
                        
                        <div className="flex items-center flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground mt-2">
                          {/* Domain */}
                          <span className="text-xs px-2 py-0.5 rounded bg-secondary">
                            {getDomain(story.url)}
                          </span>
                          
                          {/* Score */}
                          <span className="flex items-center gap-1">
                            <ArrowUp className="h-3.5 w-3.5 text-orange-500" />
                            {story.score}
                          </span>
                          
                          {/* Comments */}
                          <a 
                            href={story.hnUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 hover:text-orange-500 transition-colors"
                          >
                            <MessageSquare className="h-3.5 w-3.5" />
                            {story.commentsCount}
                          </a>
                          
                          {/* Time */}
                          <span className="flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" />
                            {formatTimeAgo(story.time)}
                          </span>
                          
                          {/* Author */}
                          <span className="text-xs">
                            by <span className="text-foreground/70">{story.author}</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Footer */}
            {fetchedAt && (
              <div className="text-center text-sm text-muted-foreground mt-6">
                {t('news.updated')}: {new Date(fetchedAt).toLocaleString()}
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
};

export default NewsPage;
