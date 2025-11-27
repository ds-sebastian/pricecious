import React from 'react';
import { ExternalLink, Edit2, RefreshCw, Trash2, AlertTriangle, Clock } from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Marquee } from '@/components/ui/marquee';
import { cn } from '@/lib/utils';

export function ItemCard({ item, onEdit, onDelete, onCheck, onZoom }) {
    const getStockStatus = (inStock) => {
        if (inStock === true) return { label: 'In Stock', color: 'bg-green-500/90 text-white border-green-400/50' };
        if (inStock === false) return { label: 'Out of Stock', color: 'bg-red-500/90 text-white border-red-400/50' };
        return { label: 'Unknown', color: 'bg-zinc-500/90 text-white border-zinc-400/50' };
    };

    const stockStatus = getStockStatus(item.in_stock);

    return (
        <Card className="group overflow-hidden transition-all duration-300 hover:shadow-md border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
            <div className="relative aspect-video overflow-hidden bg-zinc-100 dark:bg-zinc-950 cursor-zoom-in group/image" onClick={() => onZoom(item.screenshot_url)}>
                {item.screenshot_url ? (
                    <>
                        <img
                            src={`${item.screenshot_url}?t=${new Date(item.last_checked).getTime()}`}
                            alt={`Screenshot of ${item.name}`}
                            className="h-full w-full object-cover transition-transform duration-500 group-hover/image:scale-105"
                            onError={(e) => { e.target.style.display = 'none' }}
                        />
                        <div className="absolute inset-0 bg-black/0 transition-colors group-hover/image:bg-black/10" />
                    </>
                ) : (
                    <div className="flex h-full w-full items-center justify-center text-sm text-zinc-400">
                        No screenshot
                    </div>
                )}

                {/* Stock Confidence Bar */}
                {(item.in_stock_confidence !== null && item.in_stock_confidence !== undefined) && (
                    <div className="absolute bottom-0 left-0 right-0 h-1.5 bg-black/20 backdrop-blur-sm">
                        <div
                            className={cn("h-full transition-all duration-500",
                                item.in_stock_confidence > 0.8 ? 'bg-emerald-500' :
                                    item.in_stock_confidence > 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                            )}
                            style={{ width: `${item.in_stock_confidence * 100}%` }}
                            title={`Stock Confidence: ${Math.round(item.in_stock_confidence * 100)}%`}
                        />
                    </div>
                )}

                {/* Stock Badge */}
                <div className={cn("absolute right-3 top-3 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide shadow-sm backdrop-blur-md", stockStatus.color)}>
                    {stockStatus.label}
                </div>
            </div>

            <CardContent className="p-5 relative">
                <div className="mb-4 flex items-start justify-between">
                    <div className="flex-1 overflow-hidden pr-2">
                        <div className="flex items-center gap-2 mb-1">
                            <a
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex-shrink-0 rounded-md bg-zinc-100 p-1.5 text-zinc-500 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700"
                            >
                                <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                            <div className="w-full overflow-hidden">
                                <Marquee text={item.name} className="font-semibold leading-tight" />
                            </div>
                        </div>
                        <a href={item.url} target="_blank" rel="noopener noreferrer" className="block truncate text-xs text-zinc-400 transition-colors hover:text-primary">
                            {new URL(item.url).hostname.replace('www.', '')}
                        </a>
                    </div>

                </div>

                <div className="space-y-4">
                    <div>
                        <div className="mb-1 flex items-baseline justify-between">
                            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Price</span>
                            {item.target_price && (
                                <span className={cn("rounded px-2 py-0.5 text-xs font-medium",
                                    item.current_price <= item.target_price
                                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                        : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400'
                                )}>
                                    Target: ${item.target_price}
                                </span>
                            )}
                        </div>

                        <div className="flex items-end gap-2">
                            <span className={cn("text-3xl font-bold tracking-tight leading-none",
                                item.target_price && item.current_price <= item.target_price
                                    ? 'text-green-600 dark:text-green-400'
                                    : 'text-foreground'
                            )}>
                                {item.current_price ? `$${item.current_price}` : '---'}
                            </span>
                        </div>

                        {/* Price Confidence Bar */}
                        {(item.current_price_confidence !== null && item.current_price_confidence !== undefined) && (
                            <div className="group/confidence relative mt-2">
                                <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                                    <div
                                        className={cn("h-full rounded-full transition-all duration-500",
                                            item.current_price_confidence > 0.8 ? 'bg-primary' :
                                                item.current_price_confidence > 0.5 ? 'bg-primary/70' : 'bg-primary/40'
                                        )}
                                        style={{ width: `${item.current_price_confidence * 100}%` }}
                                    />
                                </div>
                                <div className="absolute -bottom-4 left-0 text-[10px] text-muted-foreground opacity-0 transition-opacity group-hover/confidence:opacity-100">
                                    Price Confidence: {Math.round(item.current_price_confidence * 100)}%
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Tags */}
                    {item.tags && (
                        <div className="flex flex-wrap gap-1.5">
                            {item.tags.split(',').map(tag => (
                                <span key={tag} className="rounded-md border bg-secondary px-2 py-0.5 text-[10px] font-medium text-secondary-foreground">
                                    {tag.trim()}
                                </span>
                            ))}
                        </div>
                    )}

                    {/* Description */}
                    {item.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                            {item.description}
                        </p>
                    )}
                </div>
            </CardContent>

            <CardFooter className="border-t bg-zinc-50/50 p-3 dark:bg-zinc-900/50">
                <div className="flex w-full items-center justify-between">
                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                            <Clock className="h-3 w-3" />
                            <span>{item.last_checked ? new Date(item.last_checked).toLocaleString() : 'Never'}</span>
                        </div>
                        {item.next_check && (
                            <div className="flex items-center gap-1.5 border-l pl-3 border-zinc-200 dark:border-zinc-700">
                                <span>Next: {new Date(item.next_check).toLocaleString()} ({item.interval}m)</span>
                            </div>
                        )}
                        {item.last_error && (
                            <div className="flex items-center gap-1 text-destructive" title={item.last_error}>
                                <AlertTriangle className="h-3 w-3" />
                                <span className="max-w-[100px] truncate">Error</span>
                            </div>
                        )}
                    </div>

                    <div className="flex gap-1">
                        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => onEdit(item)}>
                            <Edit2 className="h-3 w-3" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => onCheck(item.id)} disabled={item.is_refreshing}>
                            <RefreshCw className={cn("h-3 w-3", item.is_refreshing && "animate-spin text-primary")} />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:text-destructive" onClick={() => onDelete(item)}>
                            <Trash2 className="h-3 w-3" />
                        </Button>
                    </div>
                </div>
            </CardFooter>
        </Card>
    );
}
