import React from 'react';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import {
  Loader2, Send, Plus, Upload, Link, ImageIcon, Save, Brain, Paperclip, X,
  FileText, FileSpreadsheet, File
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
  chat,
  messages,
  isSavingContext,
  onFileUpload,
  onShowSourcePanel,
  onSaveContext,
  onOpenMemory,
  textareaRef,
  plusMenuRef,
  showPlusMenu,
  onTogglePlusMenu,
  // ── Temp file props ──
  tempFile,
  isTempUploading,
  onPaperclipChange,
  onRemoveTempFile,
}) => {
  const canSend = (input.trim() || tempFile) && !isSending;

  return (
    <div className="border-t border-border px-6 py-4 bg-card/50 backdrop-blur">
      <div className="max-w-3xl mx-auto space-y-2">

        {/* ── Temp file preview badge ── */}
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

        <div className="flex gap-3 items-end">
          {/* Plus menu — only for project chats */}
          {!isQuickChat && (
            <div className="relative flex-shrink-0 self-end mb-0.5" ref={plusMenuRef}>
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.md,.png,.jpg,.jpeg"
                onChange={(e) => { onFileUpload(e); onTogglePlusMenu(false); }}
                className="hidden"
                id="chat-input-file"
              />
              <button
                onClick={() => onTogglePlusMenu(prev => !prev)}
                disabled={isUploading}
                className="flex items-center justify-center h-9 w-9 rounded-full border border-border bg-background hover:bg-secondary transition-colors disabled:opacity-50"
                data-testid="chat-plus-btn"
              >
                {isUploading
                  ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  : <Plus className="h-4 w-4 text-muted-foreground" />}
              </button>

              {showPlusMenu && (
                <div className="absolute bottom-11 left-0 z-50 w-52 rounded-xl border border-border bg-card shadow-xl overflow-hidden">
                  <button
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary transition-colors text-left"
                    onClick={() => { document.getElementById('chat-input-file').click(); onTogglePlusMenu(false); }}
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
                      <Link className="h-4 w-4 text-blue-400" />
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
                      <p className="text-xs text-muted-foreground">Save to AI Profile</p>
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
                </div>
              )}
            </div>
          )}

          <Textarea
            ref={textareaRef}
            placeholder={
              tempFile
                ? `Задайте вопрос по файлу "${tempFile.filename}"...`
                : activeSourceIds.length > 0
                  ? "Ask a question about the selected sources..."
                  : "Type your message... (Enter to send, Shift+Enter for new line)"
            }
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={onKeyDown}
            className="min-h-[60px] max-h-[200px] resize-none bg-background flex-1"
            disabled={isSending}
            data-testid="chat-input"
          />

          {/* Paperclip button — temp file attach (always visible) */}
          <div className="flex-shrink-0 self-end mb-0.5">
            <input
              type="file"
              accept=".jpg,.jpeg,.png,.pdf,.xlsx,.xls,.csv,.docx"
              onChange={onPaperclipChange}
              className="hidden"
              id="chat-temp-file-input"
            />
            <button
              onClick={() => document.getElementById('chat-temp-file-input').click()}
              disabled={isTempUploading || isSending}
              className={`flex items-center justify-center h-9 w-9 rounded-full border transition-colors disabled:opacity-50
                ${tempFile
                  ? 'border-amber-500/50 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400'
                  : 'border-border bg-background hover:bg-secondary text-muted-foreground'}`}
              title="Прикрепить файл (временно, только для этого сообщения)"
              data-testid="chat-paperclip-btn"
            >
              {isTempUploading
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Paperclip className="h-4 w-4" />}
            </button>
          </div>

          <Button
            onClick={onSend}
            disabled={!canSend}
            className="btn-hover self-end"
            data-testid="send-message-btn"
          >
            {isSending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
          </Button>
        </div>
      </div>
    </div>
  );
};
