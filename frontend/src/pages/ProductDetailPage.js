import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import DashboardLayout from '../components/DashboardLayout';
import { Button } from '../components/ui/button';
import {
  ArrowLeft,
  ExternalLink,
  MessageSquare,
  Tag,
  Sparkles,
  Loader2,
  Trash2,
  ChevronRight,
  Image as ImageIcon,
  FileText,
  Youtube,
  Box,
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const IMG_PROXY = `${process.env.REACT_APP_BACKEND_URL}/api/planet/img?path=`;

function getImgSrc(img) {
  if (!img) return null;
  // Prefer optimizedPath, fall back to path636px, then path
  const rel = img.optimizedPath || (img.path636px ? `public/${img.path636px}` : null) || img.path || null;
  if (!rel) return null;
  return `${IMG_PROXY}${encodeURIComponent(rel)}`;
}

export default function ProductDetailPage() {
  const slug = useParams()['*'];
  const navigate = useNavigate();
  const { user } = useAuth();

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [learnedAliases, setLearnedAliases] = useState([]);
  const [aiRelations, setAiRelations] = useState([]);
  const [aiRelationsLoading, setAiRelationsLoading] = useState(false);
  const [activeImg, setActiveImg] = useState(0);

  const canDelete = user?.isAdmin || user?.canEditProductCatalog;

  useEffect(() => {
    if (slug) loadProduct();
  }, [slug]);

  const loadProduct = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/planet/products/${slug}`);
      const p = res.data;
      setProduct(p);
      setActiveImg(0);

      const crmCode = p.crmCode;
      if (crmCode) {
        setAiRelationsLoading(true);
        const [aliasesRes, relationsRes] = await Promise.allSettled([
          axios.get(`${API}/planet/by-crm/${crmCode}/aliases`),
          axios.get(`${API}/planet/by-crm/${crmCode}/relations`),
        ]);
        if (aliasesRes.status === 'fulfilled') setLearnedAliases(aliasesRes.value.data || []);
        if (relationsRes.status === 'fulfilled') setAiRelations(relationsRes.value.data || []);
        setAiRelationsLoading(false);
      }
    } catch {
      toast.error('Продукт не найден');
      navigate('/product-catalog');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAlias = async (aliasId) => {
    if (!window.confirm('Delete this alias?')) return;
    try {
      await axios.delete(`${API}/product-matching/aliases/${aliasId}`);
      setLearnedAliases(prev => prev.filter(a => a.id !== aliasId));
      toast.success('Alias deleted');
    } catch {
      toast.error('Failed to delete alias');
    }
  };

  const openChatWithProduct = () => {
    navigate('/dashboard', {
      state: {
        productContext: {
          crm_code: product.crmCode,
          title_en: product.name,
          article_number: product.model,
        },
      },
    });
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </DashboardLayout>
    );
  }

  if (!product) return null;

  const images = (product.images || []).map(getImgSrc).filter(Boolean);
  const currentImg = images[activeImg] || null;

  // All attributes with a name (show even if value is empty)
  const attributes = (product.attributeValues || product.attribute_values || []).filter(av => av.attribute?.name);

  // Category breadcrumb from slug
  const slugParts = (product.slug || slug || '').split('/');
  const categoryParts = slugParts.slice(0, -1);

  const confidenceBadge = (level) => {
    if (level === 'high') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400';
    if (level === 'medium') return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
    return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  };

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-6xl mx-auto" data-testid="product-detail-page">

        {/* Top bar */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => navigate('/product-catalog')}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            {/* Breadcrumb */}
            {categoryParts.length > 0 && (
              <div className="hidden sm:flex items-center gap-1 text-xs text-muted-foreground flex-wrap">
                <span
                  className="hover:text-foreground cursor-pointer"
                  onClick={() => navigate('/product-catalog')}
                >
                  Catalog
                </span>
                {categoryParts.map((part, i) => (
                  <React.Fragment key={i}>
                    <ChevronRight className="h-3 w-3 shrink-0" />
                    <span className="capitalize">{part.replace(/-/g, ' ')}</span>
                  </React.Fragment>
                ))}
              </div>
            )}
          </div>
          <div className="flex gap-2 shrink-0">
            <Button variant="outline" size="sm" onClick={openChatWithProduct}>
              <MessageSquare className="h-4 w-4 mr-2" />
              Chat with AI
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(`https://planetworkspace.com/web/product/${product.slug || slug}`, '_blank')}
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              PlanetWorkspace
            </Button>
          </div>
        </div>

        {/* Hero: Image + Key Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Image panel */}
          <div className="space-y-2">
            <div className="border rounded-xl bg-white dark:bg-muted/10 flex items-center justify-center min-h-64 p-6">
              {currentImg ? (
                <img
                  src={currentImg}
                  alt={product.name}
                  className="max-h-72 max-w-full object-contain"
                  onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling?.style.removeProperty('display'); }}
                />
              ) : (
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                  <ImageIcon className="h-12 w-12 opacity-30" />
                  <span className="text-sm">Нет изображения</span>
                </div>
              )}
              {/* hidden fallback */}
              <span style={{ display: 'none' }} className="flex flex-col items-center gap-2 text-muted-foreground">
                <ImageIcon className="h-12 w-12 opacity-30" />
              </span>
            </div>
            {/* Thumbnails */}
            {images.length > 1 && (
              <div className="flex gap-2 flex-wrap">
                {images.map((src, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveImg(i)}
                    className={`w-14 h-14 border-2 rounded-lg overflow-hidden bg-white dark:bg-muted/10 p-1 transition-colors ${
                      i === activeImg ? 'border-primary' : 'border-transparent hover:border-border'
                    }`}
                  >
                    <img src={src} alt="" className="w-full h-full object-contain" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Key info */}
          <div className="space-y-4">
            {/* Status badges */}
            <div className="flex flex-wrap gap-2">
              {product.isNew && <Badge color="green">New</Badge>}
              {product.isHot && <Badge color="orange">Hot</Badge>}
              {product.isDiscontinued && <Badge color="red">Discontinued</Badge>}
              {(product.brandName || product.vendor) && (
                <Badge color="purple">{product.brandName || product.vendor}</Badge>
              )}
              {(product.category?.name || product.category_name) && (
                <Badge color="blue">{product.category?.name || product.category_name}</Badge>
              )}
            </div>

            <h1 className="text-2xl font-bold leading-tight">
              {product.name || product.title_en || product.model || '—'}
            </h1>

            <div className="grid grid-cols-2 gap-x-6 gap-y-3 pt-1">
              <KV label="CRM Code" value={product.crmCode || product.crm_code} mono />
              <KV label="Модель" value={product.model || product.product_model} mono />
              <KV label="Артикул" value={product.articleCode || product.article_number} mono />
              <KV label="Бренд" value={product.brandName || product.vendor} />
              {(product.inStock ?? 0) > 0 && (
                <KV label="В наличии" value={String(product.inStock)} />
              )}
              {product.moq != null && <KV label="MOQ" value={String(product.moq)} />}
            </div>

            {/* Datasheet download */}
            {product.publicDatasheets?.[0] && (
              <a
                href={`${IMG_PROXY}${encodeURIComponent(product.publicDatasheets[0].path)}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border hover:bg-muted/50 text-sm transition-colors"
              >
                <FileText className="h-4 w-4 text-red-500 shrink-0" />
                <span className="truncate max-w-[220px]">{product.publicDatasheets[0].filename || 'Datasheet (PDF)'}</span>
              </a>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-6">

            {/* Description — HTML from planet API */}
            {product.description && (
              <div className="border rounded-lg p-6 space-y-2">
                <h2 className="text-lg font-semibold">Описание</h2>
                <div
                  className="text-sm leading-relaxed text-muted-foreground prose prose-sm dark:prose-invert max-w-none"
                  dangerouslySetInnerHTML={{ __html: product.description }}
                />
              </div>
            )}

            {/* Features — HTML from planet API */}
            {product.features && (
              <div className="border rounded-lg p-6 space-y-2">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Box className="h-5 w-5 text-primary" />
                  Особенности
                </h2>
                <div
                  className="text-sm leading-relaxed text-muted-foreground prose prose-sm dark:prose-invert max-w-none"
                  dangerouslySetInnerHTML={{ __html: product.features }}
                />
              </div>
            )}

            {/* Technical attributes */}
            {attributes.length > 0 && (
              <div className="border rounded-lg p-6 space-y-3">
                <h2 className="text-lg font-semibold">Технические характеристики</h2>
                <div className="divide-y">
                  {attributes.filter(av => av.textValue || av.numericValue != null).map((av, i) => {
                    const val = av.textValue || String(av.numericValue);
                    const unit = av.attribute?.unit_id ? ` ${av.attribute.unit_id}` : '';
                    return (
                      <div key={i} className="flex justify-between py-2.5 text-sm gap-4">
                        <span className="text-muted-foreground shrink-0">{av.attribute.name.trim()}</span>
                        <span className="font-medium text-right">{val}{unit}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* YouTube video */}
            {product.contentForm?.youtubeUrl && (
              <div className="border rounded-lg p-6 space-y-3">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Youtube className="h-5 w-5 text-red-500" />
                  Видео
                </h2>
                <div className="relative w-full" style={{ paddingBottom: '56.25%' }}>
                  <iframe
                    src={product.contentForm.youtubeUrl}
                    className="absolute inset-0 w-full h-full rounded-lg"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                    title={product.name}
                  />
                </div>
              </div>
            )}

            {/* Learned Aliases */}
            {learnedAliases.length > 0 && (
              <div className="border rounded-lg p-6 space-y-3">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Tag className="h-5 w-5 text-blue-500" />
                  Learned Aliases
                  <span className="text-xs font-normal text-muted-foreground">(из product matching)</span>
                </h2>
                <div className="space-y-2">
                  {learnedAliases.map((a) => (
                    <div key={a.id} className="flex items-center justify-between px-3 py-2 bg-blue-500/5 border border-blue-500/15 rounded-lg">
                      <span className="text-sm">{a.alias}</span>
                      <div className="flex items-center gap-2 shrink-0 ml-4">
                        <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                          a.confidence === 'confirmed'
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : 'bg-muted text-muted-foreground'
                        }`}>
                          {a.confidence}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {a.saved_at ? new Date(a.saved_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : ''}
                        </span>
                        {canDelete && (
                          <button
                            onClick={() => handleDeleteAlias(a.id)}
                            className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                            title="Delete alias"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-6">

            {/* AI Relations */}
            <div className="border rounded-lg p-5">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-5 w-5 text-primary" />
                <h2 className="font-semibold">Both Together</h2>
                <span className="text-xs text-muted-foreground">AI suggested</span>
              </div>
              {aiRelationsLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading…
                </div>
              ) : aiRelations.length === 0 ? (
                <p className="text-sm text-muted-foreground">Нет AI-связей для этого продукта</p>
              ) : (
                <div className="space-y-3">
                  {aiRelations.map((rel, i) => (
                    <div key={i} className="p-3 bg-primary/5 border border-primary/10 rounded-lg">
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-sm leading-tight">{rel.title || rel.crm_code}</p>
                        {rel.confidence && (
                          <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${confidenceBadge(rel.confidence)}`}>
                            {rel.confidence}
                          </span>
                        )}
                      </div>
                      {rel.crm_code && (
                        <p className="text-xs text-muted-foreground font-mono mt-0.5">{rel.crm_code}</p>
                      )}
                      {rel.reason && (
                        <p className="text-xs text-muted-foreground mt-1.5 line-clamp-3 leading-relaxed">{rel.reason}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Meta */}
            <div className="border rounded-lg p-5 space-y-2 text-sm">
              <h2 className="font-semibold mb-3">Метаданные</h2>
              {product.id != null && <MetaRow label="ID" value={String(product.id)} />}
              {(product.crmCode || product.crm_code) && (
                <MetaRow label="CRM Code" value={product.crmCode || product.crm_code} />
              )}
              {(product.articleCode || product.article_number) && (
                <MetaRow label="Артикул" value={product.articleCode || product.article_number} />
              )}
              {(product.category?.name || product.category_name) && (
                <MetaRow label="Категория" value={product.category?.name || product.category_name} />
              )}
              {(product.quantityUnit?.name) && (
                <MetaRow label="Ед. изм." value={product.quantityUnit.name} />
              )}
              {product.createdAt && (
                <MetaRow label="Создан" value={new Date(product.createdAt).toLocaleDateString('ru-RU')} />
              )}
              {product.updatedAt && (
                <MetaRow label="Обновлён" value={new Date(product.updatedAt).toLocaleDateString('ru-RU')} />
              )}
              {product.slug && (
                <div className="pt-2 border-t">
                  <p className="text-muted-foreground text-xs break-all">{product.slug}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function Badge({ color, children }) {
  const colors = {
    green: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    orange: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
    red: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    purple: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
    blue: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[color] || colors.blue}`}>
      {children}
    </span>
  );
}

function KV({ label, value, mono = false }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`font-medium mt-0.5 ${mono ? 'font-mono text-sm' : 'text-sm'}`}>{value}</p>
    </div>
  );
}

function MetaRow({ label, value }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}
