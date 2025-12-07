import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
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

        custom_prompt: '',
        notification_profile_id: '',
        current_price: '',
        in_stock: 'unknown'
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

                custom_prompt: item.custom_prompt || '',
                notification_profile_id: item.notification_profile_id ? item.notification_profile_id.toString() : '',
                current_price: item.current_price || '',
                in_stock: item.in_stock === true ? 'true' : item.in_stock === false ? 'false' : 'unknown'
            });
        } else {
            setFormData({
                url: '',
                name: '',
                target_price: '',
                selector: '',
                tags: '',
                description: '',

                custom_prompt: '',
                notification_profile_id: '',
                current_price: '',
                in_stock: 'unknown'
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
                notification_profile_id: formData.notification_profile_id ? parseInt(formData.notification_profile_id) : null,
                current_price: formData.current_price ? parseFloat(formData.current_price) : null,
                in_stock: formData.in_stock === 'true' ? true : formData.in_stock === 'false' ? false : null
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
                    <DialogDescription>
                        {item ? "Make changes to your item here. Click save when you're done." : "Add a new item to track details for. Click save when you're done."}
                    </DialogDescription>
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

                    {/* Manual Override Section */}
                    {item && (
                        <div className="rounded-md bg-muted/50 p-3 space-y-3 border border-border/50">
                            <h4 className="text-sm font-medium">Manual Override</h4>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="current_price">Current Price ($)</Label>
                                    <Input
                                        id="current_price"
                                        type="number"
                                        step="0.01"
                                        placeholder="0.00"
                                        value={formData.current_price}
                                        onChange={e => setFormData({ ...formData, current_price: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="in_stock">Stock Status</Label>
                                    <Select
                                        value={formData.in_stock}
                                        onValueChange={(value) => setFormData({ ...formData, in_stock: value })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select status" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="unknown">Unknown</SelectItem>
                                            <SelectItem value="true">In Stock</SelectItem>
                                            <SelectItem value="false">Out of Stock</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Manually setting these values helps correct bad data or reset the baseline for outlier detection.
                            </p>
                        </div>
                    )}

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
                    <div className="space-y-2">
                        <Label htmlFor="custom_prompt">Custom AI Prompt (Optional)</Label>
                        <textarea
                            id="custom_prompt"
                            className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            placeholder="Override the default price extraction prompt. Use {context_section} to include page text."
                            value={formData.custom_prompt}
                            onChange={e => setFormData({ ...formData, custom_prompt: e.target.value })}
                        />
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                        <Button type="submit">Save Item</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog >
    );
}
