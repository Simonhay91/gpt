import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { toast } from 'sonner';
import { ImageIcon, Loader2, Download, Sparkles, Info } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Planet Image Standard presets
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

const ImageGenerator = ({ projectId, onImageGenerated }) => {
  const [isOpen, setIsOpen] = useState(false);
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

  // Fetch image as blob when generatedImage changes
  useEffect(() => {
    if (generatedImage) {
      fetchImageBlob(generatedImage.id);
    }
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [generatedImage]);

  const fetchImageBlob = async (imageId) => {
    try {
      const response = await axios.get(`${API}/images/${imageId}`, {
        responseType: 'blob'
      });
      const url = URL.createObjectURL(response.data);
      setImageUrl(url);
    } catch (error) {
      console.error('Failed to fetch image:', error);
    }
  };

  const getEffectiveSize = () => {
    if (standard === 'custom') {
      const w = parseInt(customWidth) || 1024;
      const h = parseInt(customHeight) || 1024;
      // Clamp to DALL-E supported sizes
      return '1024x1024'; // DALL-E only supports specific sizes
    }
    
    // Map Planet sizes to closest DALL-E size
    if (sizePreset.includes('1092') || sizePreset.includes('1500') || sizePreset.includes('2000')) {
      return '1024x1024'; // Square
    }
    
    return sizePreset;
  };

  const buildPrompt = () => {
    let enhancedPrompt = prompt.trim();
    
    if (standard === 'planet') {
      // Add Planet Image Standard requirements to prompt
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
    if (!prompt.trim()) {
      toast.error('Please enter a prompt');
      return;
    }

    setIsGenerating(true);
    setGeneratedImage(null);
    setImageUrl(null);

    try {
      const response = await axios.post(`${API}/projects/${projectId}/generate-image`, {
        prompt: buildPrompt(),
        size: getEffectiveSize()
      });
      
      setGeneratedImage(response.data);
      toast.success('Image generated successfully!');
      
      if (onImageGenerated) {
        onImageGenerated(response.data);
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to generate image';
      toast.error(message);
    } finally {
      setIsGenerating(false);
    }
  };

  const downloadImage = async () => {
    if (!generatedImage) return;
    
    try {
      const response = await axios.get(`${API}/images/${generatedImage.id}`, {
        responseType: 'blob'
      });
      
      const ext = backgroundType === 'transparent' ? 'png' : 'jpg';
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `planet_image_${generatedImage.id}.${ext}`);
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
    if (imageUrl) {
      URL.revokeObjectURL(imageUrl);
      setImageUrl(null);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => open ? setIsOpen(true) : handleClose()}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          data-testid="generate-image-btn"
        >
          <ImageIcon className="h-4 w-4" />
          Generate Image
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            Generate AI Image
          </DialogTitle>
          <DialogDescription>
            Create professional product images with Planet Image Standard
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          {/* Image Standard Selection */}
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

          {/* Planet Standard Info */}
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

          {/* Size Selection */}
          {standard === 'planet' && (
            <div className="space-y-2">
              <Label>Size (Square format)</Label>
              <Select value={sizePreset} onValueChange={setSizePreset} disabled={isGenerating}>
                <SelectTrigger data-testid="image-size-select">
                  <SelectValue placeholder="Select size" />
                </SelectTrigger>
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
                <SelectTrigger data-testid="image-size-select">
                  <SelectValue placeholder="Select size" />
                </SelectTrigger>
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
                <Input
                  type="number"
                  placeholder="Width"
                  value={customWidth}
                  onChange={(e) => setCustomWidth(e.target.value)}
                  className="w-24"
                  min="256"
                  max="2048"
                  disabled={isGenerating}
                  data-testid="custom-width-input"
                />
                <span className="text-muted-foreground">×</span>
                <Input
                  type="number"
                  placeholder="Height"
                  value={customHeight}
                  onChange={(e) => setCustomHeight(e.target.value)}
                  className="w-24"
                  min="256"
                  max="2048"
                  disabled={isGenerating}
                  data-testid="custom-height-input"
                />
                <span className="text-xs text-muted-foreground">px</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Note: DALL-E will use closest supported size (1024×1024, 1024×1792, or 1792×1024)
              </p>
            </div>
          )}

          {/* Background Type (for Planet Standard) */}
          {standard === 'planet' && (
            <div className="space-y-2">
              <Label>Background</Label>
              <Select value={backgroundType} onValueChange={setBackgroundType} disabled={isGenerating}>
                <SelectTrigger data-testid="background-type-select">
                  <SelectValue placeholder="Select background" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="transparent">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded border border-border bg-[url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAJElEQVQoU2NkYGD4z4AKGJG5jIxwDgMDA8N/BgYGRpgCuAIYBwD+SQaB3Z9P0wAAAABJRU5ErkJggg==')] bg-repeat" />
                      Transparent (PNG) - First Image
                    </div>
                  </SelectItem>
                  <SelectItem value="white">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded border border-border bg-white" />
                      White Background (JPG) - Additional Images
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Prompt */}
          <div className="space-y-2">
            <Label>Product Description</Label>
            <Textarea
              placeholder={standard === 'planet' 
                ? "Describe your product: e.g., 'wireless bluetooth earbuds in matte black finish with charging case'"
                : "A futuristic cityscape at sunset with flying cars..."
              }
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isGenerating}
              className="min-h-[80px]"
              data-testid="image-prompt-input"
            />
            {standard === 'planet' && (
              <p className="text-xs text-muted-foreground">
                Focus on the product itself. Background, padding, and lighting will be applied automatically.
              </p>
            )}
          </div>
          
          {/* Generate Button */}
          <Button
            onClick={generateImage}
            disabled={!prompt.trim() || isGenerating}
            className="w-full"
            data-testid="confirm-generate-btn"
          >
            {isGenerating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Generate Image
              </>
            )}
          </Button>
          
          {/* Generated Image Preview */}
          {generatedImage && (
            <div className="mt-4 space-y-3">
              <div className="relative rounded-lg overflow-hidden border border-border">
                {imageUrl ? (
                  <div className={backgroundType === 'transparent' 
                    ? "bg-[url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAJElEQVQoU2NkYGD4z4AKGJG5jIxwDgMDA8N/BgYGRpgCuAIYBwD+SQaB3Z9P0wAAAABJRU5ErkJggg==')] bg-repeat"
                    : "bg-white"
                  }>
                    <img
                      src={imageUrl}
                      alt={generatedImage.prompt}
                      className="w-full h-auto"
                      data-testid="generated-image-preview"
                    />
                  </div>
                ) : (
                  <div className="w-full h-48 flex items-center justify-center bg-secondary">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-muted-foreground truncate">
                    {prompt}
                  </p>
                  <p className="text-xs text-emerald-400">
                    {standard === 'planet' ? `Planet Standard • ${sizePreset} • ${backgroundType === 'transparent' ? 'PNG' : 'JPG'}` : sizePreset}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={downloadImage}
                  className="gap-2 shrink-0"
                  data-testid="download-image-btn"
                >
                  <Download className="h-4 w-4" />
                  Download
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ImageGenerator;
