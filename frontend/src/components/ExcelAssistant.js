import React, { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './ui/dialog';
import { FileSpreadsheet, Upload, X, Download, Loader2, CheckCircle2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MAX_SIZE = 10 * 1024 * 1024; // 10MB
const ACCEPTED_EXTS = ['.xlsx', '.xls', '.csv'];

export default function ExcelAssistant({
  chatId,
  open: openProp,
  onOpenChange,
  hideTrigger = false,
}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const isControlled = openProp !== undefined;
  const open = isControlled ? openProp : internalOpen;
  const setOpen = (next) => {
    if (isControlled) onOpenChange?.(next);
    else setInternalOpen(next);
  };
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [instruction, setInstruction] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const reset = () => {
    setFile(null);
    setInstruction('');
    setResult(null);
    setIsProcessing(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleClose = () => {
    setOpen(false);
    reset();
  };

  const validateFile = (f) => {
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!ACCEPTED_EXTS.includes(ext)) {
      toast.error('Поддерживаются только файлы .xlsx, .xls, .csv');
      return false;
    }
    if (f.size > MAX_SIZE) {
      toast.error('Файл слишком большой (максимум 10 МБ)');
      return false;
    }
    return true;
  };

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (f && validateFile(f)) {
      setFile(f);
      setResult(null);
    }
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f && validateFile(f)) {
      setFile(f);
      setResult(null);
    }
  }, []);

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = () => setIsDragging(false);

  const handleProcess = async () => {
    if (!file) { toast.error('Выберите файл'); return; }
    if (!instruction.trim()) { toast.error('Введите инструкцию'); return; }

    setIsProcessing(true);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('instruction', instruction.trim());

    try {
      const response = await axios.post(
        `${API}/chats/${chatId}/excel-process`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      setResult(response.data);
      toast.success('Файл успешно обработан');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка обработки файла');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!result?.download_url) return;
    try {
      const response = await axios.get(
        `${process.env.REACT_APP_BACKEND_URL}${result.download_url}`,
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
    } catch (err) {
      toast.error('Не удалось скачать файл');
    }
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <>
      {!hideTrigger && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpen(true)}
          className="gap-2"
          data-testid="excel-assistant-btn"
          title="Excel / CSV Assistant"
        >
          <FileSpreadsheet className="h-4 w-4 text-green-400" />
          <span className="hidden sm:inline">Excel</span>
        </Button>
      )}

      <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); else setOpen(true); }}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-green-400" />
              Excel / CSV Assistant
            </DialogTitle>
            <DialogDescription>
              Загрузите таблицу и опишите, что нужно сделать — AI применит трансформации и вернёт готовый файл.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 pt-2">
            {/* Dropzone */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => !file && fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer
                ${isDragging ? 'border-green-400 bg-green-500/10' : 'border-border hover:border-green-400/50 hover:bg-secondary/30'}
                ${file ? 'cursor-default' : ''}`}
              data-testid="excel-dropzone"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                onChange={handleFileChange}
                className="hidden"
                data-testid="excel-file-input"
              />
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <FileSpreadsheet className="h-8 w-8 text-green-400 flex-shrink-0" />
                  <div className="text-left">
                    <p className="font-medium text-sm truncate max-w-xs">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{formatSize(file.size)}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 ml-auto"
                    onClick={(e) => { e.stopPropagation(); setFile(null); setResult(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}
                    data-testid="excel-remove-file"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <Upload className="h-10 w-10 text-muted-foreground mx-auto" />
                  <p className="text-sm font-medium">Перетащите файл или кликните для выбора</p>
                  <p className="text-xs text-muted-foreground">.xlsx, .xls, .csv — до 10 МБ</p>
                </div>
              )}
            </div>

            {/* Instruction */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Инструкция</label>
              <Textarea
                placeholder="Например: переименуй колонку 'name' в 'Имя', переведи колонку 'status' на русский, удали строки где количество = 0..."
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={3}
                className="resize-none"
                data-testid="excel-instruction-input"
              />
            </div>

            {/* Process Button */}
            <Button
              className="w-full gap-2"
              onClick={handleProcess}
              disabled={isProcessing || !file || !instruction.trim()}
              data-testid="excel-process-btn"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Обрабатываю...
                </>
              ) : (
                <>
                  <FileSpreadsheet className="h-4 w-4" />
                  Обработать
                </>
              )}
            </Button>

            {/* Result */}
            {result && (
              <div className="space-y-3 animate-in fade-in duration-300" data-testid="excel-result">
                {/* AI message */}
                <div className="flex items-start gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                  <CheckCircle2 className="h-4 w-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-green-400">Готово</p>
                    <p className="text-sm text-foreground/90" data-testid="excel-result-message">{result.message}</p>
                    <p className="text-xs text-muted-foreground">{result.rows} строк · {result.columns} колонок</p>
                  </div>
                </div>

                {/* Preview table */}
                {result.preview_columns && result.preview_columns.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">Предпросмотр (первые 5 строк)</p>
                    <div className="overflow-x-auto rounded-lg border border-border">
                      <table className="w-full text-xs" data-testid="excel-preview-table">
                        <thead className="bg-secondary/50">
                          <tr>
                            {result.preview_columns.map((col, i) => (
                              <th key={i} className="px-3 py-2 text-left font-medium text-foreground whitespace-nowrap border-r border-border last:border-r-0">
                                {String(col)}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(result.preview || []).map((row, ri) => (
                            <tr key={ri} className="border-t border-border hover:bg-secondary/20">
                              {result.preview_columns.map((_, ci) => (
                                <td key={ci} className="px-3 py-1.5 text-muted-foreground whitespace-nowrap border-r border-border last:border-r-0">
                                  {row[ci] !== null && row[ci] !== undefined ? String(row[ci]) : '—'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Download button */}
                <Button
                  variant="outline"
                  className="w-full gap-2 border-green-500/40 text-green-400 hover:bg-green-500/10"
                  onClick={handleDownload}
                  data-testid="excel-download-btn"
                >
                  <Download className="h-4 w-4" />
                  Скачать результат (.xlsx)
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
