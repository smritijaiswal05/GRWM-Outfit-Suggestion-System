import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Upload, Image as ImageIcon, Loader2, Plus, Shirt, Footprints, Package, Trash2, X } from 'lucide-react';
import { getImageUrl } from '@/lib/utils';

export function Wardrobe() {
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [deletingId, setDeletingId] = useState<string | number | null>(null);

  const [editingItem, setEditingItem] = useState<any>(null);
  const [editForm, setEditForm] = useState({ category: '', formality: '', fit: '' });
  const [updating, setUpdating] = useState(false);

  const showUpload = searchParams.get('upload') === 'true';

  const fetchWardrobe = async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError('');
      const data = await api.getWardrobe();
      // Handle various response shapes gracefully
      if (Array.isArray(data)) {
        setItems(data);
      } else if (data && typeof data === 'object') {
        setItems(data.wardrobe || data.items || []);
      } else {
        setItems([]);
      }
    } catch (err: any) {
      // Don't show error for empty wardrobe
      if (err.message && (err.message.includes('empty') || err.message.includes('404'))) {
        setItems([]);
      } else {
        setError(err.message || 'Failed to load wardrobe');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWardrobe();
  }, [token]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !token) return;

    try {
      setUploading(true);
      setError('');
      await api.uploadImage(file);
      await fetchWardrobe();
      
      // Remove upload param if present
      if (showUpload) {
        setSearchParams({});
      }
    } catch (err: any) {
      setError(err.message || 'Failed to upload image');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async (itemId: string | number) => {
    if (!token || !itemId) return;
    
    // Optimistic UI update or just show loading state
    try {
      setDeletingId(itemId);
      await api.deleteItem(itemId);
      // Refresh wardrobe
      await fetchWardrobe();
    } catch (err: any) {
      setError(err.message || 'Failed to delete item');
    } finally {
      setDeletingId(null);
    }
  };

  const openEditModal = (item: any) => {
    setEditingItem(item);
    setEditForm({
      category: typeof item.category === 'string' ? item.category : 'shirt',
      formality: item.formality || 'casual',
      fit: item.fit || 'regular'
    });
  };

  const handleUpdate = async () => {
    if (!editingItem) return;
    try {
        setUpdating(true);
        await api.updateWardrobeItem(getItemId(editingItem), editForm.category, editForm.formality, editForm.fit);
        setEditingItem(null);
        await fetchWardrobe();
    } catch(err: any) {
        setError(err.message || 'Failed to update item');
    } finally {
        setUpdating(false);
    }
  };

  // Categorize items
  const getCategoryString = (cat: any) => {
    if (typeof cat === 'string') return cat.toLowerCase();
    if (Array.isArray(cat)) return cat.join(' ').toLowerCase();
    return '';
  };

  const upperWear = items.filter(item => {
    const cat = getCategoryString(item.category);
    return cat.includes('shirt') || cat.includes('top') || cat.includes('t-shirt') || cat.includes('jacket') || cat.includes('sweater') || cat.includes('hoodie') || cat.includes('coat');
  });

  const bottomWear = items.filter(item => {
    const cat = getCategoryString(item.category);
    return cat.includes('pant') || cat.includes('jeans') || cat.includes('short') || cat.includes('skirt') || cat.includes('trouser') || cat.includes('legging');
  });

  const otherWear = items.filter(item => !upperWear.includes(item) && !bottomWear.includes(item));

  const getItemId = (item: any) => item.itemID || item.id || item.item_id;

  const renderItemGrid = (gridItems: any[]) => (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {gridItems.map((item, idx) => {
        const itemId = getItemId(item);
        return (
          <div 
            key={itemId || idx} 
            className="group relative aspect-square rounded-2xl overflow-hidden bg-zinc-100 border border-zinc-200 cursor-pointer"
            onClick={(e) => {
              if ((e.target as HTMLElement).closest('button')) return;
              openEditModal(item);
            }}
          >
            <img 
              src={getImageUrl(item)} 
              alt={`Wardrobe item ${idx + 1}`} 
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
              onError={(e) => {
                (e.target as HTMLImageElement).src = 'https://placehold.co/400x400?text=Image+Not+Found';
              }}
            />
            {itemId && (
              <button
                onClick={() => handleDelete(itemId)}
                disabled={deletingId === itemId}
                className="absolute top-2 right-2 p-2 bg-white/80 hover:bg-red-50 text-red-600 rounded-full opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shadow-sm"
                title="Remove item"
              >
                {deletingId === itemId ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </button>
            )}
            {item.category && (
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-3 pt-8">
                <p className="text-white text-xs font-medium capitalize truncate">
                  {typeof item.category === 'string' ? item.category : (Array.isArray(item.category) ? item.category.join(', ') : 'Item')}
                </p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="space-y-8 pb-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">My Wardrobe</h1>
          <p className="text-zinc-500">Manage your digital clothing collection.</p>
        </div>
        <Button 
          onClick={() => fileInputRef.current?.click()} 
          className="bg-indigo-600 hover:bg-indigo-700 text-white shrink-0 rounded-xl h-11 px-6"
          disabled={uploading}
        >
          {uploading ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Plus className="w-5 h-5 mr-2" />
          )}
          Add Item
        </Button>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept="image/*" 
          className="hidden" 
        />
      </div>

      {error && (
        <div className="p-4 text-sm text-red-600 bg-red-50 rounded-xl border border-red-100">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
          <Loader2 className="w-8 h-8 animate-spin mb-4 text-indigo-600" />
          <p>Loading your wardrobe...</p>
        </div>
      ) : items.length === 0 ? (
        <Card className="border-dashed border-2 bg-zinc-50/50">
          <CardContent className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mb-4 shadow-sm">
              <ImageIcon className="w-8 h-8 text-zinc-400" />
            </div>
            <h3 className="text-xl font-semibold mb-2">Your wardrobe is empty</h3>
            <p className="text-zinc-500 mb-6 max-w-sm">
              Upload photos of your clothes to start getting AI-powered outfit suggestions.
            </p>
            <Button 
              onClick={() => fileInputRef.current?.click()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload First Item
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-10">
          {upperWear.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-4">
                <div className="p-2 bg-indigo-100 text-indigo-600 rounded-lg">
                  <Shirt className="w-5 h-5" />
                </div>
                <h2 className="text-xl font-semibold text-zinc-800">Upper Wear</h2>
                <span className="ml-2 text-sm text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded-full">{upperWear.length}</span>
              </div>
              {renderItemGrid(upperWear)}
            </section>
          )}

          {bottomWear.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-4">
                <div className="p-2 bg-indigo-100 text-indigo-600 rounded-lg">
                  <Footprints className="w-5 h-5" />
                </div>
                <h2 className="text-xl font-semibold text-zinc-800">Bottom Wear</h2>
                <span className="ml-2 text-sm text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded-full">{bottomWear.length}</span>
              </div>
              {renderItemGrid(bottomWear)}
            </section>
          )}

          {otherWear.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-4">
                <div className="p-2 bg-zinc-100 text-zinc-600 rounded-lg">
                  <Package className="w-5 h-5" />
                </div>
                <h2 className="text-xl font-semibold text-zinc-800">Other Items</h2>
                <span className="ml-2 text-sm text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded-full">{otherWear.length}</span>
              </div>
              {renderItemGrid(otherWear)}
            </section>
          )}
        </div>
      )}

      {editingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <Card className="w-full max-w-md bg-white border-0 shadow-2xl overflow-hidden">
            <CardContent className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold text-zinc-800">Edit Item</h3>
                <button onClick={() => setEditingItem(null)} className="p-2 text-zinc-400 hover:text-zinc-600 bg-zinc-100 rounded-full">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1">Category</label>
                  <select 
                    value={editForm.category}
                    onChange={(e) => setEditForm({...editForm, category: e.target.value})}
                    className="w-full h-11 px-3 border border-zinc-200 rounded-xl bg-white"
                  >
                    <option value="shirt">Shirt / Top</option>
                    <option value="pants">Pants / Bottoms</option>
                    <option value="dress">Dress</option>
                    <option value="outerwear">Outerwear / Jacket</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1">Formality</label>
                  <select 
                    value={editForm.formality}
                    onChange={(e) => setEditForm({...editForm, formality: e.target.value})}
                    className="w-full h-11 px-3 border border-zinc-200 rounded-xl bg-white"
                  >
                    <option value="formal">Formal</option>
                    <option value="business_casual">Business Casual</option>
                    <option value="casual">Casual</option>
                    <option value="loungewear">Loungewear</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1">Fit</label>
                  <select 
                    value={editForm.fit}
                    onChange={(e) => setEditForm({...editForm, fit: e.target.value})}
                    className="w-full h-11 px-3 border border-zinc-200 rounded-xl bg-white"
                  >
                    <option value="slim">Slim</option>
                    <option value="regular">Regular</option>
                    <option value="loose">Loose</option>
                    <option value="oversized">Oversized</option>
                  </select>
                </div>
              </div>
              <Button 
                onClick={handleUpdate}
                disabled={updating}
                className="w-full mt-6 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl h-11"
              >
                {updating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Save Changes
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
