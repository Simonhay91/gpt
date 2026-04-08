import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { ScrollArea } from './ui/scroll-area';
import { CHANGELOG, APP_VERSION } from '../data/changelog';
import { CheckCircle2, Sparkles } from 'lucide-react';

const ChangelogModal = ({ open, onClose }) => {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg max-h-[80vh] flex flex-col gap-0 p-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            <DialogTitle>История обновлений</DialogTitle>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Текущая версия: <span className="font-semibold text-indigo-400">v{APP_VERSION}</span>
          </p>
        </DialogHeader>

        <ScrollArea className="flex-1 overflow-auto">
          <div className="px-6 py-4 space-y-6">
            {CHANGELOG.map((release, idx) => (
              <div key={release.version}>
                {/* Version header */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-base font-bold">v{release.version}</span>
                  {release.badge === 'new' && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 uppercase tracking-wide">
                      Новое
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground ml-auto">{release.date}</span>
                </div>

                {/* Changes list */}
                <ul className="space-y-1.5">
                  {release.changes.map((change, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className={`h-3.5 w-3.5 mt-0.5 flex-shrink-0 ${idx === 0 ? 'text-indigo-400' : 'text-muted-foreground/50'}`} />
                      <span>{change}</span>
                    </li>
                  ))}
                </ul>

                {/* Divider */}
                {idx < CHANGELOG.length - 1 && (
                  <div className="mt-5 border-t border-border" />
                )}
              </div>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};

export default ChangelogModal;
