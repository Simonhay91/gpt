import React, { useState } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { toast } from 'sonner';
import { ImageIcon, Loader2, Download, Sparkles } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ImageGenerator = ({ projectId, onImageGenerated }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [size, setSize] = useState('1024x1024');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState(null);

  const generateImage = async () => {
    if (!prompt.trim()) {
      toast.error('Please enter a prompt');
      return;
    }

    setIsGenerating(true);
    setGeneratedImage(null);

    try {
      const response = await axios.post(`${API}/projects/${projectId}/generate-image`, {
        prompt: prompt.trim(),
        size
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
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `generated_${generatedImage.id}.png`);
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
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            Generate AI Image
          </DialogTitle>
          <DialogDescription>
            Describe the image you want to create. Be specific for better results.
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Prompt</label>
            <Input
              placeholder="A futuristic cityscape at sunset with flying cars..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !isGenerating && generateImage()}
              disabled={isGenerating}
              data-testid="image-prompt-input"
            />
          </div>
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Size</label>
            <Select value={size} onValueChange={setSize} disabled={isGenerating}>
              <SelectTrigger data-testid="image-size-select">
                <SelectValue placeholder="Select size" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1024x1024">Square (1024x1024)</SelectItem>
                <SelectItem value="1024x1792">Portrait (1024x1792)</SelectItem>
                <SelectItem value="1792x1024">Landscape (1792x1024)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
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
                Generate
              </>
            )}
          </Button>
          
          {/* Generated Image Preview */}
          {generatedImage && (
            <div className="mt-4 space-y-3">
              <div className="relative rounded-lg overflow-hidden border border-border">
                <img
                  src={`${API}/images/${generatedImage.id}`}
                  alt={generatedImage.prompt}
                  className="w-full h-auto"
                  data-testid="generated-image-preview"
                />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground truncate max-w-[70%]">
                  {generatedImage.prompt}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={downloadImage}
                  className="gap-2"
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
