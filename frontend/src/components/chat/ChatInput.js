import React from 'react';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { Loader2, Send, Plus, Upload, Link, ImageIcon, Save, Brain } from 'lucide-react';

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
}) => {
  return (
    <div className="border-t border-border px-6 py-4 bg-card/50 backdrop-blur">
      <div className="max-w-3xl mx-auto space-y-2">
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
              activeSourceIds.length > 0
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

          <Button
            onClick={onSend}
            disabled={!input.trim() || isSending}
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
