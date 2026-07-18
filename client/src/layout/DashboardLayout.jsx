import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import NotificationMenu from '../components/NotificationMenu';
import ResponsiveNavbar from '../components/layout/ResponsiveNavbar';
import ResponsiveSidebar from '../components/layout/ResponsiveSidebar';
import Card from '../components/ui/Card';
import SearchBar from '../components/ui/SearchBar';
import { apiFetch } from '../config/api';
import LifelinkAiChat from '../components/LifelinkAiChat';
import DataModeToggle from '../components/ui/DataModeToggle';

import ProfileModal from '../components/ProfileModal';
import HospitalProfileModal from '../components/HospitalProfileModal';
import GovernmentProfileModal from '../components/GovernmentProfileModal';

const DashboardLayout = ({ children, sidebarItems = [], activeItem, onSelect, onRefresh, refreshLabel = 'Refresh' }) => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const [hasUnread, setHasUnread] = useState(false);

    const [searchMode] = useState('db');
    const [searchQuery, setSearchQuery] = useState('');
    const [searchLoading, setSearchLoading] = useState(false);
    const [searchResult, setSearchResult] = useState(null);
    const [searchError, setSearchError] = useState('');
    const searchCacheRef = useRef(new Map());
    const searchCacheTtlMs = 300000;
    const [searchLocation, setSearchLocation] = useState(null);

    const readStoredSearchCache = () => {
        try {
            const key = user?.id ? `lifelink:search-cache:${user.id}` : 'lifelink:search-cache:guest';
            const stored = localStorage.getItem(key);
            return stored ? JSON.parse(stored) : {};
        } catch (err) {
            return {};
        }
    };

    const writeStoredSearchCache = (cache) => {
        try {
            const key = user?.id ? `lifelink:search-cache:${user.id}` : 'lifelink:search-cache:guest';
            localStorage.setItem(key, JSON.stringify(cache));
        } catch (err) {
            // ignore storage failures
        }
    };

    const [isDrawerOpen, setIsDrawerOpen] = useState(false);
    const [isMobileSearchOpen, setIsMobileSearchOpen] = useState(false);
    const [isAiPanelOpen, setIsAiPanelOpen] = useState(false);

    useEffect(() => {
        const checkUnread = async () => {
            if (!user?.id) return;
            try {
                const res = await apiFetch(`/api/dashboard/public/${user.id}/full`, { method: 'GET', ttlMs: 30000 });
                const data = res.data || {};
                const readKey = user?.id ? `lifelink:lastReadTime:${user.id}` : 'lifelink:lastReadTime';
                const lastRead = localStorage.getItem(readKey);
                const lastReadDate = lastRead ? new Date(lastRead) : new Date(0);
                const allItems = [...(data.alerts || []), ...(data.resourceRequests || [])];
                const hasNew = allItems.some(item => new Date(item.createdAt) > lastReadDate);
                setHasUnread(hasNew);
            } catch (err) {
                console.error(err);
            }
        };
        if (user?.role !== 'government') checkUnread();
    }, [user?.id, user?.role]);

    useEffect(() => {
        if (typeof navigator === 'undefined' || !navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
            (pos) => setSearchLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
            () => setSearchLocation(null),
            { enableHighAccuracy: true }
        );
    }, []);

    const handleLogout = () => {
        logout();
        navigate('/');
    };

    const handleSelect = (key) => {
        onSelect?.(key);
        setIsDrawerOpen(false);
    };

    const handleProfile = () => handleSelect('profile');
    const handleNotifications = () => handleSelect('notifications');

    const handleSwitchRole = () => {
        const role = user?.role?.toLowerCase();
        if (!role) return;
        const isDemo = localStorage.getItem('lifelink_data_mode') === 'demo';

        if (isDemo) {
            navigate(`/demo/role/${role}`);
            return;
        }

        if (role === 'hospital') {
            navigate('/dashboard/hospital/roles?switch=1', { replace: true });
            return;
        }
        if (role === 'government') {
            navigate('/dashboard/government/roles?switch=1', { replace: true });
            return;
        }
        if (role === 'ambulance') {
            navigate('/dashboard/ambulance/roles?switch=1', { replace: true });
            return;
        }
    };

    const renderProfilePanel = () => {
        switch (user?.role) {
            case 'hospital':
                return <HospitalProfileModal variant="panel" />;
            case 'government':
                return <GovernmentProfileModal variant="panel" />;
            case 'public':
            default:
                return <ProfileModal variant="panel" />;
        }
    };

    const handleSearch = async () => {
        const trimmed = searchQuery.trim();
        if (!trimmed) return;
        const cacheKey = `${searchMode}:${trimmed.toLowerCase()}`;
        const cached = searchCacheRef.current.get(cacheKey);
        if (cached && Date.now() - cached.timestamp < searchCacheTtlMs) {
            setSearchResult(cached.result);
            setSearchError('');
            return;
        }
        if (typeof navigator !== 'undefined' && navigator.onLine === false) {
            const offlineCache = readStoredSearchCache();
            const offlineMatch = offlineCache[cacheKey];
            if (offlineMatch) {
                setSearchResult({ ...offlineMatch, offline: true });
                setSearchError('');
                return;
            }
            if (searchMode === 'db') {
                const entries = Object.values(offlineCache).filter((item) => item?.mode === 'db');
                const aggregate = { users: [], alerts: [], ambulances: [], hospitals: [] };
                entries.forEach((entry) => {
                    const results = entry?.data?.results || {};
                    Object.keys(aggregate).forEach((key) => {
                        const items = Array.isArray(results[key]) ? results[key] : [];
                        aggregate[key] = aggregate[key].concat(items);
                    });
                });
                const term = trimmed.toLowerCase();
                const filterItems = (items) => items.filter((item) => JSON.stringify(item).toLowerCase().includes(term)).slice(0, 5);
                setSearchResult({
                    mode: 'db',
                    offline: true,
                    data: {
                        query: trimmed,
                        results: {
                            users: filterItems(aggregate.users),
                            alerts: filterItems(aggregate.alerts),
                            ambulances: filterItems(aggregate.ambulances),
                            hospitals: filterItems(aggregate.hospitals),
                        }
                    }
                });
                setSearchError('');
                return;
            }
            const aiFallback = {
                mode: 'ai',
                offline: true,
                data: {
                    answer: 'Offline mode: cached intelligence is unavailable. Reconnect to ask LifeLink AI.'
                }
            };
            setSearchResult(aiFallback);
            setSearchError('');
            return;
        }
        setSearchLoading(true);
        setSearchError('');
        setSearchResult(null);
        try {
            const path = '/v2/search';
            const payload = { query: trimmed };
            const { ok, data, status } = await apiFetch(path, {
                method: 'POST',
                body: JSON.stringify(payload),
                timeoutMs: 20000,
            });
            if (!ok) {
                const message = data.detail || data.error || `Search failed (${status})`;
                setSearchError(message);
            } else {
                const result = { mode: 'db', data };
                setSearchResult(result);
                searchCacheRef.current.set(cacheKey, { timestamp: Date.now(), result });
                const stored = readStoredSearchCache();
                stored[cacheKey] = result;
                writeStoredSearchCache(stored);
            }
        } catch (err) {
            const message = err?.name === 'AbortError' || /aborted/i.test(err?.message || '')
                ? 'Search timed out. Try again with a shorter query.'
                : (err.message || 'Search failed');
            setSearchError(message);
        } finally {
            setSearchLoading(false);
        }
    };

    const renderSearchResults = () => {
        if (!searchResult && !searchError) return null;
        return (
            <Card className="mb-6">
                <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                        Database Results
                    </p>
                    {searchResult?.offline && (
                        <span className="text-[10px] text-amber-600 font-semibold uppercase">Offline cache</span>
                    )}
                    <button
                        className="text-xs text-slate-400 hover:text-slate-600"
                        onClick={() => {
                            setSearchResult(null);
                            setSearchError('');
                        }}
                    >
                        Clear
                    </button>
                </div>
                {searchError && (
                    <p className="text-sm text-red-600">{searchError}</p>
                )}
                {searchResult?.mode === 'ai' && (
                    <div>
                        <p className="text-sm text-slate-700 whitespace-pre-line">{searchResult.data.answer}</p>
                        {searchResult.data.contextUsed?.length > 0 && (
                            <div className="mt-4 space-y-2">
                                {searchResult.data.contextUsed.map((item, idx) => (
                                    <div key={idx} className="p-3 bg-slate-50 rounded-xl text-xs text-slate-600">
                                        {item.content}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
                {searchResult?.mode === 'db' && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                        {Object.entries(searchResult.data.results || {}).map(([key, items]) => (
                            <div key={key}>
                                <p className="font-semibold text-slate-700 mb-2 capitalize">{key}</p>
                                {items?.length ? (
                                    items.map((item) => (
                                        <div key={item._id} className="p-2 bg-slate-50 rounded-lg mb-2">
                                            <p className="text-slate-700 font-medium">{item.name || item.message || item.ambulanceId || 'Record'}</p>
                                            <p className="text-xs text-slate-500">
                                                {item.email
                                                    || (typeof item.location === 'string'
                                                        ? item.location
                                                        : item.location?.city || item.location?.address || '')
                                                    || item.registrationNumber
                                                    || ''}
                                            </p>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-xs text-slate-400">No matches</p>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </Card>
        );
    };

    const isNotificationsTab = activeItem === 'notifications';
    const isProfileTab = activeItem === 'profile';
    const allowSwitchRole = ['hospital', 'government'].includes(String(user?.role || '').toLowerCase());
    const subtitle = user?.role ? `${user.role} portal${user?.subRole ? ` • ${user.subRole}` : ''}` : 'Portal';

    return (
        <div className="gradient-background-universal min-h-screen">
            <div className="flex flex-col lg:flex-row min-h-screen lg:h-screen lg:overflow-hidden">
                <ResponsiveSidebar
                    isOpen={isDrawerOpen}
                    onClose={() => setIsDrawerOpen(false)}
                    user={user}
                    items={sidebarItems}
                    activeKey={activeItem}
                    onSelect={handleSelect}
                    onLogoClick={() => {
                        setIsDrawerOpen(false);
                        navigate('/');
                    }}
                    onLogout={handleLogout}
                    onSwitchRole={allowSwitchRole ? handleSwitchRole : null}
                    onProfile={handleProfile}
                    onNotifications={handleNotifications}
                    hasUnread={hasUnread}
                />
                <div className="relative flex-1 min-w-0">
                    <main className={`flex-1 min-w-0 flex flex-col lg:h-screen transition-all duration-300 ${isAiPanelOpen ? 'lg:mr-[360px]' : ''}`}>
                        <ResponsiveNavbar
                            title="LifeLink"
                            subtitle={subtitle}
                            onLogoClick={() => navigate('/')}
                            onMenuClick={() => setIsDrawerOpen(true)}
                            onSearchToggle={() => setIsMobileSearchOpen((prev) => !prev)}
                            isSearchOpen={isMobileSearchOpen}
                        />

                        {isMobileSearchOpen && (
                            <div className="lg:hidden bg-white/95 backdrop-blur border-b border-slate-200 px-4 pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex-1 min-w-0">
                                        <SearchBar
                                            mode="db"
                                            showModeToggle={false}
                                            query={searchQuery}
                                            onQueryChange={setSearchQuery}
                                            onSubmit={handleSearch}
                                            loading={searchLoading}
                                        />
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setIsAiPanelOpen((prev) => !prev)}
                                        className="text-xs font-semibold bg-white text-slate-700 border border-slate-200 px-3 py-2 rounded-lg hover:bg-slate-50 shrink-0 flex items-center gap-2"
                                    >
                                        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 text-white text-[10px]">
                                            <i className="fas fa-heartbeat"></i>
                                        </span>
                                        LifeLink AI
                                    </button>
                                    <DataModeToggle size="sm" />
                                    {onRefresh && (
                                        <button
                                            type="button"
                                            onClick={onRefresh}
                                            className="text-xs font-semibold bg-slate-900 text-white px-3 py-2 rounded-lg hover:bg-slate-800 shrink-0"
                                        >
                                            {refreshLabel}
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="hidden lg:block sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-slate-200 shrink-0">
                            <div className="px-6 sm:px-8 py-4">
                                <div className="flex items-center gap-3">
                                    <div className="flex-1 min-w-0">
                                        <SearchBar
                                            mode="db"
                                            showModeToggle={false}
                                            query={searchQuery}
                                            onQueryChange={setSearchQuery}
                                            onSubmit={handleSearch}
                                            loading={searchLoading}
                                        />
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setIsAiPanelOpen((prev) => !prev)}
                                        className="text-xs font-semibold bg-white text-slate-700 border border-slate-200 px-3 py-2 rounded-lg hover:bg-slate-50 shrink-0 flex items-center gap-2"
                                    >
                                        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 text-white text-[10px]">
                                            <i className="fas fa-heartbeat"></i>
                                        </span>
                                        LifeLink AI
                                    </button>
                                    <DataModeToggle size="sm" />
                                    {onRefresh && (
                                        <button
                                            type="button"
                                            onClick={onRefresh}
                                            className="text-xs font-semibold bg-slate-900 text-white px-3 py-2 rounded-lg hover:bg-slate-800 shrink-0"
                                        >
                                            {refreshLabel}
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                        <div className="flex-1 px-4 sm:px-6 lg:px-8 py-6 lg:py-8 lg:overflow-y-auto">
                            {isNotificationsTab ? (
                                <div className="w-full">
                                    <NotificationMenu variant="panel" onMarkRead={() => setHasUnread(false)} />
                                </div>
                            ) : isProfileTab ? (
                                <div className="w-full">
                                    {renderProfilePanel()}
                                </div>
                            ) : (
                                <>
                                    {renderSearchResults()}
                                    {children}
                                </>
                            )}
                        </div>
                    </main>
                    <aside
                        className={`hidden lg:flex flex-col absolute right-0 top-0 h-full w-[360px] bg-white/95 backdrop-blur border-l border-slate-200 shadow-xl transition-transform duration-300 ${isAiPanelOpen ? 'translate-x-0' : 'translate-x-full'}`}
                    >
                        <div className="p-4 h-full">
                            <LifelinkAiChat
                                variant="panel"
                                onClose={() => setIsAiPanelOpen(false)}
                                location={searchLocation}
                                moduleKey={activeItem || 'dashboard'}
                            />
                        </div>
                    </aside>
                </div>
            </div>
            {isAiPanelOpen && (
                <div className="lg:hidden fixed inset-0 z-50 bg-slate-900/30">
                    <div className="absolute right-0 top-0 h-full w-full sm:max-w-md bg-white shadow-2xl p-4">
                        <LifelinkAiChat
                            variant="panel"
                            onClose={() => setIsAiPanelOpen(false)}
                            location={searchLocation}
                        />
                    </div>
                </div>
            )}
        </div>
    );
};

export default DashboardLayout;