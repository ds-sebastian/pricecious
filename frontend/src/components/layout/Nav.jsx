import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Settings, LineChart } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
    { icon: LineChart, label: 'Analytics', path: '/analytics' },
    { icon: Settings, label: 'Settings', path: '/settings' },
];

export function Nav({ onItemClick }) {
    const location = useLocation();

    return (
        <nav className="flex-1 space-y-1 p-4">
            {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                    <Link key={item.path} to={item.path} onClick={onItemClick}>
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
    );
}
