import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { toast } from 'sonner';
import { ImageIcon, Loader2, Download, Sparkles, Info, Upload, ZoomIn, Pencil } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IMAGE_STANDARDS = {
  planet: {
    name: 'Planet Image Standard',
    description: 'Square format, product-focused, 20% padding',
    sizes: [
      { value: '1024x1024', label: '1092 x 1092 (Minimum)' },
      { value: '1024x1024', label: '1500 x 1500 (Recommended)' },
      { value: '1024x1024', label: '2000 x 2000 (Maximum)' },
    ],
    rules: [
      'Square format required',
      'Product occupies max 80% of image',
      'Min 20% padding on all sides',
      'First image: transparent background (PNG)',
      'Other images: white background (JPG)',
      'High-resolution, no pixelation'
    ]
  },
  custom: {
    name: 'Custom Size',
    description: 'Set your own dimensions'
  }
};

const SIZE_PRESETS = [
  { value: '1024x1024', label: 'Square 1024×1024', group: 'Standard' },
  { value: '1024x1792', label: 'Portrait 1024×1792', group: 'Standard' },
  { value: '1792x1024', label: 'Landscape 1792×1024', group: 'Standard' },
  { value: '1092x1092', label: 'Planet Min 1092×1092', group: 'Planet Standard' },
  { value: '1500x1500', label: 'Planet Rec 1500×1500', group: 'Planet Standard' },
  { value: '2000x2000', label: 'Planet Max 2000×2000', group: 'Planet Standard' },
];

const TABS = [
  { id: 'generate', label: 'Generate', icon: Sparkles },
  { id: 'edit', label: 'Edit (AI)', icon: Pencil },
  { id: 'resize', label: 'Resize', icon: ImageIcon },
  { id: 'upscale', label: 'Upscale', icon: ZoomIn },
];

const ImageGenerator = ({ projectId, onImageGenerated }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('generate');

  // Generate tab state
  const [prompt, setPrompt] = useState('');
  const [standard, setStandard] = useState('planet');
  const [sizePreset, setSizePreset] = useState('1092x1092');
  const [customWidth, setCustomWidth] = useState('1024');
  const [customHeight, setCustomHeight] = useState('1024');
  const [backgroundType, setBackgroundType] = useState('transparent');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState(null);
  const [imageUrl, setImageUrl] = useState(null);
  const [showRules, setShowRules] = useState(false);

  // Reference photo for Generate tab
  const [referenceFile, setReferenceFile] = useState(null);
  const [referencePreview, setReferencePreview] = useState(null);
  const referenceFileRef = useRef();
  const [editPreview, setEditPreview] = useState(null);
  const [editPrompt, setEditPrompt] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [editedImage, setEditedImage] = useState(null);
  const [editedImageUrl, setEditedImageUrl] = useState(null);
  const editFileRef = useRef();

  // Resize tab state
  const [resizeFile, setResizeFile] = useState(null);
  const [resizePreview, setResizePreview] = useState(null);
  const [resizeWidth, setResizeWidth] = useState('1024');
  const [resizeHeight, setResizeHeight] = useState('1024');
  const [isResizing, setIsResizing] = useState(false);
  const [resizedImage, setResizedImage] = useState(null);
  const [resizedImageUrl, setResizedImageUrl] = useState(null);
  const resizeFileRef = useRef();

  // Upscale tab state
  const [upscaleFile, setUpscaleFile] = useState(null);
  const [upscalePreview, setUpscalePreview] = useState(null);
  const [upscaleScale, setUpscaleScale] = useState('2');
  const [isUpscaling, setIsUpscaling] = useState(false);
  const [upscaledImage, setUpscaledImage] = useState(null);
  const [upscaledImageUrl, setUpscaledImageUrl] = useState(null);
  const upscaleFileRef = useRef();

  useEffect(() => {
    if (generatedImage) fetchImageBlob(generatedImage.id, setImageUrl);
    return () => { if (imageUrl) URL.revokeObjectURL(imageUrl); };
  }, [generatedImage]);

  useEffect(() => {
    if (editedImage) fetchImageBlob(editedImage.id, setEditedImageUrl);
    return () => { if (editedImageUrl) URL.revokeObjectURL(editedImageUrl); };
  }, [editedImage]);

  useEffect(() => {
    if (resizedImage) fetchImageBlob(resizedImage.id, setResizedImageUrl);
    return () => { if (resizedImageUrl) URL.revokeObjectURL(resizedImageUrl); };
  }, [resizedImage]);

  useEffect(() => {
    if (upscaledImage) fetchImageBlob(upscaledImage.id, setUpscaledImageUrl);
    return () => { if (upscaledImageUrl) URL.revokeObjectURL(upscaledImageUrl); };
  }, [upscaledImage]);

  const fetchImageBlob = async (imageId, setter) => {
    try {
      const response = await axios.get(`${API}/images/${imageId}`, { responseType: 'blob' });
      setter(URL.createObjectURL(response.data));
    } catch (error) {
      console.error('Failed to fetch image:', error);
    }
  };

  const handleFileChange = (e, setFile, setPreview) => {
    const file = e.target.files[0];
    if (!file) return;
    setFile(file);
    const reader = new FileReader();
    reader.onloadend = () => setPreview(reader.result);
    reader.readAsDataURL(file);
  };

  const getEffectiveSize = () => {
    if (standard === 'custom') return '1024x1024';
    if (sizePreset.includes('1092') || sizePreset.includes('1500') || sizePreset.includes('2000')) return '1024x1024';
    return sizePreset;
  };

  const buildPrompt = () => {
    let enhancedPrompt = prompt.trim();
    if (standard === 'planet') {
      const bgInstruction = backgroundType === 'transparent'
        ? 'on a completely transparent background, PNG format ready'
        : 'on a clean pure white background (#FFFFFF), no shadows, no gradients';
      enhancedPrompt = `Product photography: ${enhancedPrompt}. 
Requirements: 
- ${bgInstruction}
- Product centered with 20% padding on all sides
- Product occupies maximum 80% of frame
- High-resolution, sharp details, no noise or artifacts
- Professional studio lighting, consistent and balanced
- Clean, minimalist composition`;
    }
    return enhancedPrompt;
  };

  const generateImage = async () => {
    if (!prompt.trim() && !referenceFile) { toast.error('Please enter a prompt or upload a photo'); return; }
    setIsGenerating(true);
    setGeneratedImage(null);
    setImageUrl(null);
    try {
      if (referenceFile) {
        const bgInstruction = backgroundType === 'transparent'
          ? 'transparent background (PNG), remove all original background'
          : 'clean pure white background (#FFFFFF), no shadows';
        const userDesc = prompt.trim() ? prompt.trim() : 'product';
        const planetPrompt = `Apply Planet Image Standard to this ${userDesc}: ${bgInstruction}. Product centered with 20% padding on all sides, occupies max 80% of frame. Professional studio lighting, high-resolution, sharp details, no noise.`;
        const formData = new FormData();
        formData.append('file', referenceFile);
        formData.append('prompt', planetPrompt);
        const response = await axios.post(`${API}/projects/${projectId}/edit-image`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        setGeneratedImage(response.data);
      } else {
        const response = await axios.post(`${API}/projects/${projectId}/generate-image`, {
          prompt: buildPrompt(),
          size: getEffectiveSize()
        });
        setGeneratedImage(response.data);
      }
      toast.success('Image generated successfully!');
      if (onImageGenerated) onImageGenerated();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate image');
    } finally {
      setIsGenerating(false);
    }
  };

  const editImage = async () => {
    if (!editFile) { toast.error('Please upload an image'); return; }
    if (!editPrompt.trim()) { toast.error('Please enter a prompt'); return; }
    setIsEditing(true);
    setEditedImage(null);
    setEditedImageUrl(null);
    try {
      const formData = new FormData();
      formData.append('file', editFile);
      formData.append('prompt', editPrompt);
      const response = await axios.post(`${API}/projects/${projectId}/edit-image`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setEditedImage(response.data);
      toast.success('Image edited successfully!');
      if (onImageGenerated) onImageGenerated(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to edit image');
    } finally {
      setIsEditing(false);
    }
  };

  const resizeImage = async () => {
    if (!resizeFile) { toast.error('Please upload an image'); return; }
    const w = parseInt(resizeWidth);
    const h = parseInt(resizeHeight);
    if (!w || !h || w <= 0 || h <= 0) { toast.error('Enter valid width and height'); return; }
    setIsResizing(true);
    setResizedImage(null);
    setResizedImageUrl(null);
    try {
      const formData = new FormData();
      formData.append('file', resizeFile);
      formData.append('width', w);
      formData.append('height', h);
      const response = await axios.post(`${API}/projects/${projectId}/resize-image`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResizedImage(response.data);
      toast.success('Image resized successfully!');
      if (onImageGenerated) onImageGenerated(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to resize image');
    } finally {
      setIsResizing(false);
    }
  };

  const upscaleImage = async () => {
    if (!upscaleFile) { toast.error('Please upload an image'); return; }
    setIsUpscaling(true);
    setUpscaledImage(null);
    setUpscaledImageUrl(null);
    try {
      const formData = new FormData();
      formData.append('file', upscaleFile);
      formData.append('scale', parseInt(upscaleScale));
      const response = await axios.post(`${API}/projects/${projectId}/upscale-image`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUpscaledImage(response.data);
      toast.success(`Image upscaled ${upscaleScale}x successfully!`);
      if (onImageGenerated) onImageGenerated(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to upscale image');
    } finally {
      setIsUpscaling(false);
    }
  };

  const downloadImage = async (imageId, filename) => {
    try {
      const response = await axios.get(`${API}/images/${imageId}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error('Failed to download image');
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    setPrompt('');
    setGeneratedImage(null);
    setReferenceFile(null); setReferencePreview(null);
    setEditFile(null); setEditPreview(null); setEditPrompt(''); setEditedImage(null); setEditedImageUrl(null);
    setResizeFile(null); setResizePreview(null); setResizedImage(null); setResizedImageUrl(null);
    setUpscaleFile(null); setUpscalePreview(null); setUpscaledImage(null); setUpscaledImageUrl(null);
    [imageUrl, editedImageUrl, resizedImageUrl, upscaledImageUrl].forEach(u => { if (u) URL.revokeObjectURL(u); });
  };

  const FileUploadArea = ({ preview, fileRef, onChange, disabled }) => (
    <div
      className="border-2 border-dashed border-border rounded-lg p-4 text-center cursor-pointer hover:border-indigo-400 transition-colors"
      onClick={() => fileRef.current?.click()}
    >
      <input
        type="file"
        ref={fileRef}
        accept="image/*"
        className="hidden"
        onChange={onChange}
        disabled={disabled}
      />
      {preview ? (
        <img src={preview} alt="preview" className="max-h-40 mx-auto rounded object-contain" />
      ) : (
        <div className="flex flex-col items-center gap-2 py-4 text-muted-foreground">
          <Upload className="h-8 w-8" />
          <span className="text-sm">Click to upload image</span>
        </div>
      )}
    </div>
  );

  const ResultPreview = ({ imageUrl, image, filename }) => image && (
    <div className="mt-4 space-y-3">
      <div className="relative rounded-lg overflow-hidden border border-border">
        {imageUrl ? (
          <img src={imageUrl} alt="result" className="w-full h-auto" />
        ) : (
          <div className="w-full h-48 flex items-center justify-center bg-secondary">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>
      <div className="flex justify-between items-center">
        <p className="text-xs text-emerald-400">{image.size}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => downloadImage(image.id, filename)}
          className="gap-2"
        >
          <Download className="h-4 w-4" />
          Download
        </Button>
      </div>
    </div>
  );

  return (
    <Dialog open={isOpen} onOpenChange={(open) => open ? setIsOpen(true) : handleClose()}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2" data-testid="generate-image-btn">
          <ImageIcon className="h-4 w-4" />
          Generate Image
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            AI Image Tools
          </DialogTitle>
          <DialogDescription>
            Generate, edit, resize or upscale product images
          </DialogDescription>
        </DialogHeader>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border pb-0 mt-2">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-t-md transition-colors ${
                activeTab === id
                  ? 'bg-secondary text-foreground border-b-2 border-indigo-400 font-medium'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        <div className="space-y-4 py-4">

          {/* ── GENERATE TAB ── */}
          {activeTab === 'generate' && (
            <>
              <div className="space-y-2">
                <Label>Image Standard</Label>
                <Select value={standard} onValueChange={setStandard} disabled={isGenerating}>
                  <SelectTrigger data-testid="image-standard-select">
                    <SelectValue placeholder="Select standard" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="planet">
                      <div className="flex items-center gap-2">
                        <span className="text-emerald-400">●</span>
                        Planet Image Standard
                      </div>
                    </SelectItem>
                    <SelectItem value="standard">Standard Sizes</SelectItem>
                    <SelectItem value="custom">Custom Size</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {standard === 'planet' && (
                <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3">
                  <button
                    className="flex items-center gap-2 text-sm font-medium text-emerald-400 w-full"
                    onClick={() => setShowRules(!showRules)}
                  >
                    <Info className="h-4 w-4" />
                    Planet Image Standard Requirements
                    <span className="ml-auto text-xs">{showRules ? '▼' : '▶'}</span>
                  </button>
                  {showRules && (
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {IMAGE_STANDARDS.planet.rules.map((rule, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="text-emerald-400">•</span>
                          {rule}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {standard === 'planet' && (
                <div className="space-y-2">
                  <Label>Size (Square format)</Label>
                  <Select value={sizePreset} onValueChange={setSizePreset} disabled={isGenerating}>
                    <SelectTrigger data-testid="image-size-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1092x1092">1092 × 1092 px (Minimum)</SelectItem>
                      <SelectItem value="1500x1500">1500 × 1500 px (Recommended)</SelectItem>
                      <SelectItem value="2000x2000">2000 × 2000 px (Maximum)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {standard === 'standard' && (
                <div className="space-y-2">
                  <Label>Size</Label>
                  <Select value={sizePreset} onValueChange={setSizePreset} disabled={isGenerating}>
                    <SelectTrigger data-testid="image-size-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1024x1024">Square (1024 × 1024)</SelectItem>
                      <SelectItem value="1024x1792">Portrait (1024 × 1792)</SelectItem>
                      <SelectItem value="1792x1024">Landscape (1792 × 1024)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {standard === 'custom' && (
                <div className="space-y-2">
                  <Label>Custom Size</Label>
                  <div className="flex gap-2 items-center">
                    <Input type="number" placeholder="Width" value={customWidth} onChange={(e) => setCustomWidth(e.target.value)} className="w-24" min="256" max="2048" disabled={isGenerating} data-testid="custom-width-input" />
                    <span className="text-muted-foreground">×</span>
                    <Input type="number" placeholder="Height" value={customHeight} onChange={(e) => setCustomHeight(e.target.value)} className="w-24" min="256" max="2048" disabled={isGenerating} data-testid="custom-height-input" />
                    <span className="text-xs text-muted-foreground">px</span>
                  </div>
                  <p className="text-xs text-muted-foreground">DALL-E will use closest supported size</p>
                </div>
              )}

              {standard === 'planet' && (
                <div className="space-y-2">
                  <Label>Background</Label>
                  <Select value={backgroundType} onValueChange={setBackgroundType} disabled={isGenerating}>
                    <SelectTrigger data-testid="background-type-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="transparent">Transparent (PNG) - First Image</SelectItem>
                      <SelectItem value="white">White Background (JPG) - Additional Images</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="space-y-2">
                <Label>Product Description <span className="text-xs text-muted-foreground font-normal">(optional with photo)</span></Label>
                <Textarea
                  placeholder={standard === 'planet' ? "Describe your product: e.g., 'wireless bluetooth earbuds in matte black finish'" : "A futuristic cityscape at sunset..."}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={isGenerating}
                  className="min-h-[80px]"
                  data-testid="image-prompt-input"
                />
              </div>

              {/* Reference Photo Upload */}
              <div className="space-y-2">
                <Label className="flex items-center gap-1.5">
                  <Upload className="h-3.5 w-3.5 text-muted-foreground" />
                  Reference Photo
                  <span className="text-xs text-muted-foreground font-normal">(optional — AI applies Planet standards)</span>
                </Label>
                <FileUploadArea
                  preview={referencePreview}
                  fileRef={referenceFileRef}
                  onChange={(e) => handleFileChange(e, setReferenceFile, setReferencePreview)}
                  disabled={isGenerating}
                />
                {referenceFile && (
                  <button
                    type="button"
                    onClick={() => { setReferenceFile(null); setReferencePreview(null); }}
                    className="text-xs text-muted-foreground hover:text-destructive transition-colors"
                  >
                    Remove photo
                  </button>
                )}
              </div>

              <Button onClick={generateImage} disabled={(!prompt.trim() && !referenceFile) || isGenerating} className="w-full" data-testid="confirm-generate-btn">
                {isGenerating
                  ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Generating...</>
                  : referenceFile
                    ? <><Upload className="mr-2 h-4 w-4" />Apply Planet Standards to Photo</>
                    : <><Sparkles className="mr-2 h-4 w-4" />Generate Image</>
                }
              </Button>

              {generatedImage && (
                <div className="mt-4 space-y-3">
                  <div className="relative rounded-lg overflow-hidden border border-border">
                    {imageUrl ? (
                      <div className={backgroundType === 'transparent' ? "bg-[url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAJElEQVQoU2NkYGD4z4AKGJG5jIxwDgMDA8N/BgYGRpgCuAIYBwD+SQaB3Z9P0wAAAABJRU5ErkJggg==')] bg-repeat" : "bg-white"}>
                        <img src={imageUrl} alt={generatedImage.prompt} className="w-full h-auto" data-testid="generated-image-preview" />
                      </div>
                    ) : (
                      <div className="w-full h-48 flex items-center justify-center bg-secondary"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground truncate">{prompt}</p>
                      <p className="text-xs text-emerald-400">{standard === 'planet' ? `Planet Standard • ${sizePreset} • ${backgroundType === 'transparent' ? 'PNG' : 'JPG'}` : sizePreset}</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => downloadImage(generatedImage.id, `planet_image_${generatedImage.id}.${backgroundType === 'transparent' ? 'png' : 'jpg'}`)} className="gap-2 shrink-0" data-testid="download-image-btn">
                      <Download className="h-4 w-4" />Download
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── EDIT TAB ── */}
          {activeTab === 'edit' && (
            <>
              <p className="text-xs text-muted-foreground">Upload an image and describe the changes. Uses DALL-E 2 inpainting.</p>
              <div className="space-y-2">
                <Label>Upload Image</Label>
                <FileUploadArea preview={editPreview} fileRef={editFileRef} onChange={(e) => handleFileChange(e, setEditFile, setEditPreview)} disabled={isEditing} />
              </div>
              <div className="space-y-2">
                <Label>Edit Instructions</Label>
                <Textarea
                  placeholder="e.g., 'Change background to forest', 'Add a red bow on top', 'Make it look vintage'"
                  value={editPrompt}
                  onChange={(e) => setEditPrompt(e.target.value)}
                  disabled={isEditing}
                  className="min-h-[80px]"
                />
              </div>
              <Button onClick={editImage} disabled={!editFile || !editPrompt.trim() || isEditing} className="w-full">
                {isEditing ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Editing...</> : <><Pencil className="mr-2 h-4 w-4" />Edit Image</>}
              </Button>
              <ResultPreview imageUrl={editedImageUrl} image={editedImage} filename={`edited_${editedImage?.id}.png`} />
            </>
          )}

          {/* ── RESIZE TAB ── */}
          {activeTab === 'resize' && (
            <>
              <p className="text-xs text-muted-foreground">Resize your image to exact pixel dimensions.</p>
              <div className="space-y-2">
                <Label>Upload Image</Label>
                <FileUploadArea preview={resizePreview} fileRef={resizeFileRef} onChange={(e) => handleFileChange(e, setResizeFile, setResizePreview)} disabled={isResizing} />
              </div>
              <div className="space-y-2">
                <Label>New Dimensions</Label>
                <div className="flex gap-2 items-center">
                  <Input type="number" placeholder="Width" value={resizeWidth} onChange={(e) => setResizeWidth(e.target.value)} className="w-24" min="1" max="8000" disabled={isResizing} />
                  <span className="text-muted-foreground">×</span>
                  <Input type="number" placeholder="Height" value={resizeHeight} onChange={(e) => setResizeHeight(e.target.value)} className="w-24" min="1" max="8000" disabled={isResizing} />
                  <span className="text-xs text-muted-foreground">px</span>
                </div>
              </div>
              <Button onClick={resizeImage} disabled={!resizeFile || isResizing} className="w-full">
                {isResizing ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Resizing...</> : <><ImageIcon className="mr-2 h-4 w-4" />Resize Image</>}
              </Button>
              <ResultPreview imageUrl={resizedImageUrl} image={resizedImage} filename={`resized_${resizedImage?.id}.png`} />
            </>
          )}

          {/* ── UPSCALE TAB ── */}
          {activeTab === 'upscale' && (
            <>
              <p className="text-xs text-muted-foreground">Increase image resolution by 2x or 4x using high-quality upscaling.</p>
              <div className="space-y-2">
                <Label>Upload Image</Label>
                <FileUploadArea preview={upscalePreview} fileRef={upscaleFileRef} onChange={(e) => handleFileChange(e, setUpscaleFile, setUpscalePreview)} disabled={isUpscaling} />
              </div>
              <div className="space-y-2">
                <Label>Scale Factor</Label>
                <Select value={upscaleScale} onValueChange={setUpscaleScale} disabled={isUpscaling}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="2">2× (Double resolution)</SelectItem>
                    <SelectItem value="4">4× (Quadruple resolution)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={upscaleImage} disabled={!upscaleFile || isUpscaling} className="w-full">
                {isUpscaling ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Upscaling...</> : <><ZoomIn className="mr-2 h-4 w-4" />Upscale Image</>}
              </Button>
              <ResultPreview imageUrl={upscaledImageUrl} image={upscaledImage} filename={`upscaled_${upscaleScale}x_${upscaledImage?.id}.png`} />
            </>
          )}

        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ImageGenerator;