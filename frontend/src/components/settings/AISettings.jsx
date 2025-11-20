import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export function AISettings({ config, advancedConfig, onUpdateConfig, onUpdateAdvancedConfig }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>AI Configuration</CardTitle>
                <CardDescription>Configure the AI model used for analyzing product pages.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                <form onSubmit={onUpdateConfig} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="ai_provider">Provider</Label>
                            <Select
                                value={config.ai_provider}
                                onValueChange={(val) => onUpdateConfig({ preventDefault: () => { }, target: { value: val } }, 'ai_provider')}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select provider" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="ollama">Ollama</SelectItem>
                                    <SelectItem value="openai">OpenAI</SelectItem>
                                    <SelectItem value="anthropic">Anthropic</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="ai_model">Model</Label>
                            <Input
                                id="ai_model"
                                value={config.ai_model}
                                onChange={(e) => onUpdateConfig(e, 'ai_model')}
                                placeholder="e.g., moondream"
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="ai_api_base">API Base URL</Label>
                        <Input
                            id="ai_api_base"
                            value={config.ai_api_base}
                            onChange={(e) => onUpdateConfig(e, 'ai_api_base')}
                            placeholder="http://localhost:11434"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="ai_api_key">API Key</Label>
                        <Input
                            id="ai_api_key"
                            type="password"
                            value={config.ai_api_key}
                            onChange={(e) => onUpdateConfig(e, 'ai_api_key')}
                            placeholder="Optional for local models"
                        />
                    </div>
                    <Button type="submit">Save AI Config</Button>
                </form>

                <div className="border-t pt-6">
                    <h4 className="text-sm font-medium mb-4">Advanced Settings</h4>
                    <form onSubmit={onUpdateAdvancedConfig} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="ai_temperature">Temperature ({advancedConfig.ai_temperature})</Label>
                                <Input
                                    id="ai_temperature"
                                    type="number"
                                    step="0.1"
                                    min="0"
                                    max="1"
                                    value={advancedConfig.ai_temperature}
                                    onChange={(e) => onUpdateAdvancedConfig(e, 'ai_temperature')}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="ai_max_tokens">Max Tokens</Label>
                                <Input
                                    id="ai_max_tokens"
                                    type="number"
                                    value={advancedConfig.ai_max_tokens}
                                    onChange={(e) => onUpdateAdvancedConfig(e, 'ai_max_tokens')}
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="confidence_threshold_price">Price Confidence Threshold</Label>
                                <Input
                                    id="confidence_threshold_price"
                                    type="number"
                                    step="0.1"
                                    min="0"
                                    max="1"
                                    value={advancedConfig.confidence_threshold_price}
                                    onChange={(e) => onUpdateAdvancedConfig(e, 'confidence_threshold_price')}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="confidence_threshold_stock">Stock Confidence Threshold</Label>
                                <Input
                                    id="confidence_threshold_stock"
                                    type="number"
                                    step="0.1"
                                    min="0"
                                    max="1"
                                    value={advancedConfig.confidence_threshold_stock}
                                    onChange={(e) => onUpdateAdvancedConfig(e, 'confidence_threshold_stock')}
                                />
                            </div>
                        </div>
                        <div className="flex items-center justify-between">
                            <Label htmlFor="enable_json_repair">Enable JSON Repair</Label>
                            <Switch
                                id="enable_json_repair"
                                checked={advancedConfig.enable_json_repair}
                                onCheckedChange={(checked) => onUpdateAdvancedConfig({ preventDefault: () => { }, target: { value: checked } }, 'enable_json_repair')}
                            />
                        </div>
                        <Button type="submit" variant="secondary">Save Advanced Config</Button>
                    </form>
                </div>
            </CardContent>
        </Card>
    );
}
