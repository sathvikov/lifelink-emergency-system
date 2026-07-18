import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import DashboardLayout from '../layout/DashboardLayout';
import { DashboardCard } from '../components/Common';
import AmbulanceLiveTracking from '../components/AmbulanceLiveTracking';
import AIExpansionPanel from '../components/AIExpansionPanel';
import { useDataMode } from '../context/DataModeContext';
import { useAuth } from '../context/AuthContext';
import { apiFetch, getAuthToken } from '../config/api';
import MobileCard from '../components/ui/MobileCard';
import MobileDrawer from '../components/layout/MobileDrawer';
import LifelinkAiChat from '../components/LifelinkAiChat';
import ProfileModal from '../components/ProfileModal';
import {
    AmbulanceAssignments,
    AmbulanceEmergencyResponse,
    AmbulancePatientInfo,
    AmbulanceNavigation,
    AmbulanceEmergencyStatus,
    AmbulanceHistory,
} from '../components/AmbulanceModules';

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

const resolveAmbulanceId = (user) => user?._id || user?.id || '';

const normalizeAssignments = (items) => (items || []).map((item) => ({
    ...item,
    patient: item.patient || item.patientName || item.name || 'Unknown',
    emergencyType: item.emergencyType || item.emergency_type || item.type || 'General',
    etaMinutes: item.etaMinutes ?? item.eta ?? item.estimatedTimeMinutes,
    status: item.status || 'Active',
}));

const normalizePatientInfo = (items) => (items || []).map((item) => ({
    ...item,
    patient: item.patient || item.patientName || item.name || 'Unknown',
    emergencyType: item.emergencyType || item.emergency_type || item.type || 'General',
    patientVitals: item.patientVitals || item.vitals || {},
    status: item.status || 'Active',
}));

const normalizeHistory = (items) => (items || []).map((item) => ({
    ...item,
    patient: item.patient || item.patientName || item.name || 'Unknown',
    emergencyType: item.emergencyType || item.emergency_type || item.type || 'General',
    updatedAt: item.updatedAt || item.completedAt || item.createdAt,
    status: item.status || 'Completed',
}));

const trafficLevelFromRatio = (ratio) => {
    if (ratio >= 1.2) return 'Heavy';
    if (ratio >= 1.1) return 'Moderate';
    return 'Light';
};

const toLatLng = (value) => {
    if (!value || typeof value !== 'object') return { lat: null, lng: null, address: '' };
    return {
        lat: value.latitude ?? value.lat,
        lng: value.longitude ?? value.lng,
        address: value.address || '',
    };
};

const hasCoords = (point) => Number.isFinite(point?.lat) && Number.isFinite(point?.lng);

const BENGALURU_BOUNDS = {
    latMin: 12.85,
    latMax: 13.05,
    lngMin: 77.45,
    lngMax: 77.75,
};

const isWithinBengaluru = (point) => (
    hasCoords(point)
    && point.lat >= BENGALURU_BOUNDS.latMin
    && point.lat <= BENGALURU_BOUNDS.latMax
    && point.lng >= BENGALURU_BOUNDS.lngMin
    && point.lng <= BENGALURU_BOUNDS.lngMax
);

const coerceToBengaluru = (point, fallback) => (isWithinBengaluru(point) ? point : { ...fallback });

const fallbackEmergency = {
    incident: {
        title: 'Multi-vehicle collision',
        location: 'Majestic, Bengaluru',
        severity: 'Critical',
        lat: 12.9716,
        lng: 77.5946,
    },
    hospital: {
        name: "St. Martha's Hospital",
        location: 'Nrupathunga Road, Bengaluru',
        lat: 12.9686,
        lng: 77.5995,
    },
};

const ambulanceModuleSet = [
    { key: 'emergency', label: 'Emergency', icon: 'fa-triangle-exclamation' },
    { key: 'assignments', label: 'Assignments', icon: 'fa-clipboard-list' },
    { key: 'live-tracking', label: 'Live Tracking', icon: 'fa-map-marker-alt' },
    { key: 'patient-info', label: 'Patient Info', icon: 'fa-notes-medical' },
    { key: 'navigation', label: 'Navigation', icon: 'fa-route' },
    { key: 'emergency-status', label: 'Emergency Status', icon: 'fa-exclamation-triangle' },
    { key: 'history', label: 'History', icon: 'fa-history' },
];

const DesktopAmbulanceDashboard = () => {
    const navigate = useNavigate();
    const { mode } = useDataMode();
    const { module } = useParams();
    const [activeTab, setActiveTab] = useState('');
    const [refreshKeys, setRefreshKeys] = useState({});

    const allowedTabs = useMemo(() => ambulanceModuleSet.map((item) => item.key), []);
    const defaultTab = allowedTabs[0] || 'assignments';
    const moduleKey = (module || defaultTab).toLowerCase();
    const activeLabel = ambulanceModuleSet.find((item) => item.key === activeTab)?.label || 'Module';

    useEffect(() => {
        if (!module) {
            navigate(`/dashboard/ambulance/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        if (!allowedTabs.includes(moduleKey)) {
            navigate(`/dashboard/ambulance/${defaultTab}`, { replace: true });
            setActiveTab(defaultTab);
            return;
        }

        setActiveTab(moduleKey);
    }, [module, moduleKey, allowedTabs, defaultTab, navigate]);

    useEffect(() => {
        if (mode !== 'real') return;
        const preloadKey = 'ambulance_preload';
        if (sessionStorage.getItem(preloadKey)) return;
        sessionStorage.setItem(preloadKey, '1');
        Promise.allSettled([
            apiFetch('/api/ambulance/assignments', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/api/ambulance/emergency-status', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/api/ambulance/history', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            apiFetch('/v2/ai/insights?role=ambulance&module_key=assignments', { method: 'GET', ttlMs: 60000, staleWhileRevalidate: true }),
        ]);
    }, [mode]);

    const handleSelect = (key) => {
        if (key === 'profile' || key === 'notifications') {
            setActiveTab(key);
            return;
        }
        navigate(`/dashboard/ambulance/${key}`);
    };

    const handleRefresh = () => {
        setRefreshKeys((prev) => ({
            ...prev,
            [activeTab]: (prev[activeTab] || 0) + 1,
        }));
    };

    const renderModule = (tabKey) => {
        switch (tabKey) {
            case 'emergency':
                return <AmbulanceEmergencyResponse />;
            case 'assignments':
                return <AmbulanceAssignments />;
            case 'live-tracking':
                return (
                    <DashboardCard>
                        <AmbulanceLiveTracking />
                    </DashboardCard>
                );
            case 'patient-info':
                return <AmbulancePatientInfo />;
            case 'navigation':
                return <AmbulanceNavigation />;
            case 'emergency-status':
                return <AmbulanceEmergencyStatus />;
            case 'history':
                return <AmbulanceHistory />;
            default:
                return null;
        }
    };

    const renderContent = () => {
        const activeModule = ambulanceModuleSet.find((item) => item.key === activeTab) || ambulanceModuleSet[0];
        if (!activeModule) return null;
        const refreshKey = refreshKeys[activeModule.key] || 0;
        return (
            <div className="space-y-6" key={`${activeModule.key}-${refreshKey}`}>
                {renderModule(activeModule.key)}
                <AIExpansionPanel
                    role="ambulance"
                    moduleKey={activeModule.key}
                    title="AI Expansion"
                    description="Futuristic AI capabilities tailored to this ambulance module."
                    autoRefresh={false}
                />
            </div>
        );
    };

    const sidebarItems = ambulanceModuleSet.map(({ key, label, icon }) => ({ key, label, icon }));
    const emergencyAlert = {
        title: 'Critical incident: Multi-vehicle collision',
        location: 'Majestic, Bengaluru',
        priority: 'Critical',
        eta: '11 min',
    };

    return (
        <DashboardLayout
            sidebarItems={sidebarItems}
            activeItem={activeTab}
            onSelect={handleSelect}
            onRefresh={handleRefresh}
            refreshLabel="Refresh module"
        >
            <div className="min-h-[60vh] animate-fade-in space-y-6">
                {activeTab !== 'emergency' && (
                    <DashboardCard>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <p className="text-xs font-bold uppercase text-rose-500">Emergency alert</p>
                                <p className="text-lg font-bold text-slate-900">{emergencyAlert.title}</p>
                                <p className="text-sm text-slate-600">{emergencyAlert.location} · Priority {emergencyAlert.priority} · ETA {emergencyAlert.eta}</p>
                            </div>
                            <button
                                className="px-4 py-2 text-xs font-bold bg-rose-600 text-white rounded"
                                onClick={() => navigate('/dashboard/ambulance/emergency')}
                            >
                                View emergency route
                            </button>
                        </div>
                    </DashboardCard>
                )}
                {renderContent()}
            </div>
        </DashboardLayout>
    );
};

const MobileAmbulanceDashboard = () => {
    const { user, logout } = useAuth();
    const ambulanceId = resolveAmbulanceId(user);
    const cacheKey = ambulanceId ? `ambulance_mobile_${ambulanceId}` : 'ambulance_mobile';
    const [menuOpen, setMenuOpen] = useState(false);
    const [activeTab, setActiveTab] = useState('emergency');
    const [showChat, setShowChat] = useState(false);
    const [showProfile, setShowProfile] = useState(false);
    const [state, setState] = useState({
        loading: true,
        updating: false,
        emergency: fallbackEmergency,
        assignments: [],
        patientInfo: [],
        history: [],
        updatedAt: null,
    });

    useEffect(() => {
        let isActive = true;

        const readCache = () => {
            try {
                const cached = localStorage.getItem(cacheKey);
                if (!cached) return false;
                const parsed = JSON.parse(cached);
                if (!parsed) return false;
                setState((prev) => ({
                    ...prev,
                    loading: false,
                    emergency: parsed.emergency || prev.emergency,
                    assignments: parsed.assignments || prev.assignments,
                    patientInfo: parsed.patientInfo || prev.patientInfo,
                    history: parsed.history || prev.history,
                    updatedAt: parsed.updatedAt || prev.updatedAt,
                    updating: true,
                }));
                return true;
            } catch (error) {
                return false;
            }
        };

        const writeCache = (payload) => {
            try {
                localStorage.setItem(cacheKey, JSON.stringify(payload));
            } catch (error) {
                // ignore cache errors
            }
        };

        const fetchRouteSummary = async (start, end, hasAuth) => {
            if (!hasCoords(start) || !hasCoords(end)) return null;
            if (!hasAuth) {
                const distanceKm = Math.round(getDistanceKm(start.lat, start.lng, end.lat, end.lng) * 10) / 10;
                const baseMinutes = Math.max(3, Math.round((distanceKm / 35) * 60));
                const etaMinutes = Math.round(baseMinutes * 1.1);
                return {
                    distanceKm,
                    etaMinutes,
                    baseMinutes,
                    trafficLevel: trafficLevelFromRatio(1.1),
                };
            }
            const [routeRes, trafficRes] = await Promise.all([
                apiFetch(`/v2/route?start_lat=${start.lat}&start_lng=${start.lng}&end_lat=${end.lat}&end_lng=${end.lng}&include_geometry=false`, { method: 'GET' }),
                apiFetch(`/v2/integrations/traffic?origin=${start.lat},${start.lng}&destination=${end.lat},${end.lng}`, { method: 'GET' }),
            ]);
            if (!routeRes.ok) return null;
            const distanceKm = routeRes.data?.distance_meters
                ? Math.round((routeRes.data.distance_meters / 1000) * 10) / 10
                : Math.round(getDistanceKm(start.lat, start.lng, end.lat, end.lng) * 10) / 10;
            const baseSeconds = trafficRes.data?.base_duration_seconds || routeRes.data?.duration_seconds || 0;
            const adjustedSeconds = trafficRes.data?.adjusted_duration_seconds || baseSeconds;
            const ratio = baseSeconds ? adjustedSeconds / baseSeconds : 1;
            return {
                distanceKm,
                etaMinutes: Math.max(1, Math.round((adjustedSeconds || 600) / 60)),
                baseMinutes: Math.max(1, Math.round((baseSeconds || adjustedSeconds || 600) / 60)),
                trafficLevel: trafficLevelFromRatio(ratio),
            };
        };

        const loadData = async () => {
            const hasCache = readCache();
            if (!hasCache) {
                setState((prev) => ({ ...prev, loading: false, updating: true }));
            }

            try {
                const hasAuth = Boolean(getAuthToken());
                const [assignmentsRes, patientRes, historyRes, ambulanceRes] = await Promise.all([
                    apiFetch(`/api/ambulance/assignments${ambulanceId ? `?ambulance_id=${ambulanceId}` : ''}`, { method: 'GET' }),
                    apiFetch(`/api/ambulance/patient-info${ambulanceId ? `?ambulance_id=${ambulanceId}` : ''}`, { method: 'GET' }),
                    apiFetch(`/api/ambulance/history${ambulanceId ? `?ambulance_id=${ambulanceId}` : ''}`, { method: 'GET' }),
                    apiFetch('/api/ambulance', { method: 'GET' }),
                ]);

                const assignments = normalizeAssignments(assignmentsRes.data?.data || assignmentsRes.data || []);
                const patientInfo = normalizePatientInfo(patientRes.data?.data || patientRes.data || []);
                const history = normalizeHistory(historyRes.data?.data || historyRes.data || []);

                const activeAssignment = assignments.find((item) => (
                    ['active', 'en route', 'at location', 'assigned'].includes(String(item.status || '').toLowerCase())
                )) || assignments[0];

                const ambulances = Array.isArray(ambulanceRes.data?.data) ? ambulanceRes.data.data : (ambulanceRes.data || []);
                const matchedAmbulance = ambulances.find((item) => item.ambulanceId === activeAssignment?.ambulanceId)
                    || ambulances[0];
                const vehicleLoc = toLatLng(matchedAmbulance?.currentLocation || {});
                const pickupLoc = toLatLng(activeAssignment?.pickupLocation || {});
                const destinationLoc = toLatLng(activeAssignment?.destinationLocation || {});

                const incident = {
                    title: activeAssignment?.emergencyType || fallbackEmergency.incident.title,
                    location: activeAssignment?.pickup || pickupLoc.address || fallbackEmergency.incident.location,
                    severity: activeAssignment?.priorityLevel || activeAssignment?.priority || fallbackEmergency.incident.severity,
                    lat: pickupLoc.lat ?? fallbackEmergency.incident.lat,
                    lng: pickupLoc.lng ?? fallbackEmergency.incident.lng,
                };
                const hospital = {
                    name: activeAssignment?.destination || destinationLoc.address || fallbackEmergency.hospital.name,
                    location: destinationLoc.address || activeAssignment?.destination || fallbackEmergency.hospital.location,
                    lat: destinationLoc.lat ?? fallbackEmergency.hospital.lat,
                    lng: destinationLoc.lng ?? fallbackEmergency.hospital.lng,
                };

                const safeVehicle = coerceToBengaluru(vehicleLoc, { lat: fallbackEmergency.incident.lat, lng: fallbackEmergency.incident.lng });
                const safeIncident = coerceToBengaluru(incident, fallbackEmergency.incident);
                const safeHospital = coerceToBengaluru(hospital, fallbackEmergency.hospital);

                const pickupSummary = await fetchRouteSummary(safeVehicle, safeIncident, hasAuth);
                const hospitalSummary = await fetchRouteSummary(safeIncident, safeHospital, hasAuth);

                const emergency = {
                    incident: safeIncident,
                    hospital: safeHospital,
                    pickupSummary,
                    hospitalSummary,
                    etaMinutes: activeAssignment?.etaMinutes || pickupSummary?.etaMinutes || 0,
                };

                const updatedAt = new Date().toISOString();

                if (!isActive) return;
                const nextState = {
                    loading: false,
                    updating: false,
                    emergency,
                    assignments,
                    patientInfo,
                    history,
                    updatedAt,
                };
                setState(nextState);
                writeCache(nextState);
            } catch (error) {
                if (!isActive) return;
                setState((prev) => ({ ...prev, loading: false, updating: false }));
            }
        };

        loadData();
        return () => {
            isActive = false;
        };
    }, [ambulanceId, cacheKey]);

    const assignments = state.assignments.slice(0, 4);
    const patientInfo = state.patientInfo.slice(0, 3);
    const history = state.history.slice(0, 4);
    const emergency = state.emergency || fallbackEmergency;

    const statusColor = emergency.incident.severity === 'Critical' ? 'text-rose-600 bg-rose-50 border-rose-200'
        : emergency.incident.severity === 'High'
            ? 'text-amber-600 bg-amber-50 border-amber-200'
            : 'text-sky-600 bg-sky-50 border-sky-200';

    const tabs = [
        { key: 'emergency', label: 'Emergency', icon: 'fa-triangle-exclamation' },
        { key: 'assignments', label: 'Assignments', icon: 'fa-clipboard-list' },
        { key: 'patients', label: 'Patients', icon: 'fa-notes-medical' },
        { key: 'history', label: 'History', icon: 'fa-history' },
    ];

    const renderTabContent = () => {
        if (activeTab === 'emergency') {
            return (
                <div className="space-y-4">
                    <MobileCard className="border border-slate-200 shadow-md">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <p className="text-xs font-semibold uppercase text-rose-500">Emergency Dispatch</p>
                                <h2 className="text-lg font-bold text-slate-900">{emergency.incident.title}</h2>
                                <p className="text-xs text-slate-500 mt-1">Pickup · {emergency.incident.location}</p>
                                <p className="text-xs text-slate-500">Drop · {emergency.hospital.name}</p>
                            </div>
                            <span className={`px-2 py-1 text-[10px] font-semibold rounded-full border ${statusColor}`}>
                                {emergency.incident.severity}
                            </span>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-600">
                            <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                                <p className="text-[10px] uppercase text-slate-400">To pickup</p>
                                <p className="text-base font-bold text-slate-900">{emergency.pickupSummary?.etaMinutes || emergency.etaMinutes || '--'} min</p>
                                <p>{emergency.pickupSummary?.distanceKm || '--'} km · {emergency.pickupSummary?.trafficLevel || 'Light'} traffic</p>
                                {emergency.pickupSummary && (
                                    <p className="text-[10px] text-slate-400">Δ {Math.max(0, emergency.pickupSummary.etaMinutes - emergency.pickupSummary.baseMinutes)} min</p>
                                )}
                            </div>
                            <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                                <p className="text-[10px] uppercase text-slate-400">To hospital</p>
                                <p className="text-base font-bold text-slate-900">{emergency.hospitalSummary?.etaMinutes || '--'} min</p>
                                <p>{emergency.hospitalSummary?.distanceKm || '--'} km · {emergency.hospitalSummary?.trafficLevel || 'Moderate'} traffic</p>
                                {emergency.hospitalSummary && (
                                    <p className="text-[10px] text-slate-400">Δ {Math.max(0, emergency.hospitalSummary.etaMinutes - emergency.hospitalSummary.baseMinutes)} min</p>
                                )}
                            </div>
                        </div>
                        {state.updating && <p className="mt-2 text-[10px] text-slate-400">Updating live route data...</p>}
                    </MobileCard>
                    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                        <AmbulanceEmergencyResponse />
                    </div>
                </div>
            );
        }

        if (activeTab === 'assignments') {
            return (
                <MobileCard>
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-base font-bold text-slate-900">Assignments</h3>
                        <span className="text-xs text-slate-400">{assignments.length} active</span>
                    </div>
                    <div className="space-y-3">
                        {assignments.map((item) => (
                            <div key={item.id || item._id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                                <div>
                                    <p className="text-sm font-semibold text-slate-900">{item.patient}</p>
                                    <p className="text-xs text-slate-500">{item.emergencyType}</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-xs font-semibold text-slate-700">{item.status}</p>
                                    <p className="text-[11px] text-slate-400">ETA {item.etaMinutes || '--'} min</p>
                                </div>
                            </div>
                        ))}
                        {assignments.length === 0 && <p className="text-xs text-slate-400">No active assignments.</p>}
                    </div>
                </MobileCard>
            );
        }

        if (activeTab === 'patients') {
            return (
                <MobileCard>
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-base font-bold text-slate-900">Patient Details</h3>
                        <span className="text-xs text-slate-400">Live vitals</span>
                    </div>
                    <div className="space-y-3">
                        {patientInfo.map((item) => (
                            <div key={item.id || item._id} className="rounded-xl border border-slate-200 bg-white p-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-semibold text-slate-900">{item.patient}</p>
                                        <p className="text-xs text-slate-500">{item.emergencyType}</p>
                                    </div>
                                    <span className="text-[10px] font-semibold px-2 py-1 rounded-full bg-sky-50 text-sky-600 border border-sky-100">
                                        {item.status}
                                    </span>
                                </div>
                                <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-slate-500">
                                    <div className="rounded-lg bg-slate-50 border border-slate-200 p-2">
                                        <p className="text-[10px] uppercase">HR</p>
                                        <p className="text-sm font-semibold text-slate-900">{item.patientVitals?.heartRate || '--'} bpm</p>
                                    </div>
                                    <div className="rounded-lg bg-slate-50 border border-slate-200 p-2">
                                        <p className="text-[10px] uppercase">O2</p>
                                        <p className="text-sm font-semibold text-slate-900">{item.patientVitals?.oxygen || '--'}%</p>
                                    </div>
                                    <div className="rounded-lg bg-slate-50 border border-slate-200 p-2">
                                        <p className="text-[10px] uppercase">BP</p>
                                        <p className="text-sm font-semibold text-slate-900">{item.patientVitals?.bp || '--'}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                        {patientInfo.length === 0 && <p className="text-xs text-slate-400">No live patient updates.</p>}
                    </div>
                </MobileCard>
            );
        }

        return (
            <MobileCard>
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-base font-bold text-slate-900">History</h3>
                    <span className="text-xs text-slate-400">Last 4 missions</span>
                </div>
                <div className="space-y-3">
                    {history.map((item) => (
                        <div key={item.id || item._id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
                            <div>
                                <p className="text-sm font-semibold text-slate-900">{item.patient}</p>
                                <p className="text-xs text-slate-500">{item.emergencyType}</p>
                            </div>
                            <div className="text-right">
                                <p className="text-xs font-semibold text-slate-700">{item.status}</p>
                                <p className="text-[11px] text-slate-400">{item.updatedAt ? new Date(item.updatedAt).toLocaleDateString() : ''}</p>
                            </div>
                        </div>
                    ))}
                    {history.length === 0 && <p className="text-xs text-slate-400">No completed missions yet.</p>}
                </div>
            </MobileCard>
        );
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

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
                    <LifelinkAiChat variant="page" moduleKey="ambulance_mobile" />
                </div>
                <MobileDrawer open={menuOpen} onClose={() => setMenuOpen(false)}>
                    <MobileAmbulanceMenu
                        onSelect={(key) => {
                            setMenuOpen(false);
                            if (key === 'chat') return;
                            if (key === 'profile') {
                                setShowProfile(true);
                                return;
                            }
                            if (key === 'logout') {
                                handleLogout();
                                return;
                            }
                        }}
                        onProfile={() => {
                            setMenuOpen(false);
                            setShowProfile(true);
                        }}
                    />
                </MobileDrawer>
                {showProfile && <ProfileModal onClose={() => setShowProfile(false)} />}
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
                            <p className="text-xs text-slate-400 uppercase">LifeLink</p>
                            <p className="text-sm font-semibold text-slate-900">Ambulance</p>
                        </div>
                    </div>
                    <div className="text-xs text-slate-500">Unit {ambulanceId || 'AMB-101'}</div>
                </div>
                <div className="flex gap-2 overflow-x-auto px-4 pb-3">
                    {tabs.map((tab) => (
                        <button
                            key={tab.key}
                            type="button"
                            onClick={() => setActiveTab(tab.key)}
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
                {renderTabContent()}
            </div>

            <MobileDrawer open={menuOpen} onClose={() => setMenuOpen(false)}>
                <MobileAmbulanceMenu
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
                        if (key === 'logout') {
                            handleLogout();
                            return;
                        }
                    }}
                    onProfile={() => {
                        setMenuOpen(false);
                        setShowProfile(true);
                    }}
                />
            </MobileDrawer>
            {showProfile && <ProfileModal onClose={() => setShowProfile(false)} />}
        </div>
    );
};

const MobileAmbulanceMenu = ({ onSelect, onProfile }) => (
    <div className="h-full flex flex-col">
        <div className="px-5 py-6 border-b border-slate-200">
            <div className="flex items-center gap-3">
                <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg shadow">
                    <i className="fas fa-heartbeat text-lg"></i>
                </div>
                <div>
                    <h1 className="text-lg font-bold text-slate-900 font-display">LifeLink</h1>
                    <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Ambulance portal</p>
                </div>
            </div>
        </div>
        <div className="flex-1 px-4 py-4 space-y-2">
            <button onClick={() => onSelect('chat')} className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold bg-slate-50 text-slate-700 hover:bg-slate-100">
                <i className="fas fa-robot"></i>
                LifeLink Chat
            </button>
        </div>
        <div className="px-4 py-4 border-t border-slate-200 space-y-3">
            <div className="flex items-center justify-between rounded-xl bg-slate-50 border border-slate-200 px-4 py-3">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg">
                        <i className="fas fa-user"></i>
                    </div>
                    <div>
                        <p className="text-xs text-slate-400 uppercase">Profile</p>
                        <p className="text-sm font-semibold text-slate-900">LifeLink</p>
                    </div>
                </div>
                <button onClick={onProfile} className="text-xs font-semibold text-sky-600">Open</button>
            </div>
            <button onClick={() => onSelect('logout')} className="w-full flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold text-red-600 bg-red-50 hover:bg-red-100">
                <i className="fas fa-sign-out-alt"></i>
                Logout
            </button>
        </div>
    </div>
);

const AmbulanceDashboard = () => {
    const isDesktop = useIsDesktop();
    return isDesktop ? <DesktopAmbulanceDashboard /> : <MobileAmbulanceDashboard />;
};

export default AmbulanceDashboard;
