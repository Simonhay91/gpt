import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import DashboardLayout from '../components/DashboardLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { 
  Package, 
  ArrowLeft, 
  Edit, 
  Save,
  X,
  Link2,
  Plus,
  Trash2,
  ExternalLink,
  MessageSquare,
  Tag
} from 'lucide-react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

export default function ProductDetailPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [relatedProducts, setRelatedProducts] = useState([]);
  
  // Add relation modal
  const [showAddRelation, setShowAddRelation] = useState(false);
  const [relationSearch, setRelationSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedRelationType, setSelectedRelationType] = useState('compatible');
  
  const [canEdit, setCanEdit] = useState(false);

  useEffect(() => {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    const isAdmin = user.email?.endsWith('@admin.com') || user.isAdmin;
    setCanEdit(isAdmin);
  }, []);

  useEffect(() => {
    loadProduct();
  }, [productId]);

  const loadProduct = async () => {
    try {
      const response = await axios.get(`${API}/product-catalog/${productId}`);
      setProduct(response.data);
      setEditData(response.data);
      
      // Load related products
      if (response.data.relations?.length > 0) {
        const relatedIds = response.data.relations.map(r => r.product_id);
        const relatedResponse = await axios.get(`${API}/product-catalog?limit=100`);
        const related = relatedResponse.data.filter(p => relatedIds.includes(p.id));
        setRelatedProducts(related);
      }
    } catch (error) {
      toast.error('Продукт не найден');
      navigate('/product-catalog');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      await axios.put(`${API}/product-catalog/${productId}`, editData);
      toast.success('Продукт обновлён');
      setEditing(false);
      loadProduct();
    } catch (error) {
      toast.error('Ошибка сохранения');
    }
  };

  const searchProducts = async (query) => {
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    try {
      const response = await axios.get(`${API}/product-catalog?search=${query}&limit=10`);
      // Filter out current product and already related products
      const existingRelationIds = product.relations?.map(r => r.product_id) || [];
      const filtered = response.data.filter(
        p => p.id !== productId && !existingRelationIds.includes(p.id)
      );
      setSearchResults(filtered);
    } catch (error) {
      console.error('Search error:', error);
    }
  };

  const addRelation = async (relatedProductId) => {
    try {
      await axios.post(`${API}/product-catalog/${productId}/relations`, {
        product_id: relatedProductId,
        relation_type: selectedRelationType
      });
      toast.success('Связь добавлена');
      setShowAddRelation(false);
      setRelationSearch('');
      setSearchResults([]);
      loadProduct();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка добавления связи');
    }
  };

  const removeRelation = async (relatedProductId) => {
    if (!window.confirm('Удалить эту связь?')) return;
    
    try {
      await axios.delete(`${API}/product-catalog/${productId}/relations/${relatedProductId}`);
      toast.success('Связь удалена');
      loadProduct();
    } catch (error) {
      toast.error('Ошибка удаления связи');
    }
  };

  const openChatWithProduct = () => {
    // Navigate to chat with product context
    navigate('/dashboard', { 
      state: { 
        productContext: {
          id: product.id,
          article_number: product.article_number,
          title_en: product.title_en
        }
      }
    });
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Загрузка...</div>
        </div>
      </DashboardLayout>
    );
  }

  if (!product) return null;

  const getRelationLabel = (type) => {
    switch (type) {
      case 'compatible': return 'Совместим';
      case 'bundle': return 'В комплекте';
      case 'requires': return 'Требует';
      default: return type;
    }
  };

  const getRelationColor = (type) => {
    switch (type) {
      case 'compatible': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
      case 'bundle': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400';
      case 'requires': return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6" data-testid="product-detail-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => navigate('/product-catalog')}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Package className="h-6 w-6" />
                {product.title_en}
              </h1>
              <p className="text-sm text-muted-foreground font-mono">{product.article_number}</p>
            </div>
          </div>
          
          <div className="flex gap-2">
            <Button variant="outline" onClick={openChatWithProduct}>
              <MessageSquare className="h-4 w-4 mr-2" />
              Chat with AI
            </Button>
            {canEdit && !editing && (
              <Button onClick={() => setEditing(true)}>
                <Edit className="h-4 w-4 mr-2" />
                Редактировать
              </Button>
            )}
            {editing && (
              <>
                <Button variant="outline" onClick={() => { setEditing(false); setEditData(product); }}>
                  <X className="h-4 w-4 mr-2" />
                  Отмена
                </Button>
                <Button onClick={handleSave}>
                  <Save className="h-4 w-4 mr-2" />
                  Сохранить
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Status badges */}
        <div className="flex flex-wrap gap-2">
          {!product.is_active && (
            <span className="px-2 py-1 bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 rounded text-sm">
              Неактивен
            </span>
          )}
          {product.source === 'csv_import' && (
            <span className="px-2 py-1 bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 rounded text-sm">
              Импорт CSV
            </span>
          )}
          {product.vendor && (
            <span className="px-2 py-1 bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400 rounded text-sm">
              {product.vendor}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Info */}
          <div className="lg:col-span-2 space-y-6">
            {/* Basic Info Card */}
            <div className="border rounded-lg p-6 space-y-4">
              <h2 className="text-lg font-semibold">Основная информация</h2>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-muted-foreground">Название</label>
                  {editing ? (
                    <Input
                      value={editData.title_en || ''}
                      onChange={(e) => setEditData({...editData, title_en: e.target.value})}
                    />
                  ) : (
                    <p className="font-medium">{product.title_en}</p>
                  )}
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">CRM Code</label>
                  {editing ? (
                    <Input
                      value={editData.crm_code || ''}
                      onChange={(e) => setEditData({...editData, crm_code: e.target.value})}
                    />
                  ) : (
                    <p className="font-medium">{product.crm_code || '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">Вендор</label>
                  {editing ? (
                    <Input
                      value={editData.vendor || ''}
                      onChange={(e) => setEditData({...editData, vendor: e.target.value})}
                    />
                  ) : (
                    <p className="font-medium">{product.vendor || '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">Модель</label>
                  {editing ? (
                    <Input
                      value={editData.product_model || ''}
                      onChange={(e) => setEditData({...editData, product_model: e.target.value})}
                    />
                  ) : (
                    <p className="font-medium">{product.product_model || '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">Цена</label>
                  {editing ? (
                    <Input
                      type="number"
                      value={editData.price || ''}
                      onChange={(e) => setEditData({...editData, price: parseFloat(e.target.value) || null})}
                    />
                  ) : (
                    <p className="font-medium">{product.price ? `$${product.price.toFixed(2)}` : '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">Datasheet</label>
                  {editing ? (
                    <Input
                      value={editData.datasheet_url || ''}
                      onChange={(e) => setEditData({...editData, datasheet_url: e.target.value})}
                      placeholder="https://..."
                    />
                  ) : product.datasheet_url ? (
                    <a 
                      href={product.datasheet_url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-primary hover:underline flex items-center gap-1"
                    >
                      Открыть <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : (
                    <p className="text-muted-foreground">-</p>
                  )}
                </div>
              </div>
            </div>

            {/* Categories */}
            <div className="border rounded-lg p-6 space-y-4">
              <h2 className="text-lg font-semibold">Категории</h2>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-muted-foreground">Root Category</label>
                  {editing ? (
                    <Input
                      value={editData.root_category || ''}
                      onChange={(e) => setEditData({...editData, root_category: e.target.value})}
                    />
                  ) : (
                    <p className="font-medium">{product.root_category || '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">LVL 1</label>
                  <p className="font-medium">{product.lvl1_subcategory || '-'}</p>
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">LVL 2</label>
                  <p className="font-medium">{product.lvl2_subcategory || '-'}</p>
                </div>
                
                <div>
                  <label className="text-sm text-muted-foreground">LVL 3</label>
                  <p className="font-medium">{product.lvl3_subcategory || '-'}</p>
                </div>
              </div>
            </div>

            {/* Description & Features */}
            <div className="border rounded-lg p-6 space-y-4">
              <h2 className="text-lg font-semibold">Описание и характеристики</h2>
              
              {product.description && (
                <div>
                  <label className="text-sm text-muted-foreground">Описание</label>
                  <p className="mt-1 whitespace-pre-wrap">{product.description}</p>
                </div>
              )}
              
              {product.features && (
                <div>
                  <label className="text-sm text-muted-foreground">Features</label>
                  <p className="mt-1 whitespace-pre-wrap">{product.features}</p>
                </div>
              )}
              
              {product.attribute_values && (
                <div>
                  <label className="text-sm text-muted-foreground">Атрибуты</label>
                  <p className="mt-1 whitespace-pre-wrap">{product.attribute_values}</p>
                </div>
              )}
            </div>

            {/* Aliases */}
            {product.aliases?.length > 0 && (
              <div className="border rounded-lg p-6 space-y-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Tag className="h-5 w-5" />
                  Алиасы
                </h2>
                <div className="flex flex-wrap gap-2">
                  {product.aliases.map((alias, i) => (
                    <span key={i} className="px-2 py-1 bg-muted rounded text-sm">
                      {alias}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Extra Fields */}
            {product.extra_fields && Object.keys(product.extra_fields).length > 0 && (
              <div className="border rounded-lg p-6 space-y-4">
                <h2 className="text-lg font-semibold">Дополнительные поля</h2>
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(product.extra_fields).map(([key, value]) => (
                    <div key={key}>
                      <label className="text-sm text-muted-foreground capitalize">{key}</label>
                      <p className="font-medium">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Relations Sidebar */}
          <div className="space-y-6">
            <div className="border rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Link2 className="h-5 w-5" />
                  Связи
                </h2>
                {canEdit && (
                  <Button size="sm" variant="outline" onClick={() => setShowAddRelation(true)}>
                    <Plus className="h-4 w-4" />
                  </Button>
                )}
              </div>
              
              {product.relations?.length > 0 ? (
                <div className="space-y-3">
                  {product.relations.map((relation) => {
                    const relatedProduct = relatedProducts.find(p => p.id === relation.product_id);
                    return (
                      <div 
                        key={relation.product_id}
                        className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                      >
                        <div className="flex-1 min-w-0">
                          <span className={`inline-block px-2 py-0.5 rounded text-xs mb-1 ${getRelationColor(relation.relation_type)}`}>
                            {getRelationLabel(relation.relation_type)}
                          </span>
                          {relatedProduct ? (
                            <p 
                              className="font-medium truncate cursor-pointer hover:text-primary"
                              onClick={() => navigate(`/product-catalog/${relation.product_id}`)}
                            >
                              {relatedProduct.title_en}
                            </p>
                          ) : (
                            <p className="text-muted-foreground text-sm">ID: {relation.product_id}</p>
                          )}
                        </div>
                        {canEdit && (
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => removeRelation(relation.product_id)}
                            className="text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">Нет связанных продуктов</p>
              )}
            </div>

            {/* Meta Info */}
            <div className="border rounded-lg p-6 space-y-3 text-sm">
              <h2 className="font-semibold">Метаданные</h2>
              <div className="space-y-2 text-muted-foreground">
                <p>Создан: {new Date(product.created_at).toLocaleDateString()}</p>
                {product.updated_at && (
                  <p>Обновлён: {new Date(product.updated_at).toLocaleDateString()}</p>
                )}
                {product.last_synced_at && (
                  <p>Синхронизация: {new Date(product.last_synced_at).toLocaleDateString()}</p>
                )}
                <p>Источник: {product.source === 'csv_import' ? 'CSV импорт' : 'Вручную'}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Add Relation Modal */}
        {showAddRelation && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-background rounded-lg p-6 max-w-md w-full mx-4">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">Добавить связь</h2>
                <Button variant="ghost" size="sm" onClick={() => {
                  setShowAddRelation(false);
                  setRelationSearch('');
                  setSearchResults([]);
                }}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Тип связи</label>
                  <select
                    value={selectedRelationType}
                    onChange={(e) => setSelectedRelationType(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border bg-background mt-1"
                  >
                    <option value="compatible">Совместим (compatible)</option>
                    <option value="bundle">В комплекте (bundle)</option>
                    <option value="requires">Требует (requires)</option>
                  </select>
                </div>
                
                <div>
                  <label className="text-sm font-medium">Поиск продукта</label>
                  <Input
                    value={relationSearch}
                    onChange={(e) => {
                      setRelationSearch(e.target.value);
                      searchProducts(e.target.value);
                    }}
                    placeholder="Введите название или артикул..."
                    className="mt-1"
                  />
                </div>
                
                {searchResults.length > 0 && (
                  <div className="border rounded-lg max-h-60 overflow-y-auto">
                    {searchResults.map(p => (
                      <div
                        key={p.id}
                        className="p-3 hover:bg-muted cursor-pointer border-b last:border-b-0"
                        onClick={() => addRelation(p.id)}
                      >
                        <p className="font-medium">{p.title_en}</p>
                        <p className="text-sm text-muted-foreground">{p.article_number}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
