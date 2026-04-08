import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Plus, Pencil, Trash2, Upload, X, Save, Loader2, Building2, Image as ImageIcon, Check
} from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api/oem`;
const BASE_URL = process.env.REACT_APP_BACKEND_URL;

const emptyForm = { name: '', address: '', phone: '', email: '', website: '', warrantyText: '' };

const AdminBrandsPage = () => {
  const [brands, setBrands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBrand, setEditingBrand] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [uploadingLogoFor, setUploadingLogoFor] = useState(null);
  const logoInputRef = useRef(null);
  const [logoTargetBrand, setLogoTargetBrand] = useState(null);

  useEffect(() => { fetchBrands(); }, []);

  const fetchBrands = async () => {
    try {
      const res = await axios.get(`${API}/brands`);
      setBrands(res.data);
    } catch {
      toast.error('Failed to load brands');
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditingBrand(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (brand) => {
    setEditingBrand(brand);
    setForm({
      name: brand.name || '',
      address: brand.address || '',
      phone: brand.phone || '',
      email: brand.email || '',
      website: brand.website || '',
      warrantyText: brand.warrantyText || '',
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('Brand name is required'); return; }
    setSaving(true);
    try {
      const formData = new FormData();
      Object.entries(form).forEach(([k, v]) => formData.append(k, v));

      if (editingBrand) {
        const res = await axios.put(`${API}/brands/${editingBrand.id}`, formData);
        setBrands(prev => prev.map(b => b.id === editingBrand.id ? res.data : b));
        toast.success('Brand updated');
      } else {
        const res = await axios.post(`${API}/brands`, formData);
        setBrands(prev => [...prev, res.data]);
        toast.success('Brand created');
      }
      setDialogOpen(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save brand');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (brand) => {
    if (!window.confirm(`Delete brand "${brand.name}"?`)) return;
    setDeletingId(brand.id);
    try {
      await axios.delete(`${API}/brands/${brand.id}`);
      setBrands(prev => prev.filter(b => b.id !== brand.id));
      toast.success('Brand deleted');
    } catch {
      toast.error('Failed to delete brand');
    } finally {
      setDeletingId(null);
    }
  };

  const triggerLogoUpload = (brand) => {
    setLogoTargetBrand(brand);
    setTimeout(() => logoInputRef.current?.click(), 50);
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !logoTargetBrand) return;
    setUploadingLogoFor(logoTargetBrand.id);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post(`${API}/brands/${logoTargetBrand.id}/logo`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setBrands(prev => prev.map(b =>
        b.id === logoTargetBrand.id ? { ...b, approvedLogos: res.data.approvedLogos } : b
      ));
      toast.success('Logo uploaded');
    } catch {
      toast.error('Failed to upload logo');
    } finally {
      setUploadingLogoFor(null);
      if (logoInputRef.current) logoInputRef.current.value = '';
    }
  };

  const handleDeleteLogo = async (brand, filename) => {
    try {
      const res = await axios.delete(`${API}/brands/${brand.id}/logo/${filename}`);
      setBrands(prev => prev.map(b =>
        b.id === brand.id ? { ...b, approvedLogos: res.data.approvedLogos } : b
      ));
      toast.success('Logo removed');
    } catch {
      toast.error('Failed to remove logo');
    }
  };

  return (
    <DashboardLayout>
      <div className="p-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Building2 className="h-6 w-6 text-indigo-400" />
              OEM Brands
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              Setup brand information for OEM datasheet rebranding
            </p>
          </div>
          <Button onClick={openCreate} className="gap-2">
            <Plus className="h-4 w-4" />
            Add Brand
          </Button>
        </div>

        {/* Hidden logo file input */}
        <input
          ref={logoInputRef}
          type="file"
          accept=".png,.jpg,.jpeg,.svg,.webp"
          className="hidden"
          onChange={handleLogoUpload}
        />

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : brands.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            <Building2 className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="text-lg font-medium">No brands yet</p>
            <p className="text-sm mt-1">Create a brand to start rebranding datasheets</p>
            <Button onClick={openCreate} className="mt-4 gap-2">
              <Plus className="h-4 w-4" /> Add First Brand
            </Button>
          </div>
        ) : (
          <div className="grid gap-4">
            {brands.map(brand => (
              <Card key={brand.id} className="border border-border">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-lg">{brand.name}</CardTitle>
                    <div className="flex gap-2">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(brand)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(brand)}
                        disabled={deletingId === brand.id}
                        className="text-destructive hover:text-destructive"
                      >
                        {deletingId === brand.id
                          ? <Loader2 className="h-4 w-4 animate-spin" />
                          : <Trash2 className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2 text-sm mb-4">
                    {brand.address && <div><span className="text-muted-foreground">Address:</span> {brand.address}</div>}
                    {brand.phone && <div><span className="text-muted-foreground">Phone:</span> {brand.phone}</div>}
                    {brand.email && <div><span className="text-muted-foreground">Email:</span> {brand.email}</div>}
                    {brand.website && <div><span className="text-muted-foreground">Website:</span> {brand.website}</div>}
                    {brand.warrantyText && (
                      <div className="col-span-2">
                        <span className="text-muted-foreground">Warranty:</span> {brand.warrantyText}
                      </div>
                    )}
                  </div>

                  {/* Logos section */}
                  <div className="border-t border-border pt-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-muted-foreground">
                        Approved Logos ({(brand.approvedLogos || []).length})
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-2 h-7 text-xs"
                        onClick={() => triggerLogoUpload(brand)}
                        disabled={uploadingLogoFor === brand.id}
                      >
                        {uploadingLogoFor === brand.id
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <Upload className="h-3 w-3" />}
                        Add Logo
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(brand.approvedLogos || []).map(filename => (
                        <div key={filename} className="relative group border border-border rounded-lg p-2 bg-background">
                          <img
                            src={`${BASE_URL}/api/oem/logo/${filename}`}
                            alt={filename}
                            className="h-12 w-auto object-contain"
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                          <button
                            onClick={() => handleDeleteLogo(brand, filename)}
                            className="absolute -top-1.5 -right-1.5 bg-destructive text-destructive-foreground rounded-full h-4 w-4 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <X className="h-2.5 w-2.5" />
                          </button>
                        </div>
                      ))}
                      {(brand.approvedLogos || []).length === 0 && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                          <ImageIcon className="h-4 w-4" />
                          No logos uploaded yet
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Create / Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>{editingBrand ? 'Edit Brand' : 'Create Brand'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-1">
                <Label>Brand Name *</Label>
                <Input
                  placeholder="Planet Fiber"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div className="space-y-1">
                <Label>Address</Label>
                <Input
                  placeholder="Yerevan, Armenia"
                  value={form.address}
                  onChange={e => setForm(f => ({ ...f, address: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Phone</Label>
                  <Input
                    placeholder="+374 10 123456"
                    value={form.phone}
                    onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Email</Label>
                  <Input
                    placeholder="info@brand.com"
                    value={form.email}
                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Website</Label>
                <Input
                  placeholder="https://brand.com"
                  value={form.website}
                  onChange={e => setForm(f => ({ ...f, website: e.target.value }))}
                />
              </div>
              <div className="space-y-1">
                <Label>Warranty Text</Label>
                <Textarea
                  placeholder="2 year warranty on all products..."
                  value={form.warrantyText}
                  onChange={e => setForm(f => ({ ...f, warrantyText: e.target.value }))}
                  rows={2}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving} className="gap-2">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {editingBrand ? 'Save Changes' : 'Create Brand'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
};

export default AdminBrandsPage;
