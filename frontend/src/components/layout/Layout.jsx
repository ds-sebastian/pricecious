import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Settings, Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const Layout = ({ children, theme, toggleTheme }) => {
    const location = useLocation();

    const navItems = [
        { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
        { icon: Settings, label: 'Settings', path: '/settings' },
    ];

    return (
        <div className="min-h-screen bg-background font-sans antialiased">
            {/* Sidebar */}
            <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r bg-card hidden md:block">
                <div className="flex h-full flex-col">
                    <div className="flex h-14 items-center border-b px-6">
                        <Link to="/" className="flex items-center gap-2 font-semibold">
                            <span className="text-xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
                                Pricecious
                            </span>
                        </Link>
                    </div>
                    <nav className="flex-1 space-y-1 p-4">
                        {navItems.map((item) => {
                            const Icon = item.icon;
                            const isActive = location.pathname === item.path;
                            return (
                                <Link key={item.path} to={item.path}>
                                    <Button
                                        variant={isActive ? "secondary" : "ghost"}
                                        className={cn("w-full justify-start gap-2", isActive && "bg-secondary")}
                                    >
                                        <Icon className="h-4 w-4" />
                                        {item.label}
                                    </Button>
                                </Link>
                            );
                        })}
                    </nav>
                    <div className="border-t p-4">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={toggleTheme}
                            className="w-full justify-start gap-2 px-4"
                        >
                            {theme === 'dark' ? (
                                <>
                                    <Sun className="h-4 w-4" />
                                    <span>Light Mode</span>
                                </>
                            ) : (
                                <>
                                    <Moon className="h-4 w-4" />
                                    <span>Dark Mode</span>
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </aside>

            {/* Mobile Header */}
            <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background px-6 md:hidden">
                <Link to="/" className="font-semibold">
                    Pricecious
                </Link>
                <div className="ml-auto flex items-center gap-2">
                    <Button variant="ghost" size="icon" onClick={toggleTheme}>
                        {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                    </Button>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 md:pl-64">
                <div className="container py-6">
                    {children}
                </div>
            </main>
        </div>
    );
};

export default Layout;
