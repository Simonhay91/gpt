import React from 'react';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import {
  Loader2, Send, Plus, Upload, Link, ImageIcon, Save, Brain, X,
  FileText, FileSpreadsheet, File, MoveRight, Globe, Check
} from 'lucide-react';

const FILE_TYPE_ICON = {
  pdf:   <FileText className="h-3.5 w-3.5 text-red-400" />,
  xlsx:  <FileSpreadsheet className="h-3.5 w-3.5 text-green-400" />,
  xls:   <FileSpreadsheet className="h-3.5 w-3.5 text-green-400" />,
  csv:   <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-400" />,
  docx:  <FileText className="h-3.5 w-3.5 text-blue-400" />,
  image: <File className="h-3.5 w-3.5 text-purple-400" />,
};

export const ChatInput = ({
  input,
  onInputChange,
  onSend,
  onKeyDown,
  isSending,
  isUploading,
  isQuickChat,
  activeSourceIds,
  sourcesExplicitlySet,
  chat,
  messages,
  isSavingContext,
  onFileUpload,
  onShowSourcePanel,
  onSaveContext,
  onOpenMemory,
  onOpenMoveDialog,
  webSearchEnabled,
  onToggleWebSearch,
  textareaRef,
  plusMenuRef,
  showPlusMenu,
  onTogglePlusMenu,
  tempFile,
  isTempUploading,
  onPaperclipChange,
  onRemoveTempFile,
}) => {
  const canSend = (input.trim() || tempFile) && !isSending;

  return (
    <div className="px-4 py-3 bg-card/50 backdrop-blur">
      <div className="max-w-3xl mx-auto space-y-2">

        {/* Temp file preview badge */}
        {(tempFile || isTempUploading) && (
          <div className="flex items-center gap-2 px-1">
            {isTempUploading ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Загрузка файла...
              </span>
            ) : tempFile && (
              <span
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs font-medium max-w-xs"
                data-testid="temp-file-badge"
              >
                {FILE_TYPE_ICON[tempFile.fileType] ?? <File className="h-3.5 w-3.5 text-amber-400" />}
                <span className="truncate max-w-[180px]">{tempFile.filename}</span>
                <button
                  onClick={onRemoveTempFile}
                  className="ml-1 hover:text-red-400 transition-colors flex-shrink-0"
                  data-testid="remove-temp-file-btn"
                  title="Удалить прикреплённый файл"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
          </div>
        )}

        <div className="flex gap-2 items-end">
          {/* Plus menu — only for project chats */}
          {!isQuickChat && (
            <div className="relative flex-shrink-0 self-end mb-1" ref={plusMenuRef}>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.pdf,.xlsx,.xls,.csv,.docx"
                onChange={(e) => { onPaperclipChange(e); onTogglePlusMenu(false); }}
                className="hidden"
                id="chat-plus-file-input"
              />
              <button
                onClick={() => onTogglePlusMenu(prev => !prev)}
                disabled={isTempUploading}
                className="flex items-center justify-center h-9 w-9 rounded-full border border-border bg-background hover:bg-secondary transition-colors disabled:opacity-50"
                data-testid="chat-plus-btn"
              >
                {isTempUploading
                  ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  : <Plus className="h-4 w-4 text-muted-foreground" />}
              </button>

              {showPlusMenu && (
                <div className="absolute bottom-11 left-0 z-50 w-52 rounded-xl border border-border bg-card shadow-xl overflow-hidden">
                  <button
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                    onClick={() => { document.getElementById('chat-plus-file-input').click(); onTogglePlusMenu(false); }}
                  >
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-indigo-500/15">
                      <Upload className="h-4 w-4 text-indigo-400" />
                    </div>
                    <div>
                      <p className="font-medium">Upload File</p>
                      <p className="text-xs text-muted-foreground">PDF, DOCX, XLSX, IMG</p>
                    </div>
                  </button>

                  <button
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                    onClick={() => { onShowSourcePanel(); onTogglePlusMenu(false); }}
                  >
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-blue-500/15">
                      <FileText className="h-4 w-4 text-blue-400" />
                    </div>
                    <div>
                      <p className="font-medium">My Sources</p>
                      <p className="text-xs text-muted-foreground">
                        {sourcesExplicitlySet
                          ? (activeSourceIds?.length > 0 ? `${activeSourceIds.length} active` : 'none selected')
                          : 'all active'}
                      </p>
                    </div>
                  </button>

                  <button
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                    onClick={() => { onShowSourcePanel(); onTogglePlusMenu(false); }}
                  >
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-cyan-500/15">
                      <Link className="h-4 w-4 text-cyan-400" />
                    </div>
                    <div>
                      <p className="font-medium">Add URL</p>
                      <p className="text-xs text-muted-foreground">Web page or article</p>
                    </div>
                  </button>

                  {chat?.projectId && (
                    <button
                      className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                      onClick={() => { onTogglePlusMenu(false); document.querySelector('[data-testid="generate-image-btn"]')?.click(); }}
                    >
                      <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-purple-500/15">
                        <ImageIcon className="h-4 w-4 text-purple-400" />
                      </div>
                      <div>
                        <p className="font-medium">Generate Image</p>
                        <p className="text-xs text-muted-foreground">AI image generation</p>
                      </div>
                    </button>
                  )}

                  <button
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                    onClick={() => { onSaveContext(); onTogglePlusMenu(false); }}
                    disabled={isSavingContext || messages.length === 0}
                  >
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-emerald-500/15">
                      <Save className="h-4 w-4 text-emerald-400" />
                    </div>
                    <div>
                      <p className="font-medium">Save Context</p>
                      <p className="text-xs text-muted-foreground">→ AI Profile (not Project Memory)</p>
                    </div>
                  </button>

                  {!isQuickChat && (
                    <button
                      className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                      onClick={() => { onOpenMemory(); onTogglePlusMenu(false); }}
                      disabled={messages.length === 0}
                    >
                      <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-violet-500/15">
                        <Brain className="h-4 w-4 text-violet-400" />
                      </div>
                      <div>
                        <p className="font-medium">Project Memory</p>
                        <p className="text-xs text-muted-foreground">Save to memory</p>
                      </div>
                    </button>
                  )}

                  <button
                    className={`w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left border-t border-border ${webSearchEnabled ? 'bg-blue-500/5' : ''}`}
                    onClick={() => { onToggleWebSearch(); }}
                  >
                    <div className={`flex items-center justify-center h-8 w-8 rounded-lg ${webSearchEnabled ? 'bg-blue-500/25' : 'bg-blue-500/15'}`}>
                      <Globe className={`h-4 w-4 ${webSearchEnabled ? 'text-blue-400' : 'text-blue-400/60'}`} />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium">Web Search</p>
                      <p className="text-xs text-muted-foreground">{webSearchEnabled ? 'ON — Brave search active' : 'OFF — auto only'}</p>
                    </div>
                    {webSearchEnabled && <Check className="h-4 w-4 text-blue-400 flex-shrink-0" />}
                  </button>

                  <button
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                    onClick={() => { onOpenMoveDialog?.(); onTogglePlusMenu(false); }}
                  >
                    <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-orange-500/15">
                      <MoveRight className="h-4 w-4 text-orange-400" />
                    </div>
                    <div>
                      <p className="font-medium">Move Chat</p>
                      <p className="text-xs text-muted-foreground">Move to another project</p>
                    </div>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Pill input container */}
          <div className={`flex-1 flex items-end gap-2 rounded-2xl border bg-background px-4 py-2 focus-within:ring-2 transition-shadow ${webSearchEnabled ? 'border-blue-500/50 focus-within:ring-blue-500/30' : 'border-border focus-within:ring-indigo-500/30'}`}>
            <Textarea
              ref={textareaRef}
              placeholder={
                tempFile
                  ? `Ask about "${tempFile.filename}"...`
                  : webSearchEnabled
                    ? "Search the web..."
                    : "Message..."
              }
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={onKeyDown}
              className="min-h-[36px] max-h-[160px] resize-none bg-transparent border-0 shadow-none focus-visible:ring-0 p-0 flex-1 text-sm"
              disabled={isSending}
              data-testid="chat-input"
            />
            <Button
              onClick={onSend}
              disabled={!canSend}
              size="icon"
              className="h-8 w-8 rounded-xl flex-shrink-0 self-end"
              data-testid="send-message-btn"
            >
              {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};