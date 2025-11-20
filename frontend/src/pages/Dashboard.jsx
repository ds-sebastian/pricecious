import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Plus, RefreshCw, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ItemCard } from '@/components/dashboard/ItemCard';
import { ItemModal } from '@/components/dashboard/ItemModal';
import { DeleteConfirmationModal } from '@/components/dashboard/DeleteConfirmationModal';

const API_URL = '/api';

export default function Dashboard() {
    const [items, setItems] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [showAddModal, setShowAddModal] = useState(false);
    const [editingItem, setEditingItem] = useState(null);
    const [itemToDelete, setItemToDelete] = useState(null);
    const [zoomedImage, setZoomedImage] = useState(null);

    const refreshItems = async () => {
        try {
            const response = await axios.get(`${API_URL}/items`);
            setItems(response.data);
        } catch (error) {
            console.error('Error fetching items:', error);
            toast.error('Failed to fetch items');
        }
    };

    useEffect(() => {
        refreshItems();
        const interval = setInterval(refreshItems, 10000);
        return () => clearInterval(interval);
    }, []);

    const handleCheck = async (id) => {
        try {
            toast.info('Check triggered...');
            await axios.post(`${API_URL}/items/${id}/check`);
            toast.success('Check started in background');
            refreshItems();
        } catch (error) {
            console.error('Error triggering check:', error);
            toast.error('Failed to trigger check');
        }
    };

    const handleRefreshAll = async () => {
        try {
            toast.info('Triggering refresh for all items...');
            setItems(prevItems => prevItems.map(item => ({ ...item, is_refreshing: true })));
            await axios.post(`${API_URL}/jobs/refresh-all`);
            toast.success('Refresh all started');
        } catch (error) {
            console.error('Error triggering refresh all:', error);
            toast.error('Failed to trigger refresh all');
            refreshItems();
        }
    };

    const handleDelete = async () => {
        if (!itemToDelete) return;
        try {
            await axios.delete(`${API_URL}/items/${itemToDelete.id}`);
            toast.success('Item deleted');
            refreshItems();
            setItemToDelete(null);
        } catch (error) {
            console.error('Error deleting item:', error);
            toast.error('Failed to delete item');
        }
    };

    const filteredItems = items.filter(item => {
        const term = searchTerm.toLowerCase();
        return (
            item.name.toLowerCase().includes(term) ||
            item.url.toLowerCase().includes(term) ||
            (item.tags && item.tags.toLowerCase().includes(term)) ||
            (item.description && item.description.toLowerCase().includes(term))
        );
    });

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
                    <p className="text-muted-foreground">Manage and monitor your product watchlist.</p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="relative w-full md:w-64">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search items..."
                            className="pl-8"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                    <Button variant="outline" onClick={handleRefreshAll}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Refresh All
                    </Button>
                    <Button onClick={() => setShowAddModal(true)}>
                        <Plus className="mr-2 h-4 w-4" />
                        Add Item
                    </Button>
                </div>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {filteredItems.map(item => (
                    <ItemCard
                        key={item.id}
                        item={item}
                        onEdit={setEditingItem}
                        onDelete={setItemToDelete}
                        onCheck={handleCheck}
                        onZoom={setZoomedImage}
                    />
                ))}
            </div>

            <ItemModal
                open={showAddModal}
                onClose={() => setShowAddModal(false)}
                onSaved={refreshItems}
            />

            <ItemModal
                open={!!editingItem}
                item={editingItem}
                onClose={() => setEditingItem(null)}
                onSaved={refreshItems}
            />

            <DeleteConfirmationModal
                open={!!itemToDelete}
                item={itemToDelete}
                onClose={() => setItemToDelete(null)}
                onConfirm={handleDelete}
            />

            {/* Image Zoom Modal */}
            {zoomedImage && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
                    onClick={() => setZoomedImage(null)}
                >
                    <div className="relative max-h-full max-w-full">
                        <img
                            src={zoomedImage}
                            alt="Zoomed screenshot"
                            className="max-h-[90vh] max-w-[90vw] rounded-lg shadow-2xl"
                        />
                        <Button
                            size="icon"
                            variant="secondary"
                            className="absolute -right-4 -top-4 rounded-full shadow-lg"
                            onClick={() => setZoomedImage(null)}
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
