import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { AISettings } from '@/components/settings/AISettings';
import { ScraperSettings } from '@/components/settings/ScraperSettings';
import { JobSettings } from '@/components/settings/JobSettings';
import { ProfileSettings } from '@/components/settings/ProfileSettings';

const API_URL = '/api';

export default function Settings() {
    const [profiles, setProfiles] = useState([]);
    const [jobConfig, setJobConfig] = useState({ refresh_interval_minutes: 60, next_run: null, running: false });
    const [aiConfig, setAiConfig] = useState({
        ai_provider: 'ollama',
        ai_model: 'moondream',
        ai_api_key: '',
        ai_api_base: 'http://ollama:11434'
    });
    const [aiAdvancedConfig, setAiAdvancedConfig] = useState({
        ai_temperature: 0.1,
        ai_max_tokens: 300,
        confidence_threshold_price: 0.5,
        confidence_threshold_stock: 0.5,
        enable_json_repair: true
    });
    const [scraperConfig, setScraperConfig] = useState({
        smart_scroll_enabled: false,
        smart_scroll_pixels: 350,
        text_context_enabled: false,
        text_context_length: 5000,
        scraper_timeout: 90000
    });

    useEffect(() => {
        fetchProfiles();
        fetchJobConfig();
        fetchScraperConfig();
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

            setAiAdvancedConfig({
                ai_temperature: parseFloat(settingsMap['ai_temperature'] || '0.1'),
                ai_max_tokens: parseInt(settingsMap['ai_max_tokens'] || '300'),
                confidence_threshold_price: parseFloat(settingsMap['confidence_threshold_price'] || '0.5'),
                confidence_threshold_stock: parseFloat(settingsMap['confidence_threshold_stock'] || '0.5'),
                enable_json_repair: settingsMap['enable_json_repair'] !== 'false'
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

    const handleUpdateScraperConfig = async (e, key) => {
        if (e && e.preventDefault) e.preventDefault();
        const value = e.target.value;
        const newConfig = { ...scraperConfig, [key]: value };
        setScraperConfig(newConfig);

        try {
            await axios.post(`${API_URL}/settings`, { key, value: value.toString() });
            toast.success('Scraper configuration updated');
        } catch (error) {
            toast.error('Failed to update scraper config');
        }
    };

    const handleUpdateAiConfig = async (e, key) => {
        if (e && e.preventDefault) e.preventDefault();
        const value = e.target.value;
        const newConfig = { ...aiConfig, [key]: value };
        setAiConfig(newConfig);

        try {
            await axios.post(`${API_URL}/settings`, { key, value: value.toString() });
            toast.success('AI configuration updated');
        } catch (error) {
            toast.error('Failed to update AI config');
        }
    };

    const handleUpdateAiAdvancedConfig = async (e, key) => {
        if (e && e.preventDefault) e.preventDefault();
        const value = e.target.value;
        const newConfig = { ...aiAdvancedConfig, [key]: value };
        setAiAdvancedConfig(newConfig);

        try {
            await axios.post(`${API_URL}/settings`, { key, value: value.toString() });
            toast.success('AI Advanced settings updated');
        } catch (error) {
            toast.error('Failed to update AI advanced config');
        }
    };

    const handleCreateProfile = async (profile) => {
        try {
            await axios.post(`${API_URL}/notification-profiles`, profile);
            toast.success('Profile created');
            fetchProfiles();
        } catch (error) {
            toast.error('Failed to create profile');
        }
    };

    const handleDeleteProfile = async (id) => {
        try {
            await axios.delete(`${API_URL}/notification-profiles/${id}`);
            toast.success('Profile deleted');
            fetchProfiles();
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

            <div className="grid gap-6">
                <AISettings
                    config={aiConfig}
                    advancedConfig={aiAdvancedConfig}
                    onUpdateConfig={handleUpdateAiConfig}
                    onUpdateAdvancedConfig={handleUpdateAiAdvancedConfig}
                />

                <ScraperSettings
                    config={scraperConfig}
                    onUpdate={handleUpdateScraperConfig}
                />

                <JobSettings
                    config={jobConfig}
                    onUpdate={handleUpdateJobConfig}
                />

                <ProfileSettings
                    profiles={profiles}
                    onCreate={handleCreateProfile}
                    onDelete={handleDeleteProfile}
                />
            </div>
        </div>
    );
}
