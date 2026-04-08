import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import DashboardLayout from '../components/DashboardLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { 
  Package, 
  Search, 
  Plus, 
  Upload, 
  Filter,
  ChevronDown,
  ExternalLink,
  Edit,
  Trash2,
  X,
  Check,
  AlertCircle
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ProductCatalogPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, active: 0, inactive: 0 });
  const [categories, setCategories] = useState({ root_categories: [], vendors: [] });
  
  // Filters
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedVendor, setSelectedVendor] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  
  // Modals
  const [showImportModal, setShowImportModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  
  // Import state
  const [importFile, setImportFile] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [selectedExtraColumns, setSelectedExtraColumns] = useState([]);
  const [importing, setImporting] = useState(false);
  
  // Create form
  const [newProduct, setNewProduct] = useState({
    article_number: '',
    title_en: '',
    vendor: '',
    root_category: '',
    description: ''
  });
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalProducts, setTotalProducts] = useState(0);
  const pageSize = 20;
  
  // Permission check - Admin or Manager can edit
  const canEdit = user?.isAdmin || user?.email?.endsWith('@admin.com');

  const loadProducts = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (selectedCategory) params.append('root_category', selectedCategory);
      if (selectedVendor) params.append('vendor', selectedVendor);
      if (!showInactive) params.append('is_active', 'true');
      params.append('limit', pageSize.toString());
      params.append('offset', ((page - 1) * pageSize).toString());
      
      const response = await axios.get(`${API}/product-catalog?${params}`);
      setProducts(response.data);
    } catch (error) {
      toast.error('Не удалось загрузить продукты');
    } finally {
      setLoading(false);
    }
  }, [search, selectedCategory, selectedVendor, showInactive, page]);

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API}/product-catalog/stats`);
      setStats(response.data);
      setTotalProducts(showInactive ? response.data.total : response.data.active);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const loadCategories = async () => {
    try {
      const response = await axios.get(`${API}/product-catalog/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  };

  useEffect(() => {
    loadProducts();
    loadStats();
    loadCategories();
  }, [loadProducts]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [search, selectedCategory, selectedVendor, showInactive]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      loadProducts();
    }, 300);
    return () => clearTimeout(timer);
  }, [search, loadProducts]);

  const handleImportPreview = async () => {
    if (!importFile) return;
    
    const formData = new FormData();
    formData.append('file', importFile);
    
    try {
      const response = await axios.post(`${API}/product-catalog/import/preview`, formData);
      setImportPreview(response.data);
    } catch (error) {
      toast.error('Не удалось прочитать файл');
    }
  };

  const handleImport = async () => {
    if (!importFile) return;
    
    setImporting(true);
    const formData = new FormData();
    formData.append('file', importFile);
    
    const extraCols = selectedExtraColumns.join(',');
    
    try {
      const response = await axios.post(
        `${API}/product-catalog/import${extraCols ? `?extra_columns=${extraCols}` : ''}`,
        formData
      );
      
      const result = response.data;
      toast.success(
        `Импорт завершён: добавлено ${result.added}, обновлено ${result.updated}, деактивировано ${result.deactivated}`
      );
      
      setShowImportModal(false);
      setImportFile(null);
      setImportPreview(null);
      setSelectedExtraColumns([]);
      loadProducts();
      loadStats();
      loadCategories();
    } catch (error) {
      toast.error('Ошибка импорта');
    } finally {
      setImporting(false);
    }
  };

  const handleCreate = async () => {
    if (!newProduct.article_number || !newProduct.title_en) {
      toast.error('Заполните обязательные поля');
      return;
    }
    
    try {
      await axios.post(`${API}/product-catalog`, newProduct);
      toast.success('Продукт создан');
      setShowCreateModal(false);
      setNewProduct({ article_number: '', title_en: '', vendor: '', root_category: '', description: '' });
      loadProducts();
      loadStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Ошибка создания');
    }
  };

  const handleDelete = async (productId) => {
    if (!window.confirm('Деактивировать этот продукт?')) return;
    
    try {
      await axios.delete(`${API}/product-catalog/${productId}`);
      toast.success('Продукт деактивирован');
      loadProducts();
      loadStats();
    } catch (error) {
      toast.error('Ошибка удаления');
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6" data-testid="product-catalog-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Package className="h-6 w-6" />
              Product Catalog
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {stats.active} активных · {stats.inactive} неактивных · {stats.total} всего
            </p>
          </div>
          
          {canEdit && (
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                onClick={() => setShowImportModal(true)}
                data-testid="import-btn"
              >
                <Upload className="h-4 w-4 mr-2" />
                Импорт CSV
              </Button>
              <Button onClick={() => setShowCreateModal(true)} data-testid="create-product-btn">
                <Plus className="h-4 w-4 mr-2" />
                Добавить
              </Button>
            </div>
          )}
        </div>

        {/* Search & Filters */}
        <div className="space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Поиск по названию, артикулу, вендору..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
                data-testid="search-input"
              />
            </div>
            <Button 
              variant="outline" 
              onClick={() => setShowFilters(!showFilters)}
              data-testid="filter-btn"
            >
              <Filter className="h-4 w-4 mr-2" />
              Фильтры
              <ChevronDown className={`h-4 w-4 ml-2 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
            </Button>
          </div>
          
          {showFilters && (
            <div className="flex flex-wrap gap-4 p-4 bg-muted/50 rounded-lg">
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-3 py-2 rounded-md border bg-background"
              >
                <option value="">Все категории</option>
                {categories.root_categories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
              
              <select
                value={selectedVendor}
                onChange={(e) => setSelectedVendor(e.target.value)}
                className="px-3 py-2 rounded-md border bg-background"
              >
                <option value="">Все вендоры</option>
                {categories.vendors.map(v => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
              
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showInactive}
                  onChange={(e) => setShowInactive(e.target.checked)}
                />
                Показать неактивные
              </label>
            </div>
          )}
        </div>

        {/* Products Table */}
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3 font-medium">Артикул</th>
                <th className="text-left p-3 font-medium">Название</th>
                <th className="text-left p-3 font-medium hidden md:table-cell">Вендор</th>
                <th className="text-left p-3 font-medium hidden lg:table-cell">Категория</th>
                <th className="text-left p-3 font-medium hidden lg:table-cell">Цена</th>
                <th className="text-right p-3 font-medium">Действия</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center p-8 text-muted-foreground">
                    Загрузка...
                  </td>
                </tr>
              ) : products.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center p-8 text-muted-foreground">
                    Продукты не найдены
                  </td>
                </tr>
              ) : (
                products.map(product => (
                  <tr 
                    key={product.id} 
                    className={`border-t hover:bg-muted/30 cursor-pointer ${!product.is_active ? 'opacity-50' : ''}`}
                    onClick={() => navigate(`/product-catalog/${product.id}`)}
                    data-testid={`product-row-${product.article_number}`}
                  >
                    <td className="p-3 font-mono text-sm">{product.article_number}</td>
                    <td className="p-3">
                      <div className="font-medium">{product.title_en}</div>
                      {product.product_model && (
                        <div className="text-xs text-muted-foreground">{product.product_model}</div>
                      )}
                    </td>
                    <td className="p-3 hidden md:table-cell">{product.vendor || '-'}</td>
                    <td className="p-3 hidden lg:table-cell">{product.root_category || '-'}</td>
                    <td className="p-3 hidden lg:table-cell">
                      {product.price ? `$${product.price.toFixed(2)}` : '-'}
                    </td>
                    <td className="p-3 text-right">
                      <div className="flex justify-end gap-1" onClick={e => e.stopPropagation()}>
                        {product.datasheet_url && (
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => window.open(product.datasheet_url, '_blank')}
                          >
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        )}
                        {canEdit && (
                          <>
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => navigate(`/product-catalog/${product.id}`)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => handleDelete(product.id)}
                              className="text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalProducts > pageSize && (
          <div className="flex items-center justify-between px-4 py-3 border rounded-lg bg-muted/30">
            <div className="text-sm text-muted-foreground">
              Показано {((page - 1) * pageSize) + 1} - {Math.min(page * pageSize, totalProducts)} из {totalProducts}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← Назад
              </Button>
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, Math.ceil(totalProducts / pageSize)) }, (_, i) => {
                  const totalPages = Math.ceil(totalProducts / pageSize);
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (page <= 3) {
                    pageNum = i + 1;
                  } else if (page >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = page - 2 + i;
                  }
                  return (
                    <Button
                      key={pageNum}
                      variant={page === pageNum ? "default" : "outline"}
                      size="sm"
                      onClick={() => setPage(pageNum)}
                      className="w-8"
                    >
                      {pageNum}
                    </Button>
                  );
                })}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(Math.ceil(totalProducts / pageSize), p + 1))}
                disabled={page >= Math.ceil(totalProducts / pageSize)}
              >
                Вперёд →
              </Button>
            </div>
          </div>
        )}

        {/* Import Modal */}
        {showImportModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-background rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">Импорт продуктов из CSV</h2>
                <Button variant="ghost" size="sm" onClick={() => {
                  setShowImportModal(false);
                  setImportFile(null);
                  setImportPreview(null);
                }}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              
              {!importPreview ? (
                <div className="space-y-4">
                  <div className="border-2 border-dashed rounded-lg p-8 text-center">
                    <input
                      type="file"
                      accept=".csv,.xlsx"
                      onChange={(e) => setImportFile(e.target.files[0])}
                      className="hidden"
                      id="import-file"
                    />
                    <label htmlFor="import-file" className="cursor-pointer">
                      <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                      <p className="text-lg font-medium">
                        {importFile ? importFile.name : 'Выберите CSV файл'}
                      </p>
                      <p className="text-sm text-muted-foreground mt-2">
                        Обязательные колонки: Article Number, Title EN
                      </p>
                    </label>
                  </div>
                  
                  {importFile && (
                    <Button onClick={handleImportPreview} className="w-full">
                      Предпросмотр
                    </Button>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="bg-muted/50 p-4 rounded-lg">
                    <p><strong>Файл:</strong> {importPreview.filename}</p>
                    <p><strong>Строк:</strong> {importPreview.total_rows}</p>
                  </div>
                  
                  <div>
                    <h3 className="font-medium mb-2 flex items-center gap-2">
                      <Check className="h-4 w-4 text-green-500" />
                      Распознанные колонки ({importPreview.known_columns.length})
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {importPreview.known_columns.map(col => (
                        <span key={col.original} className="px-2 py-1 bg-green-100 dark:bg-green-900/30 rounded text-sm">
                          {col.original} → {col.mapped_to}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  {importPreview.unknown_columns.length > 0 && (
                    <div>
                      <h3 className="font-medium mb-2 flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 text-yellow-500" />
                        Дополнительные колонки ({importPreview.unknown_columns.length})
                      </h3>
                      <p className="text-sm text-muted-foreground mb-2">
                        Выберите колонки для сохранения в extra_fields:
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {importPreview.unknown_columns.map(col => (
                          <label key={col} className="flex items-center gap-2 px-2 py-1 bg-muted rounded cursor-pointer">
                            <input
                              type="checkbox"
                              checked={selectedExtraColumns.includes(col)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedExtraColumns([...selectedExtraColumns, col]);
                                } else {
                                  setSelectedExtraColumns(selectedExtraColumns.filter(c => c !== col));
                                }
                              }}
                            />
                            {col}
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <div className="flex gap-2 pt-4">
                    <Button 
                      variant="outline" 
                      onClick={() => {
                        setImportPreview(null);
                        setImportFile(null);
                      }}
                      className="flex-1"
                    >
                      Назад
                    </Button>
                    <Button 
                      onClick={handleImport} 
                      disabled={importing}
                      className="flex-1"
                    >
                      {importing ? 'Импорт...' : 'Импортировать'}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Create Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-background rounded-lg p-6 max-w-md w-full mx-4">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">Новый продукт</h2>
                <Button variant="ghost" size="sm" onClick={() => setShowCreateModal(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Артикул *</label>
                  <Input
                    value={newProduct.article_number}
                    onChange={(e) => setNewProduct({...newProduct, article_number: e.target.value})}
                    placeholder="TEST-001"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium">Название *</label>
                  <Input
                    value={newProduct.title_en}
                    onChange={(e) => setNewProduct({...newProduct, title_en: e.target.value})}
                    placeholder="Product Name"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium">Вендор</label>
                  <Input
                    value={newProduct.vendor}
                    onChange={(e) => setNewProduct({...newProduct, vendor: e.target.value})}
                    placeholder="Vendor Name"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium">Категория</label>
                  <Input
                    value={newProduct.root_category}
                    onChange={(e) => setNewProduct({...newProduct, root_category: e.target.value})}
                    placeholder="Network"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium">Описание</label>
                  <textarea
                    value={newProduct.description}
                    onChange={(e) => setNewProduct({...newProduct, description: e.target.value})}
                    className="w-full px-3 py-2 rounded-md border bg-background min-h-[100px]"
                    placeholder="Описание продукта..."
                  />
                </div>
                
                <div className="flex gap-2 pt-4">
                  <Button variant="outline" onClick={() => setShowCreateModal(false)} className="flex-1">
                    Отмена
                  </Button>
                  <Button onClick={handleCreate} className="flex-1">
                    Создать
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
