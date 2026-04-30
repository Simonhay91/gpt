import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import DashboardLayout from '../components/DashboardLayout';
import { Button } from '../components/ui/button';
import {
  Package,
  ArrowLeft,
  ExternalLink,
  MessageSquare,
  Tag,
  Sparkles,
  Loader2,
  Trash2,
  ChevronRight,
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ProductDetailPage() {
  const slug = useParams()['*'];
  const navigate = useNavigate();
  const { user } = useAuth();

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [learnedAliases, setLearnedAliases] = useState([]);
  const [aiRelations, setAiRelations] = useState([]);
  const [aiRelationsLoading, setAiRelationsLoading] = useState(false);

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

      const crmCode = p.crmCode;
      if (crmCode) {
        // Load aliases and relations in parallel
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

  // Derive image URL
  const images = product.images || [];
  const mainImage = images[0]?.url || images[0]?.large || null;

  // Attributes
  const attributes = (product.attributeValues || []).filter(
    av => av.textValue || av.numericValue != null
  );

  // Category breadcrumb from slug
  const slugParts = (product.slug || slug || '').split('/');

  const confidenceBadge = (level) => {
    if (level === 'high') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400';
    if (level === 'medium') return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
    return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  };

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-6xl mx-auto" data-testid="product-detail-page">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate('/product-catalog')}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              {/* Breadcrumb */}
              {slugParts.length > 1 && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1 flex-wrap">
                  {slugParts.slice(0, -1).map((part, i) => (
                    <React.Fragment key={i}>
                      <span className="capitalize">{part.replace(/-/g, ' ')}</span>
                      {i < slugParts.length - 2 && <ChevronRight className="h-3 w-3" />}
                    </React.Fragment>
                  ))}
                </div>
              )}
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Package className="h-6 w-6 shrink-0" />
                {product.name}
              </h1>
              {product.model && (
                <p className="text-sm text-muted-foreground font-mono mt-0.5">{product.model}</p>
              )}
            </div>
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

        {/* Status badges */}
        <div className="flex flex-wrap gap-2">
          {product.isNew && (
            <span className="px-2 py-1 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 rounded text-xs font-medium">New</span>
          )}
          {product.isHot && (
            <span className="px-2 py-1 bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400 rounded text-xs font-medium">Hot</span>
          )}
          {product.isDiscontinued && (
            <span className="px-2 py-1 bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 rounded text-xs font-medium">Discontinued</span>
          )}
          {product.brandName && (
            <span className="px-2 py-1 bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400 rounded text-xs font-medium">
              {product.brandName}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left — Main Info */}
          <div className="lg:col-span-2 space-y-6">

            {/* Image */}
            {mainImage && (
              <div className="border rounded-lg overflow-hidden bg-muted/30 flex items-center justify-center p-4">
                <img
                  src={mainImage}
                  alt={product.name}
                  className="max-h-64 object-contain"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              </div>
            )}

            {/* Basic info */}
            <div className="border rounded-lg p-6 space-y-4">
              <h2 className="text-lg font-semibold">Основная информация</h2>
              <div className="grid grid-cols-2 gap-4">
                <InfoField label="Название" value={product.name} />
                <InfoField label="CRM Code" value={product.crmCode} mono />
                <InfoField label="Модель" value={product.model} mono />
                <InfoField label="Артикул" value={product.articleCode || product.model} mono />
                <InfoField label="Вендор / Бренд" value={product.brandName} />
                {product.moq != null && <InfoField label="MOQ" value={String(product.moq)} />}
                {product.productionDays != null && <InfoField label="Production days" value={String(product.productionDays)} />}
                {product.stockAmount != null && <InfoField label="Остаток" value={String(product.stockAmount)} />}
              </div>
            </div>

            {/* Category path */}
            {slugParts.length > 1 && (
              <div className="border rounded-lg p-6 space-y-3">
                <h2 className="text-lg font-semibold">Категории</h2>
                <div className="flex flex-wrap gap-2">
                  {slugParts.slice(0, -1).map((part, i) => (
                    <React.Fragment key={i}>
                      <span className="px-2 py-1 bg-muted rounded text-sm capitalize">
                        {part.replace(/-/g, ' ')}
                      </span>
                      {i < slugParts.length - 2 && <ChevronRight className="h-4 w-4 text-muted-foreground self-center" />}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}

            {/* Description */}
            {(product.description || product.shortDescription) && (
              <div className="border rounded-lg p-6 space-y-3">
                <h2 className="text-lg font-semibold">Описание</h2>
                {product.shortDescription && (
                  <p className="text-sm text-muted-foreground">{product.shortDescription}</p>
                )}
                {product.description && (
                  <p className="text-sm whitespace-pre-wrap">{product.description}</p>
                )}
              </div>
            )}

            {/* Technical attributes */}
            {attributes.length > 0 && (
              <div className="border rounded-lg p-6 space-y-3">
                <h2 className="text-lg font-semibold">Технические характеристики</h2>
                <div className="divide-y">
                  {attributes.map((av, i) => (
                    <div key={i} className="flex justify-between py-2 text-sm">
                      <span className="text-muted-foreground">{av.attribute?.name || `Attr ${av.attributeId}`}</span>
                      <span className="font-medium text-right ml-4">
                        {av.textValue || (av.numericValue != null ? String(av.numericValue) : '')}
                        {av.attribute?.unit_id ? ` ${av.attribute.unit_id}` : ''}
                      </span>
                    </div>
                  ))}
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

          {/* Right — sidebar */}
          <div className="space-y-6">

            {/* AI Relations */}
            <div className="border rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Both Together</h2>
                <span className="text-xs text-muted-foreground font-normal">AI suggested</span>
              </div>
              {aiRelationsLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading…
                </div>
              ) : aiRelations.length === 0 ? (
                <p className="text-sm text-muted-foreground">Нет AI-связей</p>
              ) : (
                <div className="space-y-3">
                  {aiRelations.map((rel, i) => (
                    <div
                      key={i}
                      className="p-3 bg-primary/5 border border-primary/10 rounded-lg"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-sm">{rel.title || rel.crm_code}</p>
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
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{rel.reason}</p>
                      )}
                      {rel.rule_title && (
                        <p className="text-xs text-muted-foreground/60 mt-1">Rule: {rel.rule_title}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Meta Info */}
            <div className="border rounded-lg p-6 space-y-2 text-sm">
              <h2 className="font-semibold mb-3">Метаданные</h2>
              {product.id && <MetaRow label="ID" value={String(product.id)} />}
              {product.crmCode && <MetaRow label="CRM Code" value={product.crmCode} />}
              {product.slug && <MetaRow label="Slug" value={product.slug} small />}
              {product.createdAt && <MetaRow label="Создан" value={new Date(product.createdAt).toLocaleDateString('ru-RU')} />}
              {product.updatedAt && <MetaRow label="Обновлён" value={new Date(product.updatedAt).toLocaleDateString('ru-RU')} />}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function InfoField({ label, value, mono = false, small = false }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
      <p className={`font-medium ${mono ? 'font-mono text-sm' : ''} ${small ? 'text-xs' : ''}`}>{value}</p>
    </div>
  );
}

function MetaRow({ label, value, small = false }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={`text-right ${small ? 'text-xs break-all' : ''}`}>{value}</span>
    </div>
  );
}
