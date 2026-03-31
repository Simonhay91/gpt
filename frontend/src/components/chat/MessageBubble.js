import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import {
  Bot, User, Loader2, Globe, FileText, Quote,
  ImageIcon, Download, MessageSquare, Pencil, Check, X, Copy,
  Save, Globe2, Link, TrendingUp, ChevronDown, ChevronUp
} from 'lucide-react';
import AuthImage from '../AuthImage';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const renderTextWithLinks = (text) => {
  if (!text) return null;
  const urlPattern = /https?:\/\/[^\s<>"{}|\\^`[\]]+/g;
  const parts = [];
  let lastIndex = 0;
  let match;
  while ((match = urlPattern.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const url = match[0];
    parts.push(
      React.createElement('a', {
        key: match.index,
        href: url,
        target: '_blank',
        rel: 'noopener noreferrer',
        className: 'text-indigo-400 hover:text-indigo-300 underline underline-offset-2 break-all',
        onClick: (e) => e.stopPropagation()
      }, url)
    );
    lastIndex = match.index + url.length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length > 0 ? parts : text;
};

export const MessageBubble = ({
  message,
  index,
  messagesCount,
  isEditing,
  editedContent,
  onEditChange,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onSendMessage,
  onViewSource,
  onSaveToProjectMemory,
  onDownloadImage,
  expandedSources,
  onToggleSourceExpansion,
  chatId,
  originalUserMessage,
}) => {
  const [saveDropdownOpen, setSaveDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    if (!saveDropdownOpen) return;
    const handler = () => setSaveDropdownOpen(false);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [saveDropdownOpen]);

  const formatTime = (dateString) =>
    new Date(dateString).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  const isNearBottom = index >= messagesCount * 0.6;

  return (
    <div
      className={`flex gap-4 animate-slideIn ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
      style={{ animationDelay: `${index * 30}ms` }}
      data-testid={`message-${message.role}-${index}`}
    >
      {message.role === 'assistant' && (
        <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit">
          <Bot className="h-5 w-5 text-indigo-400" />
        </div>
      )}

      <div className={`flex flex-col gap-1 max-w-[80%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
        {message.role === 'user' && message.senderName && (
          <span className="text-xs text-muted-foreground px-2">{message.senderName}</span>
        )}

        {/* Generated image */}
        {message.isGeneratedImage && message.imageData ? (
          <div className="space-y-2">
            <div className="relative rounded-lg overflow-hidden border border-indigo-500/30 max-w-md">
              <AuthImage imageId={message.imageData.id} alt={message.imageData.prompt} className="w-full h-auto" data-testid={`generated-image-${message.imageData.id}`} />
              <div className="absolute top-2 right-2">
                <Button variant="secondary" size="icon" className="h-8 w-8 bg-black/50 hover:bg-black/70" onClick={() => onDownloadImage(message.imageData.id)} data-testid={`download-image-${message.imageData.id}`}>
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2 px-2">
              <ImageIcon className="h-3 w-3 text-indigo-400" />
              <span className="text-xs text-muted-foreground truncate max-w-xs">{message.imageData.prompt}</span>
            </div>
          </div>
        ) : (
          <div className={`group relative ${isEditing ? '' : ''}`}>
            {isEditing ? (
              <div className="space-y-2">
                <textarea
                  value={editedContent}
                  onChange={(e) => {
                    onEditChange(e.target.value);
                    e.target.style.height = 'auto';
                    e.target.style.height = e.target.scrollHeight + 'px';
                  }}
                  ref={(el) => { if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px'; } }}
                  style={{
                    width: `${Math.min(Math.max(
                      Math.max(...editedContent.split('\n').map(l => l.length)) * 8.5 + 40, 200
                    ), 560)}px`
                  }}
                  className="px-4 py-3 rounded-2xl bg-primary/10 text-foreground border border-primary/20 focus:border-primary focus:outline-none resize-none overflow-hidden block"
                  autoFocus
                />
                <div className="flex gap-2 justify-end">
                  <Button size="sm" variant="ghost" onClick={onCancelEdit}>
                    <X className="h-4 w-4 mr-1" />Cancel
                  </Button>
                  <Button size="sm" onClick={() => onSaveEdit(message.id)}>
                    <Check className="h-4 w-4 mr-1" />Save
                  </Button>
                </div>
              </div>
            ) : (
              <>
                {/* File upload badge */}
                {message.role === 'user' && message.uploadedFile && (
                  <div className="flex justify-end mb-1">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted border border-border text-xs text-muted-foreground max-w-[260px]" data-testid={`file-badge-${index}`}>
                      <span>{message.uploadedFile.fileType === 'pdf' ? '📄' : message.uploadedFile.fileType === 'excel' ? '📊' : message.uploadedFile.fileType === 'image' ? '🖼️' : message.uploadedFile.fileType === 'doc' ? '📝' : '📎'}</span>
                      <span className="truncate">{message.uploadedFile.name}</span>
                    </span>
                  </div>
                )}

                <div className={`px-4 py-3 rounded-2xl ${message.role === 'user' ? 'bg-primary text-primary-foreground rounded-br-sm' : 'bg-secondary text-secondary-foreground rounded-bl-sm'}`}>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{renderTextWithLinks(message.content)}</p>
                </div>

                {/* User edit button */}
                {message.role === 'user' && (
                  <div className="absolute -bottom-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="icon" className="h-7 w-7 bg-background border border-border shadow-sm" onClick={() => onStartEdit(message)} title="Edit message">
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}

                {/* Assistant action buttons */}
                {message.role === 'assistant' && (
                  <div className="absolute -bottom-1 -right-1 flex gap-1" style={{ transition: 'none' }}>
                    {/* Save dropdown */}
                    <div className="relative" ref={dropdownRef} style={{ transition: 'none' }}>
                      <Button
                        variant="ghost" size="icon"
                        className="h-7 w-7 bg-background border border-border shadow-sm"
                        onClick={(e) => { e.stopPropagation(); setSaveDropdownOpen(prev => !prev); }}
                        title="Save"
                        data-testid={`save-message-${index}`}
                      >
                        <Save className="h-3.5 w-3.5 text-green-500" />
                      </Button>

                      {saveDropdownOpen && (
                        <div
                          className="absolute z-50 min-w-[160px] rounded-md border border-border bg-background shadow-lg py-1"
                          style={{ [isNearBottom ? 'bottom' : 'top']: '110%', right: 0, transition: 'none' }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
                            data-testid={`save-to-memory-${index}`}
                            onClick={() => { setSaveDropdownOpen(false); onSaveToProjectMemory(message.content); }}
                          >
                            <span>💾</span><span>Project Memory</span>
                          </button>
                          <button
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
                            data-testid={`save-to-sources-${index}`}
                            onClick={async () => {
                              setSaveDropdownOpen(false);
                              try {
                                await axios.post(`${API}/save-to-knowledge`, { content: message.content, chatId });
                                toast.success('Saved to My Sources ✅');
                              } catch { toast.error('Failed to save'); }
                            }}
                          >
                            <span>📎</span><span>My Sources</span>
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Copy button */}
                    <Button
                      variant="ghost" size="icon"
                      className="h-7 w-7 bg-background border border-border shadow-sm"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(message.content);
                          toast.success('Copied to clipboard');
                        } catch {
                          const textArea = document.createElement('textarea');
                          textArea.value = message.content;
                          textArea.style.cssText = 'position:fixed;left:-9999px';
                          document.body.appendChild(textArea);
                          textArea.select();
                          try { document.execCommand('copy'); toast.success('Copied to clipboard'); }
                          catch { toast.error('Failed to copy'); }
                          document.body.removeChild(textArea);
                        }
                      }}
                      data-testid={`copy-message-${index}`}
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Auto-ingested URLs */}
        {message.role === 'user' && message.autoIngestedUrls?.length > 0 && (
          <div className="mt-1 px-2">
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">
              <Globe className="h-3 w-3" />
              {message.autoIngestedUrls.length} URL{message.autoIngestedUrls.length > 1 ? 's' : ''} auto-ingested
            </span>
          </div>
        )}

        {/* Competitor info */}
        {message.role === 'assistant' && message.competitorInfo && (
          <div className="mt-2 px-2">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <TrendingUp className="h-4 w-4 text-orange-400" />
              <div className="flex-1">
                <p className="text-xs font-medium text-orange-400">Competitor Data Used</p>
                <p className="text-xs text-muted-foreground">{message.competitorInfo.competitor_name} - {message.competitorInfo.product_title}</p>
              </div>
            </div>
          </div>
        )}

        {/* Citations / Used Sources */}
        {message.role === 'assistant' && !message.isGeneratedImage && (message.citations?.length > 0 || message.usedSources?.length > 0) && (
          <div className="mt-2 px-2">
            <button
              onClick={() => onToggleSourceExpansion(message.id)}
              className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full py-1 px-2 rounded hover:bg-secondary/50"
              data-testid={`toggle-sources-${index}`}
            >
              <Quote className="h-3 w-3" />
              <span className="font-medium">Sources ({(message.citations || message.usedSources)?.length})</span>
              {expandedSources[message.id] ? <ChevronUp className="h-3 w-3 ml-auto" /> : <ChevronDown className="h-3 w-3 ml-auto" />}
            </button>
            {expandedSources[message.id] && (
              <div className="flex flex-wrap gap-2 mt-2 animate-slideIn">
                {message.citations
                  ? message.citations.map((citation, cidx) => {
                      const isGlobal = citation.sourceType === 'global';
                      return (
                        <button
                          key={cidx}
                          onClick={() => onViewSource(citation.sourceId, citation.sourceName)}
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs border cursor-pointer hover:opacity-80 transition-opacity ${isGlobal ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'}`}
                          data-testid={`citation-${cidx}`}
                          title={`Click to view: ${citation.sourceName}`}
                        >
                          {isGlobal ? <Globe className="h-3 w-3" /> : <FileText className="h-3 w-3" />}
                          <span className="font-medium">{isGlobal ? '🌐 ' : '📁 '}{citation.sourceName.length > 25 ? citation.sourceName.slice(0, 25) + '...' : citation.sourceName}</span>
                          {citation.chunks && <span className="opacity-70">(chunks {Array.isArray(citation.chunks) ? citation.chunks.map(c => c.index || c).join(', ') : citation.chunks})</span>}
                        </button>
                      );
                    })
                  : message.usedSources?.map((source, sidx) => {
                      const isGlobal = source.sourceType === 'global';
                      return (
                        <button
                          key={sidx}
                          onClick={() => onViewSource(source.sourceId, source.sourceName)}
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs border cursor-pointer hover:opacity-80 transition-opacity ${isGlobal ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'}`}
                          data-testid={`used-source-${sidx}`}
                          title={`Click to view: ${source.sourceName}`}
                        >
                          {isGlobal ? <Globe className="h-3 w-3" /> : <FileText className="h-3 w-3" />}
                          {isGlobal ? '🌐 ' : '📁 '}{source.sourceName.length > 25 ? source.sourceName.slice(0, 25) + '...' : source.sourceName}
                        </button>
                      );
                    })
                }
              </div>
            )}
          </div>
        )}

        {/* Web sources */}
        {message.role === 'assistant' && message.web_sources?.length > 0 && (
          <div className="mt-2 px-2">
            <div className="flex flex-wrap gap-1.5">
              {message.web_sources.map((webSource, idx) => (
                <a key={idx} href={webSource.url} target="_blank" rel="noopener noreferrer" title={webSource.url}
                  className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-blue-500/10 text-blue-400 text-xs border border-blue-500/20 hover:bg-blue-500/20 transition-colors max-w-[220px]">
                  <Globe2 className="h-3 w-3 flex-shrink-0" />
                  <span className="truncate">{webSource.title || (() => { try { return new URL(webSource.url).hostname; } catch { return webSource.url; } })()}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Fetched URL indicators */}
        {message.role === 'assistant' && message.fetchedUrls?.length > 0 && (
          <div className="mt-2 px-2">
            <div className="flex flex-wrap gap-1.5" data-testid="fetched-urls-indicator">
              {message.fetchedUrls.map((url, idx) => {
                let hostname = url;
                try { hostname = new URL(url).hostname; } catch {}
                return (
                  <a key={idx} href={url} target="_blank" rel="noopener noreferrer" title={url}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-sky-500/10 text-sky-400 text-xs border border-sky-500/20 hover:bg-sky-500/20 transition-colors"
                    data-testid={`fetched-url-badge-${idx}`}>
                    <Link className="h-3 w-3 flex-shrink-0" />
                    <span className="truncate max-w-[160px]">URL прочитан: {hostname}</span>
                  </a>
                );
              })}
            </div>
          </div>
        )}

        {/* Excel result */}
        {message.role === 'assistant' && message.excel_preview && message.excel_file_id && (
          <div className="mt-2 px-2" data-testid={`excel-result-block-${index}`}>
            <button
              onClick={async (e) => {
                e.stopPropagation();
                try {
                  const response = await axios.get(
                    `${process.env.REACT_APP_BACKEND_URL}/api/excel/download/${message.excel_file_id}`,
                    { responseType: 'blob' }
                  );
                  const url = window.URL.createObjectURL(new Blob([response.data]));
                  const link = document.createElement('a');
                  link.href = url;
                  link.setAttribute('download', 'result.xlsx');
                  document.body.appendChild(link);
                  link.click();
                  link.remove();
                  window.URL.revokeObjectURL(url);
                } catch { toast.error('Не удалось скачать файл'); }
              }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-green-500/30 bg-green-500/10 hover:bg-green-500/20 text-green-400 text-xs font-medium transition-colors"
              data-testid={`excel-download-chat-${index}`}
            >
              <Download className="h-3.5 w-3.5" />
              Скачать Excel ({message.excel_preview.total_rows} строк)
            </button>
          </div>
        )}

        {/* Excel confirmation button — shown when AI asked clarifying questions before generating */}
        {message.role === 'assistant' && message.is_excel_clarification && !message.excel_file_id && originalUserMessage && (
          <div className="mt-3 px-2" data-testid={`excel-confirm-block-${index}`}>
            <div className="p-3 rounded-lg bg-green-50 dark:bg-green-500/10 border border-green-300 dark:border-green-500/20">
              <div className="flex items-start gap-2 mb-3">
                <MessageSquare className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm font-medium text-green-800 dark:text-green-300">
                  Ответьте на вопросы выше или нажмите кнопку для генерации сразу
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onSendMessage(`__CONFIRM_EXCEL__ ${originalUserMessage}`)}
                className="bg-green-100 dark:bg-green-500/20 border-green-400 dark:border-green-500/30 text-green-800 dark:text-green-200 hover:bg-green-200 dark:hover:bg-green-500/30"
                data-testid={`excel-confirm-btn-${index}`}
              >
                Да, генерируй Excel
              </Button>
            </div>
          </div>
        )}

        {/* Clarifying questions */}
        {message.role === 'assistant' && message.clarifying_question && message.clarifying_options?.length > 0 && (
          <div className="mt-3 px-2">
            <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-300 dark:border-amber-500/20">
              <div className="flex items-start gap-2 mb-3">
                <MessageSquare className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm font-medium text-amber-800 dark:text-amber-300">{message.clarifying_question}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {message.clarifying_options.map((option, idx) => (
                  <Button
                    key={idx}
                    variant="outline"
                    size="sm"
                    onClick={() => onSendMessage(option)}
                    className="bg-amber-100 dark:bg-amber-500/20 border-amber-400 dark:border-amber-500/30 text-amber-800 dark:text-amber-200 hover:bg-amber-200 dark:hover:bg-amber-500/30"
                  >
                    {option}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Cache indicator */}
        {message.fromCache && (
          <div className="mt-1 px-2">
            <span className="inline-flex items-center gap-1 text-xs text-amber-500">
              📦 Из кэша {message.cacheInfo?.similarity && <span className="opacity-70">({(message.cacheInfo.similarity * 100).toFixed(0)}%)</span>}
            </span>
          </div>
        )}

        <span className="text-xs text-muted-foreground px-1">{formatTime(message.createdAt)}</span>
      </div>

      {message.role === 'user' && (
        <div className="flex-shrink-0 rounded-full bg-emerald-500/20 p-2 h-fit">
          <User className="h-5 w-5 text-emerald-400" />
        </div>
      )}
    </div>
  );
};
