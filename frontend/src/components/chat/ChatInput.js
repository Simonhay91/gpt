/**
 * ChatInput Component
 * Text input area for sending messages
 */
import React, { useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';

export const ChatInput = ({
  input,
  setInput,
  onSend,
  isSending,
  activeSourceIds = [],
  placeholder
}) => {
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isSending) {
        onSend();
      }
    }
  };

  const defaultPlaceholder = activeSourceIds.length > 0 
    ? "Ask a question about the selected sources..." 
    : "Type your message... (Enter to send, Shift+Enter for new line)";

  return (
    <div className="border-t border-border px-6 py-4 bg-card/50 backdrop-blur">
      <div className="max-w-3xl mx-auto flex gap-4">
        <Textarea
          ref={textareaRef}
          placeholder={placeholder || defaultPlaceholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          className="min-h-[60px] max-h-[200px] resize-none bg-background"
          disabled={isSending}
          data-testid="chat-input"
        />
        <Button
          onClick={onSend}
          disabled={!input.trim() || isSending}
          className="btn-hover self-end"
          data-testid="send-message-btn"
        >
          {isSending ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Send className="h-5 w-5" />
          )}
        </Button>
      </div>
    </div>
  );
};

export default ChatInput;
