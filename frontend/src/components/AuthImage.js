import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AuthImage = ({ imageId, alt, className, onError }) => {
  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;
    
    const fetchImage = async () => {
      try {
        setLoading(true);
        setError(false);
        const response = await axios.get(`${API}/images/${imageId}`, {
          responseType: 'blob'
        });
        
        if (mounted) {
          const url = URL.createObjectURL(response.data);
          setImageUrl(url);
          setLoading(false);
        }
      } catch (err) {
        if (mounted) {
          setError(true);
          setLoading(false);
          if (onError) onError(err);
        }
      }
    };

    if (imageId) {
      fetchImage();
    }

    return () => {
      mounted = false;
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageId]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center bg-secondary ${className}`} style={{ minHeight: '200px' }}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !imageUrl) {
    return (
      <div className={`flex items-center justify-center bg-secondary text-muted-foreground ${className}`} style={{ minHeight: '200px' }}>
        Failed to load image
      </div>
    );
  }

  return (
    <img
      src={imageUrl}
      alt={alt}
      className={className}
    />
  );
};

export default AuthImage;
