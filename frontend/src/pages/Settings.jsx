import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Sun, Clock, Cpu, Settings as SettingsIcon, Bell, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const API_URL = '/api';

export default function Settings() {
    const [profiles, setProfiles] = useState([]);
    const [jobConfig, setJobConfig] = useState({ refresh_interval_minutes: 60, next_run: null, running: false });
    const [config, setConfig] = useState({
        ai_provider: 'ollama',
        ai_model: 'moondream',
        ai_api_key: '',
        ai_api_base: 'http://ollama:11434',
        ai_temperature: 0.1,
        ai_max_tokens: 300,
        confidence_threshold_price: 0.5,
        confidence_threshold_stock: 0.5,
        enable_json_repair: true,
        smart_scroll_enabled: false,
        smart_scroll_pixels: 350,
        text_context_enabled: false,
        text_context_length: 5000,
        scraper_timeout: 90000
    });
    const [newProfile, setNewProfile] = useState({
        name: '',
        apprise_url: '',
        check_interval_minutes: 60,
        notify_on_price_drop: true,
        notify_on_target_price: true,
        price_drop_threshold_percent: 10,
        notify_on_stock_change: true
    });

    useEffect(() => {
        fetchAll();
    }, []);

    const fetchAll = async () => {
        try {
            const [profilesRes, settingsRes, jobRes] = await Promise.all([
                axios.get(`${API_URL}/notification-profiles`),
                axios.get(`${API_URL}/settings`),
                axios.get(`${API_URL}/jobs/config`)
            ]);

            setProfiles(profilesRes.data);
            setJobConfig(jobRes.data);

            const settingsMap = {};
            settingsRes.data.forEach(s => settingsMap[s.key] = s.value);

            setConfig({
                ai_provider: settingsMap['ai_provider'] || 'ollama',
                ai_model: settingsMap['ai_model'] || 'moondream',
                ai_api_key: settingsMap['ai_api_key'] || '',
                ai_api_base: settingsMap['ai_api_base'] || 'http://ollama:11434',
                ai_temperature: parseFloat(settingsMap['ai_temperature'] || '0.1'),
                ai_max_tokens: parseInt(settingsMap['ai_max_tokens'] || '300'),
                confidence_threshold_price: parseFloat(settingsMap['confidence_threshold_price'] || '0.5'),
                confidence_threshold_stock: parseFloat(settingsMap['confidence_threshold_stock'] || '0.5'),
                enable_json_repair: settingsMap['enable_json_repair'] !== 'false',
                smart_scroll_enabled: settingsMap['smart_scroll_enabled'] === 'true',
                smart_scroll_pixels: parseInt(settingsMap['smart_scroll_pixels'] || '350'),
                text_context_enabled: settingsMap['text_context_enabled'] === 'true',
                text_context_length: parseInt(settingsMap['text_context_length'] || '5000'),
                scraper_timeout: parseInt(settingsMap['scraper_timeout'] || '90000')
            });
        } catch (error) {
            toast.error('Failed to fetch settings');
        }
    };

    const updateSetting = async (key, value) => {
        try {
            await axios.post(`${API_URL}/settings`, { key, value: value.toString() });
            setConfig(prev => ({ ...prev, [key]: value }));
            toast.success('Setting updated');
        } catch (error) {
            toast.error('Failed to update setting');
        }
    };

    const updateJobConfig = async () => {
        try {
            await axios.post(`${API_URL}/jobs/config`, {
                key: 'refresh_interval_minutes',
                value: jobConfig.refresh_interval_minutes.toString()
            });
            toast.success('Job configuration updated');
            fetchAll();
        } catch (error) {
            toast.error('Failed to update job config');
        }
    };

    const createProfile = async (e) => {
        e.preventDefault();
        try {
            await axios.post(`${API_URL}/notification-profiles`, newProfile);
            toast.success('Profile created');
            setNewProfile({
                name: '',
                apprise_url: '',
                check_interval_minutes: 60,
                notify_on_price_drop: true,
                notify_on_target_price: true,
                price_drop_threshold_percent: 10,
                notify_on_stock_change: true
            });
            fetchAll();
        } catch (error) {
            toast.error('Failed to create profile');
        }
    };

    const deleteProfile = async (id) => {
        try {
            await axios.delete(`${API_URL}/notification-profiles/${id}`);
            toast.success('Profile deleted');
            fetchAll();
        } catch (error) {
            toast.error('Failed to delete profile');
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto">
            <div>
                <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
                <p className="text-muted-foreground">Configure application preferences and notifications.</p>
            </div>

            {/* AI Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Cpu className="h-5 w-5" />AI Configuration</CardTitle>
                    <CardDescription>Configure the AI model used for analyzing product pages.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Provider</Label>
                            <Select value={config.ai_provider} onValueChange={(val) => updateSetting('ai_provider', val)}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="ollama">Ollama</SelectItem>
                                    <SelectItem value="openai">OpenAI</SelectItem>
                                    <SelectItem value="anthropic">Anthropic</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label>Model</Label>
                            <Input value={config.ai_model} onChange={(e) => updateSetting('ai_model', e.target.value)} placeholder="e.g., moondream" />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label>API Base URL</Label>
                        <Input value={config.ai_api_base} onChange={(e) => updateSetting('ai_api_base', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                        <Label>API Key</Label>
                        <Input type="password" value={config.ai_api_key} onChange={(e) => updateSetting('ai_api_key', e.target.value)} placeholder="Optional for local models" />
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t">
                        <div className="space-y-2">
                            <Label>Temperature</Label>
                            <Input type="number" step="0.1" min="0" max="1" value={config.ai_temperature} onChange={(e) => updateSetting('ai_temperature', parseFloat(e.target.value))} />
                        </div>
                        <div className="space-y-2">
                            <Label>Max Tokens</Label>
                            <Input type="number" value={config.ai_max_tokens} onChange={(e) => updateSetting('ai_max_tokens', parseInt(e.target.value))} />
                        </div>
                        <div className="space-y-2">
                            <Label>Price Confidence</Label>
                            <Input type="number" step="0.1" min="0" max="1" value={config.confidence_threshold_price} onChange={(e) => updateSetting('confidence_threshold_price', parseFloat(e.target.value))} />
                        </div>
                        <div className="space-y-2">
                            <Label>Stock Confidence</Label>
                            <Input type="number" step="0.1" min="0" max="1" value={config.confidence_threshold_stock} onChange={(e) => updateSetting('confidence_threshold_stock', parseFloat(e.target.value))} />
                        </div>
                    </div>
                    <div className="flex items-center justify-between pt-2">
                        <Label htmlFor="json_repair">Enable JSON Repair</Label>
                        <Switch id="json_repair" checked={config.enable_json_repair} onCheckedChange={(checked) => updateSetting('enable_json_repair', checked)} />
                    </div>
                </CardContent>
            </Card>

            {/* Scraper Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><SettingsIcon className="h-5 w-5" />Scraper Configuration</CardTitle>
                    <CardDescription>Configure how the scraper interacts with web pages.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <Label>Smart Scroll</Label>
                            <p className="text-sm text-muted-foreground">Scroll down to trigger lazy loading.</p>
                        </div>
                        <Switch checked={config.smart_scroll_enabled} onCheckedChange={(checked) => updateSetting('smart_scroll_enabled', checked)} />
                    </div>
                    {config.smart_scroll_enabled && (
                        <div className="space-y-2">
                            <Label>Scroll Pixels</Label>
                            <Input type="number" value={config.smart_scroll_pixels} onChange={(e) => updateSetting('smart_scroll_pixels', parseInt(e.target.value))} />
                        </div>
                    )}
                    <div className="flex items-center justify-between">
                        <div>
                            <Label>Text Context</Label>
                            <p className="text-sm text-muted-foreground">Send page text to AI along with screenshot.</p>
                        </div>
                        <Switch checked={config.text_context_enabled} onCheckedChange={(checked) => updateSetting('text_context_enabled', checked)} />
                    </div>
                    {config.text_context_enabled && (
                        <div className="space-y-2">
                            <Label>Max Text Length</Label>
                            <Input type="number" value={config.text_context_length} onChange={(e) => updateSetting('text_context_length', parseInt(e.target.value))} />
                        </div>
                    )}
                    <div className="space-y-2">
                        <Label>Timeout (ms)</Label>
                        <Input type="number" value={config.scraper_timeout} onChange={(e) => updateSetting('scraper_timeout', parseInt(e.target.value))} />
                    </div>
                </CardContent>
            </Card>

            {/* Job Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Clock className="h-5 w-5" />Automated Refresh Job</CardTitle>
                    <CardDescription>Configure the background job that checks for price updates.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label>Refresh Interval (Minutes)</Label>
                        <Input type="number" min="1" value={jobConfig.refresh_interval_minutes} onChange={(e) => setJobConfig({ ...jobConfig, refresh_interval_minutes: e.target.value })} />
                    </div>
                    <div className="text-sm text-muted-foreground space-y-1">
                        <p>Next run: {jobConfig.next_run ? new Date(jobConfig.next_run).toLocaleString() : 'Not scheduled'}</p>
                        <p>Status: {jobConfig.running ? 'Running' : 'Idle'}</p>
                    </div>
                    <Button onClick={updateJobConfig}>Save Job Config</Button>
                </CardContent>
            </Card>

            {/* Notification Profiles */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Bell className="h-5 w-5" />Notification Profiles</CardTitle>
                    <CardDescription>Manage notification settings for different groups of items.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    <form onSubmit={createProfile} className="space-y-4 border-b pb-6">
                        <h4 className="text-sm font-medium">Create New Profile</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Name</Label>
                                <Input required value={newProfile.name} onChange={(e) => setNewProfile({ ...newProfile, name: e.target.value })} placeholder="e.g., Email Alerts" />
                            </div>
                            <div className="space-y-2">
                                <Label>Apprise URL</Label>
                                <Input required value={newProfile.apprise_url} onChange={(e) => setNewProfile({ ...newProfile, apprise_url: e.target.value })} placeholder="mailto://user:pass@gmail.com" />
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Check Interval (Minutes)</Label>
                                <Input type="number" min="1" value={newProfile.check_interval_minutes} onChange={(e) => setNewProfile({ ...newProfile, check_interval_minutes: parseInt(e.target.value) })} />
                            </div>
                            <div className="space-y-2">
                                <Label>Price Drop Threshold (%)</Label>
                                <Input type="number" min="1" max="100" value={newProfile.price_drop_threshold_percent} onChange={(e) => setNewProfile({ ...newProfile, price_drop_threshold_percent: parseFloat(e.target.value) })} />
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-4">
                            <div className="flex items-center space-x-2">
                                <Switch checked={newProfile.notify_on_price_drop} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_price_drop: checked })} />
                                <Label>Notify on Drop</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <Switch checked={newProfile.notify_on_target_price} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_target_price: checked })} />
                                <Label>Notify on Target</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <Switch checked={newProfile.notify_on_stock_change} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_stock_change: checked })} />
                                <Label>Notify on Stock Change</Label>
                            </div>
                        </div>
                        <Button type="submit">Create Profile</Button>
                    </form>

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
                                        <Button variant="ghost" size="icon" onClick={() => deleteProfile(profile.id)}>
                                            <Trash2 className="h-4 w-4 text-destructive" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
