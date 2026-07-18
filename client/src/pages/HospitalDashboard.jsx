import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDataMode } from '../context/DataModeContext';
import DashboardLayout from '../layout/DashboardLayout';
import { apiFetch } from '../config/api';
import MobileDrawer from '../components/layout/MobileDrawer';
import LifelinkAiChat from '../components/LifelinkAiChat';
import NotificationMenu from '../components/NotificationMenu';
import HospitalProfileModal from '../components/HospitalProfileModal';

// --- CHECK THESE IMPORTS CAREFULLY ---
import HospitalOverview from '../components/HospitalOverview';
import HospitalAnalytics from '../components/HospitalAnalytics'; // Ensure this points to the Analytics file
import HospitalPatients from '../components/HospitalPatients';
import HospitalResources from '../components/HospitalResources';
import HospitalCommunications from '../components/HospitalCommunications';
import AmbulanceETARoute from '../components/AmbulanceETARoute';
import HospitalBedManagement from '../components/HospitalBedManagement';
import AIExpansionPanel from '../components/AIExpansionPanel';
import {
    HospitalDepartmentAnalytics,
    HospitalFinanceOverview,
    HospitalStaffManagement,
    HospitalReports,
    HospitalBillingSystem,
    HospitalRevenueAnalytics,
    HospitalInsuranceClaims,
    HospitalLiveEmergencyFeed,
    HospitalOPDScheduling,
    HospitalDoctorManagement,
    HospitalOPDQueue,
    HospitalConsultationRecords,
    HospitalICULiveMonitoring,
    HospitalICUAlerts,
    HospitalICUVitals,
    HospitalICURiskPanel,
    HospitalRadiologyRequests,
    HospitalRadiologyReportUpload,
    HospitalRadiologyAIInsights,
    HospitalOTSurgeryScheduling,
    HospitalOTStaffAllocation,
} from '../components/HospitalOpsModules';

const hospitalModuleSets = {
    ceo: [
        { key: 'global-overview', label: 'Global Overview', icon: 'fa-chart-pie', render: () => <HospitalOverview /> },
        { key: 'ai-insights', label: 'AI Insights', icon: 'fa-brain', render: () => <HospitalAnalytics /> },
        { key: 'department-analytics', label: 'Department Analytics', icon: 'fa-chart-line', render: () => <HospitalDepartmentAnalytics /> },
        { key: 'bed-management', label: 'Bed Management', icon: 'fa-bed', render: () => <HospitalBedManagement /> },
        { key: 'resource-management', label: 'Resource Management', icon: 'fa-warehouse', render: () => <HospitalResources /> },
        { key: 'ambulance-coordination', label: 'Ambulance Coordination', icon: 'fa-ambulance', render: ({ user }) => (
            <AmbulanceETARoute
                currentHospitalId={user?._id || user?.id}
                currentHospitalName={user?.name}
                hospitalLocation={{ lat: 12.9716, lng: 77.5946 }}
            />
        ) },
        { key: 'finance-overview', label: 'Finance Overview', icon: 'fa-coins', render: () => <HospitalFinanceOverview /> },
        { key: 'staff-management', label: 'Staff Management', icon: 'fa-user-nurse', render: () => <HospitalStaffManagement /> },
        { key: 'reports', label: 'Reports', icon: 'fa-file-alt', render: () => <HospitalReports /> },
        { key: 'multi-hospital-network', label: 'Multi-Hospital Network', icon: 'fa-network-wired', render: ({ user }) => (
            <HospitalCommunications
                currentHospitalId={user?._id || user?.id}
                currentHospitalName={user?.name}
            />
        ) },
    ],
    emergency: [
        { key: 'live-emergency-feed', label: 'Live Emergency Feed', icon: 'fa-triangle-exclamation', render: () => <HospitalLiveEmergencyFeed /> },
        { key: 'ambulance-tracking', label: 'Ambulance Tracking', icon: 'fa-ambulance', render: ({ user }) => (
            <AmbulanceETARoute
                currentHospitalId={user?._id || user?.id}
                currentHospitalName={user?.name}
                hospitalLocation={{ lat: 12.9716, lng: 77.5946 }}
            />
        ) },
        { key: 'patient-intake', label: 'Patient Intake', icon: 'fa-user-injured', render: () => <HospitalPatients /> },
        { key: 'bed-allocation', label: 'Bed Allocation', icon: 'fa-bed', render: () => <HospitalBedManagement /> },
        { key: 'ai-decision-panel', label: 'AI Decision Panel', icon: 'fa-brain', render: () => <HospitalAnalytics /> },
    ],
    finance: [
        { key: 'billing', label: 'Billing', icon: 'fa-file-invoice-dollar', render: () => <HospitalBillingSystem /> },
        { key: 'revenue-analytics', label: 'Revenue Analytics', icon: 'fa-chart-line', render: () => <HospitalRevenueAnalytics /> },
        { key: 'insurance', label: 'Insurance', icon: 'fa-shield-alt', render: () => <HospitalInsuranceClaims /> },
        { key: 'cost-optimization', label: 'Cost Optimization', icon: 'fa-sack-dollar', render: () => <HospitalResources /> },
    ],
    opd: [
        { key: 'appointment-scheduling', label: 'Appointment Scheduling', icon: 'fa-calendar-check', render: () => <HospitalOPDScheduling /> },
        { key: 'doctor-management', label: 'Doctor Management', icon: 'fa-user-doctor', render: () => <HospitalDoctorManagement /> },
        { key: 'patient-queue', label: 'Patient Queue', icon: 'fa-list-check', render: () => <HospitalOPDQueue /> },
        { key: 'consultation-records', label: 'Consultation Records', icon: 'fa-notes-medical', render: () => <HospitalConsultationRecords /> },
    ],
    icu: [
        { key: 'live-patient-monitoring', label: 'Live Patient Monitoring', icon: 'fa-heart-pulse', render: () => <HospitalICULiveMonitoring /> },
        { key: 'critical-alerts', label: 'Critical Alerts', icon: 'fa-bell', render: () => <HospitalICUAlerts /> },
        { key: 'ai-risk-prediction', label: 'AI Risk Prediction', icon: 'fa-brain', render: () => <HospitalICURiskPanel /> },
        { key: 'vitals-dashboard', label: 'Vitals Dashboard', icon: 'fa-wave-square', render: () => <HospitalICUVitals /> },
    ],
    radiology: [
        { key: 'scan-requests', label: 'Scan Requests', icon: 'fa-x-ray', render: () => <HospitalRadiologyRequests /> },
        { key: 'report-upload', label: 'Report Upload', icon: 'fa-file-upload', render: () => <HospitalRadiologyReportUpload /> },
        { key: 'ai-scan-insights', label: 'AI Scan Insights', icon: 'fa-robot', render: () => <HospitalRadiologyAIInsights /> },
    ],
    ot: [
        { key: 'surgery-scheduling', label: 'Surgery Scheduling', icon: 'fa-user-nurse', render: () => <HospitalOTSurgeryScheduling /> },
        { key: 'staff-allocation', label: 'Staff Allocation', icon: 'fa-users', render: () => <HospitalOTStaffAllocation /> },
        { key: 'equipment-tracking', label: 'Equipment Tracking', icon: 'fa-briefcase-medical', render: () => <HospitalResources /> },
    ],
    default: [
        { key: 'global-overview', label: 'Global Overview', icon: 'fa-chart-pie', render: () => <HospitalOverview /> },
    ],
};

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

const DesktopHospitalDashboard = () => {
    const { user } = useAuth();
    const { mode } = useDataMode();
    const navigate = useNavigate();
    const { module } = useParams();
    const [activeTab, setActiveTab] = useState('');
    const [refreshKeys, setRefreshKeys] = useState({});

    const subRole = user?.subRole?.toLowerCase();
    const moduleSet = useMemo(() => {
        return hospitalModuleSets[subRole] || hospitalModuleSets.default;
    }, [subRole]);
    const allowedTabs = useMemo(() => moduleSet.map((item) => item.key), [moduleSet]);
    const defaultTab = allowedTabs[0] || 'overview';
    const moduleKey = (module || defaultTab).toLowerCase();

    useEffect(() => {
        if (user?.role === 'hospital' && !user?.subRole) {
            navigate('/dashboard/hospital/roles');
        }
    }, [user?.role, user?.subRole, navigate]);

    useEffect(() => {
        if (!module) {
            navigate(`/dashboard/hospital/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        if (!allowedTabs.includes(moduleKey)) {
            navigate(`/dashboard/hospital/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        setActiveTab(moduleKey);
    }, [module, moduleKey, allowedTabs, defaultTab, navigate]);

    useEffect(() => {
        if (mode !== 'real') return;
        if (!user?._id && !user?.id) return;
        const preloadKey = `hospital_preload_${subRole || 'default'}`;
        if (sessionStorage.getItem(preloadKey)) return;
        sessionStorage.setItem(preloadKey, '1');

        const paramsFor = (moduleKey) => {
            const params = new URLSearchParams({ role: 'hospital', module_key: moduleKey });
            if (subRole) params.set('sub_role', subRole);
            return params.toString();
        };

        const moduleKeys = moduleSet.map((item) => item.key);
        const insightCalls = moduleKeys.map((key) =>
            apiFetch(`/v2/ai/insights?${paramsFor(key)}`, {
                method: 'GET',
                ttlMs: 60000,
                staleWhileRevalidate: true,
            })
        );

        const hospitalId = user?._id || user?.id;
        const coreCalls = [
            apiFetch('/api/hospital-ops/preload', {
                method: 'POST',
                body: JSON.stringify({ hospitalId, scale: 320 })
            }),
            apiFetch(`/api/hospital-ops/ceo/global-metrics?hospitalId=${hospitalId}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch(`/api/hospital-ops/emergency/feed?hospitalId=${hospitalId}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch(`/api/hospital-ops/ceo/ai-insights?hospitalId=${hospitalId}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
        ];

        Promise.allSettled(insightCalls.concat(coreCalls));
    }, [mode, subRole, moduleSet, user?._id, user?.id]);

    const handleSelect = (key) => {
        if (key === 'profile' || key === 'notifications') {
            setActiveTab(key);
            return;
        }
        navigate(`/dashboard/hospital/${key}`);
    };

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
        return (
            <div className="space-y-6" key={`${activeModule.key}-${refreshKey}`}>
                {activeModule.render({ user })}
                <AIExpansionPanel
                    role="hospital"
                    subRole={subRole}
                    moduleKey={activeModule.key}
                    title="AI Expansion"
                    description="Futuristic AI capabilities tailored to this hospital unit."
                    entityId={user?._id || user?.id || user?.userId}
                    autoRefresh={false}
                />
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
            <div className="min-h-[60vh] animate-fade-in">
                {renderContent()}
            </div>
        </DashboardLayout>
    );
};

const MobileHospitalDashboard = () => {
    const { user, logout } = useAuth();
    const { mode } = useDataMode();
    const navigate = useNavigate();
    const { module } = useParams();
    const [activeTab, setActiveTab] = useState('');
    const [refreshKeys, setRefreshKeys] = useState({});
    const [menuOpen, setMenuOpen] = useState(false);
    const [showChat, setShowChat] = useState(false);
    const [showProfile, setShowProfile] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);

    const subRole = user?.subRole?.toLowerCase();
    const moduleSet = useMemo(() => hospitalModuleSets[subRole] || hospitalModuleSets.default, [subRole]);
    const allowedTabs = useMemo(() => moduleSet.map((item) => item.key), [moduleSet]);
    const defaultTab = allowedTabs[0] || 'overview';
    const moduleKey = (module || defaultTab).toLowerCase();

    useEffect(() => {
        if (user?.role === 'hospital' && !user?.subRole) {
            navigate('/dashboard/hospital/roles');
        }
    }, [user?.role, user?.subRole, navigate]);

    useEffect(() => {
        if (!module) {
            navigate(`/dashboard/hospital/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        if (!allowedTabs.includes(moduleKey)) {
            navigate(`/dashboard/hospital/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        setActiveTab(moduleKey);
    }, [module, moduleKey, allowedTabs, defaultTab, navigate]);

    useEffect(() => {
        if (mode !== 'real') return;
        if (!user?._id && !user?.id) return;
        const preloadKey = `hospital_preload_${subRole || 'default'}`;
        if (sessionStorage.getItem(preloadKey)) return;
        sessionStorage.setItem(preloadKey, '1');

        const paramsFor = (moduleKey) => {
            const params = new URLSearchParams({ role: 'hospital', module_key: moduleKey });
            if (subRole) params.set('sub_role', subRole);
            return params.toString();
        };

        const moduleKeys = moduleSet.map((item) => item.key);
        const insightCalls = moduleKeys.map((key) =>
            apiFetch(`/v2/ai/insights?${paramsFor(key)}`, {
                method: 'GET',
                ttlMs: 60000,
                staleWhileRevalidate: true,
            })
        );

        const hospitalId = user?._id || user?.id;
        const coreCalls = [
            apiFetch('/api/hospital-ops/preload', {
                method: 'POST',
                body: JSON.stringify({ hospitalId, scale: 320 })
            }),
            apiFetch(`/api/hospital-ops/ceo/global-metrics?hospitalId=${hospitalId}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch(`/api/hospital-ops/emergency/feed?hospitalId=${hospitalId}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch(`/api/hospital-ops/ceo/ai-insights?hospitalId=${hospitalId}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
        ];

        Promise.allSettled(insightCalls.concat(coreCalls));
    }, [mode, subRole, moduleSet, user?._id, user?.id]);

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
        return (
            <div className="space-y-4" key={`${activeModule.key}-${refreshKey}`}>
                {activeModule.render({ user })}
                <AIExpansionPanel
                    role="hospital"
                    subRole={subRole}
                    moduleKey={activeModule.key}
                    title="AI Expansion"
                    description="Futuristic AI capabilities tailored to this hospital unit."
                    entityId={user?._id || user?.id}
                    autoRefresh={false}
                />
            </div>
        );
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const activeLabel = moduleSet.find((item) => item.key === activeTab)?.label || 'Hospital';

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
                    <LifelinkAiChat variant="page" moduleKey={`hospital_${activeTab || 'dashboard'}_mobile`} />
                </div>
                <MobileHospitalMenu
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
                            navigate('/dashboard/hospital/roles?switch=1');
                            return;
                        }
                        navigate(`/dashboard/hospital/${key}`);
                    }}
                    onLogout={handleLogout}
                />
                {showProfile && <HospitalProfileModal onClose={() => setShowProfile(false)} />}
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
                            <p className="text-sm font-semibold text-slate-900">Hospital</p>
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
                            onClick={() => navigate(`/dashboard/hospital/${tab.key}`)}
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

            <MobileHospitalMenu
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
                        navigate('/dashboard/hospital/roles?switch=1');
                        return;
                    }
                    navigate(`/dashboard/hospital/${key}`);
                }}
                onLogout={handleLogout}
            />
            {showProfile && <HospitalProfileModal onClose={() => setShowProfile(false)} />}
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

const MobileHospitalMenu = ({ open, onClose, onSelect, onLogout }) => (
    <MobileDrawer open={open} onClose={onClose}>
        <div className="h-full flex flex-col">
            <div className="px-5 py-6 border-b border-slate-200">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg shadow">
                        <i className="fas fa-heartbeat text-lg"></i>
                    </div>
                    <div>
                        <h1 className="text-lg font-bold text-slate-900 font-display">LifeLink</h1>
                        <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Hospital portal</p>
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

const HospitalDashboard = () => {
    const isDesktop = useIsDesktop();
    return isDesktop ? <DesktopHospitalDashboard /> : <MobileHospitalDashboard />;
};

export default HospitalDashboard;