import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';

export function ScraperSettings({ config, onUpdate }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Scraper Configuration</CardTitle>
                <CardDescription>Configure how the scraper interacts with web pages.</CardDescription>
            </CardHeader>
            <CardContent>
                <form onSubmit={onUpdate} className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label htmlFor="smart_scroll_enabled">Smart Scroll</Label>
                            <p className="text-sm text-muted-foreground">Scroll down to trigger lazy loading.</p>
                        </div>
                        <Switch
                            id="smart_scroll_enabled"
                            checked={config.smart_scroll_enabled}
                            onCheckedChange={(checked) => onUpdate({ preventDefault: () => { }, target: { value: checked } }, 'smart_scroll_enabled')}
                        />
                    </div>
                    {config.smart_scroll_enabled && (
                        <div className="space-y-2">
                            <Label htmlFor="smart_scroll_pixels">Scroll Pixels</Label>
                            <Input
                                id="smart_scroll_pixels"
                                type="number"
                                value={config.smart_scroll_pixels}
                                onChange={(e) => onUpdate(e, 'smart_scroll_pixels')}
                            />
                        </div>
                    )}
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label htmlFor="text_context_enabled">Text Context</Label>
                            <p className="text-sm text-muted-foreground">Send page text to AI along with screenshot.</p>
                        </div>
                        <Switch
                            id="text_context_enabled"
                            checked={config.text_context_enabled}
                            onCheckedChange={(checked) => onUpdate({ preventDefault: () => { }, target: { value: checked } }, 'text_context_enabled')}
                        />
                    </div>
                    {config.text_context_enabled && (
                        <div className="space-y-2">
                            <Label htmlFor="text_context_length">Max Text Length</Label>
                            <Input
                                id="text_context_length"
                                type="number"
                                value={config.text_context_length}
                                onChange={(e) => onUpdate(e, 'text_context_length')}
                            />
                        </div>
                    )}
                    <div className="space-y-2">
                        <Label htmlFor="scraper_timeout">Timeout (ms)</Label>
                        <Input
                            id="scraper_timeout"
                            type="number"
                            value={config.scraper_timeout}
                            onChange={(e) => onUpdate(e, 'scraper_timeout')}
                        />
                    </div>
                    <Button type="submit">Save Scraper Config</Button>
                </form>
            </CardContent>
        </Card>
    );
}
