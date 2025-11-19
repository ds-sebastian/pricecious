import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { Plus, Trash2, RefreshCw, ExternalLink, Settings as SettingsIcon, Save, X, Edit2, Bell, Search, Clock, AlertTriangle, Moon, Sun, ChevronRight, Check } from 'lucide-react'
import { Toaster, toast } from 'sonner'

const API_URL = '/api';

function App() {
    const [items, setItems] = useState([]);
    const [view, setView] = useState('dashboard'); // 'dashboard' or 'settings'
    const [searchTerm, setSearchTerm] = useState('');
    const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');

    useEffect(() => {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

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

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-black text-zinc-900 dark:text-zinc-100 transition-colors duration-300 font-sans selection:bg-purple-500/30">
            <Toaster position="bottom-right" theme={theme} />

            {/* Sticky Glass Header */}
            <header className="sticky top-0 z-40 w-full backdrop-blur-xl bg-white/70 dark:bg-black/70 border-b border-zinc-200 dark:border-zinc-800 transition-colors duration-300">
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 cursor-pointer" onClick={() => setView('dashboard')}>
                        <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-lg flex items-center justify-center shadow-lg shadow-purple-500/20">
                            <span className="text-lg">💍</span>
                        </div>
                        <h1 className="text-lg font-semibold tracking-tight">
                            Pricecious
                        </h1>
                    </div>

                    {/* Search Bar */}
                    {view === 'dashboard' && (
                        <div className="flex-1 max-w-md relative hidden md:block group">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-400 w-4 h-4 group-focus-within:text-purple-500 transition-colors" />
                            <input
                                type="text"
                                placeholder="Search items..."
                                className="w-full bg-zinc-100 dark:bg-zinc-900 border-none rounded-xl pl-10 pr-4 py-2 text-sm focus:ring-2 focus:ring-purple-500/50 transition-all placeholder:text-zinc-500"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    )}

                    <div className="flex items-center gap-2">
                        <button
                            onClick={toggleTheme}
                            className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 transition-colors"
                            title="Toggle Theme"
                        >
                            {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                        </button>
                        <div className="h-6 w-px bg-zinc-200 dark:bg-zinc-800 mx-1"></div>
                        <button
                            onClick={() => setView('dashboard')}
                            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${view === 'dashboard' ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100' : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100'}`}
                        >
                            Dashboard
                        </button>
                        <button
                            onClick={() => setView('settings')}
                            className={`p-2 rounded-lg transition-all ${view === 'settings' ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100' : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100'}`}
                        >
                            <SettingsIcon className="w-5 h-5" />
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto p-6">
                {view === 'dashboard' ? (
                    <Dashboard items={items} refreshItems={refreshItems} searchTerm={searchTerm} />
                ) : (
                    <SettingsPage theme={theme} toggleTheme={toggleTheme} />
                )}
            </main>
        </div>
    );
}

function MarqueeText({ text, className }) {
    const [isOverflowing, setIsOverflowing] = useState(false);
    const containerRef = useRef(null);
    const textRef = useRef(null);
    const [duration, setDuration] = useState(0);
    const [distance, setDistance] = useState(0);

    useEffect(() => {
        const checkOverflow = () => {
            if (containerRef.current && textRef.current) {
                const containerWidth = containerRef.current.clientWidth;
                const textWidth = textRef.current.scrollWidth;
                const gap = 32; // 2rem gap

                const isOver = textWidth > containerWidth;
                setIsOverflowing(isOver);

                if (isOver) {
                    // Calculate duration based on width to ensure constant speed
                    // Speed = pixels / second. Let's say 50px/s is a good reading speed
                    const speed = 50;
                    const totalDistance = textWidth + gap;
                    setDistance(totalDistance);
                    setDuration(totalDistance / speed);
                }
            }
        };

        checkOverflow();
        // Add a small delay to ensure fonts are loaded and layout is stable
        const timeoutId = setTimeout(checkOverflow, 100);

        window.addEventListener('resize', checkOverflow);
        return () => {
            window.removeEventListener('resize', checkOverflow);
            clearTimeout(timeoutId);
        };
    }, [text]);

    return (
        <div ref={containerRef} className={`overflow-hidden w-full ${className}`}>
            <div
                ref={textRef}
                className={`whitespace-nowrap flex gap-8 ${isOverflowing ? 'animate-marquee' : ''}`}
                style={isOverflowing ? {
                    '--marquee-duration': `${duration}s`,
                    '--marquee-distance': `${distance}px`
                } : {}}
                title={text}
            >
                <span>{text}</span>
                {isOverflowing && <span aria-hidden="true">{text}</span>}
            </div>
        </div>
    );
}

function Dashboard({ items, refreshItems, searchTerm }) {
    const [showAddModal, setShowAddModal] = useState(false);
    const [editingItem, setEditingItem] = useState(null);
    const [zoomedImage, setZoomedImage] = useState(null);
    const [itemToDelete, setItemToDelete] = useState(null);

    const filteredItems = items.filter(item => {
        const term = searchTerm.toLowerCase();
        return (
            item.name.toLowerCase().includes(term) ||
            item.url.toLowerCase().includes(term) ||
            (item.tags && item.tags.toLowerCase().includes(term)) ||
            (item.description && item.description.toLowerCase().includes(term))
        );
    });

    const handleCheck = async (id) => {
        try {
            toast.info('Check triggered...');
            await axios.post(`${API_URL}/items/${id}/check`);
            toast.success('Check started in background');
            setTimeout(refreshItems, 2000);
        } catch (error) {
            console.error('Error triggering check:', error);
            toast.error('Failed to trigger check');
        }
    };

    const handleRefreshAll = async () => {
        try {
            toast.info('Triggering refresh for all items...');
            await axios.post(`${API_URL}/jobs/refresh-all`);
            toast.success('Refresh all started');
        } catch (error) {
            console.error('Error triggering refresh all:', error);
            toast.error('Failed to trigger refresh all');
        }
    };

    const handleDelete = (item) => {
        setItemToDelete(item);
    };

    const confirmDelete = async () => {
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

    return (
        <div className="animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Tracked Items</h2>
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">Manage and monitor your product watchlist.</p>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={handleRefreshAll}
                        className="flex items-center gap-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-800 px-4 py-2 rounded-xl transition-all shadow-sm text-sm font-medium"
                    >
                        <RefreshCw className="w-4 h-4" /> Refresh All
                    </button>
                    <button
                        onClick={() => setShowAddModal(true)}
                        className="flex items-center gap-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 px-4 py-2 rounded-xl transition-all shadow-lg shadow-zinc-500/20 text-sm font-medium"
                    >
                        <Plus className="w-4 h-4" /> Add Item
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredItems.map(item => (
                    <div key={item.id} className="group bg-white dark:bg-zinc-900 rounded-2xl p-5 border border-zinc-200 dark:border-zinc-800 shadow-sm hover:shadow-md dark:hover:border-zinc-700 transition-all duration-300 flex flex-col relative overflow-hidden">

                        <div className="flex justify-between items-start mb-4 z-10 relative">
                            <div className="flex items-center gap-3 overflow-hidden flex-1">
                                <a
                                    href={item.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="p-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg text-zinc-500 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors flex-shrink-0"
                                >
                                    <ExternalLink className="w-4 h-4" />
                                </a>
                                <div className="overflow-hidden w-full relative group/title">
                                    <MarqueeText
                                        text={item.name}
                                        className="font-semibold text-base leading-tight"
                                    />
                                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-xs text-zinc-400 hover:text-purple-500 truncate block mt-0.5 transition-colors">
                                        {new URL(item.url).hostname.replace('www.', '')}
                                    </a>
                                </div>
                            </div>
                            <div className="absolute top-0 right-0 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 dark:bg-zinc-900/90 backdrop-blur-sm rounded-lg p-1 shadow-sm border border-zinc-100 dark:border-zinc-800 z-20">
                                <button onClick={() => setEditingItem(item)} className="p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                                    <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button onClick={() => handleCheck(item.id)} className="p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                                    <RefreshCw className="w-3.5 h-3.5" />
                                </button>
                                <button onClick={() => handleDelete(item)} className="p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md text-zinc-400 hover:text-red-500 transition-colors">
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>

                        {/* Screenshot Display */}
                        <div className="mb-5 relative rounded-xl overflow-hidden border border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 aspect-video group/image cursor-zoom-in" onClick={() => setZoomedImage(`${item.screenshot_url}?t=${new Date().getTime()}`)}>
                            {item.screenshot_url ? (
                                <>
                                    <img
                                        src={`${item.screenshot_url}?t=${new Date(item.last_checked).getTime()}`}
                                        alt={`Screenshot of ${item.name}`}
                                        className="w-full h-full object-cover transition-transform duration-500 group-hover/image:scale-105"
                                        onError={(e) => { e.target.style.display = 'none' }}
                                    />
                                    <div className="absolute inset-0 bg-black/0 group-hover/image:bg-black/10 transition-colors" />
                                </>
                            ) : (
                                <div className="w-full h-full flex items-center justify-center text-zinc-400 text-sm">
                                    No screenshot
                                </div>
                            )}

                            {/* Stock Badge */}
                            <div className={`absolute top-3 right-3 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wide uppercase backdrop-blur-md shadow-sm border ${item.in_stock === true ? 'bg-green-500/90 text-white border-green-400/50' :
                                item.in_stock === false ? 'bg-red-500/90 text-white border-red-400/50' :
                                    'bg-zinc-500/90 text-white border-zinc-400/50'
                                }`}>
                                {item.in_stock === true ? 'In Stock' : item.in_stock === false ? 'Out of Stock' : 'Unknown'}
                            </div>
                        </div>

                        <div className="space-y-3 flex-grow">
                            <div className="flex justify-between items-baseline">
                                <span className="text-zinc-500 text-sm font-medium">Current Price</span>
                                <span className={`text-2xl font-bold tracking-tight ${item.target_price && item.current_price <= item.target_price
                                    ? 'text-green-600 dark:text-green-400'
                                    : item.target_price && item.current_price > item.target_price
                                        ? 'text-red-600 dark:text-red-400'
                                        : 'text-zinc-900 dark:text-white'
                                    }`}>
                                    {item.current_price ? `$${item.current_price}` : '---'}
                                </span>
                            </div>

                            {item.target_price ? (
                                <div className="flex justify-between items-center">
                                    <span className="text-zinc-400 text-xs font-medium uppercase tracking-wider">Target</span>
                                    <span className="text-zinc-600 dark:text-zinc-400 font-medium bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded text-sm">
                                        ${item.target_price}
                                    </span>
                                </div>
                            ) : (
                                <div className="flex justify-between items-center">
                                    <span className="text-zinc-400 text-xs font-medium uppercase tracking-wider">Target</span>
                                    <span className="text-zinc-400 text-xs italic">Not set</span>
                                </div>
                            )}

                            {/* Tags */}
                            {item.tags && (
                                <div className="flex flex-wrap gap-1.5 pt-1">
                                    {item.tags.split(',').map(tag => (
                                        <span key={tag} className="px-2 py-0.5 bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md text-[10px] font-medium text-zinc-600 dark:text-zinc-400">
                                            {tag.trim()}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Description */}
                            {item.description && (
                                <p className="text-xs text-zinc-500 mt-2 line-clamp-2 leading-relaxed">
                                    {item.description}
                                </p>
                            )}
                        </div>

                        <div className="flex justify-between items-center text-[10px] text-zinc-400 mt-5 pt-4 border-t border-zinc-100 dark:border-zinc-800/50">
                            <div className="flex items-center gap-1.5">
                                <Clock className="w-3 h-3" />
                                <span>{item.last_checked ? new Date(item.last_checked).toLocaleString() : 'Never'}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {showAddModal && (
                <ItemModal onClose={() => setShowAddModal(false)} onSaved={refreshItems} />
            )}

            {editingItem && (
                <ItemModal item={editingItem} onClose={() => setEditingItem(null)} onSaved={refreshItems} />
            )}

            {/* Image Zoom Modal */}
            {zoomedImage && (
                <div
                    className="fixed inset-0 bg-white/80 dark:bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 cursor-zoom-out animate-in fade-in duration-200"
                    onClick={() => setZoomedImage(null)}
                >
                    <img
                        src={zoomedImage}
                        alt="Zoomed screenshot"
                        className="max-w-full max-h-full rounded-xl shadow-2xl border border-zinc-200 dark:border-zinc-800"
                    />
                    <button
                        className="absolute top-6 right-6 p-2 bg-white dark:bg-zinc-800 rounded-full shadow-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors"
                        onClick={() => setZoomedImage(null)}
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>
            )}

            {itemToDelete && (
                <DeleteConfirmationModal
                    item={itemToDelete}
                    onClose={() => setItemToDelete(null)}
                    onConfirm={confirmDelete}
                />
            )}
        </div>
    );
}

function ItemModal({ item, onClose, onSaved }) {
    const [formData, setFormData] = useState({
        url: item?.url || '',
        name: item?.name || '',
        target_price: item?.target_price || '',
        selector: item?.selector || '',
        tags: item?.tags || '',
        description: item?.description || '',
        notification_profile_id: item?.notification_profile_id || ''
    });
    const [profiles, setProfiles] = useState([]);

    useEffect(() => {
        axios.get(`${API_URL}/notification-profiles`).then(res => setProfiles(res.data));
    }, []);

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
        <div className="fixed inset-0 bg-black/20 dark:bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-8 w-full max-w-lg border border-zinc-200 dark:border-zinc-800 shadow-2xl">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold tracking-tight">{item ? 'Edit Item' : 'Add New Item'}</h2>
                    <button onClick={onClose} className="text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>
                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">URL</label>
                        <input
                            type="url"
                            required
                            className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                            value={formData.url}
                            onChange={e => setFormData({ ...formData, url: e.target.value })}
                            placeholder="https://example.com/product"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Name</label>
                        <input
                            type="text"
                            required
                            className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                            value={formData.name}
                            onChange={e => setFormData({ ...formData, name: e.target.value })}
                            placeholder="Product Name"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-5">
                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Target Price ($)</label>
                            <input
                                type="number"
                                step="0.01"
                                className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                                value={formData.target_price}
                                onChange={e => setFormData({ ...formData, target_price: e.target.value })}
                                placeholder="0.00"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Selector (Optional)</label>
                            <input
                                type="text"
                                className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                                placeholder=".price-class"
                                value={formData.selector}
                                onChange={e => setFormData({ ...formData, selector: e.target.value })}
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Notification Profile</label>
                        <div className="relative">
                            <select
                                className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all appearance-none"
                                value={formData.notification_profile_id}
                                onChange={e => setFormData({ ...formData, notification_profile_id: e.target.value })}
                            >
                                <option value="">None</option>
                                {profiles.map(p => (
                                    <option key={p.id} value={p.id}>{p.name}</option>
                                ))}
                            </select>
                            <ChevronRight className="absolute right-4 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-400 rotate-90 pointer-events-none" />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Tags</label>
                        <input
                            type="text"
                            className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                            placeholder="tech, home, gift (comma separated)"
                            value={formData.tags}
                            onChange={e => setFormData({ ...formData, tags: e.target.value })}
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Description</label>
                        <textarea
                            className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all h-24 resize-none"
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                            placeholder="Add notes about this item..."
                        />
                    </div>

                    <div className="flex justify-end gap-3 mt-8">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-5 py-2.5 text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-zinc-500/20"
                        >
                            Save Item
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function SettingsPage({ theme, toggleTheme }) {
    const [profiles, setProfiles] = useState([]);
    const [newProfile, setNewProfile] = useState({
        name: '',
        apprise_url: '',
        check_interval_minutes: 60,
        notify_on_price_drop: true,
        notify_on_target_price: true,
        price_drop_threshold_percent: 10,
        notify_on_stock_change: true
    });
    const [jobConfig, setJobConfig] = useState({ refresh_interval_minutes: 60, next_run: null, running: false });
    const [aiConfig, setAiConfig] = useState({
        ai_provider: 'ollama',
        ai_model: 'moondream',
        ai_api_key: '',
        ai_api_base: 'http://ollama:11434'
    });
    const [scraperConfig, setScraperConfig] = useState({
        smart_scroll_enabled: false,
        smart_scroll_pixels: 350,
        text_context_enabled: false,
        text_context_length: 5000,
        scraper_timeout: 90000
    });
    const [deleteProfileId, setDeleteProfileId] = useState(null);

    useEffect(() => {
        fetchProfiles();
        fetchJobConfig();
        fetchJobConfig();
        fetchScraperConfig();
        fetchAiConfig();
    }, []);

    const fetchProfiles = async () => {
        try {
            const res = await axios.get(`${API_URL}/notification-profiles`);
            setProfiles(res.data);
        } catch (error) {
            toast.error('Failed to fetch profiles');
        }
    };

    const fetchScraperConfig = async () => {
        try {
            const res = await axios.get(`${API_URL}/settings`);
            const settingsMap = {};
            res.data.forEach(s => settingsMap[s.key] = s.value);

            setScraperConfig({
                smart_scroll_enabled: settingsMap['smart_scroll_enabled'] === 'true',
                smart_scroll_pixels: parseInt(settingsMap['smart_scroll_pixels'] || '350'),
                text_context_enabled: settingsMap['text_context_enabled'] === 'true',
                text_context_length: parseInt(settingsMap['text_context_length'] || '5000'),
                scraper_timeout: parseInt(settingsMap['scraper_timeout'] || '90000')
            });

            setAiConfig({
                ai_provider: settingsMap['ai_provider'] || 'ollama',
                ai_model: settingsMap['ai_model'] || 'moondream',
                ai_api_key: settingsMap['ai_api_key'] || '',
                ai_api_base: settingsMap['ai_api_base'] || 'http://ollama:11434'
            });
        } catch (error) {
            console.error("Failed to fetch settings", error);
        }
    };

    const fetchJobConfig = async () => {
        try {
            const res = await axios.get(`${API_URL}/jobs/config`);
            setJobConfig(res.data);
        } catch (error) {
            console.error("Failed to fetch job config", error);
        }
    };

    const handleUpdateJobConfig = async (e) => {
        e.preventDefault();
        try {
            await axios.post(`${API_URL}/jobs/config`, {
                key: 'refresh_interval_minutes',
                value: jobConfig.refresh_interval_minutes.toString()
            });
            toast.success('Job configuration updated');
            fetchJobConfig();
        } catch (error) {
            toast.error('Failed to update job config');
        }
    };

    const handleUpdateScraperConfig = async (e) => {
        e.preventDefault();
        try {
            await axios.post(`${API_URL}/settings`, { key: 'smart_scroll_enabled', value: scraperConfig.smart_scroll_enabled.toString() });
            await axios.post(`${API_URL}/settings`, { key: 'smart_scroll_pixels', value: scraperConfig.smart_scroll_pixels.toString() });
            await axios.post(`${API_URL}/settings`, { key: 'text_context_enabled', value: scraperConfig.text_context_enabled.toString() });
            await axios.post(`${API_URL}/settings`, { key: 'text_context_length', value: scraperConfig.text_context_length.toString() });
            await axios.post(`${API_URL}/settings`, { key: 'scraper_timeout', value: scraperConfig.scraper_timeout.toString() });
            toast.success('Scraper configuration updated');
        } catch (error) {
            toast.error('Failed to update scraper config');
        }
    };

    const handleUpdateAiConfig = async (e) => {
        e.preventDefault();
        try {
            await axios.post(`${API_URL}/settings`, { key: 'ai_provider', value: aiConfig.ai_provider });
            await axios.post(`${API_URL}/settings`, { key: 'ai_model', value: aiConfig.ai_model });
            await axios.post(`${API_URL}/settings`, { key: 'ai_api_key', value: aiConfig.ai_api_key });
            await axios.post(`${API_URL}/settings`, { key: 'ai_api_base', value: aiConfig.ai_api_base });
            toast.success('AI configuration updated');
        } catch (error) {
            toast.error('Failed to update AI config');
        }
    };

    const handleCreateProfile = async (e) => {
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
            fetchProfiles();
        } catch (error) {
            toast.error('Failed to create profile');
        }
    };

    const handleDeleteProfile = async () => {
        if (!deleteProfileId) return;
        try {
            await axios.delete(`${API_URL}/notification-profiles/${deleteProfileId}`);
            toast.success('Profile deleted');
            fetchProfiles();
            setDeleteProfileId(null);
        } catch (error) {
            toast.error('Failed to delete profile');
        }
    };

    return (
        <div className="space-y-8 max-w-4xl mx-auto animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">Configure application preferences and notifications.</p>
                </div>
            </div>

            {/* Theme Settings */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Sun className="w-5 h-5" /> Appearance
                </h3>
                <div className="flex items-center justify-between">
                    <div>
                        <p className="font-medium">Theme Mode</p>
                        <p className="text-sm text-zinc-500">Toggle between light and dark themes.</p>
                    </div>
                    <button
                        onClick={toggleTheme}
                        className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 ${theme === 'dark' ? 'bg-purple-600' : 'bg-zinc-200'}`}
                    >
                        <span
                            className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${theme === 'dark' ? 'translate-x-6' : 'translate-x-1'}`}
                        />
                    </button>
                </div>
            </div>

            {/* Job Configuration */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                    <Clock className="w-5 h-5" /> Automated Refresh Job
                </h3>
                <form onSubmit={handleUpdateJobConfig} className="flex items-end gap-4">
                    <div>
                        <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Refresh Interval (Minutes)</label>
                        <input
                            type="number"
                            min="1"
                            className="bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none w-40 transition-all"
                            value={jobConfig.refresh_interval_minutes}
                            onChange={e => setJobConfig({ ...jobConfig, refresh_interval_minutes: e.target.value })}
                        />
                    </div>
                    <button type="submit" className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-zinc-500/20 mb-[1px]">
                        Save Config
                    </button>
                </form>
                <div className="mt-4 text-xs text-zinc-500 bg-zinc-50 dark:bg-zinc-950 p-3 rounded-lg inline-block border border-zinc-100 dark:border-zinc-800">
                    <p>Status: <span className={`font-medium ${jobConfig.running ? "text-green-500" : "text-red-500"}`}>{jobConfig.running ? "Running" : "Stopped"}</span></p>
                    {jobConfig.next_run && <p className="mt-1">Next Run: {new Date(jobConfig.next_run).toLocaleString()}</p>}
                </div>
            </div>

            {/* AI Configuration */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                    <span className="text-xl">🤖</span> AI Provider Configuration
                </h3>
                <form onSubmit={handleUpdateAiConfig} className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Provider</label>
                            <div className="relative">
                                <select
                                    className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all appearance-none"
                                    value={aiConfig.ai_provider}
                                    onChange={e => {
                                        const provider = e.target.value;
                                        let model = aiConfig.ai_model;
                                        let base = aiConfig.ai_api_base;

                                        // Set defaults when switching providers
                                        if (provider === 'ollama') {
                                            model = 'moondream';
                                            base = 'http://ollama:11434';
                                        } else if (provider === 'openai') {
                                            model = 'gpt-4o';
                                            base = '';
                                        } else if (provider === 'anthropic') {
                                            model = 'claude-3-5-sonnet-20240620';
                                            base = '';
                                        } else if (provider === 'gemini') {
                                            model = 'gemini-1.5-flash';
                                            base = '';
                                        }

                                        setAiConfig({ ...aiConfig, ai_provider: provider, ai_model: model, ai_api_base: base });
                                    }}
                                >
                                    <option value="ollama">Ollama (Local)</option>
                                    <option value="openai">OpenAI</option>
                                    <option value="anthropic">Anthropic</option>
                                    <option value="gemini">Google Gemini</option>
                                    <option value="custom">Custom / Other</option>
                                </select>
                                <ChevronRight className="absolute right-4 top-1/2 transform -translate-y-1/2 w-4 h-4 text-zinc-400 rotate-90 pointer-events-none" />
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Model Name</label>
                            <input
                                type="text"
                                className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                                value={aiConfig.ai_model}
                                onChange={e => setAiConfig({ ...aiConfig, ai_model: e.target.value })}
                                placeholder="e.g. gpt-4o, moondream"
                            />
                        </div>
                    </div>

                    {aiConfig.ai_provider !== 'ollama' && (
                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">API Key</label>
                            <input
                                type="password"
                                className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                                value={aiConfig.ai_api_key}
                                onChange={e => setAiConfig({ ...aiConfig, ai_api_key: e.target.value })}
                                placeholder="sk-..."
                            />
                        </div>
                    )}

                    {(aiConfig.ai_provider === 'ollama' || aiConfig.ai_provider === 'custom' || aiConfig.ai_provider === 'openai') && (
                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">
                                {aiConfig.ai_provider === 'ollama' ? 'Ollama Base URL' : 'API Base URL (Optional)'}
                            </label>
                            <input
                                type="text"
                                className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                                value={aiConfig.ai_api_base}
                                onChange={e => setAiConfig({ ...aiConfig, ai_api_base: e.target.value })}
                                placeholder="http://localhost:11434"
                            />
                        </div>
                    )}

                    <div className="flex justify-end">
                        <button type="submit" className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-zinc-500/20">
                            Save AI Settings
                        </button>
                    </div>
                </form>
            </div>

            {/* Scraper Configuration */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                    <SettingsIcon className="w-5 h-5" /> Scraper Configuration
                </h3>
                <form onSubmit={handleUpdateScraperConfig} className="space-y-6">
                    <div className="space-y-4">
                        <label className="flex items-start gap-4 cursor-pointer group">
                            <div className="relative flex items-center">
                                <input
                                    type="checkbox"
                                    className="peer sr-only"
                                    checked={scraperConfig.smart_scroll_enabled}
                                    onChange={e => setScraperConfig({ ...scraperConfig, smart_scroll_enabled: e.target.checked })}
                                />
                                <div className="w-11 h-6 bg-zinc-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 dark:peer-focus:ring-purple-800 rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-purple-600"></div>
                            </div>
                            <div>
                                <span className="font-medium block text-zinc-900 dark:text-zinc-100">Enable Smart Scroll</span>
                                <span className="text-sm text-zinc-500">Scroll down 400px before capturing screenshot to reveal hidden content.</span>
                            </div>
                        </label>

                        {scraperConfig.smart_scroll_enabled && (
                            <div className="pl-14 animate-in slide-in-from-top-2 duration-200">
                                <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Scroll Pixels</label>
                                <input
                                    type="number"
                                    min="100"
                                    max="5000"
                                    className="bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none w-40 transition-all"
                                    value={scraperConfig.smart_scroll_pixels}
                                    onChange={e => setScraperConfig({ ...scraperConfig, smart_scroll_pixels: e.target.value })}
                                />
                            </div>
                        )}

                        <label className="flex items-start gap-4 cursor-pointer group">
                            <div className="relative flex items-center">
                                <input
                                    type="checkbox"
                                    className="peer sr-only"
                                    checked={scraperConfig.text_context_enabled}
                                    onChange={e => setScraperConfig({ ...scraperConfig, text_context_enabled: e.target.checked })}
                                />
                                <div className="w-11 h-6 bg-zinc-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 dark:peer-focus:ring-purple-800 rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-purple-600"></div>
                            </div>
                            <div>
                                <span className="font-medium block text-zinc-900 dark:text-zinc-100">Enable Text Context</span>
                                <span className="text-sm text-zinc-500">Extract webpage text and send it to the AI model for better accuracy.</span>
                            </div>
                        </label>

                        {scraperConfig.text_context_enabled && (
                            <div className="pl-14 animate-in slide-in-from-top-2 duration-200">
                                <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Text Context Length</label>
                                <input
                                    type="number"
                                    min="100"
                                    max="20000"
                                    className="bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none w-40 transition-all"
                                    value={scraperConfig.text_context_length}
                                    onChange={e => setScraperConfig({ ...scraperConfig, text_context_length: e.target.value })}
                                />
                            </div>
                        )}

                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Scraper Timeout (ms)</label>
                            <input
                                type="number"
                                min="1000"
                                max="300000"
                                className="bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none w-40 transition-all"
                                value={scraperConfig.scraper_timeout}
                                onChange={e => setScraperConfig({ ...scraperConfig, scraper_timeout: e.target.value })}
                            />
                            <p className="text-xs text-zinc-500 mt-1">Maximum time to wait for a page to load (default: 90000ms).</p>
                        </div>
                    </div>
                    <button type="submit" className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-zinc-500/20">
                        Save Scraper Config
                    </button>
                </form>
            </div>

            {/* Notification Profiles */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                    <Bell className="w-5 h-5" /> Notification Profiles
                </h3>

                <div className="space-y-4 mb-8">
                    {profiles.map(profile => (
                        <div key={profile.id} className="flex items-center justify-between bg-zinc-50 dark:bg-zinc-950 p-4 rounded-xl border border-zinc-100 dark:border-zinc-800">
                            <div>
                                <h3 className="font-medium text-zinc-900 dark:text-zinc-100">{profile.name}</h3>
                                <p className="text-xs text-zinc-500 truncate max-w-md font-mono mt-1">{profile.apprise_url}</p>
                                <div className="flex gap-2 mt-2">
                                    <span className="bg-white dark:bg-zinc-900 px-2 py-0.5 rounded-md border border-zinc-200 dark:border-zinc-800 text-[10px] font-medium text-zinc-500">
                                        {profile.check_interval_minutes}m Interval
                                    </span>
                                    {profile.notify_on_price_drop && (
                                        <span className="bg-green-50 dark:bg-green-900/20 px-2 py-0.5 rounded-md border border-green-200 dark:border-green-900/30 text-[10px] font-medium text-green-600 dark:text-green-400">
                                            Drop &gt;{profile.price_drop_threshold_percent}%
                                        </span>
                                    )}
                                    {profile.notify_on_target_price && (
                                        <span className="bg-purple-50 dark:bg-purple-900/20 px-2 py-0.5 rounded-md border border-purple-200 dark:border-purple-900/30 text-[10px] font-medium text-purple-600 dark:text-purple-400">
                                            Target Price
                                        </span>
                                    )}
                                    {profile.notify_on_stock_change && (
                                        <span className="bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 rounded-md border border-blue-200 dark:border-blue-900/30 text-[10px] font-medium text-blue-600 dark:text-blue-400">
                                            Stock Change
                                        </span>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={() => setDeleteProfileId(profile.id)}
                                className="text-zinc-400 hover:text-red-500 p-2 transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                    {profiles.length === 0 && (
                        <div className="text-center py-8 border-2 border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
                            <p className="text-zinc-500 text-sm">No profiles configured</p>
                        </div>
                    )}
                </div>

                <form onSubmit={handleCreateProfile} className="bg-zinc-50 dark:bg-zinc-950 p-6 rounded-xl border border-zinc-100 dark:border-zinc-800">
                    <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Add New Profile</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <input
                            type="text"
                            placeholder="Profile Name (e.g. 'Discord')"
                            required
                            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                            value={newProfile.name}
                            onChange={e => setNewProfile({ ...newProfile, name: e.target.value })}
                        />
                        <input
                            type="text"
                            placeholder="Apprise URL"
                            required
                            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                            value={newProfile.apprise_url}
                            onChange={e => setNewProfile({ ...newProfile, apprise_url: e.target.value })}
                        />
                        <div>
                            <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Check Interval (Minutes)</label>
                            <input
                                type="number"
                                min="1"
                                className="w-full bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                                value={newProfile.check_interval_minutes}
                                onChange={e => setNewProfile({ ...newProfile, check_interval_minutes: e.target.value })}
                            />
                        </div>
                        <div className="flex flex-col justify-center gap-3">
                            <label className="flex items-center gap-3 text-sm text-zinc-600 dark:text-zinc-300 cursor-pointer">
                                <div className="relative flex items-center">
                                    <input
                                        type="checkbox"
                                        className="peer sr-only"
                                        checked={newProfile.notify_on_price_drop}
                                        onChange={e => setNewProfile({ ...newProfile, notify_on_price_drop: e.target.checked })}
                                    />
                                    <div className="w-9 h-5 bg-zinc-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-purple-600"></div>
                                </div>
                                Notify on Price Drop
                            </label>

                            {newProfile.notify_on_price_drop && (
                                <div className="pl-12 animate-in slide-in-from-top-2 duration-200">
                                    <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Threshold (%)</label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="100"
                                        className="w-24 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all"
                                        value={newProfile.price_drop_threshold_percent}
                                        onChange={e => setNewProfile({ ...newProfile, price_drop_threshold_percent: e.target.value })}
                                    />
                                </div>
                            )}

                            <label className="flex items-center gap-3 text-sm text-zinc-600 dark:text-zinc-300 cursor-pointer">
                                <div className="relative flex items-center">
                                    <input
                                        type="checkbox"
                                        className="peer sr-only"
                                        checked={newProfile.notify_on_target_price}
                                        onChange={e => setNewProfile({ ...newProfile, notify_on_target_price: e.target.checked })}
                                    />
                                    <div className="w-9 h-5 bg-zinc-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-purple-600"></div>
                                </div>
                                Notify on Target Price
                            </label>

                            <label className="flex items-center gap-3 text-sm text-zinc-600 dark:text-zinc-300 cursor-pointer">
                                <div className="relative flex items-center">
                                    <input
                                        type="checkbox"
                                        className="peer sr-only"
                                        checked={newProfile.notify_on_stock_change}
                                        onChange={e => setNewProfile({ ...newProfile, notify_on_stock_change: e.target.checked })}
                                    />
                                    <div className="w-9 h-5 bg-zinc-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-purple-600"></div>
                                </div>
                                Notify on Stock Change
                            </label>
                        </div>
                    </div>
                    <button type="submit" className="mt-6 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-zinc-500/20 w-full md:w-auto">
                        Add Profile
                    </button>
                </form>
            </div>

            {/* Delete Confirmation Modal */}
            {deleteProfileId && (
                <div className="fixed inset-0 bg-black/20 dark:bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
                    <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 w-full max-w-sm border border-zinc-200 dark:border-zinc-800 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4 text-red-500">
                            <div className="p-2 bg-red-50 dark:bg-red-900/20 rounded-full">
                                <AlertTriangle className="w-5 h-5" />
                            </div>
                            <h3 className="text-lg font-bold tracking-tight">Delete Profile?</h3>
                        </div>
                        <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm leading-relaxed">Are you sure you want to delete this notification profile? This action cannot be undone.</p>
                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => setDeleteProfileId(null)}
                                className="px-4 py-2 text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDeleteProfile}
                                className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-xl text-sm font-medium transition-all shadow-lg shadow-red-500/20"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function DeleteConfirmationModal({ item, onClose, onConfirm }) {
    return (
        <div className="fixed inset-0 bg-black/20 dark:bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 w-full max-w-sm border border-zinc-200 dark:border-zinc-800 shadow-2xl">
                <div className="flex flex-col items-center text-center mb-6">
                    <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-4 text-red-600 dark:text-red-400">
                        <Trash2 className="w-6 h-6" />
                    </div>
                    <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Delete Item?</h3>
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-2">
                        Are you sure you want to delete <span className="font-medium text-zinc-900 dark:text-zinc-100">{item.name}</span>? This action cannot be undone.
                    </p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2.5 text-sm font-medium text-zinc-700 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-xl transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-xl transition-colors shadow-lg shadow-red-500/20"
                    >
                        Delete
                    </button>
                </div>
            </div>
        </div>
    );
}

export default App
