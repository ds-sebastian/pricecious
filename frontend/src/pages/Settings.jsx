import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Sun, Clock, Cpu, Settings as SettingsIcon, Bell, Trash2, ChevronDown, ChevronUp, Edit2, CheckCircle2, AlertCircle, TrendingDown, DollarSign, Package } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';

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
        scraper_timeout: 90000,
        ai_reasoning_effort: 'low'
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

    const [editingProfileId, setEditingProfileId] = useState(null);
    const [showAdvancedAI, setShowAdvancedAI] = useState(false);

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
                ai_api_base: settingsMap['ai_api_base'] !== undefined ? settingsMap['ai_api_base'] : 'http://ollama:11434',
                ai_temperature: parseFloat(settingsMap['ai_temperature'] || '0.1'),
                ai_max_tokens: parseInt(settingsMap['ai_max_tokens'] || '300'),
                confidence_threshold_price: parseFloat(settingsMap['confidence_threshold_price'] || '0.5'),
                confidence_threshold_stock: parseFloat(settingsMap['confidence_threshold_stock'] || '0.5'),
                enable_json_repair: settingsMap['enable_json_repair'] !== 'false',
                smart_scroll_enabled: settingsMap['smart_scroll_enabled'] === 'true',
                smart_scroll_pixels: parseInt(settingsMap['smart_scroll_pixels'] || '350'),
                text_context_enabled: settingsMap['text_context_enabled'] === 'true',
                text_context_length: parseInt(settingsMap['text_context_length'] || '5000'),
                scraper_timeout: parseInt(settingsMap['scraper_timeout'] || '90000'),
                ai_reasoning_effort: settingsMap['ai_reasoning_effort'] || 'low'
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

    const handleProfileSubmit = async (e) => {
        e.preventDefault();
        try {
            if (editingProfileId) {
                await axios.put(`${API_URL}/notification-profiles/${editingProfileId}`, newProfile);
                toast.success('Profile updated');
            } else {
                await axios.post(`${API_URL}/notification-profiles`, newProfile);
                toast.success('Profile created');
            }

            setNewProfile({
                name: '',
                apprise_url: '',
                check_interval_minutes: 60,
                notify_on_price_drop: true,
                notify_on_target_price: true,
                price_drop_threshold_percent: 10,
                notify_on_stock_change: true
            });
            setEditingProfileId(null);
            fetchAll();
        } catch (error) {
            toast.error(editingProfileId ? 'Failed to update profile' : 'Failed to create profile');
        }
    };

    const editProfile = (profile) => {
        setNewProfile({
            name: profile.name,
            apprise_url: profile.apprise_url,
            check_interval_minutes: profile.check_interval_minutes,
            notify_on_price_drop: profile.notify_on_price_drop,
            notify_on_target_price: profile.notify_on_target_price,
            price_drop_threshold_percent: profile.price_drop_threshold_percent,
            notify_on_stock_change: profile.notify_on_stock_change
        });
        setEditingProfileId(profile.id);
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    };

    const cancelEdit = () => {
        setNewProfile({
            name: '',
            apprise_url: '',
            check_interval_minutes: 60,
            notify_on_price_drop: true,
            notify_on_target_price: true,
            price_drop_threshold_percent: 10,
            notify_on_stock_change: true
        });
        setEditingProfileId(null);
    };

    const deleteProfile = async (id) => {
        if (confirm('Are you sure you want to delete this profile?')) {
            try {
                await axios.delete(`${API_URL}/notification-profiles/${id}`);
                toast.success('Profile deleted');
                if (editingProfileId === id) {
                    cancelEdit();
                }
                fetchAll();
            } catch (error) {
                toast.error('Failed to delete profile');
            }
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto pb-10">
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
                <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Provider</Label>
                            <Select value={config.ai_provider} onValueChange={(val) => updateSetting('ai_provider', val)}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="ollama">Ollama</SelectItem>
                                    <SelectItem value="openai">OpenAI</SelectItem>
                                    <SelectItem value="anthropic">Anthropic</SelectItem>
                                    <SelectItem value="openrouter">OpenRouter</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label>Model</Label>
                            <Input value={config.ai_model} onChange={(e) => updateSetting('ai_model', e.target.value)} placeholder="e.g., moondream" />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label>API Key</Label>
                        <Input type="password" value={config.ai_api_key} onChange={(e) => updateSetting('ai_api_key', e.target.value)} placeholder="Optional for local models" />
                    </div>

                    <div className="pt-2">
                        <Button
                            variant="outline"
                            size="sm"
                            className="w-full flex items-center justify-between"
                            onClick={() => setShowAdvancedAI(!showAdvancedAI)}
                        >
                            <span>Advanced Settings</span>
                            {showAdvancedAI ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                    </div>

                    {showAdvancedAI && (
                        <div className="space-y-6 pt-4 animate-in slide-in-from-top-2 duration-200">
                            <div className="space-y-2">
                                <Label>API Base URL</Label>
                                <Input value={config.ai_api_base} onChange={(e) => updateSetting('ai_api_base', e.target.value)} />
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Temperature</Label>
                                            <span className="text-xs text-muted-foreground">{config.ai_temperature}</span>
                                        </div>
                                        <Slider
                                            min={0}
                                            max={1}
                                            step={0.1}
                                            value={config.ai_temperature}
                                            onChange={(e) => updateSetting('ai_temperature', parseFloat(e.target.value))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Reasoning Effort</Label>
                                        <Select value={config.ai_reasoning_effort} onValueChange={(val) => updateSetting('ai_reasoning_effort', val)}>
                                            <SelectTrigger><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="minimal">Minimal (Fastest)</SelectItem>
                                                <SelectItem value="low">Low (Faster/Cheaper)</SelectItem>
                                                <SelectItem value="medium">Medium</SelectItem>
                                                <SelectItem value="high">High (More Thorough)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <p className="text-xs text-muted-foreground">Only for supported models (e.g. gpt-5, gpt-5.1, o1). Use "minimal" for fastest/cheapest responses.</p>
                                    </div>
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Price Confidence Threshold</Label>
                                            <span className="text-xs text-muted-foreground">{config.confidence_threshold_price}</span>
                                        </div>
                                        <Slider
                                            min={0}
                                            max={1}
                                            step={0.1}
                                            value={config.confidence_threshold_price}
                                            onChange={(e) => updateSetting('confidence_threshold_price', parseFloat(e.target.value))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Stock Confidence Threshold</Label>
                                            <span className="text-xs text-muted-foreground">{config.confidence_threshold_stock}</span>
                                        </div>
                                        <Slider
                                            min={0}
                                            max={1}
                                            step={0.1}
                                            value={config.confidence_threshold_stock}
                                            onChange={(e) => updateSetting('confidence_threshold_stock', parseFloat(e.target.value))}
                                        />
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <Label>Max Tokens</Label>
                                        <Input type="number" value={config.ai_max_tokens} onChange={(e) => updateSetting('ai_max_tokens', parseInt(e.target.value))} />
                                    </div>
                                    <div className="flex items-center justify-between pt-2">
                                        <Label htmlFor="json_repair">Enable JSON Repair</Label>
                                        <Switch id="json_repair" checked={config.enable_json_repair} onCheckedChange={(checked) => updateSetting('enable_json_repair', checked)} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
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
                <CardContent className="space-y-8">
                    <form onSubmit={handleProfileSubmit} className="space-y-4 border-b pb-8">
                        <div className="flex items-center justify-between">
                            <h4 className="text-sm font-medium">{editingProfileId ? 'Edit Profile' : 'Create New Profile'}</h4>
                            {editingProfileId && (
                                <Button type="button" variant="ghost" size="sm" onClick={cancelEdit}>Cancel Edit</Button>
                            )}
                        </div>
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
                        <Button type="submit">{editingProfileId ? 'Update Profile' : 'Create Profile'}</Button>
                    </form>

                    <div className="space-y-4">
                        <h4 className="text-sm font-medium">Existing Profiles</h4>
                        {profiles.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No profiles created yet.</p>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {profiles.map(profile => (
                                    <div key={profile.id} className={cn(
                                        "relative group overflow-hidden rounded-xl border bg-card text-card-foreground shadow transition-all hover:shadow-md",
                                        editingProfileId === profile.id && "ring-2 ring-primary"
                                    )}>
                                        <div className="p-6 space-y-4">
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <h3 className="font-semibold leading-none tracking-tight">{profile.name}</h3>
                                                    <p className="text-sm text-muted-foreground mt-1 truncate max-w-[200px]" title={profile.apprise_url}>{profile.apprise_url}</p>
                                                </div>
                                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => editProfile(profile)}>
                                                        <Edit2 className="h-4 w-4" />
                                                    </Button>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => deleteProfile(profile.id)}>
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div className="flex items-center gap-2">
                                                    <Clock className="h-4 w-4 text-muted-foreground" />
                                                    <span>{profile.check_interval_minutes}m interval</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <TrendingDown className="h-4 w-4 text-muted-foreground" />
                                                    <span>{profile.price_drop_threshold_percent}% drop</span>
                                                </div>
                                            </div>

                                            <div className="flex flex-wrap gap-2 pt-2">
                                                {profile.notify_on_price_drop && (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                                                        <DollarSign className="mr-1 h-3 w-3" /> Price Drop
                                                    </span>
                                                )}
                                                {profile.notify_on_target_price && (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                                                        <CheckCircle2 className="mr-1 h-3 w-3" /> Target Hit
                                                    </span>
                                                )}
                                                {profile.notify_on_stock_change && (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                                                        <Package className="mr-1 h-3 w-3" /> Stock Change
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="absolute top-0 right-0 p-6 opacity-5 pointer-events-none">
                                            <Bell className="h-24 w-24" />
                                        </div>
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
