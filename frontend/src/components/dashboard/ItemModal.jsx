import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { API_URL } from '@/lib/api';

export function ItemModal({ item, onClose, onSaved, open }) {
    const [formData, setFormData] = useState({
        url: '',
        name: '',
        target_price: '',
        selector: '',
        tags: '',
        description: '',
        notification_profile_id: ''
    });
    const [profiles, setProfiles] = useState([]);

    useEffect(() => {
        if (item) {
            setFormData({
                url: item.url || '',
                name: item.name || '',
                target_price: item.target_price || '',
                selector: item.selector || '',
                tags: item.tags || '',
                description: item.description || '',
                notification_profile_id: item.notification_profile_id ? item.notification_profile_id.toString() : ''
            });
        } else {
            setFormData({
                url: '',
                name: '',
                target_price: '',
                selector: '',
                tags: '',
                description: '',
                notification_profile_id: ''
            });
        }
    }, [item, open]);

    useEffect(() => {
        if (open) {
            axios.get(`${API_URL}/notification-profiles`).then(res => setProfiles(res.data)).catch(console.error);
        }
    }, [open]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                ...formData,
                target_price: formData.target_price ? parseFloat(formData.target_price) : null,
                notification_profile_id: formData.notification_profile_id ? parseInt(formData.notification_profile_id) : null
            };

            if (item) {
                await axios.put(`${API_URL}/items/${item.id}`, payload);
                toast.success('Item updated');
            } else {
                await axios.post(`${API_URL}/items`, payload);
                toast.success('Item added');
            }
            onSaved();
            onClose();
        } catch (error) {
            console.error('Error saving item:', error);
            toast.error('Failed to save item');
        }
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>{item ? 'Edit Item' : 'Add New Item'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="url">URL</Label>
                        <Input
                            id="url"
                            type="url"
                            required
                            placeholder="https://example.com/product"
                            value={formData.url}
                            onChange={e => setFormData({ ...formData, url: e.target.value })}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="name">Name</Label>
                        <Input
                            id="name"
                            required
                            placeholder="Product Name"
                            value={formData.name}
                            onChange={e => setFormData({ ...formData, name: e.target.value })}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="target_price">Target Price ($)</Label>
                            <Input
                                id="target_price"
                                type="number"
                                step="0.01"
                                placeholder="0.00"
                                value={formData.target_price}
                                onChange={e => setFormData({ ...formData, target_price: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="selector">Selector (Optional)</Label>
                            <Input
                                id="selector"
                                placeholder=".price-class"
                                value={formData.selector}
                                onChange={e => setFormData({ ...formData, selector: e.target.value })}
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="profile">Notification Profile</Label>
                        <Select
                            value={formData.notification_profile_id}
                            onValueChange={(value) => setFormData({ ...formData, notification_profile_id: value })}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Select a profile" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">None</SelectItem>
                                {profiles.map(p => (
                                    <SelectItem key={p.id} value={p.id.toString()}>{p.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="tags">Tags</Label>
                        <Input
                            id="tags"
                            placeholder="tech, home, gift (comma separated)"
                            value={formData.tags}
                            onChange={e => setFormData({ ...formData, tags: e.target.value })}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="description">Description</Label>
                        <textarea
                            id="description"
                            className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            placeholder="Add notes about this item..."
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                        />
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                        <Button type="submit">Save Item</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
