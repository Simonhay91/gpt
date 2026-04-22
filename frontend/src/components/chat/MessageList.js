/**
 * MessageList Component
 * Displays all chat messages with loading state
 */
import React, { useRef, useEffect } from 'react';
import { Bot, Loader2, FileText } from 'lucide-react';
import { ScrollArea } from '../ui/scroll-area';
import Message from './Message';

export const MessageList = ({
  messages,
  isSending,
  projectSources = [],
  onSaveToKnowledge,
  onDownloadImage,
  API
}) => {
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isSending]);

  return (
    <ScrollArea className="flex-1 px-6 py-4">
      {messages.length === 0 ? (
        <EmptyState projectSources={projectSources} />
      ) : (
        <div className="space-y-6 max-w-3xl mx-auto">
          {messages.map((message, index) => (
            <Message
              key={message.id}
              message={message}
              index={index}
              onSaveToKnowledge={onSaveToKnowledge}
              onDownloadImage={onDownloadImage}
              API={API}
              chatHistory={messages.slice(0, index + 1)}
            />
          ))}
          
          {/* Sending indicator */}
          {isSending && (
            <div className="flex gap-4 justify-start animate-slideIn">
              <div className="flex-shrink-0 rounded-full bg-indigo-500/20 p-2 h-fit">
                <Bot className="h-5 w-5 text-indigo-400" />
              </div>
              <div className="bg-secondary px-4 py-3 rounded-2xl rounded-bl-sm">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      )}
    </ScrollArea>
  );
};

// Empty state component
const EmptyState = ({ projectSources }) => (
  <div className="flex flex-col items-center justify-center h-full text-center">
    <div className="rounded-full bg-secondary p-4 mb-4">
      <Bot className="h-8 w-8 text-indigo-400" />
    </div>
    <h3 className="text-lg font-semibold mb-2">Start a conversation</h3>
    <p className="text-muted-foreground max-w-md">
      {projectSources.length > 0 ? (
        <span>
          Select sources above, then ask questions about them.
          <span className="block mt-2 text-indigo-400">
            The AI will cite specific chunks from your documents.
          </span>
        </span>
      ) : (
        <span>
          Upload PDFs, DOCX, TXT files or add URLs to use as context.
          <span className="block mt-2">
            The AI will answer questions based on your sources.
          </span>
        </span>
      )}
    </p>
  </div>
);

export default MessageList;
