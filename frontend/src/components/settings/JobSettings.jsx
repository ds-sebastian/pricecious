import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export function JobSettings({ config, onUpdate }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Automated Refresh Job</CardTitle>
                <CardDescription>Configure the background job that checks for price updates.</CardDescription>
            </CardHeader>
            <CardContent>
                <form onSubmit={onUpdate} className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="refresh_interval_minutes">Refresh Interval (Minutes)</Label>
                        <Input
                            id="refresh_interval_minutes"
                            type="number"
                            min="1"
                            value={config.refresh_interval_minutes}
                            onChange={(e) => onUpdate(e, 'refresh_interval_minutes')}
                        />
                    </div>
                    <div className="text-sm text-muted-foreground">
                        <p>Next run: {config.next_run ? new Date(config.next_run).toLocaleString() : 'Not scheduled'}</p>
                        <p>Status: {config.running ? 'Running' : 'Idle'}</p>
                    </div>
                    <Button type="submit">Save Job Config</Button>
                </form>
            </CardContent>
        </Card>
    );
}
