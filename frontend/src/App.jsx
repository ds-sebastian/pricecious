import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import Settings from '@/pages/Settings'
import { useTheme } from '@/hooks/use-theme'

export default function App() {
    const { theme, toggleTheme } = useTheme();

    return (
        <Router>
            <Toaster position="bottom-right" theme={theme} />
            <Layout theme={theme} toggleTheme={toggleTheme}>
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/settings" element={<Settings />} />
                </Routes>
            </Layout>
        </Router>
    );
}
