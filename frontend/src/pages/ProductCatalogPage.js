import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import DashboardLayout from '../components/DashboardLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { 
  Package, 
  Search, 
  Filter,
  ChevronDown,
  ExternalLink,
  X,
  Check,
  FileSearch,
  Download,
  Loader2,
  Globe,
  Tag,
  CheckCircle2,
  FileText,
  FileSpreadsheet,
  File,
  Settings,
  Link2,
  Play
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ── CategorySelector — cascading dropdowns + multi-tag selector ──────────────
function CategorySelector({ label, tree, selected, selRoot, setSelRoot, selLvl1, setSelLvl1, onAdd, onRemove }) {
  const roots = Object.keys(tree).sort();
  const lvl1Options = selRoot ? Object.keys(tree[selRoot] || {}).sort() : [];
  const lvl2Options = selRoot && selLvl1 ? Object.keys(tree[selRoot]?.[selLvl1] || {}).sort() : [];

  const addCategory = (cat) => {
    if (cat) onAdd(cat);
  };

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
      {/* Cascading selects */}
      <div className="flex gap-1.5 flex-wrap">
        <select
          className="flex-1 min-w-0 border border-input rounded-md px-2 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
          value={selRoot}
          onChange={e => { setSelRoot(e.target.value); setSelLvl1(''); }}
        >
          <option value="">Root…</option>
          {roots.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        {lvl1Options.length > 0 && (
          <select
            className="flex-1 min-w-0 border border-input rounded-md px-2 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            value={selLvl1}
            onChange={e => setSelLvl1(e.target.value)}
          >
            <option value="">Lvl1…</option>
            {lvl1Options.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
        {lvl2Options.length > 0 && (
          <select
            className="flex-1 min-w-0 border border-input rounded-md px-2 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            onChange={e => { if (e.target.value) addCategory(e.target.value); e.target.value = ''; }}
            defaultValue=""
          >
            <option value="">Lvl2…</option>
            {lvl2Options.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
        <button
          type="button"
          onClick={() => addCategory(selLvl1 || selRoot)}
          disabled={!selRoot}
          className="px-2.5 py-1.5 text-xs rounded-md bg-primary text-primary-foreground disabled:opacity-40 hover:bg-primary/90 shrink-0"
        >
          + Add
        </button>
      </div>
      {/* Selected tags */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map(cat => (
            <span key={cat} className="flex items-center gap-1 px-2 py-0.5 bg-primary/10 border border-primary/20 rounded-full text-xs">
              {cat}
              <button type="button" onClick={() => onRemove(cat)} className="text-muted-foreground hover:text-destructive ml-0.5">×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProductCatalogPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [totalProducts, setTotalProducts] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [categoryList, setCategoryList] = useState([]);  // flat list for filter dropdown
  const [brandList, setBrandList] = useState([]);

  // Filters
  const [search, setSearch] = useState('');
  const [selectedCategoryId, setSelectedCategoryId] = useState('');
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 24;

  // Match File state
  const [showMatchModal, setShowMatchModal] = useState(false);
  const [matchFile, setMatchFile] = useState(null);
  const [matchMode, setMatchMode] = useState('global');
  const [matching, setMatching] = useState(false);
  const [matchError, setMatchError] = useState(null);
  const [matchIsDragging, setMatchIsDragging] = useState(false);
  const matchFileInputRef = useRef(null);

  // Preview step state
  const [matchStep, setMatchStep] = useState('upload'); // 'upload' | 'preview'
  const [matchResults, setMatchResults] = useState([]);
  const [editingRowIdx, setEditingRowIdx] = useState(null);
  const [editSearch, setEditSearch] = useState('');
  const [editSearchResults, setEditSearchResults] = useState([]);
  const [editSearchLoading, setEditSearchLoading] = useState(false);
  const [generatingExcel, setGeneratingExcel] = useState(false);
  const editSearchRef = useRef(null);
  const [researchingIdx, setResearchingIdx] = useState(null);

  // Domain rules state
  const [showRulesModal, setShowRulesModal] = useState(false);
  const [domainRules, setDomainRules] = useState([]);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [ruleForm, setRuleForm] = useState({ title: '', content: '', category: 'general', is_active: true });
  const [ruleSaving, setRuleSaving] = useState(false);

  // Relation rules state
  const [showRelationRulesModal, setShowRelationRulesModal] = useState(false);
  const [relationRules, setRelationRules] = useState([]);
  const [relationRulesLoading, setRelationRulesLoading] = useState(false);
  const [editingRelRule, setEditingRelRule] = useState(null);
  const [relRuleForm, setRelRuleForm] = useState({ title: '', categories_a: [], categories_b: [], description: '', is_active: true });
  const [relRuleSaving, setRelRuleSaving] = useState(false);
  const [runningRuleId, setRunningRuleId] = useState(null);
  const [categoryTree, setCategoryTree] = useState({});
  const [selRootA, setSelRootA] = useState('');
  const [selLvl1A, setSelLvl1A] = useState('');
  const [selRootB, setSelRootB] = useState('');
  const [selLvl1B, setSelLvl1B] = useState('');

  const loadProducts = useCallback(async () => {
    try {
      setLoading(true);
      const body = { page, limit: pageSize };
      if (search) body.productName = search;
      if (selectedCategoryId) body.categoryId = selectedCategoryId;
      if (selectedBrandId) body.brandId = selectedBrandId;

      const response = await axios.post(`${API}/planet/products`, body);
      const data = response.data;
      const items = data.products || data.items || (Array.isArray(data) ? data : []);
      setProducts(items);
      setTotalProducts(data.total ?? items.length);
      setTotalPages(data.totalPages ?? Math.ceil((data.total ?? items.length) / pageSize));
    } catch (error) {
      toast.error('Failed to load products');
    } finally {
      setLoading(false);
    }
  }, [search, selectedCategoryId, selectedBrandId, page]);

  const loadCategories = useCallback(async () => {
    try {
      const [catRes, brandRes] = await Promise.all([
        axios.get(`${API}/planet/categories`),
        axios.get(`${API}/planet/brands`),
      ]);
      // Flatten category tree for dropdown
      const flat = [];
      const flatten = (nodes, depth = 0) => {
        for (const n of (nodes || [])) {
          flat.push({ id: String(n.id), name: ('  '.repeat(depth)) + n.name, slug: n.slug });
          if (n.children?.length) flatten(n.children, depth + 1);
        }
      };
      flatten(catRes.data);
      setCategoryList(flat);
      // Build categoryTree for relation rules modal: { rootName: { lvl1Name: {} } }
      const tree = {};
      for (const root of (catRes.data || [])) {
        tree[root.name] = {};
        for (const lvl1 of (root.children || [])) {
          tree[root.name][lvl1.name] = {};
          for (const lvl2 of (lvl1.children || [])) {
            tree[root.name][lvl1.name][lvl2.name] = {};
          }
        }
      }
      setCategoryTree(tree);
      setBrandList(brandRes.data || []);
    } catch (error) {
      console.error('Failed to load categories', error);
    }
  }, []);

  const loadDomainRules = async () => {
    setRulesLoading(true);
    try {
      const res = await axios.get(`${API}/product-matching/domain-rules`);
      setDomainRules(res.data);
    } catch (err) {
      toast.error('Failed to load domain rules');
    } finally {
      setRulesLoading(false);
    }
  };

  const openRulesModal = () => {
    setShowRulesModal(true);
    setEditingRule(null);
    setRuleForm({ title: '', content: '', category: 'general', is_active: true });
    loadDomainRules();
  };

  const startEditRule = (rule) => {
    setEditingRule(rule);
    setRuleForm({ title: rule.title, content: rule.content, category: rule.category || 'general', is_active: rule.is_active });
  };

  const cancelEditRule = () => {
    setEditingRule(null);
    setRuleForm({ title: '', content: '', category: 'general', is_active: true });
  };

  const saveRule = async () => {
    if (!ruleForm.title.trim() || !ruleForm.content.trim()) {
      toast.error('Title and content are required');
      return;
    }
    setRuleSaving(true);
    try {
      if (editingRule) {
        await axios.put(`${API}/product-matching/domain-rules/${editingRule._id}`, ruleForm);
        toast.success('Rule updated');
      } else {
        await axios.post(`${API}/product-matching/domain-rules`, ruleForm);
        toast.success('Rule added');
      }
      cancelEditRule();
      loadDomainRules();
    } catch (err) {
      toast.error('Failed to save rule');
    } finally {
      setRuleSaving(false);
    }
  };

  const toggleRuleActive = async (rule) => {
    try {
      await axios.put(`${API}/product-matching/domain-rules/${rule._id}`, { is_active: !rule.is_active });
      loadDomainRules();
    } catch (err) {
      toast.error('Failed to update rule');
    }
  };

  const deleteRule = async (ruleId) => {
    if (!window.confirm('Delete this rule?')) return;
    try {
      await axios.delete(`${API}/product-matching/domain-rules/${ruleId}`);
      toast.success('Rule deleted');
      loadDomainRules();
    } catch (err) {
      toast.error('Failed to delete rule');
    }
  };

  // ── Relation Rules ──────────────────────────────────────────────────────────

  const loadRelationRules = async () => {
    setRelationRulesLoading(true);
    try {
      const res = await axios.get(`${API}/product-relations/rules`);
      setRelationRules(res.data);
    } catch {
      toast.error('Failed to load relation rules');
    } finally {
      setRelationRulesLoading(false);
    }
  };

  const openRelationRulesModal = async () => {
    setShowRelationRulesModal(true);
    setEditingRelRule(null);
    setRelRuleForm({ title: '', categories_a: [], categories_b: [], description: '', is_active: true });
    setSelRootA(''); setSelLvl1A(''); setSelRootB(''); setSelLvl1B('');
    loadRelationRules();
    try {
      const res = await axios.get(`${API}/product-catalog/category-tree`);
      setCategoryTree(res.data);
    } catch { /* ignore */ }
  };

  const startEditRelRule = (rule) => {
    setEditingRelRule(rule);
    // Support both old (category_a str) and new (categories_a []) schema
    const catsA = rule.categories_a || (rule.category_a ? [rule.category_a] : []);
    const catsB = rule.categories_b || (rule.category_b ? [rule.category_b] : []);
    setRelRuleForm({ title: rule.title, categories_a: catsA, categories_b: catsB, description: rule.description, is_active: rule.is_active });
    setSelRootA(''); setSelLvl1A(''); setSelRootB(''); setSelLvl1B('');
  };

  const cancelEditRelRule = () => {
    setEditingRelRule(null);
    setRelRuleForm({ title: '', categories_a: [], categories_b: [], description: '', is_active: true });
    setSelRootA(''); setSelLvl1A(''); setSelRootB(''); setSelLvl1B('');
  };

  const saveRelationRule = async () => {
    if (!relRuleForm.title.trim() || relRuleForm.categories_a.length === 0 || relRuleForm.categories_b.length === 0 || !relRuleForm.description.trim()) {
      toast.error('All fields are required');
      return;
    }
    setRelRuleSaving(true);
    try {
      if (editingRelRule) {
        await axios.put(`${API}/product-relations/rules/${editingRelRule._id}`, relRuleForm);
        toast.success('Rule updated');
      } else {
        await axios.post(`${API}/product-relations/rules`, relRuleForm);
        toast.success('Rule created');
      }
      cancelEditRelRule();
      loadRelationRules();
    } catch {
      toast.error('Failed to save rule');
    } finally {
      setRelRuleSaving(false);
    }
  };

  const toggleRelRuleActive = async (rule) => {
    try {
      await axios.put(`${API}/product-relations/rules/${rule._id}`, { is_active: !rule.is_active });
      loadRelationRules();
    } catch {
      toast.error('Failed to update rule');
    }
  };

  const deleteRelationRule = async (ruleId) => {
    if (!window.confirm('Delete this relation rule?')) return;
    try {
      await axios.delete(`${API}/product-relations/rules/${ruleId}`);
      toast.success('Rule deleted');
      loadRelationRules();
    } catch {
      toast.error('Failed to delete rule');
    }
  };

  const runRelationRule = async (ruleId) => {
    setRunningRuleId(ruleId);
    try {
      await axios.post(`${API}/product-relations/rules/${ruleId}/run`);
      toast.success('Analysis started');
      // Optimistically set running status in local state
      setRelationRules(prev => prev.map(r => r._id === ruleId ? { ...r, run_status: 'running' } : r));
      // Poll every 4s until done
      const poll = setInterval(async () => {
        try {
          const res = await axios.get(`${API}/product-relations/rules`);
          const updated = res.data.find(r => r._id === ruleId);
          if (updated) {
            setRelationRules(res.data);
            if (updated.run_status !== 'running') {
              clearInterval(poll);
              setRunningRuleId(null);
              if (updated.run_status === 'completed') {
                toast.success(`Done — ${updated.run_saved ?? 0} new relations saved`);
              } else if (updated.run_status === 'failed') {
                toast.error(`Failed: ${updated.run_error || 'unknown error'}`);
              }
            }
          }
        } catch { clearInterval(poll); setRunningRuleId(null); }
      }, 4000);
    } catch {
      toast.error('Failed to start analysis');
      setRunningRuleId(null);
    }
  };

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [search, selectedCategoryId, selectedBrandId]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      loadProducts();
    }, 300);
    return () => clearTimeout(timer);
  }, [search, loadProducts]);


  const handleDownloadTemplate = async () => {
    try {
      const response = await axios.get(`${API}/product-matching/template`, {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'product_matching_template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('Failed to download template');
    }
  };

  const handleMatchFileSelect = (f) => {
    if (!f) return;
    const name = f.name.toLowerCase();
    const allowed = ['.xlsx', '.xls', '.csv', '.docx', '.pdf'];
    if (!allowed.some(ext => name.endsWith(ext))) {
      toast.error('Unsupported file type. Use xlsx, xls, csv, docx or pdf.');
      return;
    }
    setMatchFile(f);
    setMatchError(null);
  };

  const handleMatchFile = async () => {
    if (!matchFile) return;
    setMatching(true);
    setMatchError(null);
    try {
      const formData = new FormData();
      formData.append('file', matchFile);
      formData.append('mode', matchMode);

      const response = await axios.post(`${API}/product-matching/match`, formData, {
        timeout: 180000,
      });
      setMatchResults(response.data.results || []);
      setMatchStep('preview');
      toast.success('Matching complete! Review results below.');
    } catch (err) {
      let msg = 'Matching failed. Please try again.';
      if (err.response?.data?.detail) {
        msg = err.response.data.detail;
      }
      setMatchError(msg);
      toast.error('Matching failed');
    } finally {
      setMatching(false);
    }
  };

  const handleGenerateExcel = async () => {
    setGeneratingExcel(true);
    try {
      const response = await axios.post(
        `${API}/product-matching/generate`,
        { mode: matchMode, results: matchResults },
        { responseType: 'blob', timeout: 60000 }
      );
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'product_matching_results.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success('Excel downloaded!');
    } catch (err) {
      toast.error('Failed to generate Excel');
    } finally {
      setGeneratingExcel(false);
    }
  };

  const handleResearchItem = async (idx) => {
    const item = matchResults[idx]?.customer_item;
    if (!item) return;
    setResearchingIdx(idx);
    try {
      const { data } = await axios.post(`${API}/product-matching/research-item`, {
        item,
        mode: matchMode,
      }, { timeout: 60000 });
      setMatchResults(prev => prev.map((r, i) => i === idx ? { ...r, ...data } : r));
      if (data.matched_title) {
        toast.success('Web research found a match!');
      } else {
        toast.info('No match found via web research');
      }
    } catch {
      toast.error('Web research failed');
    } finally {
      setResearchingIdx(null);
    }
  };

  const handleProductSearch = async (query) => {
    if (!query || query.trim().length < 1) {
      setEditSearchResults([]);
      return;
    }
    setEditSearchLoading(true);
    try {
      const resp = await axios.get(`${API}/product-matching/search`, {
        params: { q: query.trim() },
      });
      setEditSearchResults(resp.data || []);
    } catch {
      setEditSearchResults([]);
    } finally {
      setEditSearchLoading(false);
    }
  };

  const handleSelectSearchResult = (rowIdx, product) => {
    setMatchResults(prev => prev.map((r, i) => {
      if (i !== rowIdx) return r;
      const code = matchMode === 'oem'
        ? (product.article_number || product.crm_code)
        : (product.crm_code || product.article_number);
      return {
        ...r,
        crm_code: product.crm_code || null,
        article_number: product.article_number || null,
        matched_title: product.title || '',
        code: code || null,
        match_type: 'confirmed',
        confidence: 'high',
        comment: null,
      };
    }));
    setEditingRowIdx(null);
    setEditSearch('');
    setEditSearchResults([]);
  };

  const handleMatchModalClose = () => {
    setShowMatchModal(false);
    setMatchFile(null);
    setMatchError(null);
    setMatchIsDragging(false);
    setMatchStep('upload');
    setMatchResults([]);
    setEditingRowIdx(null);
    setEditSearch('');
    setEditSearchResults([]);
    if (matchFileInputRef.current) matchFileInputRef.current.value = '';
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
              {totalProducts > 0 ? `${totalProducts} products` : 'Loading…'}
            </p>
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setShowMatchModal(true)}
              data-testid="match-file-btn"
            >
              <FileSearch className="h-4 w-4 mr-2" />
              Match File
            </Button>
            <Button
              variant="outline"
              onClick={openRulesModal}
            >
              <Settings className="h-4 w-4 mr-2" />
              Matching Rules
            </Button>
            <Button
              variant="outline"
              onClick={openRelationRulesModal}
            >
              <Link2 className="h-4 w-4 mr-2" />
              Relation Rules
            </Button>
          </div>
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
                value={selectedCategoryId}
                onChange={(e) => setSelectedCategoryId(e.target.value)}
                className="px-3 py-2 rounded-md border bg-background min-w-[180px]"
              >
                <option value="">All categories</option>
                {categoryList.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>

              <select
                value={selectedBrandId}
                onChange={(e) => setSelectedBrandId(e.target.value)}
                className="px-3 py-2 rounded-md border bg-background min-w-[150px]"
              >
                <option value="">All brands</option>
                {brandList.map(b => (
                  <option key={b.id} value={String(b.id)}>{b.name}</option>
                ))}
              </select>
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
                products.map((product, idx) => {
                  const imgSrc = product.images?.[0]
                    ? (() => {
                        const img = product.images[0];
                        return img.optimizedPath?.startsWith('public/')
                          ? `https://api-prod.planetworkspace.com/${img.optimizedPath}`
                          : `https://api-prod.planetworkspace.com/public/${img.path636px || img.optimizedPath}`;
                      })()
                    : null;
                  return (
                    <tr
                      key={product.external_id || product.id || idx}
                      className="border-t hover:bg-muted/30"
                      data-testid={`product-row-${product.article_number}`}
                    >
                      <td className="p-3 font-mono text-sm">{product.article_number || product.model || '-'}</td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          {imgSrc && (
                            <img src={imgSrc} alt="" className="w-8 h-8 object-contain rounded shrink-0" />
                          )}
                          <div>
                            <div className="font-medium">{product.title_en || product.name}</div>
                            {product.product_model && product.product_model !== product.article_number && (
                              <div className="text-xs text-muted-foreground">{product.product_model}</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="p-3 hidden md:table-cell">{product.vendor || product.brandName || '-'}</td>
                      <td className="p-3 hidden lg:table-cell">{product.category_name || product.categoryName || '-'}</td>
                      <td className="p-3 hidden lg:table-cell">
                        {product.price != null ? `$${Number(product.price).toFixed(2)}` : '-'}
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex justify-end gap-1">
                          {product.slug && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => window.open(`https://api-prod.planetworkspace.com/web/product/${product.slug}`, '_blank')}
                            >
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border rounded-lg bg-muted/30">
            <div className="text-sm text-muted-foreground">
              Page {page} of {totalPages} · {totalProducts} products
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← Prev
              </Button>
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
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
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                Next →
              </Button>
            </div>
          </div>
        )}

        {/* Match Customer File Modal */}
        {false && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-background rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">Removed</h2>
                <Button variant="ghost" size="sm">
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

        {/* Match Customer File Modal */}
        {showMatchModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className={`bg-background rounded-xl shadow-xl w-full transition-all ${matchStep === 'preview' ? 'max-w-5xl' : 'max-w-lg'}`}>
              {/* Header */}
              <div className="flex justify-between items-center px-6 pt-5 pb-4 border-b border-border">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-bold flex items-center gap-2">
                    <FileSearch className="h-5 w-5 text-primary" />
                    Product Matching
                  </h2>
                  {/* Step indicator */}
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold ${matchStep === 'upload' ? 'bg-primary text-primary-foreground' : 'bg-emerald-500 text-white'}`}>
                      {matchStep === 'upload' ? '1' : <Check className="h-3 w-3" />}
                    </span>
                    <span className={matchStep === 'upload' ? 'font-medium text-foreground' : ''}>Upload</span>
                    <span className="mx-1">→</span>
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold ${matchStep === 'preview' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>2</span>
                    <span className={matchStep === 'preview' ? 'font-medium text-foreground' : ''}>Review & Export</span>
                  </div>
                </div>
                <Button variant="ghost" size="icon" onClick={handleMatchModalClose}>
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* ── STEP 1: Upload ── */}
              {matchStep === 'upload' && (
                <div className="px-6 py-5 space-y-5">
                  {/* Mode selector */}
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Output mode</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setMatchMode('global')}
                        className={`flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg border-2 text-sm font-medium transition-all ${
                          matchMode === 'global'
                            ? 'border-indigo-500 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400'
                            : 'border-border text-muted-foreground hover:text-foreground hover:border-border/60'
                        }`}
                      >
                        <Globe className="h-4 w-4 flex-shrink-0" />
                        <div className="text-left">
                          <div className="leading-tight">Global</div>
                          <div className="text-xs font-normal opacity-70">CRM codes</div>
                        </div>
                      </button>
                      <button
                        onClick={() => setMatchMode('oem')}
                        className={`flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg border-2 text-sm font-medium transition-all ${
                          matchMode === 'oem'
                            ? 'border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : 'border-border text-muted-foreground hover:text-foreground hover:border-border/60'
                        }`}
                      >
                        <Tag className="h-4 w-4 flex-shrink-0" />
                        <div className="text-left">
                          <div className="leading-tight">OEM</div>
                          <div className="text-xs font-normal opacity-70">Article numbers</div>
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* Drag & drop upload zone */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Customer file</p>
                      <button
                        onClick={handleDownloadTemplate}
                        className="inline-flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-600 transition-colors"
                      >
                        <Download className="h-3 w-3" />
                        Download template
                      </button>
                    </div>
                    <div
                      onClick={() => !matchFile && matchFileInputRef.current?.click()}
                      onDrop={(e) => {
                        e.preventDefault();
                        setMatchIsDragging(false);
                        handleMatchFileSelect(e.dataTransfer.files[0]);
                      }}
                      onDragOver={(e) => { e.preventDefault(); setMatchIsDragging(true); }}
                      onDragLeave={() => setMatchIsDragging(false)}
                      className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
                        matchIsDragging
                          ? 'border-indigo-500 bg-indigo-500/5'
                          : matchFile
                          ? 'border-emerald-500/50 bg-emerald-500/5 cursor-default'
                          : 'border-border hover:border-indigo-400 hover:bg-accent/40 cursor-pointer'
                      }`}
                    >
                      {matchFile ? (
                        <div className="flex flex-col items-center gap-1.5">
                          {matchFile.name.endsWith('.pdf')
                            ? <FileText className="h-8 w-8 text-red-400" />
                            : matchFile.name.endsWith('.docx')
                            ? <File className="h-8 w-8 text-blue-400" />
                            : <FileSpreadsheet className="h-8 w-8 text-green-500" />
                          }
                          <p className="text-sm font-medium">{matchFile.name}</p>
                          <p className="text-xs text-muted-foreground">{(matchFile.size / 1024).toFixed(0)} KB</p>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setMatchFile(null);
                              setMatchError(null);
                              if (matchFileInputRef.current) matchFileInputRef.current.value = '';
                            }}
                            className="mt-1 text-xs text-muted-foreground hover:text-destructive flex items-center gap-1"
                          >
                            <X className="h-3 w-3" /> Remove
                          </button>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center gap-2 text-muted-foreground">
                          <Upload className="h-8 w-8" />
                          <div>
                            <p className="text-sm font-medium text-foreground">Drop file here</p>
                            <p className="text-xs mt-0.5">or click to browse</p>
                          </div>
                          <p className="text-xs">xlsx · xls · csv · docx · pdf</p>
                        </div>
                      )}
                    </div>
                    <input
                      ref={matchFileInputRef}
                      type="file"
                      accept=".xlsx,.xls,.csv,.docx,.pdf"
                      className="hidden"
                      onChange={(e) => handleMatchFileSelect(e.target.files[0])}
                    />
                  </div>

                  {matchError && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-destructive">
                      <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                      {matchError}
                    </div>
                  )}

                  <div className="flex gap-2 pt-1">
                    <Button variant="outline" onClick={handleMatchModalClose} className="flex-1">
                      Close
                    </Button>
                    <Button onClick={handleMatchFile} disabled={!matchFile || matching} className="flex-1">
                      {matching ? (
                        <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Matching...</>
                      ) : (
                        <><FileSearch className="h-4 w-4 mr-2" />Run Matching</>
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {/* ── STEP 2: Preview & Edit ── */}
              {matchStep === 'preview' && (
                <div className="px-6 py-5 space-y-4">
                  {/* Summary */}
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-muted-foreground">{matchResults.length} items</span>
                    <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {matchResults.filter(r => r.confidence === 'high').length} high confidence
                    </span>
                    <span className="flex items-center gap-1 text-yellow-600 dark:text-yellow-400">
                      <AlertCircle className="h-3.5 w-3.5" />
                      {matchResults.filter(r => r.confidence === 'medium').length} medium
                    </span>
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <X className="h-3.5 w-3.5" />
                      {matchResults.filter(r => !r.confidence).length} unmatched
                    </span>
                  </div>

                  {/* Scrollable table */}
                  <div className="border rounded-lg overflow-hidden">
                    <div className="overflow-y-auto max-h-[55vh]">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/60 sticky top-0 z-10">
                          <tr>
                            <th className="text-left p-2.5 font-medium w-[22%]">Customer Item</th>
                            <th className="text-left p-2.5 font-medium w-[22%]">Matched Product</th>
                            <th className="text-left p-2.5 font-medium w-[13%]">Code</th>
                            <th className="text-left p-2.5 font-medium w-[11%]">Confidence</th>
                            <th className="text-left p-2.5 font-medium w-[24%]">Comment</th>
                            <th className="p-2.5 w-[8%]"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {matchResults.map((row, idx) => (
                            <tr key={idx} className={`border-t hover:bg-muted/20 ${!row.code ? 'bg-destructive/5' : ''}`}>
                              <td className="p-2.5 text-muted-foreground text-xs">
                                <div className="break-words whitespace-pre-wrap">{row.customer_item}</div>
                              </td>
                              <td className="p-2.5">
                                {editingRowIdx === idx ? (
                                  <div className="relative">
                                    <input
                                      ref={editSearchRef}
                                      autoFocus
                                      value={editSearch}
                                      onChange={(e) => {
                                        setEditSearch(e.target.value);
                                        handleProductSearch(e.target.value);
                                      }}
                                      onKeyDown={(e) => {
                                        if (e.key === 'Escape') {
                                          setEditingRowIdx(null);
                                          setEditSearch('');
                                          setEditSearchResults([]);
                                        }
                                      }}
                                      placeholder="Search product..."
                                      className="w-full px-2 py-1 rounded border bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                    />
                                    {(editSearchResults.length > 0 || editSearchLoading) && (
                                      <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                                        {editSearchLoading && (
                                          <div className="p-2 text-xs text-muted-foreground flex items-center gap-1">
                                            <Loader2 className="h-3 w-3 animate-spin" /> Searching...
                                          </div>
                                        )}
                                        {editSearchResults.map((p, pi) => (
                                          <button
                                            key={pi}
                                            onClick={() => handleSelectSearchResult(idx, p)}
                                            className="w-full text-left px-3 py-2 hover:bg-muted/60 text-xs border-b last:border-0"
                                          >
                                            <div className="font-medium truncate">{p.title}</div>
                                            <div className="text-muted-foreground">{p.code} {p.vendor ? `· ${p.vendor}` : ''}</div>
                                          </button>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <div
                                    className={`text-xs break-words whitespace-pre-wrap ${!row.matched_title ? 'text-muted-foreground italic' : ''}`}
                                  >
                                    {row.matched_title || 'No match'}
                                  </div>
                                )}
                              </td>
                              <td className="p-2.5 font-mono text-xs">
                                {row.code || <span className="text-destructive">—</span>}
                              </td>
                              <td className="p-2.5">
                                {row.confidence === 'high' ? (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                                    <CheckCircle2 className="h-3 w-3" /> High
                                  </span>
                                ) : row.confidence === 'medium' ? (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs bg-yellow-500/10 text-yellow-600 dark:text-yellow-400">
                                    <AlertCircle className="h-3 w-3" /> Medium
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs bg-muted text-muted-foreground">
                                    <X className="h-3 w-3" /> None
                                  </span>
                                )}
                              </td>
                              <td className="p-2.5">
                                {row.comment ? (
                                  <span
                                    className="text-xs text-yellow-600 dark:text-yellow-400 line-clamp-2 leading-tight"
                                    title={row.comment}
                                  >
                                    {row.comment}
                                  </span>
                                ) : row.code ? (
                                  <span className="text-xs text-muted-foreground/50">—</span>
                                ) : (
                                  <span className="text-xs text-destructive/70">No match found</span>
                                )}
                              </td>
                              <td className="p-2.5 text-right">
                                <div className="flex items-center justify-end gap-1">
                                  {!row.matched_title && (
                                    <button
                                      onClick={() => handleResearchItem(idx)}
                                      disabled={researchingIdx === idx}
                                      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                      title="Search the web to find this product"
                                    >
                                      {researchingIdx === idx ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                      ) : (
                                        <Globe className="h-3 w-3" />
                                      )}
                                      {researchingIdx === idx ? '' : 'Research'}
                                    </button>
                                  )}
                                  <button
                                    onClick={() => {
                                      if (editingRowIdx === idx) {
                                        setEditingRowIdx(null);
                                        setEditSearch('');
                                        setEditSearchResults([]);
                                      } else {
                                        setEditingRowIdx(idx);
                                        setEditSearch('');
                                        setEditSearchResults([]);
                                      }
                                    }}
                                    className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                                    title="Change product"
                                  >
                                    <Edit className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 pt-1">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setMatchStep('upload');
                        setMatchResults([]);
                        setEditingRowIdx(null);
                      }}
                    >
                      ← Back
                    </Button>
                    <div className="flex-1" />
                    <Button variant="outline" onClick={handleMatchModalClose}>
                      Close
                    </Button>
                    <Button onClick={handleGenerateExcel} disabled={generatingExcel}>
                      {generatingExcel ? (
                        <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating...</>
                      ) : (
                        <><Download className="h-4 w-4 mr-2" />Generate Excel</>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Matching Domain Rules Modal */}
        {showRulesModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-background rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
              {/* Header */}
              <div className="flex justify-between items-center px-6 pt-5 pb-4 border-b border-border shrink-0">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Settings className="h-5 w-5 text-primary" />
                  Matching Domain Rules
                </h2>
                <Button variant="ghost" size="icon" onClick={() => { setShowRulesModal(false); cancelEditRule(); }}>
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* Body */}
              <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">

                {/* Add / Edit form */}
                <div className="border border-border rounded-lg p-4 space-y-3 bg-muted/30">
                  <h3 className="text-sm font-semibold text-foreground">
                    {editingRule ? 'Edit Rule' : 'Add New Rule'}
                  </h3>
                  <div className="flex gap-2">
                    <input
                      className="flex-1 border border-input rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                      placeholder="Rule title…"
                      value={ruleForm.title}
                      onChange={e => setRuleForm(f => ({ ...f, title: e.target.value }))}
                    />
                    <select
                      className="border border-input rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                      value={ruleForm.category}
                      onChange={e => setRuleForm(f => ({ ...f, category: e.target.value }))}
                    >
                      <option value="general">General</option>
                      <option value="vendor_naming">Vendor Naming</option>
                      <option value="cable_type">Cable Type</option>
                    </select>
                  </div>
                  <textarea
                    className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring font-mono resize-none"
                    rows={5}
                    placeholder="Rule content — naming convention text, examples, patterns…"
                    value={ruleForm.content}
                    onChange={e => setRuleForm(f => ({ ...f, content: e.target.value }))}
                  />
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={ruleForm.is_active}
                        onChange={e => setRuleForm(f => ({ ...f, is_active: e.target.checked }))}
                        className="accent-primary"
                      />
                      Active (applied during matching)
                    </label>
                    <div className="flex gap-2">
                      {editingRule && (
                        <Button variant="ghost" size="sm" onClick={cancelEditRule}>
                          Cancel
                        </Button>
                      )}
                      <Button size="sm" onClick={saveRule} disabled={ruleSaving}>
                        {ruleSaving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                        {editingRule ? 'Update Rule' : 'Add Rule'}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Rules list */}
                {rulesLoading ? (
                  <div className="flex items-center justify-center py-8 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin mr-2" />
                    Loading rules…
                  </div>
                ) : domainRules.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    No custom rules yet. Add one above to extend Claude's domain knowledge.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {domainRules.map(rule => (
                      <div
                        key={rule._id}
                        className={`border rounded-lg p-4 space-y-2 transition-colors ${rule.is_active ? 'border-border bg-background' : 'border-border/50 bg-muted/20 opacity-60'}`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-1 flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium text-sm truncate">{rule.title}</span>
                              <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground shrink-0">
                                {rule.category || 'general'}
                              </span>
                              {rule.is_active ? (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 shrink-0">active</span>
                              ) : (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground shrink-0">inactive</span>
                              )}
                            </div>
                            <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed line-clamp-4">
                              {rule.content}
                            </pre>
                          </div>
                          <div className="flex gap-1 shrink-0">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              title={rule.is_active ? 'Deactivate' : 'Activate'}
                              onClick={() => toggleRuleActive(rule)}
                            >
                              {rule.is_active
                                ? <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                                : <AlertCircle className="h-4 w-4 text-muted-foreground" />}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => startEditRule(rule)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => deleteRule(rule._id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        {rule.updated_at && (
                          <p className="text-xs text-muted-foreground">
                            Updated {new Date(rule.updated_at).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-6 py-4 border-t border-border shrink-0 flex justify-end">
                <Button variant="outline" onClick={() => { setShowRulesModal(false); cancelEditRule(); }}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Relation Rules Modal */}
        {showRelationRulesModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-background rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
              <div className="flex justify-between items-center px-6 pt-5 pb-4 border-b border-border shrink-0">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Link2 className="h-5 w-5 text-primary" />
                  Both Together — Relation Rules
                </h2>
                <Button variant="ghost" size="icon" onClick={() => { setShowRelationRulesModal(false); cancelEditRelRule(); }}>
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
                {/* Add / Edit form */}
                <div className="border border-border rounded-lg p-4 space-y-3 bg-muted/30">
                  <h3 className="text-sm font-semibold text-foreground">
                    {editingRelRule ? 'Edit Rule' : 'Add New Rule'}
                  </h3>
                  <input
                    className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Rule title (e.g. Cables ↔ Connectors)…"
                    value={relRuleForm.title}
                    onChange={e => setRelRuleForm(f => ({ ...f, title: e.target.value }))}
                  />
                  {/* Category A selector */}
                  <CategorySelector
                    label="Side A"
                    tree={categoryTree}
                    selected={relRuleForm.categories_a}
                    selRoot={selRootA}
                    setSelRoot={setSelRootA}
                    selLvl1={selLvl1A}
                    setSelLvl1={setSelLvl1A}
                    onAdd={cat => setRelRuleForm(f => ({ ...f, categories_a: f.categories_a.includes(cat) ? f.categories_a : [...f.categories_a, cat] }))}
                    onRemove={cat => setRelRuleForm(f => ({ ...f, categories_a: f.categories_a.filter(c => c !== cat) }))}
                  />
                  <div className="flex items-center justify-center text-muted-foreground text-sm font-medium">↔</div>
                  {/* Category B selector */}
                  <CategorySelector
                    label="Side B"
                    tree={categoryTree}
                    selected={relRuleForm.categories_b}
                    selRoot={selRootB}
                    setSelRoot={setSelRootB}
                    selLvl1={selLvl1B}
                    setSelLvl1={setSelLvl1B}
                    onAdd={cat => setRelRuleForm(f => ({ ...f, categories_b: f.categories_b.includes(cat) ? f.categories_b : [...f.categories_b, cat] }))}
                    onRemove={cat => setRelRuleForm(f => ({ ...f, categories_b: f.categories_b.filter(c => c !== cat) }))}
                  />
                  <textarea
                    className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                    rows={4}
                    placeholder="Describe compatibility logic for AI — e.g. 'A cable is compatible with a connector if the connector type (LC, SC) matches the cable's specified connector type.'"
                    value={relRuleForm.description}
                    onChange={e => setRelRuleForm(f => ({ ...f, description: e.target.value }))}
                  />
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={relRuleForm.is_active}
                        onChange={e => setRelRuleForm(f => ({ ...f, is_active: e.target.checked }))}
                        className="accent-primary"
                      />
                      Active
                    </label>
                    <div className="flex gap-2">
                      {editingRelRule && (
                        <Button variant="ghost" size="sm" onClick={cancelEditRelRule}>Cancel</Button>
                      )}
                      <Button size="sm" onClick={saveRelationRule} disabled={relRuleSaving}>
                        {relRuleSaving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                        {editingRelRule ? 'Update Rule' : 'Add Rule'}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Rules list */}
                {relationRulesLoading ? (
                  <div className="flex items-center justify-center py-8 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin mr-2" />
                    Loading…
                  </div>
                ) : relationRules.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    No relation rules yet. Add one above to start auto-detecting compatible products.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {relationRules.map(rule => (
                      <div
                        key={rule._id}
                        className={`border rounded-lg p-4 space-y-2 transition-colors ${rule.is_active ? 'border-border bg-background' : 'border-border/50 bg-muted/20 opacity-60'}`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-1 flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium text-sm">{rule.title}</span>
                              <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                                {(rule.categories_a || (rule.category_a ? [rule.category_a] : [])).join(', ')} ↔ {(rule.categories_b || (rule.category_b ? [rule.category_b] : [])).join(', ')}
                              </span>
                              {rule.is_active ? (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">active</span>
                              ) : (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">inactive</span>
                              )}
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-2">{rule.description}</p>
                            <div className="flex items-center gap-2 flex-wrap">
                              {rule.run_status === 'running' && (
                                <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                                  <Loader2 className="h-3 w-3 animate-spin" /> Running…
                                </span>
                              )}
                              {rule.run_status === 'completed' && (
                                <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                                  ✓ Done {rule.run_saved != null ? `(${rule.run_saved} saved)` : ''}
                                </span>
                              )}
                              {rule.run_status === 'failed' && (
                                <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" title={rule.run_error}>
                                  ✗ Failed
                                </span>
                              )}
                              {rule.last_run_at && (
                                <span className="text-xs text-muted-foreground">
                                  {new Date(rule.last_run_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex gap-1 shrink-0">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-primary"
                              title="Run AI analysis"
                              onClick={() => runRelationRule(rule._id)}
                              disabled={runningRuleId === rule._id || rule.run_status === 'running'}
                            >
                              {runningRuleId === rule._id
                                ? <Loader2 className="h-4 w-4 animate-spin" />
                                : <Play className="h-4 w-4" />}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              title={rule.is_active ? 'Deactivate' : 'Activate'}
                              onClick={() => toggleRelRuleActive(rule)}
                            >
                              {rule.is_active
                                ? <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                                : <AlertCircle className="h-4 w-4 text-muted-foreground" />}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => startEditRelRule(rule)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => deleteRelationRule(rule._id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="px-6 py-4 border-t border-border shrink-0 flex justify-end">
                <Button variant="outline" onClick={() => { setShowRelationRulesModal(false); cancelEditRelRule(); }}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
