import React, { useEffect, useMemo, useState, Suspense } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDataMode } from '../context/DataModeContext';
import DashboardLayout from '../layout/DashboardLayout';
import { DashboardCard, LoadingSpinner } from '../components/Common';
import { API_BASE_URL, apiFetch, getAuthToken } from '../config/api';
import AIExpansionPanel from '../components/AIExpansionPanel';
import DashboardGrid from '../components/layout/DashboardGrid';
import MobileDrawer from '../components/layout/MobileDrawer';
import LifelinkAiChat from '../components/LifelinkAiChat';
import NotificationMenu from '../components/NotificationMenu';
import GovernmentProfileModal from '../components/GovernmentProfileModal';

// Direct Imports for Stability
import {
    GovernmentAIMLHub,
    GovernmentCommandCenter,
    GovernmentDisasterCenter,
    GovernmentLiveMonitoring,
    GovernmentPolicyWorkflow,
    GovernmentSimulationCenter,
    GovernmentVerificationCenter,
} from '../components/GovernmentCommandModules';

const buildGovernmentModuleSet = (subRole) => ({
    national_admin: [
        { key: 'command-center', label: 'Command Center', icon: 'fa-tower-broadcast', render: () => <GovernmentCommandCenter /> },
        { key: 'live-monitoring', label: 'Live Monitoring', icon: 'fa-signal', render: () => <GovernmentLiveMonitoring /> },
        { key: 'disaster-management', label: 'Disaster Management', icon: 'fa-triangle-exclamation', render: () => <GovernmentDisasterCenter /> },
        { key: 'policy-workflow', label: 'Policy Workflow', icon: 'fa-clipboard-check', render: () => <GovernmentPolicyWorkflow /> },
        { key: 'verification-center', label: 'Verification Center', icon: 'fa-shield-check', render: () => <GovernmentVerificationCenter subRole={subRole} /> },
        { key: 'simulation-center', label: 'Simulation & Recovery', icon: 'fa-atom', render: () => <GovernmentSimulationCenter /> },
        { key: 'ai-ml-lab', label: 'AI/ML Lab', icon: 'fa-robot', render: () => <GovernmentAIMLHub /> },
    ],
    state_admin: [
        { key: 'command-center', label: 'Command Center', icon: 'fa-tower-broadcast', render: () => <GovernmentCommandCenter /> },
        { key: 'live-monitoring', label: 'Live Monitoring', icon: 'fa-signal', render: () => <GovernmentLiveMonitoring /> },
        { key: 'disaster-management', label: 'Disaster Management', icon: 'fa-triangle-exclamation', render: () => <GovernmentDisasterCenter /> },
        { key: 'policy-workflow', label: 'Policy Workflow', icon: 'fa-clipboard-check', render: () => <GovernmentPolicyWorkflow /> },
        { key: 'verification-center', label: 'Verification Center', icon: 'fa-shield-check', render: () => <GovernmentVerificationCenter subRole={subRole} /> },
        { key: 'simulation-center', label: 'Simulation & Recovery', icon: 'fa-atom', render: () => <GovernmentSimulationCenter /> },
        { key: 'ai-ml-lab', label: 'AI/ML Lab', icon: 'fa-robot', render: () => <GovernmentAIMLHub /> },
    ],
    district_admin: [
        { key: 'live-monitoring', label: 'Live Monitoring', icon: 'fa-signal', render: () => <GovernmentLiveMonitoring /> },
        { key: 'disaster-management', label: 'Disaster Management', icon: 'fa-triangle-exclamation', render: () => <GovernmentDisasterCenter /> },
        { key: 'verification-center', label: 'Verification Center', icon: 'fa-shield-check', render: () => <GovernmentVerificationCenter subRole={subRole} /> },
        { key: 'simulation-center', label: 'Simulation & Recovery', icon: 'fa-atom', render: () => <GovernmentSimulationCenter /> },
    ],
    supervisory_authority: [
        { key: 'policy-workflow', label: 'Policy Workflow', icon: 'fa-clipboard-check', render: () => <GovernmentPolicyWorkflow /> },
        { key: 'verification-center', label: 'Verification Center', icon: 'fa-shield-check', render: () => <GovernmentVerificationCenter subRole={subRole} /> },
        { key: 'live-monitoring', label: 'Live Monitoring', icon: 'fa-signal', render: () => <GovernmentLiveMonitoring /> },
    ],
    default: [
        { key: 'command-center', label: 'Command Center', icon: 'fa-tower-broadcast', render: () => <GovernmentCommandCenter /> },
    ],
});

const useIsDesktop = () => {
    const getMatches = () => {
        if (typeof window === 'undefined' || !window.matchMedia) return false;
        return window.matchMedia('(min-width: 1024px)').matches;
    };

    const [isDesktop, setIsDesktop] = useState(getMatches);

    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return undefined;
        const media = window.matchMedia('(min-width: 1024px)');
        const handler = (event) => setIsDesktop(event.matches);
        media.addEventListener?.('change', handler);
        setIsDesktop(media.matches);
        return () => media.removeEventListener?.('change', handler);
    }, []);

    return isDesktop;
};

const DesktopGovernmentDashboard = () => {
    const { user } = useAuth();
    const { mode } = useDataMode();
    const navigate = useNavigate();
    const { module } = useParams();
    const [activeTab, setActiveTab] = useState('');
    const [refreshKeys, setRefreshKeys] = useState({});
    const [stats, setStats] = useState({ pending: 0, emergencies: 0, utilization: 0 });

    const subRole = user?.subRole?.toLowerCase();
    const moduleSet = useMemo(() => {
        const sets = buildGovernmentModuleSet(subRole);
        return sets[subRole] || sets.default;
    }, [subRole]);
    const allowedTabs = useMemo(() => moduleSet.map((item) => item.key), [moduleSet]);
    const defaultTab = allowedTabs[0] || 'overview';
    const moduleKey = (module || defaultTab).toLowerCase();

    useEffect(() => {
        if (user?.role === 'government' && !user?.subRole) {
            navigate('/dashboard/government/roles');
        }
    }, [user?.role, user?.subRole, navigate]);

    useEffect(() => {
        if (!module) {
            navigate(`/dashboard/government/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        if (!allowedTabs.includes(moduleKey)) {
            navigate(`/dashboard/government/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        setActiveTab(moduleKey);
    }, [module, moduleKey, allowedTabs, defaultTab, navigate]);

    const handleSelect = (key) => {
        if (key === 'profile' || key === 'notifications') {
            setActiveTab(key);
            return;
        }
        navigate(`/dashboard/government/${key}`);
    };

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const summaryRes = await apiFetch('/v2/government/monitoring/summary', { method: 'GET' });
                const summary = summaryRes.ok ? summaryRes.data : null;
                let pending = 0;
                if ((subRole || '').toLowerCase() === 'district_admin') {
                    const pendingRes = await apiFetch('/v2/government/verification/pending', { method: 'GET' });
                    pending = pendingRes.ok ? (pendingRes.data?.data || []).length : 0;
                }
                setStats({
                    pending,
                    emergencies: summary?.active_emergencies || 0,
                    utilization: summary?.resource_utilization || 0,
                });
            } catch (err) {
                console.error("Stats Fetch Error:", err);
            }
        };
        fetchStats();
    }, [subRole]);

    useEffect(() => {
        if (user?.role !== 'government') return;
        if (mode !== 'real') return;
        const token = getAuthToken();
        if (!token) {
            navigate('/login', { replace: true });
            return;
        }
        const preloadKey = `gov_preload_done_${mode}_${subRole || 'default'}`;
        if (sessionStorage.getItem(preloadKey)) return;
        sessionStorage.setItem(preloadKey, '1');

        const paramsFor = (moduleKey) => {
            const params = new URLSearchParams({ role: 'government', module_key: moduleKey });
            if (subRole) params.set('sub_role', subRole);
            return params.toString();
        };

        const moduleKeys = moduleSet.map((item) => item.key);
        const insightCalls = moduleKeys.map((moduleKey) =>
            apiFetch(`/v2/ai/insights?${paramsFor(moduleKey)}`, {
                method: 'GET',
                ttlMs: 60000,
                staleWhileRevalidate: true,
            })
        );

        const commandCalls = [
            apiFetch('/v2/government/command/overview', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/decision/engine', { method: 'POST' }),
            apiFetch('/v2/government/predictions/anomaly', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/monitoring/summary', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/monitoring/feed?limit=60&window_minutes=120', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/resources/hospitals?limit=120', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/resources/ambulances?limit=120', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/verification/pending', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/policy/actions?limit=36', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
        ];

        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };

        const aiPreloads = [
            {
                key: 'gov_preload_outbreak',
                path: '/api/gov/predict_outbreak',
                body: { disease_name: 'Influenza', region: 'Central City', days_to_predict: 30 },
            },
            {
                key: 'gov_preload_allocation',
                path: '/api/gov/predict_allocation',
                body: { emergency_count: 5, hospital_capacity_percent: 65 },
            },
            {
                key: 'gov_preload_policy_segment',
                path: '/api/gov/predict_policy_segment',
                body: { emergency_rate: 10.2, avg_response_time: 15.5, hospital_bed_occupancy: 85.0 },
            },
            {
                key: 'gov_preload_policy_performance',
                path: '/api/gov/predict_performance_score',
                body: { emergency_rate: 10.2, avg_response_time: 15.5, hospital_bed_occupancy: 85.0 },
            },
            {
                key: 'gov_preload_availability',
                path: '/api/gov/predict_availability',
                body: { region: 'Central', month: 11, resource_type: 'Blood O+', donation_frequency: 150, hospital_stock_level: 75 },
            },
        ];

        Promise.allSettled(insightCalls.concat(commandCalls));
        Promise.allSettled(commandCalls).then((results) => {
            const [overviewRes, decisionRes, anomalyRes, summaryRes, feedRes, hospitalsRes, ambulancesRes, pendingRes, policyRes] = results.map((item) =>
                item.status === 'fulfilled' ? item.value : null
            );
            if (overviewRes?.ok && decisionRes?.ok && anomalyRes?.ok) {
                localStorage.setItem('gov_command_cache', JSON.stringify({
                    overview: overviewRes.data,
                    decisions: decisionRes.data?.decisions || [],
                    anomaly: anomalyRes.data?.prediction || null,
                }));
            }
            if (summaryRes?.ok && feedRes?.ok && hospitalsRes?.ok) {
                localStorage.setItem('gov_live_cache', JSON.stringify({
                    summary: summaryRes.data,
                    feed: feedRes.data?.data || [],
                    hospitals: hospitalsRes.data?.data || [],
                }));
            }
            if (hospitalsRes?.ok && ambulancesRes?.ok) {
                localStorage.setItem('gov_verification_cache', JSON.stringify({
                    hospitals: hospitalsRes.data?.data || [],
                    ambulances: ambulancesRes.data?.data || [],
                    pending: pendingRes?.ok ? (pendingRes.data?.data || []) : [],
                }));
            }
            if (policyRes?.ok) {
                sessionStorage.setItem('gov_policy_cache', JSON.stringify({
                    decisions: decisionRes?.ok ? (decisionRes.data?.decisions || []) : [],
                    anomaly: anomalyRes?.ok ? anomalyRes.data?.prediction : null,
                    policyActions: policyRes.data?.data || [],
                }));
            }
        });
        Promise.allSettled(
            aiPreloads.map(async (item) => {
                try {
                    const res = await fetch(`${API_BASE_URL}${item.path}`, {
                        method: 'POST',
                        headers,
                        body: JSON.stringify(item.body),
                    });
                    const data = await res.json().catch(() => null);
                    if (res.ok && data && data.status !== 'queued') {
                        sessionStorage.setItem(item.key, JSON.stringify(data));
                    }
                } catch (error) {
                    return null;
                }
                return null;
            })
        );
    }, [user?.role, subRole, moduleSet, mode]);

    const handleRefresh = () => {
        setRefreshKeys((prev) => ({
            ...prev,
            [activeTab]: (prev[activeTab] || 0) + 1,
        }));
    };

    const renderContent = () => {
        const activeModule = moduleSet.find((item) => item.key === activeTab) || moduleSet[0];
        if (!activeModule) return null;
        const refreshKey = refreshKeys[activeModule.key] || 0;
        let content = null;
        try {
            content = activeModule.render();
        } catch (error) {
            content = (
                <div className="p-20 text-center bg-red-50 rounded-2xl border border-red-200">
                    <i className="fas fa-exclamation-triangle text-4xl text-red-500 mb-4"></i>
                    <h3 className="text-xl font-bold text-red-800">Interface Error</h3>
                    <p className="text-red-600">A component failed to render. Check your console for details.</p>
                </div>
            );
        }
        return (
            <div className="animate-fade-in" key={`${activeModule.key}-${refreshKey}`}>
                <div className="space-y-6">
                    {content}
                    <AIExpansionPanel
                        role="government"
                        subRole={subRole}
                        moduleKey={activeModule.key}
                        title="AI Expansion"
                        description="Futuristic AI capabilities tailored to this authority module."
                        autoRefresh={false}
                    />
                </div>
            </div>
        );
    };

    const sidebarItems = moduleSet.map(({ key, label, icon }) => ({ key, label, icon }));

    return (
        <DashboardLayout
            sidebarItems={sidebarItems}
            activeItem={activeTab}
            onSelect={handleSelect}
            onRefresh={handleRefresh}
            refreshLabel="Refresh module"
        >
            <div className="space-y-6 pb-10">
                <DashboardGrid className="md:grid-cols-3">
                    <DashboardCard className="border-l-4 border-blue-500">
                        <p className="text-xs font-bold text-blue-600 uppercase">Pending Verifications</p>
                        <p className="text-3xl font-black text-blue-900">{stats.pending || 0}</p>
                    </DashboardCard>
                    <DashboardCard className="border-l-4 border-green-500">
                        <p className="text-xs font-bold text-green-600 uppercase">Active Emergencies</p>
                        <p className="text-3xl font-black text-green-900">{stats.emergencies}</p>
                    </DashboardCard>
                    <DashboardCard className="border-l-4 border-purple-500">
                        <p className="text-xs font-bold text-purple-600 uppercase">Resource Utilization</p>
                        <p className="text-3xl font-black text-purple-900">{stats.utilization}%</p>
                    </DashboardCard>
                </DashboardGrid>

                <Suspense fallback={<LoadingSpinner />}>
                    {renderContent()}
                </Suspense>
            </div>
        </DashboardLayout>
    );
};

const MobileGovernmentDashboard = () => {
    const { user, logout } = useAuth();
    const { mode } = useDataMode();
    const navigate = useNavigate();
    const { module } = useParams();
    const [activeTab, setActiveTab] = useState('');
    const [refreshKeys, setRefreshKeys] = useState({});
    const [stats, setStats] = useState({ pending: 0, emergencies: 0, utilization: 0 });
    const [menuOpen, setMenuOpen] = useState(false);
    const [showChat, setShowChat] = useState(false);
    const [showProfile, setShowProfile] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);

    const subRole = user?.subRole?.toLowerCase();
    const moduleSet = useMemo(() => {
        const sets = buildGovernmentModuleSet(subRole);
        return sets[subRole] || sets.default;
    }, [subRole]);
    const allowedTabs = useMemo(() => moduleSet.map((item) => item.key), [moduleSet]);
    const defaultTab = allowedTabs[0] || 'overview';
    const moduleKey = (module || defaultTab).toLowerCase();

    useEffect(() => {
        if (user?.role === 'government' && !user?.subRole) {
            navigate('/dashboard/government/roles');
        }
    }, [user?.role, user?.subRole, navigate]);

    useEffect(() => {
        if (!module) {
            navigate(`/dashboard/government/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        if (!allowedTabs.includes(moduleKey)) {
            navigate(`/dashboard/government/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        setActiveTab(moduleKey);
    }, [module, moduleKey, allowedTabs, defaultTab, navigate]);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const summaryRes = await apiFetch('/v2/government/monitoring/summary', { method: 'GET' });
                const summary = summaryRes.ok ? summaryRes.data : null;
                let pending = 0;
                if ((subRole || '').toLowerCase() === 'district_admin') {
                    const pendingRes = await apiFetch('/v2/government/verification/pending', { method: 'GET' });
                    pending = pendingRes.ok ? (pendingRes.data?.data || []).length : 0;
                }
                setStats({
                    pending,
                    emergencies: summary?.active_emergencies || 0,
                    utilization: summary?.resource_utilization || 0,
                });
            } catch (err) {
                console.error('Stats Fetch Error:', err);
            }
        };
        fetchStats();
    }, [subRole]);

    useEffect(() => {
        if (user?.role !== 'government') return;
        if (mode !== 'real') return;
        const token = getAuthToken();
        if (!token) {
            navigate('/login', { replace: true });
            return;
        }
        const preloadKey = `gov_preload_done_${mode}_${subRole || 'default'}`;
        if (sessionStorage.getItem(preloadKey)) return;
        sessionStorage.setItem(preloadKey, '1');

        const paramsFor = (moduleKey) => {
            const params = new URLSearchParams({ role: 'government', module_key: moduleKey });
            if (subRole) params.set('sub_role', subRole);
            return params.toString();
        };

        const moduleKeys = moduleSet.map((item) => item.key);
        const insightCalls = moduleKeys.map((moduleKey) =>
            apiFetch(`/v2/ai/insights?${paramsFor(moduleKey)}`, {
                method: 'GET',
                ttlMs: 60000,
                staleWhileRevalidate: true,
            })
        );

        const commandCalls = [
            apiFetch('/v2/government/command/overview', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/decision/engine', { method: 'POST' }),
            apiFetch('/v2/government/predictions/anomaly', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/monitoring/summary', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/monitoring/feed?limit=60&window_minutes=120', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/resources/hospitals?limit=120', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/resources/ambulances?limit=120', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/verification/pending', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/government/policy/actions?limit=36', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
        ];

        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };

        const aiPreloads = [
            {
                key: 'gov_preload_outbreak',
                path: '/api/gov/predict_outbreak',
                body: { disease_name: 'Influenza', region: 'Central City', days_to_predict: 30 },
            },
            {
                key: 'gov_preload_allocation',
                path: '/api/gov/predict_allocation',
                body: { emergency_count: 5, hospital_capacity_percent: 65 },
            },
            {
                key: 'gov_preload_policy_segment',
                path: '/api/gov/predict_policy_segment',
                body: { emergency_rate: 10.2, avg_response_time: 15.5, hospital_bed_occupancy: 85.0 },
            },
            {
                key: 'gov_preload_policy_performance',
                path: '/api/gov/predict_performance_score',
                body: { emergency_rate: 10.2, avg_response_time: 15.5, hospital_bed_occupancy: 85.0 },
            },
            {
                key: 'gov_preload_availability',
                path: '/api/gov/predict_availability',
                body: { region: 'Central', month: 11, resource_type: 'Blood O+', donation_frequency: 150, hospital_stock_level: 75 },
            },
        ];

        Promise.allSettled(insightCalls.concat(commandCalls));
        Promise.allSettled(commandCalls).then((results) => {
            const [overviewRes, decisionRes, anomalyRes, summaryRes, feedRes, hospitalsRes, ambulancesRes, pendingRes, policyRes] = results.map((item) =>
                item.status === 'fulfilled' ? item.value : null
            );
            if (overviewRes?.ok && decisionRes?.ok && anomalyRes?.ok) {
                localStorage.setItem('gov_command_cache', JSON.stringify({
                    overview: overviewRes.data,
                    decisions: decisionRes.data?.decisions || [],
                    anomaly: anomalyRes.data?.prediction || null,
                }));
            }
            if (summaryRes?.ok && feedRes?.ok && hospitalsRes?.ok) {
                localStorage.setItem('gov_live_cache', JSON.stringify({
                    summary: summaryRes.data,
                    feed: feedRes.data?.data || [],
                    hospitals: hospitalsRes.data?.data || [],
                }));
            }
            if (hospitalsRes?.ok && ambulancesRes?.ok) {
                localStorage.setItem('gov_verification_cache', JSON.stringify({
                    hospitals: hospitalsRes.data?.data || [],
                    ambulances: ambulancesRes.data?.data || [],
                    pending: pendingRes?.ok ? (pendingRes.data?.data || []) : [],
                }));
            }
            if (policyRes?.ok) {
                sessionStorage.setItem('gov_policy_cache', JSON.stringify({
                    decisions: decisionRes?.ok ? (decisionRes.data?.decisions || []) : [],
                    anomaly: anomalyRes?.ok ? anomalyRes.data?.prediction : null,
                    policyActions: policyRes.data?.data || [],
                }));
            }
        });
        Promise.allSettled(
            aiPreloads.map(async (item) => {
                try {
                    const res = await fetch(`${API_BASE_URL}${item.path}`, {
                        method: 'POST',
                        headers,
                        body: JSON.stringify(item.body),
                    });
                    const data = await res.json().catch(() => null);
                    if (res.ok && data) {
                        sessionStorage.setItem(item.key, JSON.stringify(data));
                    }
                } catch (error) {
                    return null;
                }
                return null;
            })
        );
    }, [user?.role, subRole, moduleSet, mode]);

    const handleRefresh = () => {
        setRefreshKeys((prev) => ({
            ...prev,
            [activeTab]: (prev[activeTab] || 0) + 1,
        }));
    };

    const renderContent = () => {
        const activeModule = moduleSet.find((item) => item.key === activeTab) || moduleSet[0];
        if (!activeModule) return null;
        const refreshKey = refreshKeys[activeModule.key] || 0;
        let content = null;
        try {
            content = activeModule.render();
        } catch (error) {
            content = (
                <div className="p-8 text-center bg-red-50 rounded-2xl border border-red-200">
                    <i className="fas fa-exclamation-triangle text-3xl text-red-500 mb-3"></i>
                    <h3 className="text-lg font-bold text-red-800">Interface Error</h3>
                    <p className="text-red-600 text-sm">A component failed to render. Check your console for details.</p>
                </div>
            );
        }
        return (
            <div className="animate-fade-in space-y-4" key={`${activeModule.key}-${refreshKey}`}>
                {content}
                <AIExpansionPanel
                    role="government"
                    subRole={subRole}
                    moduleKey={activeModule.key}
                    title="AI Expansion"
                    description="Futuristic AI capabilities tailored to this authority module."
                    autoRefresh={false}
                />
            </div>
        );
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const activeLabel = moduleSet.find((item) => item.key === activeTab)?.label || 'Government';

    if (showChat) {
        return (
            <div className="min-h-screen bg-slate-50">
                <div className="sticky top-0 z-20 flex items-center justify-between px-4 py-3 bg-white border-b border-slate-200">
                    <button type="button" onClick={() => setShowChat(false)} className="text-slate-500">
                        <i className="fas fa-arrow-left"></i>
                    </button>
                    <div className="flex items-center gap-2">
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 text-white">
                            <i className="fas fa-heartbeat"></i>
                        </span>
                        <span className="text-sm font-semibold text-slate-900">LifeLink AI</span>
                    </div>
                    <button type="button" onClick={() => setMenuOpen(true)} className="text-slate-500">
                        <i className="fas fa-bars"></i>
                    </button>
                </div>
                <div className="px-4 py-4">
                    <LifelinkAiChat variant="page" moduleKey={`government_${activeTab || 'dashboard'}_mobile`} />
                </div>
                <MobileGovernmentMenu
                    open={menuOpen}
                    onClose={() => setMenuOpen(false)}
                    onSelect={(key) => {
                        setMenuOpen(false);
                        if (key === 'chat') return;
                        if (key === 'profile') {
                            setShowProfile(true);
                            return;
                        }
                        if (key === 'notifications') {
                            setShowNotifications(true);
                            return;
                        }
                        if (key === 'switch-role') {
                            navigate('/dashboard/government/roles?switch=1');
                            return;
                        }
                        navigate(`/dashboard/government/${key}`);
                    }}
                    onLogout={handleLogout}
                />
                {showProfile && <GovernmentProfileModal onClose={() => setShowProfile(false)} />}
                {showNotifications && (
                    <div className="fixed inset-0 z-50 bg-slate-900/40 p-4">
                        <div className="relative max-w-3xl mx-auto">
                            <button
                                type="button"
                                onClick={() => setShowNotifications(false)}
                                className="absolute -top-10 right-0 text-white text-xl"
                                aria-label="Close notifications"
                            >
                                <i className="fas fa-times"></i>
                            </button>
                            <NotificationMenu variant="panel" onClose={() => setShowNotifications(false)} />
                        </div>
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50">
            <div className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-slate-200">
                <div className="flex items-center justify-between px-4 py-3">
                    <button type="button" onClick={() => setMenuOpen(true)} className="text-slate-600">
                        <i className="fas fa-bars"></i>
                    </button>
                    <div className="flex items-center gap-2">
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 text-white">
                            <i className="fas fa-heartbeat"></i>
                        </span>
                        <div className="text-left">
                            <p className="text-[10px] text-slate-400 uppercase">LifeLink</p>
                            <p className="text-sm font-semibold text-slate-900">Government</p>
                        </div>
                    </div>
                    <button type="button" onClick={() => setShowChat(true)} className="text-slate-600">
                        <i className="fas fa-robot"></i>
                    </button>
                </div>
                <div className="flex gap-2 overflow-x-auto px-4 pb-3">
                    {moduleSet.map((tab) => (
                        <button
                            key={tab.key}
                            type="button"
                            onClick={() => navigate(`/dashboard/government/${tab.key}`)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold whitespace-nowrap border ${
                                activeTab === tab.key
                                    ? 'bg-sky-600 text-white border-sky-600'
                                    : 'bg-white text-slate-600 border-slate-200'
                            }`}
                        >
                            <i className={`fas ${tab.icon}`}></i>
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="px-4 py-4 space-y-4">
                <DashboardGrid className="sm:grid-cols-2">
                    <DashboardCard className="border-l-4 border-blue-500">
                        <p className="text-xs font-bold text-blue-600 uppercase">Pending Verifications</p>
                        <p className="text-3xl font-black text-blue-900">{stats.pending || 0}</p>
                    </DashboardCard>
                    <DashboardCard className="border-l-4 border-green-500">
                        <p className="text-xs font-bold text-green-600 uppercase">Active Emergencies</p>
                        <p className="text-3xl font-black text-green-900">{stats.emergencies}</p>
                    </DashboardCard>
                    <DashboardCard className="border-l-4 border-purple-500">
                        <p className="text-xs font-bold text-purple-600 uppercase">Resource Utilization</p>
                        <p className="text-3xl font-black text-purple-900">{stats.utilization}%</p>
                    </DashboardCard>
                </DashboardGrid>
                <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3">
                    <div>
                        <p className="text-[10px] uppercase text-slate-400">Current module</p>
                        <p className="text-sm font-semibold text-slate-900">{activeLabel}</p>
                    </div>
                    <button
                        type="button"
                        onClick={handleRefresh}
                        className="text-xs font-semibold text-slate-700 bg-slate-100 px-3 py-2 rounded-lg"
                    >
                        Refresh
                    </button>
                </div>
                {renderContent()}
            </div>

                <MobileGovernmentMenu
                    open={menuOpen}
                    onClose={() => setMenuOpen(false)}
                    onSelect={(key) => {
                    setMenuOpen(false);
                    if (key === 'chat') {
                        setShowChat(true);
                        return;
                    }
                    if (key === 'profile') {
                        setShowProfile(true);
                        return;
                    }
                    if (key === 'notifications') {
                        setShowNotifications(true);
                        return;
                    }
                    if (key === 'switch-role') {
                        navigate('/dashboard/government/roles?switch=1');
                        return;
                    }
                    navigate(`/dashboard/government/${key}`);
                }}
                onLogout={handleLogout}
            />
            {showProfile && <GovernmentProfileModal onClose={() => setShowProfile(false)} />}
            {showNotifications && (
                <div className="fixed inset-0 z-50 bg-slate-900/40 p-4">
                    <div className="relative max-w-3xl mx-auto">
                        <button
                            type="button"
                            onClick={() => setShowNotifications(false)}
                            className="absolute -top-10 right-0 text-white text-xl"
                            aria-label="Close notifications"
                        >
                            <i className="fas fa-times"></i>
                        </button>
                        <NotificationMenu variant="panel" onClose={() => setShowNotifications(false)} />
                    </div>
                </div>
            )}
        </div>
    );
};

const MobileGovernmentMenu = ({ open, onClose, onSelect, onLogout }) => (
    <MobileDrawer open={open} onClose={onClose}>
        <div className="h-full flex flex-col">
            <div className="px-5 py-6 border-b border-slate-200">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg shadow">
                        <i className="fas fa-heartbeat text-lg"></i>
                    </div>
                    <div>
                        <h1 className="text-lg font-bold text-slate-900 font-display">LifeLink</h1>
                        <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Government portal</p>
                    </div>
                </div>
            </div>
            <div className="flex-1 px-4 py-4 space-y-2 overflow-y-auto">
                <button onClick={() => onSelect?.('chat')} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold bg-slate-50 text-slate-700 hover:bg-slate-100">
                    <i className="fas fa-robot"></i>
                    LifeLink AI
                </button>
            </div>
            <div className="px-4 py-4 border-t border-slate-200 space-y-2">
                <button onClick={() => onSelect?.('notifications')} className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100">
                    <i className="fas fa-bell"></i>
                    Notifications
                </button>
                <button onClick={() => onSelect?.('switch-role')} className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100">
                    <i className="fas fa-arrows-rotate"></i>
                    Switch Role
                </button>
                <div className="flex items-center justify-between rounded-xl bg-slate-50 border border-slate-200 px-4 py-3">
                    <div className="flex items-center gap-3">
                        <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg">
                            <i className="fas fa-user"></i>
                        </div>
                        <div>
                            <p className="text-[10px] text-slate-400 uppercase">Profile</p>
                            <p className="text-sm font-semibold text-slate-900">LifeLink</p>
                        </div>
                    </div>
                    <button onClick={() => onSelect?.('profile')} className="text-xs font-semibold text-sky-600">Open</button>
                </div>
                <button onClick={onLogout} className="w-full flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold text-red-600 bg-red-50 hover:bg-red-100">
                    <i className="fas fa-sign-out-alt"></i>
                    Logout
                </button>
            </div>
        </div>
    </MobileDrawer>
);

const GovernmentDashboard = () => {
    const isDesktop = useIsDesktop();
    return isDesktop ? <DesktopGovernmentDashboard /> : <MobileGovernmentDashboard />;
};

export default GovernmentDashboard;
