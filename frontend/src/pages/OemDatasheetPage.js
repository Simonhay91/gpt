import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Upload, FileText, ChevronDown, Loader2, Download, CheckCircle2,
  Building2, ArrowRight, RotateCcw, File, FileSpreadsheet
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';

const API = `${process.env.REACT_APP_BACKEND_URL}/api/oem`;

const ACCEPTED_TYPES = '.docx,.pdf';
const ACCEPTED_MIME = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/pdf',
];

const FileIcon = ({ filename }) => {
  if (filename?.endsWith('.pdf')) return <FileText className="h-8 w-8 text-red-400" />;
  if (filename?.endsWith('.docx')) return <File className="h-8 w-8 text-blue-400" />;
  return <FileSpreadsheet className="h-8 w-8 text-gray-400" />;
};

const StepBadge = ({ n, active, done }) => (
  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0 transition-colors ${
    done ? 'bg-emerald-500 text-white' :
    active ? 'bg-indigo-500 text-white' :
    'bg-secondary text-muted-foreground'
  }`}>
    {done ? <CheckCircle2 className="h-4 w-4" /> : n}
  </div>
);

const OemDatasheetPage = () => {
  const [brands, setBrands] = useState([]);
  const [loadingBrands, setLoadingBrands] = useState(true);

  const [file, setFile] = useState(null);
  const [selectedBrand, setSelectedBrand] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [outputFilename, setOutputFilename] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchBrands();
  }, []);

  const fetchBrands = async () => {
    try {
      const res = await axios.get(`${API}/brands`);
      setBrands(res.data);
    } catch {
      toast.error('Failed to load brands');
    } finally {
      setLoadingBrands(false);
    }
  };

  // ─── File selection ────────────────────────────────────────────────────────

  const handleFileSelect = (selectedFile) => {
    if (!selectedFile) return;
    const ext = selectedFile.name.split('.').pop().toLowerCase();
    if (!['docx', 'pdf'].includes(ext)) {
      toast.error('Only .docx and .pdf files are supported');
      return;
    }
    if (selectedFile.size > 50 * 1024 * 1024) {
      toast.error('File must be less than 50MB');
      return;
    }
    setFile(selectedFile);
    setDownloadUrl(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileSelect(dropped);
  };

  // ─── Process ───────────────────────────────────────────────────────────────

  const handleProcess = async () => {
    if (!file || !selectedBrand) return;
    setProcessing(true);
    setDownloadUrl(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('brand_id', selectedBrand.id);

      const response = await axios.post(`${API}/process`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
      });

      const contentDisposition = response.headers['content-disposition'] || '';
      const match = contentDisposition.match(/filename="?([^"]+)"?/);
      const fname = match ? match[1] : `OEM_${selectedBrand.name}.docx`;
      setOutputFilename(fname);

      const url = window.URL.createObjectURL(
        new Blob([response.data], {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        })
      );
      setDownloadUrl(url);
      toast.success('Datasheet rebranded successfully!');
    } catch (e) {
      const msg = e.response?.data
        ? await e.response.data.text?.().catch(() => 'Processing failed')
        : 'Processing failed';
      toast.error(msg);
    } finally {
      setProcessing(false);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = outputFilename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const reset = () => {
    setFile(null);
    setSelectedBrand(null);
    setDownloadUrl(null);
    setOutputFilename('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const step1Done = !!file;
  const step2Done = !!selectedBrand;
  const step3Done = !!downloadUrl;

  const canProcess = step1Done && step2Done && !processing;

  return (
    <DashboardLayout>
      <div className="p-6 max-w-3xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6 text-indigo-400" />
            OEM Datasheet Rebrander
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Upload a supplier datasheet → select your brand → download the rebranded OEM version
          </p>
        </div>

        <div className="space-y-4">

          {/* Step 1: Upload */}
          <Card className={`border transition-colors ${step1Done ? 'border-emerald-500/50' : 'border-border'}`}>
            <CardContent className="p-5">
              <div className="flex items-center gap-3 mb-4">
                <StepBadge n="1" active={!step1Done} done={step1Done} />
                <div>
                  <h2 className="font-semibold">Upload Supplier Datasheet</h2>
                  <p className="text-xs text-muted-foreground">Supported: .docx, .pdf (max 50MB)</p>
                </div>
              </div>

              {!file ? (
                <div
                  className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                    isDragging
                      ? 'border-indigo-500 bg-indigo-500/5'
                      : 'border-border hover:border-indigo-500/50 hover:bg-secondary/30'
                  }`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                >
                  <Upload className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
                  <p className="font-medium">Drop file here or click to browse</p>
                  <p className="text-sm text-muted-foreground mt-1">.docx or .pdf</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ACCEPTED_TYPES}
                    className="hidden"
                    onChange={(e) => handleFileSelect(e.target.files?.[0])}
                  />
                </div>
              ) : (
                <div className="flex items-center gap-4 p-4 bg-secondary/30 rounded-xl border border-border">
                  <FileIcon filename={file.name} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setFile(null); setDownloadUrl(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}
                    className="text-muted-foreground"
                  >
                    Change
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Step 2: Select Brand */}
          <Card className={`border transition-colors ${step2Done ? 'border-emerald-500/50' : 'border-border'}`}>
            <CardContent className="p-5">
              <div className="flex items-center gap-3 mb-4">
                <StepBadge n="2" active={step1Done && !step2Done} done={step2Done} />
                <div>
                  <h2 className="font-semibold">Select Brand</h2>
                  <p className="text-xs text-muted-foreground">Choose the brand for the OEM output</p>
                </div>
              </div>

              {loadingBrands ? (
                <div className="flex items-center gap-2 text-muted-foreground py-4">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading brands...
                </div>
              ) : brands.length === 0 ? (
                <div className="py-4 text-center text-muted-foreground">
                  <Building2 className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No brands configured yet.</p>
                  <p className="text-xs mt-1">Ask your admin to add brands in Admin → OEM Brands.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {brands.map(brand => (
                    <button
                      key={brand.id}
                      onClick={() => setSelectedBrand(brand)}
                      className={`flex items-start gap-3 p-3 rounded-lg border text-left transition-all ${
                        selectedBrand?.id === brand.id
                          ? 'border-indigo-500 bg-indigo-500/10'
                          : 'border-border hover:border-indigo-500/40 hover:bg-secondary/30'
                      }`}
                    >
                      <Building2 className={`h-5 w-5 flex-shrink-0 mt-0.5 ${
                        selectedBrand?.id === brand.id ? 'text-indigo-400' : 'text-muted-foreground'
                      }`} />
                      <div className="min-w-0">
                        <p className="font-medium text-sm">{brand.name}</p>
                        {brand.address && (
                          <p className="text-xs text-muted-foreground truncate">{brand.address}</p>
                        )}
                        {(brand.approvedLogos || []).length > 0 && (
                          <p className="text-xs text-indigo-400 mt-0.5">
                            {brand.approvedLogos.length} logo{brand.approvedLogos.length !== 1 ? 's' : ''}
                          </p>
                        )}
                      </div>
                      {selectedBrand?.id === brand.id && (
                        <CheckCircle2 className="h-4 w-4 text-indigo-400 flex-shrink-0 ml-auto mt-0.5" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Step 3: Process & Download */}
          <Card className={`border transition-colors ${step3Done ? 'border-emerald-500/50' : 'border-border'}`}>
            <CardContent className="p-5">
              <div className="flex items-center gap-3 mb-4">
                <StepBadge n="3" active={step1Done && step2Done} done={step3Done} />
                <div>
                  <h2 className="font-semibold">Generate OEM Datasheet</h2>
                  <p className="text-xs text-muted-foreground">
                    AI replaces supplier info with your brand data
                  </p>
                </div>
              </div>

              {!downloadUrl ? (
                <Button
                  onClick={handleProcess}
                  disabled={!canProcess}
                  className="w-full gap-2 h-12 text-base"
                  size="lg"
                >
                  {processing ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      AI is rebranding...
                    </>
                  ) : (
                    <>
                      <ArrowRight className="h-5 w-5" />
                      Rebrand Datasheet
                    </>
                  )}
                </Button>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
                    <CheckCircle2 className="h-8 w-8 text-emerald-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-emerald-400">Ready to download!</p>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">{outputFilename}</p>
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <Button onClick={handleDownload} className="flex-1 gap-2 bg-emerald-600 hover:bg-emerald-700">
                      <Download className="h-4 w-4" />
                      Download OEM Datasheet
                    </Button>
                    <Button variant="outline" onClick={reset} className="gap-2">
                      <RotateCcw className="h-4 w-4" />
                      New
                    </Button>
                  </div>
                </div>
              )}

              {processing && (
                <div className="mt-4 p-3 bg-secondary/30 rounded-lg">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Extracting text → identifying supplier info → replacing with brand data...</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

        </div>
      </div>
    </DashboardLayout>
  );
};

export default OemDatasheetPage;
