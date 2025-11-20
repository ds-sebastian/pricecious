import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export function ProfileSettings({ profiles, onCreate, onDelete }) {
    const [newProfile, setNewProfile] = useState({
        name: '',
        apprise_url: '',
        check_interval_minutes: 60,
        notify_on_price_drop: true,
        notify_on_target_price: true,
        price_drop_threshold_percent: 10,
        notify_on_stock_change: true
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        onCreate(newProfile);
        setNewProfile({
            name: '',
            apprise_url: '',
            check_interval_minutes: 60,
            notify_on_price_drop: true,
            notify_on_target_price: true,
            price_drop_threshold_percent: 10,
            notify_on_stock_change: true
        });
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Notification Profiles</CardTitle>
                <CardDescription>Manage notification settings for different groups of items.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Create New Profile */}
                <form onSubmit={handleSubmit} className="space-y-4 border-b pb-6">
                    <h4 className="text-sm font-medium">Create New Profile</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="profile_name">Name</Label>
                            <Input
                                id="profile_name"
                                required
                                value={newProfile.name}
                                onChange={(e) => setNewProfile({ ...newProfile, name: e.target.value })}
                                placeholder="e.g., Email Alerts"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="apprise_url">Apprise URL</Label>
                            <Input
                                id="apprise_url"
                                required
                                value={newProfile.apprise_url}
                                onChange={(e) => setNewProfile({ ...newProfile, apprise_url: e.target.value })}
                                placeholder="mailto://user:pass@gmail.com"
                            />
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="check_interval">Check Interval (Minutes)</Label>
                            <Input
                                id="check_interval"
                                type="number"
                                min="1"
                                value={newProfile.check_interval_minutes}
                                onChange={(e) => setNewProfile({ ...newProfile, check_interval_minutes: parseInt(e.target.value) })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="drop_threshold">Price Drop Threshold (%)</Label>
                            <Input
                                id="drop_threshold"
                                type="number"
                                min="1"
                                max="100"
                                value={newProfile.price_drop_threshold_percent}
                                onChange={(e) => setNewProfile({ ...newProfile, price_drop_threshold_percent: parseFloat(e.target.value) })}
                            />
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-4">
                        <div className="flex items-center space-x-2">
                            <Switch
                                id="notify_drop"
                                checked={newProfile.notify_on_price_drop}
                                onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_price_drop: checked })}
                            />
                            <Label htmlFor="notify_drop">Notify on Drop</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <Switch
                                id="notify_target"
                                checked={newProfile.notify_on_target_price}
                                onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_target_price: checked })}
                            />
                            <Label htmlFor="notify_target">Notify on Target</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <Switch
                                id="notify_stock"
                                checked={newProfile.notify_on_stock_change}
                                onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_stock_change: checked })}
                            />
                            <Label htmlFor="notify_stock">Notify on Stock Change</Label>
                        </div>
                    </div>
                    <Button type="submit">Create Profile</Button>
                </form>

                {/* List Profiles */}
                <div className="space-y-4">
                    <h4 className="text-sm font-medium">Existing Profiles</h4>
                    {profiles.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No profiles created yet.</p>
                    ) : (
                        <div className="grid gap-4">
                            {profiles.map(profile => (
                                <div key={profile.id} className="flex items-center justify-between rounded-lg border p-4">
                                    <div>
                                        <p className="font-medium">{profile.name}</p>
                                        <p className="text-xs text-muted-foreground truncate max-w-[200px]">{profile.apprise_url}</p>
                                    </div>
                                    <Button variant="ghost" size="icon" onClick={() => onDelete(profile.id)}>
                                        <Trash2 className="h-4 w-4 text-destructive" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
