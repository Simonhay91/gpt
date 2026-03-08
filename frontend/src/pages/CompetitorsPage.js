import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { TrendingUp, Plus, RefreshCw, ExternalLink, Trash2, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useLanguage } from '../contexts/LanguageContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CompetitorsPage = () => {
  const { language } = useLanguage();
  const [competitors, setCompetitors] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [selectedCompetitor, setSelectedCompetitor] = useState(null);
  const [isProductDialogOpen, setIsProductDialogOpen] = useState(false);
  const [isMatchDialogOpen, setIsMatchDialogOpen] = useState(false);
  const [isFetching, setIsFetching] = useState({});
  const [sources, setSources] = useState([]);  // For matching
  
  const [newCompetitor, setNewCompetitor] = useState({ name: '', website: '' });
  const [newProduct, setNewProduct] = useState({ url: '', auto_refresh: false, refresh_interval_days: 7 });
  const [newMatch, setNewMatch] = useState({ competitor_product_url: '', our_product_ref: '', match_type: 'manual' });

  useEffect(() => {
    loadCompetitors();
    loadSources();
  }, []);

  const loadSources = async () => {
    try {
      const response = await axios.get(`${API}/sources`);
      setSources(response.data.items || []);
    } catch (error) {
      console.error('Failed to load sources:', error);
    }
  };

  const loadCompetitors = async () => {
    try {
      const response = await axios.get(`${API}/competitors`);
      setCompetitors(response.data);
    } catch (error) {
      console.error('Failed to load competitors:', error);
      if (error.response?.status === 403) {
        toast.error(language === 'ru' ? 'Доступ запрещён' : 'Access denied');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const addCompetitor = async () => {
    try {
      await axios.post(`${API}/competitors`, newCompetitor);
      toast.success(language === 'ru' ? 'Конкурент добавлен' : 'Competitor added');
      setIsAddDialogOpen(false);
      setNewCompetitor({ name: '', website: '' });
      loadCompetitors();
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка добавления' : 'Failed to add');
    }
  };

  const deleteCompetitor = async (id) => {
    if (!window.confirm(language === 'ru' ? 'Удалить конкурента?' : 'Delete competitor?')) return;
    
    try {
      await axios.delete(`${API}/competitors/${id}`);
      toast.success(language === 'ru' ? 'Конкурент удалён' : 'Competitor deleted');
      loadCompetitors();
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка удаления' : 'Failed to delete');
    }
  };

  const addProduct = async () => {
    try {
      await axios.post(`${API}/competitors/${selectedCompetitor.id}/products`, newProduct);
      toast.success(language === 'ru' ? 'Продукт добавлен' : 'Product added');
      setIsProductDialogOpen(false);
      setNewProduct({ url: '', auto_refresh: false, refresh_interval_days: 7 });
      loadCompetitors();
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка добавления' : 'Failed to add');
    }
  };

  const deleteProduct = async (competitorId, productId) => {
    try {
      await axios.delete(`${API}/competitors/${competitorId}/products/${productId}`);
      toast.success(language === 'ru' ? 'Продукт удалён' : 'Product deleted');
      loadCompetitors();
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка удаления' : 'Failed to delete');
    }
  };

  const fetchProduct = async (competitorId, productId) => {
    setIsFetching(prev => ({ ...prev, [productId]: true }));
    try {
      await axios.post(`${API}/competitors/${competitorId}/products/${productId}/fetch`);
      toast.success(language === 'ru' ? 'Контент обновлён' : 'Content updated');
      loadCompetitors();
    } catch (error) {
      toast.error(error.response?.data?.detail || (language === 'ru' ? 'Ошибка загрузки' : 'Failed to fetch'));
    } finally {
      setIsFetching(prev => ({ ...prev, [productId]: false }));
    }
  };

  const refreshAllProducts = async (competitorId) => {
    try {
      const response = await axios.post(`${API}/competitors/${competitorId}/refresh`);
      toast.success(`${language === 'ru' ? 'Обновлено' : 'Updated'}: ${response.data.success_count}/${response.data.total}`);
      loadCompetitors();
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка обновления' : 'Failed to refresh');
    }
  };

  const addMatch = async () => {
    try {
      const competitor = competitors.find(c => c.id === selectedCompetitor.id);
      const existingMatches = competitor?.matched_our_products || [];
      
      await axios.put(`${API}/competitors/${selectedCompetitor.id}/match`, {
        matched_our_products: [...existingMatches, newMatch]
      });
      
      toast.success(language === 'ru' ? 'Match добавлен' : 'Match added');
      setIsMatchDialogOpen(false);
      setNewMatch({ competitor_product_url: '', our_product_ref: '', match_type: 'manual' });
      loadCompetitors();
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка добавления' : 'Failed to add');
    }
  };

  const removeMatch = async (competitorId, matchUrl) => {
    try {
      const competitor = competitors.find(c => c.id === competitorId);
      const updatedMatches = competitor.matched_our_products.filter(m => m.competitor_product_url !== matchUrl);
      
      await axios.put(`${API}/competitors/${competitorId}/match`, {
        matched_our_products: updatedMatches
      });
      
      toast.success(language === 'ru' ? 'Match удалён' : 'Match removed');
      loadCompetitors();
    } catch (error) {
      toast.error(language === 'ru' ? 'Ошибка удаления' : 'Failed to remove');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return language === 'ru' ? 'Никогда' : 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-500/20">
                <TrendingUp className="h-7 w-7 text-orange-500" />
              </div>
              {language === 'ru' ? 'Competitor Tracker' : 'Competitor Tracker'}
            </h1>
            <p className="text-muted-foreground mt-2">
              {language === 'ru' 
                ? 'Отслеживайте конкурентов и их продукты' 
                : 'Track competitors and their products'}
            </p>
          </div>
          <Button onClick={() => setIsAddDialogOpen(true)} className="bg-orange-500 hover:bg-orange-600">
            <Plus className="h-4 w-4 mr-2" />
            {language === 'ru' ? 'Добавить конкурента' : 'Add Competitor'}
          </Button>
        </div>

        {/* Competitors List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="spinner" />
          </div>
        ) : competitors.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <TrendingUp className="h-16 w-16 text-muted-foreground mb-4" />
              <p className="text-lg font-medium">
                {language === 'ru' ? 'Нет конкурентов' : 'No competitors'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {language === 'ru' ? 'Добавьте первого конкурента' : 'Add your first competitor'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6">
            {competitors.map((competitor) => (
              <Card key={competitor.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-xl">{competitor.name}</CardTitle>
                      <CardDescription className="flex items-center gap-2 mt-1">
                        <ExternalLink className="h-3 w-3" />
                        <a href={competitor.website} target="_blank" rel="noopener noreferrer" className="hover:underline">
                          {competitor.website}
                        </a>
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refreshAllProducts(competitor.id)}
                      >
                        <RefreshCw className="h-4 w-4 mr-1" />
                        {language === 'ru' ? 'Обновить всё' : 'Refresh All'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteCompetitor(competitor.id)}
                      >
                        <Trash2 className="h-4 w-4 text-red-400" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Products */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium">
                        {language === 'ru' ? 'Продукты' : 'Products'} ({competitor.products?.length || 0})
                      </h3>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedCompetitor(competitor);
                          setIsProductDialogOpen(true);
                        }}
                      >
                        <Plus className="h-3 w-3 mr-1" />
                        {language === 'ru' ? 'Добавить' : 'Add'}
                      </Button>
                    </div>
                    
                    {competitor.products?.length > 0 ? (
                      <div className="space-y-2">
                        {competitor.products.map((product) => (
                          <div key={product.id} className="flex items-center justify-between p-3 border rounded-lg bg-secondary/30">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <a
                                  href={product.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm font-medium hover:underline"
                                >
                                  {product.title || product.url}
                                </a>
                                {product.cached_content && (
                                  <Badge variant="outline" className="text-xs">
                                    <CheckCircle className="h-3 w-3 mr-1" />
                                    Cached
                                  </Badge>
                                )}
                              </div>
                              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatDate(product.last_fetched)}
                                </span>
                                {product.auto_refresh && (
                                  <Badge variant="secondary" className="text-xs">
                                    Auto ({product.refresh_interval_days}d)
                                  </Badge>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => fetchProduct(competitor.id, product.id)}
                                disabled={isFetching[product.id]}
                              >
                                {isFetching[product.id] ? (
                                  <div className="spinner h-4 w-4" />
                                ) : (
                                  <RefreshCw className="h-4 w-4" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => deleteProduct(competitor.id, product.id)}
                              >
                                <Trash2 className="h-4 w-4 text-red-400" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        {language === 'ru' ? 'Нет продуктов' : 'No products'}
                      </p>
                    )}
                  </div>
                  
                  {/* Matching Section */}
                  <div className="mt-6 pt-6 border-t">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium">
                        {language === 'ru' ? 'Product Matching' : 'Product Matching'} ({competitor.matched_our_products?.length || 0})
                      </h3>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedCompetitor(competitor);
                          setIsMatchDialogOpen(true);
                        }}
                      >
                        <Plus className="h-3 w-3 mr-1" />
                        {language === 'ru' ? 'Add Match' : 'Add Match'}
                      </Button>
                    </div>
                    
                    {competitor.matched_our_products?.length > 0 ? (
                      <div className="space-y-2">
                        {competitor.matched_our_products.map((match, idx) => {
                          const source = sources.find(s => s.id === match.our_product_ref);
                          return (
                            <div key={idx} className="flex items-center justify-between p-3 border rounded-lg bg-green-500/5 border-green-500/20">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <Badge variant="outline" className="text-xs bg-green-500/10">
                                    {match.match_type}
                                  </Badge>
                                  <span className="text-xs text-muted-foreground">{match.competitor_product_url}</span>
                                </div>
                                <p className="text-sm font-medium">
                                  ↔ {source?.name || match.our_product_ref}
                                </p>
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => removeMatch(competitor.id, match.competitor_product_url)}
                              >
                                <Trash2 className="h-4 w-4 text-red-400" />
                              </Button>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        {language === 'ru' ? 'Нет matches' : 'No matches'}
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Add Competitor Dialog */}
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {language === 'ru' ? 'Добавить конкурента' : 'Add Competitor'}
              </DialogTitle>
              <DialogDescription>
                {language === 'ru' 
                  ? 'Добавьте информацию о конкуренте' 
                  : 'Add competitor information'}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">{language === 'ru' ? 'Название' : 'Name'}</Label>
                <Input
                  id="name"
                  placeholder={language === 'ru' ? 'Competitor A' : 'Competitor A'}
                  value={newCompetitor.name}
                  onChange={(e) => setNewCompetitor({ ...newCompetitor, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="website">{language === 'ru' ? 'Сайт' : 'Website'}</Label>
                <Input
                  id="website"
                  placeholder="https://competitor.com"
                  value={newCompetitor.website}
                  onChange={(e) => setNewCompetitor({ ...newCompetitor, website: e.target.value })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                {language === 'ru' ? 'Отмена' : 'Cancel'}
              </Button>
              <Button
                onClick={addCompetitor}
                disabled={!newCompetitor.name || !newCompetitor.website}
                className="bg-orange-500 hover:bg-orange-600"
              >
                {language === 'ru' ? 'Добавить' : 'Add'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Add Product Dialog */}
        <Dialog open={isProductDialogOpen} onOpenChange={setIsProductDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {language === 'ru' ? 'Добавить продукт' : 'Add Product'}
              </DialogTitle>
              <DialogDescription>
                {selectedCompetitor?.name}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="product-url">URL</Label>
                <Input
                  id="product-url"
                  placeholder="https://competitor.com/product"
                  value={newProduct.url}
                  onChange={(e) => setNewProduct({ ...newProduct, url: e.target.value })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>{language === 'ru' ? 'Авто-обновление' : 'Auto-refresh'}</Label>
                  <p className="text-xs text-muted-foreground">
                    {language === 'ru' ? 'Автоматически обновлять контент' : 'Automatically update content'}
                  </p>
                </div>
                <Switch
                  checked={newProduct.auto_refresh}
                  onCheckedChange={(checked) => setNewProduct({ ...newProduct, auto_refresh: checked })}
                />
              </div>
              {newProduct.auto_refresh && (
                <div className="space-y-2">
                  <Label>{language === 'ru' ? 'Интервал (дни)' : 'Interval (days)'}</Label>
                  <Select
                    value={String(newProduct.refresh_interval_days)}
                    onValueChange={(value) => setNewProduct({ ...newProduct, refresh_interval_days: parseInt(value) })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 {language === 'ru' ? 'день' : 'day'}</SelectItem>
                      <SelectItem value="7">7 {language === 'ru' ? 'дней' : 'days'}</SelectItem>
                      <SelectItem value="14">14 {language === 'ru' ? 'дней' : 'days'}</SelectItem>
                      <SelectItem value="30">30 {language === 'ru' ? 'дней' : 'days'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsProductDialogOpen(false)}>
                {language === 'ru' ? 'Отмена' : 'Cancel'}
              </Button>
              <Button
                onClick={addProduct}
                disabled={!newProduct.url}
                className="bg-orange-500 hover:bg-orange-600"
              >
                {language === 'ru' ? 'Добавить' : 'Add'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Add Match Dialog */}
        <Dialog open={isMatchDialogOpen} onOpenChange={setIsMatchDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {language === 'ru' ? 'Add Product Match' : 'Add Product Match'}
              </DialogTitle>
              <DialogDescription>
                {selectedCompetitor?.name}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>
                  {language === 'ru' ? 'Competitor Product URL' : 'Competitor Product URL'}
                </Label>
                <Select
                  value={newMatch.competitor_product_url}
                  onValueChange={(value) => setNewMatch({ ...newMatch, competitor_product_url: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={language === 'ru' ? 'Выберите продукт' : 'Select product'} />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedCompetitor?.products?.map((product) => (
                      <SelectItem key={product.id} value={product.url}>
                        {product.title || product.url}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>{language === 'ru' ? 'Match Type' : 'Match Type'}</Label>
                <Select
                  value={newMatch.match_type}
                  onValueChange={(value) => setNewMatch({ ...newMatch, match_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="auto">Auto (AI)</SelectItem>
                    <SelectItem value="category">Category</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              {newMatch.match_type === 'manual' && (
                <div className="space-y-2">
                  <Label>
                    {language === 'ru' ? 'Our Product (Source)' : 'Our Product (Source)'}
                  </Label>
                  <Select
                    value={newMatch.our_product_ref}
                    onValueChange={(value) => setNewMatch({ ...newMatch, our_product_ref: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={language === 'ru' ? 'Выберите источник' : 'Select source'} />
                    </SelectTrigger>
                    <SelectContent>
                      {sources.map((source) => (
                        <SelectItem key={source.id} value={source.id}>
                          {source.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              
              {newMatch.match_type === 'category' && (
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Input
                    placeholder={language === 'ru' ? 'Например: CRM' : 'E.g.: CRM'}
                    value={newMatch.our_product_ref}
                    onChange={(e) => setNewMatch({ ...newMatch, our_product_ref: e.target.value })}
                  />
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsMatchDialogOpen(false)}>
                {language === 'ru' ? 'Отмена' : 'Cancel'}
              </Button>
              <Button
                onClick={addMatch}
                disabled={!newMatch.competitor_product_url || !newMatch.our_product_ref}
                className="bg-green-500 hover:bg-green-600"
              >
                {language === 'ru' ? 'Add Match' : 'Add Match'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default CompetitorsPage;
