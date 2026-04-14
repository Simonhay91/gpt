import React from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Checkbox } from '../ui/checkbox';
import { ScrollArea } from '../ui/scroll-area';
import {
  Upload, Link, FileText, File, Globe, ImageIcon, Loader2,
  Search, X, Info, Database, Target, Lightbulb, ChevronRight,
  ChevronDown, Eye, Download, Trash2, Building2, FolderOpen
} from 'lucide-react';

const getFileIcon = (mimeType, kind) => {
  if (kind === 'url') return <Globe className="h-5 w-5 text-blue-400" />;
  if (mimeType?.includes('pdf')) return <FileText className="h-5 w-5 text-red-400" />;
  if (mimeType?.includes('wordprocessingml')) return <File className="h-5 w-5 text-blue-500" />;
  if (mimeType?.includes('presentationml')) return <File className="h-5 w-5 text-orange-500" />;
  if (mimeType?.includes('spreadsheetml')) return <File className="h-5 w-5 text-green-500" />;
  if (mimeType?.includes('image')) return <ImageIcon className="h-5 w-5 text-purple-400" />;
  return <FileText className="h-5 w-5 text-gray-400" />;
};

const formatFileSize = (bytes) => {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const SourcePanel = ({
  projectSources,
  activeSourceIds,
  sourcesExplicitlySet,
  currentProjectName,
  currentUser,
  chat,
  isUploading,
  isAddingUrl,
  urlInput,
  onUrlInputChange,
  onAddUrl,
  onClose,
  onToggleSource,
  onToggleGroupSelection,
  onSelectAll,
  onDeselectAll,
  onResetToAll,
  expandedGroups,
  onToggleGroup,
  groupedSources,
  onDeleteSource,
  onPreview,
  onDownload,
  onSaveToDept,
  searchQuery,
  onSearchQueryChange,
  onSearch,
  isSearching,
  showSearchResults,
  searchResults,
  onCloseSearch,
  fileInputRef,
  onFileInputChange,
  showInfoBlock,
  onCloseInfoBlock,
}) => {
  const highlightMatch = (text, query) => {
    const regex = new RegExp(`(${query})`, 'gi');
    return text.replace(regex, '<mark class="bg-yellow-300 dark:bg-yellow-600 px-0.5 rounded">$1</mark>');
  };

  return (
    <div className="flex flex-col h-full overflow-hidden" data-testid="source-panel">
      {/* Drawer header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border flex-shrink-0">
        <span className="font-semibold text-sm">Sources</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} data-testid="close-source-panel-btn" title="Close">
          <X className="h-4 w-4 text-muted-foreground" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4">

        {/* Upload row */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.png,.jpg,.jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,text/markdown,image/png,image/jpeg"
            onChange={onFileInputChange}
            className="hidden"
            data-testid="file-input"
          />
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={isUploading} className="gap-2" data-testid="upload-file-btn">
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Upload Files
          </Button>
          <div className="flex-1 flex items-center gap-2 min-w-[200px]">
            <Input
              placeholder="https://example.com/article"
              value={urlInput}
              onChange={(e) => onUrlInputChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onAddUrl()}
              className="h-9 text-sm"
              data-testid="url-input"
            />
            <Button variant="outline" size="sm" onClick={onAddUrl} disabled={isAddingUrl || !urlInput.trim()} className="gap-2 whitespace-nowrap" data-testid="add-url-btn">
              {isAddingUrl ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link className="h-4 w-4" />}
              Add URL
            </Button>
          </div>
        </div>

        {/* Search row */}
        <div className="flex items-center gap-2 mb-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Поиск в документах (0 токенов)..."
              value={searchQuery}
              onChange={(e) => onSearchQueryChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onSearch()}
              className="h-9 text-sm pl-9"
              data-testid="search-sources-input"
            />
          </div>
          <Button variant="default" size="sm" onClick={onSearch} disabled={isSearching || !searchQuery.trim()} className="gap-2" data-testid="search-sources-btn">
            {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Найти
          </Button>
        </div>

        {/* Search results */}
        {showSearchResults && (
          <div className="mb-4 border border-border rounded-lg p-3 bg-secondary/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Результаты поиска ({searchResults.length})</span>
              <Button variant="ghost" size="sm" onClick={onCloseSearch}><X className="h-4 w-4" /></Button>
            </div>
            {searchResults.length === 0 ? (
              <p className="text-sm text-muted-foreground">Ничего не найдено</p>
            ) : (
              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                {searchResults.map((result, idx) => (
                  <div key={idx} className="p-2 bg-background rounded border border-border">
                    <div className="flex items-center gap-2 mb-1">
                      <FileText className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs font-medium truncate">{result.sourceName}</span>
                      <span className="text-xs text-muted-foreground">({result.matchCount} совпадений)</span>
                    </div>
                    <p className="text-xs text-muted-foreground" dangerouslySetInnerHTML={{ __html: highlightMatch(result.content, searchQuery) }} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="text-xs text-muted-foreground mb-3">
          Supported: PDF, DOCX, PPTX, XLSX, TXT, MD, PNG, JPEG files and web URLs (multiple files allowed)
        </div>

        {/* Info block */}
        {projectSources.length > 0 && showInfoBlock && (
          <div className="mb-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 relative">
            <button onClick={onCloseInfoBlock} className="absolute top-2 right-2 p-1 hover:bg-blue-500/20 rounded transition-colors">
              <X className="h-4 w-4 text-blue-400" />
            </button>
            <div className="flex items-start gap-3 pr-8">
              <Info className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 text-sm text-blue-200/90 space-y-2">
                <p className="font-medium text-blue-300">Как работают источники в AI-чате:</p>
                <ul className="space-y-1.5 text-xs">
                  <li className="flex items-start gap-2"><Database className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" /><span><strong className="text-blue-300">Иерархия:</strong> Личные → Проектные → Департамент → Глобальные</span></li>
                  <li className="flex items-start gap-2"><Target className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" /><span><strong className="text-blue-300">Активные источники:</strong> Только выбранные используются для ответов</span></li>
                  <li className="flex items-start gap-2"><Lightbulb className="h-3.5 w-3.5 text-blue-400 flex-shrink-0 mt-0.5" /><span><strong className="text-blue-300">Влияние на ответы:</strong> AI ищет в активных источниках и формирует ответ</span></li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Source list */}
        {projectSources.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Источники не загружены</p>
            <p className="text-xs mt-1">Загрузите файлы или добавьте URL для контекста</p>
          </div>
        ) : (
          <div className="space-y-1">
            <div className="flex items-center justify-between mb-2 pb-2 border-b border-border">
              <span className="text-xs text-muted-foreground">{sourcesExplicitlySet ? `${activeSourceIds.length} / ${projectSources.length}` : `${projectSources.length} / ${projectSources.length} (all)`}</span>
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={onSelectAll} data-testid="select-all-sources">Все</Button>
                <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={onDeselectAll} data-testid="deselect-all-sources">Сбросить</Button>
                {sourcesExplicitlySet && (
                  <Button variant="ghost" size="sm" className="h-6 text-xs px-2 text-amber-500 hover:text-amber-600" onClick={onResetToAll} title="Reset to default (use all sources)" data-testid="reset-to-all-sources">↺</Button>
                )}
              </div>
            </div>

            <div className="max-h-[280px] overflow-y-auto space-y-1">
              {groupedSources.map(([groupKey, group]) => {
                const GroupIcon = group.icon;
                const isExpanded = expandedGroups[groupKey];
                const groupSourceIds = group.sources.map(s => s.id);
                const selectedInGroup = !sourcesExplicitlySet ? group.sources.length : groupSourceIds.filter(id => activeSourceIds.includes(id)).length;
                const allSelected = selectedInGroup === group.sources.length;
                const someSelected = selectedInGroup > 0 && selectedInGroup < group.sources.length;

                return (
                  <div key={groupKey} className="rounded-lg border border-border overflow-hidden">
                    <div className="flex items-center gap-2 p-2 bg-secondary/30 cursor-pointer hover:bg-secondary/50 transition-colors" onClick={() => onToggleGroup(groupKey)}>
                      <Checkbox
                        checked={allSelected}
                        ref={someSelected ? (el) => { if (el) el.indeterminate = true; } : undefined}
                        onCheckedChange={() => onToggleGroupSelection(group.sources)}
                        onClick={(e) => e.stopPropagation()}
                        className="data-[state=checked]:bg-indigo-500"
                        data-testid={`group-checkbox-${groupKey}`}
                      />
                      {isExpanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                      <GroupIcon className={`h-4 w-4 ${group.color}`} />
                      <span className="text-sm font-medium flex-1">{group.label}</span>
                      <span className="text-xs text-muted-foreground">{selectedInGroup}/{group.sources.length}</span>
                    </div>

                    {isExpanded && (
                      <div className="border-t border-border">
                        {group.sources.map((source) => {
                          const isSelected = !sourcesExplicitlySet || activeSourceIds.includes(source.id);
                          return (
                            <div
                              key={source.id}
                              className={`flex items-center gap-2 p-2 pl-8 transition-colors ${isSelected ? 'bg-indigo-500/10' : 'hover:bg-secondary/20'}`}
                              data-testid={`source-item-${source.id}`}
                            >
                              <Checkbox
                                checked={isSelected}
                                onCheckedChange={() => onToggleSource(source.id)}
                                className="data-[state=checked]:bg-indigo-500"
                                data-testid={`source-checkbox-${source.id}`}
                              />
                              {getFileIcon(source.mimeType, source.kind)}
                              <div className="flex-1 min-w-0">
                                <p className="text-sm truncate">{source.originalName || source.url}</p>
                                <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
                                  <p className="text-xs text-muted-foreground">
                                    {source.sizeBytes ? `${formatFileSize(source.sizeBytes)} • ` : ''}{source.chunkCount} chunks
                                  </p>
                                  {currentProjectName && (
                                    <span className="inline-flex items-center gap-0.5 text-xs text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded-full border border-indigo-500/20" data-testid={`source-project-badge-${source.id}`}>
                                      <FolderOpen className="h-2.5 w-2.5 flex-shrink-0" />
                                      <span className="truncate max-w-[90px]">{currentProjectName}</span>
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="flex items-center gap-1">
                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); onPreview(source, e); }} title="Preview" data-testid={`preview-source-${source.id}`}>
                                  <Eye className="h-3.5 w-3.5 text-blue-400" />
                                </Button>
                                {source.kind === 'file' && (
                                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); onDownload(source, e); }} title="Download" data-testid={`download-source-${source.id}`}>
                                    <Download className="h-3.5 w-3.5 text-green-400" />
                                  </Button>
                                )}
                                {source.level === 'project' && currentUser?.departments?.length > 0 && (
                                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); onSaveToDept(source, e); }} title="Save to department" data-testid={`save-to-dept-${source.id}`}>
                                    <Building2 className="h-3.5 w-3.5 text-amber-400" />
                                  </Button>
                                )}
                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); onDeleteSource(source.id, e); }} data-testid={`delete-source-${source.id}`}>
                                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                </Button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {projectSources.length > 0 && (
          <p className="text-xs text-muted-foreground mt-3 flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-indigo-500"></span>
            Checked sources are used as AI context
          </p>
        )}
      </div>
    </div>
  );
};
