/**
 * Message Component
 * Displays a single chat message (user or assistant)
 */
import React from 'react';
import { 
  Bot, 
  User, 
  Copy, 
  Save, 
  Download,
  Globe,
  FileText,
  Quote,
  ImageIcon
} from 'lucide-react';
import { Button } from '../ui/button';
import { toast } from 'sonner';
import AuthImage from '../AuthImage';

// Helper function to render text with clickable links
const renderTextWithLinks = (text) => {
  if (!text) return null;
  
  const urlRegex = /(https?:\/\/[^\s<>"{}|\\^`\[\]]+)/gi;
  const parts = text.split(urlRegex);
  
  return parts.map((part, index) => {
    if (part.match(urlRegex)) {
      return (
        <a
          key={index}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-400 hover:text-indigo-300 underline"
        >
          {part}
        </a>
      );
    }
    return part;
  });
};

// Format time helper
const formatTime = (dateString) => {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
};

export const Message = ({
  message,
  index,
  onSaveToKnowledge,
  onDownloadImage,
  API
}) => {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      toast.success('Copied to clipboard');
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = message.content;
      textArea.style.position = 'fixed';
      textArea.style.left = '-9999px';
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        toast.success('Copied to clipboard');
      } catch (e) {
        toast.error('Failed to copy');
      }
      document.body.removeChild(textArea);
    }
  };

  const handleSaveToKnowledge = async () => {
    try {
      await onSaveToKnowledge(message.content);
      toast.success('Saved to Knowledge ✅');
    } catch (err) {
      toast.error('Failed to save');
    }
  };

  return (
    <div
      className={`flex gap-4 animate-slideIn ${isUser ? 'justify-end' : 'justify-start'}`}
      style={{ animationDelay: `${index * 30}ms` }}
      data-testid={`message-${message.role}-${index}`}
    >
      {/* Assistant Avatar */}
      {isAssistant && (
        <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit">
          <Bot className="h-5 w-5 text-indigo-400" />
        </div>
      )}
      
      <div className={`flex flex-col gap-1 max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Sender name for user messages */}
        {isUser && message.senderName && (
          <span className="text-xs text-muted-foreground px-2">
            {message.senderName}
          </span>
        )}
        
        {/* Generated Image Display */}
        {message.isGeneratedImage && message.imageData ? (
          <div className="space-y-2">
            <div className="relative rounded-lg overflow-hidden border border-indigo-500/30 max-w-md">
              <AuthImage
                imageId={message.imageData.id}
                alt={message.imageData.prompt}
                className="w-full h-auto"
                data-testid={`generated-image-${message.imageData.id}`}
              />
              <div className="absolute top-2 right-2">
                <Button
                  variant="secondary"
                  size="icon"
                  className="h-8 w-8 bg-black/50 hover:bg-black/70"
                  onClick={() => onDownloadImage(message.imageData.id)}
                  data-testid={`download-image-${message.imageData.id}`}
                >
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2 px-2">
              <ImageIcon className="h-3 w-3 text-indigo-400" />
              <span className="text-xs text-muted-foreground truncate max-w-xs">
                {message.imageData.prompt}
              </span>
            </div>
          </div>
        ) : (
          /* Text Message */
          <div className="group relative">
            <div className={`px-4 py-3 rounded-2xl ${
              isUser 
                ? 'bg-primary text-primary-foreground rounded-br-sm' 
                : 'bg-secondary text-secondary-foreground rounded-bl-sm'
            }`}>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {renderTextWithLinks(message.content)}
              </p>
            </div>
            
            {/* Action buttons for assistant messages */}
            {isAssistant && (
              <div className="absolute -bottom-1 -right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 bg-background border border-border shadow-sm"
                  onClick={handleSaveToKnowledge}
                  title="Save to Knowledge"
                  data-testid={`save-message-${index}`}
                >
                  <Save className="h-3.5 w-3.5 text-green-500" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 bg-background border border-border shadow-sm"
                  onClick={handleCopy}
                  data-testid={`copy-message-${index}`}
                >
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </div>
        )}
        
        {/* Auto-ingested URLs indicator */}
        {isUser && message.autoIngestedUrls?.length > 0 && (
          <div className="mt-1 px-2">
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">
              <Globe className="h-3 w-3" />
              {message.autoIngestedUrls.length} URL{message.autoIngestedUrls.length > 1 ? 's' : ''} auto-ingested
            </span>
          </div>
        )}
        
        {/* Citations / Used Sources */}
        {isAssistant && !message.isGeneratedImage && (message.citations?.length > 0 || message.usedSources?.length > 0) && (
          <Citations citations={message.citations} usedSources={message.usedSources} />
        )}
        
        {/* Cache indicator */}
        {message.fromCache && (
          <div className="mt-1 px-2">
            <span className="inline-flex items-center gap-1 text-xs text-amber-500">
              📦 Из кэша 
              {message.cacheInfo?.similarity && (
                <span className="opacity-70">({(message.cacheInfo.similarity * 100).toFixed(0)}%)</span>
              )}
            </span>
          </div>
        )}
        
        {/* Timestamp */}
        <span className="text-xs text-muted-foreground px-1">
          {formatTime(message.createdAt)}
        </span>
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex-shrink-0 rounded-full bg-emerald-500/20 p-2 h-fit">
          <User className="h-5 w-5 text-emerald-400" />
        </div>
      )}
    </div>
  );
};

// Citations sub-component
const Citations = ({ citations, usedSources }) => {
  const items = citations || usedSources || [];
  
  if (items.length === 0) return null;

  return (
    <div className="mt-2 px-2">
      <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
        <Quote className="h-3 w-3" />
        Sources used:
      </div>
      <div className="flex flex-wrap gap-2">
        {citations ? (
          citations.map((citation, cidx) => {
            const isGlobal = citation.sourceType === 'global';
            const bgColor = isGlobal ? 'bg-emerald-500/10' : 'bg-indigo-500/10';
            const textColor = isGlobal ? 'text-emerald-400' : 'text-indigo-400';
            const borderColor = isGlobal ? 'border-emerald-500/20' : 'border-indigo-500/20';
            const Icon = isGlobal ? Globe : FileText;
            
            return (
              <span
                key={cidx}
                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${bgColor} ${textColor} text-xs border ${borderColor}`}
                data-testid={`citation-${cidx}`}
                title={citation.textFragment || citation.sourceName}
              >
                <Icon className="h-3 w-3" />
                <span className="font-medium">
                  {isGlobal ? '🌐 ' : '📁 '}
                  {citation.sourceName.length > 25 
                    ? citation.sourceName.slice(0, 25) + '...' 
                    : citation.sourceName}
                </span>
                {citation.chunks && (
                  <span className="opacity-70">
                    (chunks {Array.isArray(citation.chunks) 
                      ? citation.chunks.map(c => c.index || c).join(', ')
                      : citation.chunks})
                  </span>
                )}
              </span>
            );
          })
        ) : usedSources?.map((source, sidx) => {
          const isGlobal = source.sourceType === 'global';
          const bgColor = isGlobal ? 'bg-emerald-500/10' : 'bg-indigo-500/10';
          const textColor = isGlobal ? 'text-emerald-400' : 'text-indigo-400';
          const borderColor = isGlobal ? 'border-emerald-500/20' : 'border-indigo-500/20';
          const Icon = isGlobal ? Globe : FileText;
          
          return (
            <span
              key={sidx}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded-md ${bgColor} ${textColor} text-xs border ${borderColor}`}
              data-testid={`used-source-${sidx}`}
            >
              <Icon className="h-3 w-3" />
              {isGlobal ? '🌐 ' : '📁 '}
              {source.sourceName.length > 25 
                ? source.sourceName.slice(0, 25) + '...' 
                : source.sourceName}
            </span>
          );
        })}
      </div>
    </div>
  );
};

export default Message;
