import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from '../config/api';
import { DashboardCard, LoadingSpinner, SimpleBarChart, SimpleLineChart, StatusPill } from './Common';
import { AllocationPredictor, AvailabilityPredictor, OutbreakForecast, PolicyAdvisor } from './GovernmentAI';
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import ReactFlow, { Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { useDataMode } from '../context/DataModeContext';

const severityColor = (value) => {
    const key = String(value || '').toLowerCase();
    if (key === 'critical' || key === 'high') return 'red';
    if (key === 'medium') return 'yellow';
    if (key === 'low') return 'green';
    return 'gray';
};

const impactColor = (value) => {
    const key = String(value || '').toLowerCase();
    if (key === 'high') return 'red';
    if (key === 'medium') return 'yellow';
    if (key === 'low') return 'green';
    return 'gray';
};

const formatNumber = (value) => (Number.isFinite(value) ? value : 0);

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const buildSeverityData = (feed) => {
    const buckets = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    feed.forEach((item) => {
        const key = String(item.severity || '').toLowerCase();
        if (key === 'critical') buckets.Critical += 1;
        else if (key === 'high') buckets.High += 1;
        else if (key === 'medium') buckets.Medium += 1;
        else if (key === 'low') buckets.Low += 1;
    });
    return Object.entries(buckets).map(([label, value]) => ({ label, value }));
};

const FEED_WINDOW_MINUTES = 120;
const FEED_LIMIT = 60;
const HOSPITAL_LIMIT = 60;
const MAX_MAP_POINTS = 80;
const VERIFICATION_FETCH_LIMIT = 120;
const VERIFICATION_RENDER_LIMIT = 60;
const VERIFICATION_PAGE_SIZE = 20;
const POLICY_PAGE_SIZE = 6;
const POLICY_RENDER_LIMIT = 36;
const POLICY_REFRESH_MS = 90000;

const normalizeFeed = (items, limit = FEED_LIMIT) => {
    const seen = new Set();
    const result = [];
    (items || []).forEach((item) => {
        const lat = Number(item.lat ?? item.latitude);
        const lng = Number(item.lng ?? item.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
        const key = item.id || item._id || `${lat.toFixed(5)}-${lng.toFixed(5)}-${item.occurred_at || ''}`;
        if (seen.has(key)) return;
        seen.add(key);
        result.push({ ...item, lat, lng });
    });
    return result.slice(0, limit);
};

const normalizeHospitals = (items, limit = HOSPITAL_LIMIT) => {
    const seen = new Set();
    const result = [];
    (items || []).forEach((item) => {
        const lat = Number(item.lat ?? item.latitude);
        const lng = Number(item.lng ?? item.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
        const key = item.id || item._id || `${lat.toFixed(5)}-${lng.toFixed(5)}-${item.name || ''}`;
        if (seen.has(key)) return;
        seen.add(key);
        result.push({ ...item, lat, lng });
    });
    return result.slice(0, limit);
};

const pickCenter = (points) => {
    if (!points || points.length === 0) return [12.9716, 77.5946];
    const lat = points[0].lat ?? points[0].latitude ?? 12.9716;
    const lng = points[0].lng ?? points[0].longitude ?? 77.5946;
    return [lat, lng];
};

const buildSimulationGraph = (phases, afterAction) => {
    const nodes = [];
    const edges = [];
    const centerNode = {
        id: 'sim-core',
        position: { x: 0, y: 0 },
        data: { label: 'Simulation Core' },
        style: {
            background: '#0f172a',
            color: '#fff',
            borderRadius: 12,
            padding: 10,
            fontSize: 12,
            fontWeight: 700,
        },
    };
    nodes.push(centerNode);

    const total = phases.length || 0;
    const radius = 190;
    phases.forEach((phase, index) => {
        const angle = (index / Math.max(total, 1)) * Math.PI * 2;
        const id = `phase-${index}`;
        nodes.push({
            id,
            position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
            data: { label: `${phase.name || `Phase ${index + 1}`}\n${phase.count} incidents` },
            style: {
                background: '#e0f2fe',
                color: '#0f172a',
                borderRadius: 12,
                padding: 8,
                fontSize: 11,
                fontWeight: 600,
                border: '1px solid #bae6fd',
                textAlign: 'center',
                whiteSpace: 'pre-line',
            },
        });
        edges.push({
            id: `edge-core-${id}`,
            source: centerNode.id,
            target: id,
            animated: true,
            style: { stroke: '#38bdf8', strokeWidth: 2 },
        });
    });

    if (afterAction?.summary) {
        nodes.push({
            id: 'after-action',
            position: { x: 0, y: -240 },
            data: { label: `After-Action\nCritical ${afterAction.summary.critical || 0}` },
            style: {
                background: '#fee2e2',
                color: '#7f1d1d',
                borderRadius: 12,
                padding: 10,
                fontSize: 11,
                fontWeight: 700,
                border: '1px solid #fecaca',
                textAlign: 'center',
                whiteSpace: 'pre-line',
            },
        });
        edges.push({
            id: 'edge-after-action',
            source: centerNode.id,
            target: 'after-action',
            animated: true,
            style: { stroke: '#fb7185', strokeWidth: 2 },
        });
    }

    return { nodes, edges };
};

const severityScore = (value) => {
    const key = String(value || '').toLowerCase();
    if (key === 'critical') return 4;
    if (key === 'high') return 3;
    if (key === 'medium') return 2;
    if (key === 'low') return 1;
    return 0;
};

const buildDisasterGraph = (recent) => {
    const counts = recent.reduce((acc, item) => {
        const key = String(item.severity || 'low');
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    const nodes = [
        {
            id: 'disaster-core',
            position: { x: 0, y: 0 },
            data: { label: 'Disaster Pulse' },
            style: {
                background: '#0f172a',
                color: '#fff',
                borderRadius: 14,
                padding: 10,
                fontSize: 12,
                fontWeight: 700,
            },
        },
    ];

    const severityKeys = ['Critical', 'High', 'Medium', 'Low'];
    const radius = 150;
    const edges = [];

    severityKeys.forEach((label, index) => {
        const id = `sev-${label.toLowerCase()}`;
        const angle = (index / severityKeys.length) * Math.PI * 2;
        nodes.push({
            id,
            position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
            data: { label: `${label}\n${counts[label] || 0}` },
            style: {
                background: '#f8fafc',
                color: '#0f172a',
                borderRadius: 12,
                padding: 8,
                fontSize: 11,
                fontWeight: 600,
                border: '1px solid #e2e8f0',
                textAlign: 'center',
                whiteSpace: 'pre-line',
            },
        });
        edges.push({
            id: `edge-${id}`,
            source: 'disaster-core',
            target: id,
            animated: true,
            style: { stroke: '#fb7185', strokeWidth: 2 },
        });
    });

    return { nodes, edges };
};

export const GovernmentCommandCenter = () => {
    const [overview, setOverview] = useState({ hospitals: 0, ambulances: 0, emergencies: 0 });
    const [decisions, setDecisions] = useState([]);
    const [anomaly, setAnomaly] = useState(null);
    const [loading, setLoading] = useState(true);
    const [seeding, setSeeding] = useState(false);
    const cacheKey = 'gov_command_cache';

    const load = async (withSpinner = false) => {
        const showSpinner = withSpinner === true;
        if (showSpinner) setLoading(true);
        try {
            const [overviewRes, decisionRes, anomalyRes] = await Promise.all([
                apiFetch('/v2/government/command/overview', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
                apiFetch('/v2/government/decision/engine', { method: 'POST' }),
                apiFetch('/v2/government/predictions/anomaly', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            ]);
            setOverview(overviewRes.ok ? overviewRes.data : { hospitals: 0, ambulances: 0, emergencies: 0 });
            setDecisions(decisionRes.ok ? (decisionRes.data?.decisions || []) : []);
            setAnomaly(anomalyRes.ok ? anomalyRes.data?.prediction : null);
            localStorage.setItem(cacheKey, JSON.stringify({
                overview: overviewRes.ok ? overviewRes.data : { hospitals: 0, ambulances: 0, emergencies: 0 },
                decisions: decisionRes.ok ? (decisionRes.data?.decisions || []) : [],
                anomaly: anomalyRes.ok ? anomalyRes.data?.prediction : null,
            }));

            const counts = overviewRes.ok ? overviewRes.data : null;
            if (counts && counts.hospitals === 0 && counts.ambulances === 0 && counts.emergencies === 0) {
                const seeded = sessionStorage.getItem('gov_seed_done');
                if (!seeded) {
                    sessionStorage.setItem('gov_seed_done', '1');
                    await apiFetch('/v2/government/command/seed', { method: 'POST', body: JSON.stringify({}) });
                    const seededOverview = await apiFetch('/v2/government/command/overview', { method: 'GET' });
                    if (seededOverview.ok) {
                        setOverview(seededOverview.data);
                    }
                }
            }
        } catch (err) {
            // preserve cached data on refresh errors
        } finally {
            if (showSpinner) setLoading(false);
        }
    };

    const handleSeed = async () => {
        setSeeding(true);
        try {
            await apiFetch('/v2/government/command/seed', { method: 'POST', body: JSON.stringify({}) });
            await load();
        } finally {
            setSeeding(false);
        }
    };

    useEffect(() => {
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setOverview(parsed.overview || { hospitals: 0, ambulances: 0, emergencies: 0 });
                setDecisions(parsed.decisions || []);
                setAnomaly(parsed.anomaly || null);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache errors
        }
        load(!hasCache);
    }, []);

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <p className="text-xs font-bold uppercase text-slate-500">Command Overview</p>
                        <p className="text-lg font-bold text-slate-800">System snapshot with AI decisions</p>
                    </div>
                    <div className="flex gap-2">
                        <button className="px-3 py-2 text-xs font-bold bg-slate-900 text-white rounded" onClick={() => load(true)}>
                            Refresh
                        </button>
                        <button className="px-3 py-2 text-xs font-bold bg-indigo-600 text-white rounded" onClick={handleSeed} disabled={seeding}>
                            {seeding ? 'Seeding...' : 'Seed Data'}
                        </button>
                    </div>
                </div>
            </DashboardCard>

            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <DashboardCard>
                        <p className="text-xs font-bold uppercase text-slate-500">Hospitals</p>
                        <p className="text-3xl font-black text-slate-900">{formatNumber(overview.hospitals)}</p>
                    </DashboardCard>
                    <DashboardCard>
                        <p className="text-xs font-bold uppercase text-slate-500">Ambulances</p>
                        <p className="text-3xl font-black text-slate-900">{formatNumber(overview.ambulances)}</p>
                    </DashboardCard>
                    <DashboardCard>
                        <p className="text-xs font-bold uppercase text-slate-500">Active Emergencies</p>
                        <p className="text-3xl font-black text-slate-900">{formatNumber(overview.emergencies)}</p>
                    </DashboardCard>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">Decision Engine</h3>
                    {decisions.length === 0 ? (
                        <p className="text-sm text-slate-500">No decisions generated yet.</p>
                    ) : (
                        <div className="space-y-3">
                            {decisions.map((item, idx) => (
                                <div key={`${item.event}-${idx}`} className="border rounded-lg p-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="font-semibold text-slate-800">{item.event}</p>
                                            <p className="text-xs text-slate-500">{item.location || 'Zone'} · {item.reason}</p>
                                        </div>
                                        <StatusPill text={item.impact} color={impactColor(item.impact)} />
                                    </div>
                                    <p className="text-sm text-slate-600 mt-2">{item.suggested_action}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </DashboardCard>
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">Anomaly Intelligence</h3>
                    {!anomaly ? (
                        <p className="text-sm text-slate-500">No anomalies detected in the last 24 hours.</p>
                    ) : (
                        <div className="space-y-3">
                            <p className="text-sm text-slate-600">Detected spikes at:</p>
                            <div className="flex flex-wrap gap-2">
                                {anomaly.anomaly_hours?.map((hour) => (
                                    <span key={hour} className="px-2 py-1 text-xs rounded-full bg-rose-100 text-rose-700 font-semibold">
                                        {hour}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </DashboardCard>
            </div>
        </div>
    );
};

export const GovernmentLiveMonitoring = () => {
    const [summary, setSummary] = useState(null);
    const [feed, setFeed] = useState([]);
    const [loading, setLoading] = useState(true);
    const [hospitals, setHospitals] = useState([]);
    const refreshInFlightRef = useRef(false);
    const mountedRef = useRef(false);
    const cacheKey = 'gov_live_cache';
    const disableLiveRefresh = true;

    const hospitalLoadData = useMemo(() => (
        hospitals.slice(0, 6).map((item) => ({
            label: item.name?.slice(0, 12) || 'Hospital',
            value: Math.round((item.load_score || 0) * 100),
        }))
    ), [hospitals]);

    const severityData = useMemo(() => buildSeverityData(feed), [feed]);
    const mapFeed = useMemo(() => feed.slice(0, MAX_MAP_POINTS), [feed]);
    const mapHospitals = useMemo(() => hospitals.slice(0, MAX_MAP_POINTS), [hospitals]);
    const feedCenter = useMemo(() => pickCenter(mapFeed), [mapFeed]);
    const hospitalCenter = useMemo(() => pickCenter(mapHospitals), [mapHospitals]);

    const load = async (withSpinner = false) => {
        const showSpinner = withSpinner === true;
        if (refreshInFlightRef.current) {
            if (showSpinner) setLoading(false);
            return;
        }
        refreshInFlightRef.current = true;
        if (showSpinner) {
            setLoading(true);
        }
        try {
            const [summaryRes, feedRes, hospitalsRes] = await Promise.all([
                apiFetch('/v2/government/monitoring/summary', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
                apiFetch(`/v2/government/monitoring/feed?limit=${FEED_LIMIT}&window_minutes=${FEED_WINDOW_MINUTES}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
                apiFetch(`/v2/government/resources/hospitals?limit=${HOSPITAL_LIMIT}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            ]);
            if (!mountedRef.current) return;
            setSummary(summaryRes.ok ? summaryRes.data : null);
            const feedData = feedRes.ok ? (feedRes.data?.data || []) : [];
            const normalizedFeed = normalizeFeed(feedData, FEED_LIMIT);
            setFeed(normalizedFeed);
            const hospitalData = hospitalsRes.ok ? (hospitalsRes.data?.data || []) : [];
            const normalizedHospitals = normalizeHospitals(hospitalData, HOSPITAL_LIMIT);
            setHospitals(normalizedHospitals);
            localStorage.setItem(cacheKey, JSON.stringify({
                summary: summaryRes.ok ? summaryRes.data : null,
                feed: normalizedFeed,
                hospitals: normalizedHospitals,
            }));

            if (summaryRes.ok && summaryRes.data?.active_emergencies === 0 && !sessionStorage.getItem('gov_seed_done')) {
                sessionStorage.setItem('gov_seed_done', '1');
                await apiFetch('/v2/government/command/seed', { method: 'POST', body: JSON.stringify({}) });
                const seededSummary = await apiFetch('/v2/government/monitoring/summary', { method: 'GET' });
                if (seededSummary.ok) {
                    if (!mountedRef.current) return;
                    setSummary(seededSummary.data);
                }
                const seededFeed = await apiFetch(`/v2/government/monitoring/feed?limit=${FEED_LIMIT}&window_minutes=${FEED_WINDOW_MINUTES}`, { method: 'GET' });
                if (seededFeed.ok) {
                    setFeed(normalizeFeed(seededFeed.data?.data || [], FEED_LIMIT));
                }
                const seededHospitals = await apiFetch(`/v2/government/resources/hospitals?limit=${HOSPITAL_LIMIT}`, { method: 'GET' });
                if (seededHospitals.ok) {
                    setHospitals(normalizeHospitals(seededHospitals.data?.data || [], HOSPITAL_LIMIT));
                }
            }
        } catch (err) {
            // preserve cached data on refresh errors
        } finally {
            refreshInFlightRef.current = false;
            if (showSpinner && mountedRef.current) {
                setLoading(false);
            }
        }
    };

    useEffect(() => {
        mountedRef.current = true;
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setSummary(parsed.summary || null);
                setFeed(normalizeFeed(parsed.feed || [], FEED_LIMIT));
                setHospitals(normalizeHospitals(parsed.hospitals || [], HOSPITAL_LIMIT));
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache failures
        }
        load(!hasCache);
        const interval = disableLiveRefresh ? null : setInterval(() => {
            load(false);
        }, 90000);
        return () => {
            mountedRef.current = false;
            if (interval) clearInterval(interval);
        };
    }, []);

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase text-slate-500">Live Monitoring</p>
                        <p className="text-lg font-bold text-slate-800">Operational feed and system health</p>
                    </div>
                    <button
                        className="px-3 py-2 text-xs font-bold bg-slate-300 text-slate-600 rounded cursor-not-allowed"
                        disabled
                        title="Live refresh paused"
                    >
                        Refresh paused
                    </button>
                </div>
            </DashboardCard>

            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <DashboardCard>
                        <p className="text-xs font-bold uppercase text-slate-500">Active Emergencies</p>
                        <p className="text-3xl font-black text-slate-900">{formatNumber(summary?.active_emergencies)}</p>
                    </DashboardCard>
                    <DashboardCard>
                        <p className="text-xs font-bold uppercase text-slate-500">Avg Response</p>
                        <p className="text-3xl font-black text-slate-900">{formatNumber(summary?.avg_response_minutes)}m</p>
                    </DashboardCard>
                    <DashboardCard>
                        <p className="text-xs font-bold uppercase text-slate-500">Resource Utilization</p>
                        <p className="text-3xl font-black text-slate-900">{formatNumber(summary?.resource_utilization)}%</p>
                    </DashboardCard>
                </div>
            )}

            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Incident Feed</h3>
                {feed.length === 0 ? (
                    <p className="text-sm text-slate-500">No incidents in the feed.</p>
                ) : (
                    <div className="max-h-[320px] overflow-y-auto pr-2 space-y-3">
                        {feed.map((item) => (
                            <div key={item.id} className="border rounded-lg p-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-slate-800">{item.type}</p>
                                        <p className="text-xs text-slate-500">{item.lat?.toFixed(3)}, {item.lng?.toFixed(3)}</p>
                                    </div>
                                    <StatusPill text={item.severity} color={severityColor(item.severity)} />
                                </div>
                                <p className="text-xs text-slate-500 mt-2">{item.occurred_at}</p>
                            </div>
                        ))}
                    </div>
                )}
            </DashboardCard>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <SimpleBarChart title="Severity Distribution" data={severityData} barColorClass="bg-red-500" />
                <DashboardCard className="p-0 overflow-hidden">
                    <div className="h-[380px] w-full">
                        <MapContainer center={feedCenter} zoom={10} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
                            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                            {mapFeed.map((item) => (
                                <Circle
                                    key={item.id || `${item.lat}-${item.lng}-${item.occurred_at || ''}`}
                                    center={[item.lat, item.lng]}
                                    radius={item.severity === 'Critical' ? 3500 : item.severity === 'High' ? 2500 : 1800}
                                    pathOptions={{ color: 'red', fillColor: 'red', fillOpacity: 0.3 }}
                                />
                            ))}
                        </MapContainer>
                    </div>
                </DashboardCard>
            </div>

            <DashboardCard className="p-0 overflow-hidden">
                <div className="h-[420px] w-full">
                    <MapContainer center={hospitalCenter} zoom={9} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
                        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                        {mapHospitals.map((item) => (
                            <Marker key={item.id || `${item.lat}-${item.lng}-${item.name || ''}`} position={[item.lat, item.lng]}>
                                <Popup>
                                    <div className="text-xs">
                                        <p className="font-semibold">{item.name}</p>
                                        <p>Beds: {item.beds_available}/{item.beds_total}</p>
                                        <p>Load: {Math.round(item.load_score * 100)}%</p>
                                    </div>
                                </Popup>
                            </Marker>
                        ))}
                    </MapContainer>
                </div>
            </DashboardCard>

            <SimpleBarChart title="Top Hospital Load" data={hospitalLoadData} barColorClass="bg-sky-500" />
        </div>
    );
};

export const GovernmentEVA = () => {
    const [query, setQuery] = useState('');
    const [execute, setExecute] = useState(false);
    const [response, setResponse] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleAsk = async (event) => {
        event.preventDefault();
        setLoading(true);
        try {
            const res = await apiFetch('/v2/government/ai/ask', {
                method: 'POST',
                body: JSON.stringify({ query, execute }),
            });
            setResponse(res.ok ? res.data : null);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-2">EVA Assistant</h3>
                <p className="text-sm text-slate-500 mb-4">Ask EVA for operational guidance. Enable execute to log a decision.</p>
                <form onSubmit={handleAsk} className="space-y-3">
                    <textarea
                        className="w-full border rounded-lg p-3 text-sm"
                        rows="3"
                        placeholder="Ask EVA about resource allocation, hotspots, or readiness."
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                    />
                    <label className="flex items-center gap-2 text-sm text-slate-600">
                        <input type="checkbox" checked={execute} onChange={(event) => setExecute(event.target.checked)} />
                        Execute decision in command log
                    </label>
                    <button className="px-4 py-2 text-sm font-bold bg-indigo-600 text-white rounded" disabled={loading}>
                        {loading ? 'Thinking...' : 'Ask EVA'}
                    </button>
                </form>
            </DashboardCard>

            {response?.decision && (
                <DashboardCard>
                    <h4 className="text-md font-bold text-slate-900 mb-2">EVA Recommendation</h4>
                    <div className="space-y-2">
                        <p className="text-sm"><span className="font-semibold">Event:</span> {response.decision.event}</p>
                        <p className="text-sm"><span className="font-semibold">Reason:</span> {response.decision.reason}</p>
                        <p className="text-sm"><span className="font-semibold">Suggested Action:</span> {response.decision.suggested_action}</p>
                        <p className="text-sm"><span className="font-semibold">Impact:</span> {response.decision.impact}</p>
                        <p className="text-xs text-slate-500">Executed: {response.executed ? 'Yes' : 'No'}</p>
                    </div>
                </DashboardCard>
            )}

            {response?.results && (
                <DashboardCard>
                    <h4 className="text-md font-bold text-slate-900 mb-2">Search Results</h4>
                    <div className="space-y-3 text-sm text-slate-600">
                        {response.results.hospitals?.length > 0 && (
                            <div>
                                <p className="text-xs font-bold uppercase text-slate-500">Hospitals</p>
                                {response.results.hospitals.map((item) => (
                                    <div key={item.id}>{item.name} · {item.city}</div>
                                ))}
                            </div>
                        )}
                        {response.results.ambulances?.length > 0 && (
                            <div>
                                <p className="text-xs font-bold uppercase text-slate-500">Ambulances</p>
                                {response.results.ambulances.map((item) => (
                                    <div key={item.id}>{item.code} · {item.status}</div>
                                ))}
                            </div>
                        )}
                        {response.results.emergencies?.length > 0 && (
                            <div>
                                <p className="text-xs font-bold uppercase text-slate-500">Emergencies</p>
                                {response.results.emergencies.map((item) => (
                                    <div key={item.id}>{item.type} · {item.severity}</div>
                                ))}
                            </div>
                        )}
                        {response.results.disasters?.length > 0 && (
                            <div>
                                <p className="text-xs font-bold uppercase text-slate-500">Disasters</p>
                                {response.results.disasters.map((item) => (
                                    <div key={item.id}>{item.type} · {item.zone}</div>
                                ))}
                            </div>
                        )}
                        {response.results.policies?.length > 0 && (
                            <div>
                                <p className="text-xs font-bold uppercase text-slate-500">Policies</p>
                                {response.results.policies.map((item) => (
                                    <div key={item.id}>{item.title} · {item.status}</div>
                                ))}
                            </div>
                        )}
                        {response.results.knowledge?.length > 0 && (
                            <div>
                                <p className="text-xs font-bold uppercase text-slate-500">Knowledge Base</p>
                                {response.results.knowledge.map((item) => (
                                    <div key={item.id}>{item.title} · {item.module}</div>
                                ))}
                            </div>
                        )}
                    </div>
                </DashboardCard>
            )}
        </div>
    );
};

export const GovernmentPolicyWorkflow = () => {
    const [decisions, setDecisions] = useState([]);
    const [anomaly, setAnomaly] = useState(null);
    const [policyActions, setPolicyActions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [policyPage, setPolicyPage] = useState(1);
    const cacheKey = 'gov_policy_cache';
    const seedKey = 'gov_policy_seeded';

    const load = async (withSpinner = false) => {
        const showSpinner = withSpinner === true;
        if (showSpinner) {
            setLoading(true);
        }
        try {
            const [decisionRes, anomalyRes] = await Promise.all([
                apiFetch('/v2/government/decision/engine', { method: 'POST', timeoutMs: 12000 }),
                apiFetch('/v2/government/predictions/anomaly', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
            ]);
            setDecisions(decisionRes.ok ? (decisionRes.data?.decisions || []) : []);
            setAnomaly(anomalyRes.ok ? anomalyRes.data?.prediction : null);
            const policyRes = await apiFetch(`/v2/government/policy/actions?limit=${POLICY_RENDER_LIMIT}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true });
            let nextPolicyItems = policyRes.ok ? (policyRes.data?.data || []) : [];
            setPolicyActions(nextPolicyItems);

            if (!nextPolicyItems.length && (decisionRes.data?.decisions || []).length && !sessionStorage.getItem(seedKey)) {
                sessionStorage.setItem(seedKey, '1');
                const seedPayloads = (decisionRes.data?.decisions || []).slice(0, 2).map((item) => ({
                    title: item.event,
                    action: item.suggested_action,
                    impact: item.impact,
                    status: 'Draft',
                }));
                const created = await Promise.all(seedPayloads.map((payload) => (
                    apiFetch('/v2/government/policy/actions', { method: 'POST', body: JSON.stringify(payload) })
                )));
                const createdItems = created.filter((res) => res.ok).map((res) => res.data);
                if (createdItems.length) {
                    nextPolicyItems = createdItems;
                    setPolicyActions(createdItems);
                }
            }

            sessionStorage.setItem(cacheKey, JSON.stringify({
                decisions: decisionRes.ok ? (decisionRes.data?.decisions || []) : [],
                anomaly: anomalyRes.ok ? anomalyRes.data?.prediction : null,
                policyActions: nextPolicyItems,
            }));
        } finally {
            if (showSpinner) {
                setLoading(false);
            }
        }
    };

    useEffect(() => {
        try {
            const cached = sessionStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setDecisions(parsed.decisions || []);
                setAnomaly(parsed.anomaly || null);
                setPolicyActions(parsed.policyActions || []);
                setLoading(false);
            }
        } catch (error) {
            return;
        }
        setPolicyPage(1);
        load(true);
    }, []);

    useEffect(() => {
        const interval = setInterval(() => {
            load(false);
        }, POLICY_REFRESH_MS);
        return () => clearInterval(interval);
    }, []);

    const addPolicyAction = async (decision) => {
        const res = await apiFetch('/v2/government/policy/actions', {
            method: 'POST',
            body: JSON.stringify({
                title: decision.event,
                action: decision.suggested_action,
                impact: decision.impact,
                status: 'Draft',
            }),
        });
        if (res.ok) {
            setPolicyActions((prev) => [res.data, ...prev]);
        }
    };

    const updatePolicyStatus = async (id, status) => {
        const res = await apiFetch(`/v2/government/policy/actions/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status }),
        });
        if (res.ok) {
            setPolicyActions((prev) => prev.map((item) => (item.id === id ? res.data : item)));
        }
    };

    const visiblePolicyActions = useMemo(
        () => policyActions.slice(0, Math.min(POLICY_RENDER_LIMIT, policyPage * POLICY_PAGE_SIZE)),
        [policyActions, policyPage]
    );

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase text-slate-500">Policy Workflow</p>
                        <p className="text-lg font-bold text-slate-800">Translate AI insights into governance actions.</p>
                    </div>
                    <button className="px-3 py-2 text-xs font-bold bg-slate-900 text-white rounded" onClick={() => load(true)}>
                        Refresh
                    </button>
                </div>
            </DashboardCard>

            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <DashboardCard>
                        <h3 className="text-lg font-bold text-slate-900 mb-3">Decision-to-Policy</h3>
                        {decisions.length === 0 ? (
                            <p className="text-sm text-slate-500">No decisions generated yet.</p>
                        ) : (
                            <div className="space-y-3">
                                {decisions.map((item, idx) => (
                                    <div key={`${item.event}-${idx}`} className="border rounded-lg p-3">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <p className="font-semibold text-slate-800">{item.event}</p>
                                                <p className="text-xs text-slate-500">{item.reason}</p>
                                            </div>
                                            <StatusPill text={item.impact} color={impactColor(item.impact)} />
                                        </div>
                                        <div className="flex items-center justify-between mt-2">
                                            <p className="text-sm text-slate-600">{item.suggested_action}</p>
                                            <button className="text-xs font-semibold text-indigo-600" onClick={() => addPolicyAction(item)}>
                                                Create Policy Action
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </DashboardCard>
                    <DashboardCard>
                        <h3 className="text-lg font-bold text-slate-900 mb-3">Anomaly Watch</h3>
                        {!anomaly ? (
                            <p className="text-sm text-slate-500">No anomalies detected.</p>
                        ) : (
                            <div className="space-y-2">
                                <p className="text-sm text-slate-600">Anomalous hours flagged:</p>
                                <div className="flex flex-wrap gap-2">
                                    {anomaly.anomaly_hours?.map((hour) => (
                                        <span key={hour} className="px-2 py-1 text-xs rounded-full bg-amber-100 text-amber-700 font-semibold">
                                            {hour}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </DashboardCard>
                </div>
            )}
            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Policy Workflow Board</h3>
                    {policyActions.length === 0 ? (
                    <p className="text-sm text-slate-500">No policy actions created yet.</p>
                ) : (
                    <div className="space-y-3">
                        {visiblePolicyActions.map((item) => (
                            <div key={item.id} className="border rounded-lg p-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-slate-800">{item.title}</p>
                                        <p className="text-xs text-slate-500">{item.action}</p>
                                    </div>
                                    <StatusPill text={item.status} color={item.status === 'Approved' ? 'green' : 'yellow'} />
                                </div>
                                <div className="flex gap-2 mt-2">
                                    <button className="text-xs text-indigo-600" onClick={() => updatePolicyStatus(item.id, 'In Review')}>
                                        Send to Review
                                    </button>
                                    <button className="text-xs text-green-600" onClick={() => updatePolicyStatus(item.id, 'Approved')}>
                                        Approve
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                    {policyActions.length > visiblePolicyActions.length && (
                        <div className="mt-3 flex justify-center">
                            <button
                                className="text-xs font-semibold text-slate-600 px-3 py-2 rounded bg-slate-100 hover:bg-slate-200"
                                onClick={() => setPolicyPage((prev) => prev + 1)}
                            >
                                Load more
                            </button>
                        </div>
                    )}
            </DashboardCard>
        </div>
    );
};

export const GovernmentVerificationCenter = ({ subRole }) => {
    const [pending, setPending] = useState([]);
    const [hospitals, setHospitals] = useState([]);
    const [ambulances, setAmbulances] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);
    const [pendingPage, setPendingPage] = useState(1);
    const [verifiedHospitalPage, setVerifiedHospitalPage] = useState(1);
    const [waitingHospitalPage, setWaitingHospitalPage] = useState(1);
    const [verifiedAmbulancePage, setVerifiedAmbulancePage] = useState(1);
    const [waitingAmbulancePage, setWaitingAmbulancePage] = useState(1);
    const isDistrict = String(subRole || '').toLowerCase() === 'district_admin';
    const cacheKey = 'gov_verification_cache';

    const loadAll = async (withSpinner = false) => {
        if (withSpinner) setLoading(true);
        try {
            const [hospitalRes, ambulanceRes, pendingRes] = await Promise.all([
                apiFetch(`/v2/government/resources/hospitals?limit=${VERIFICATION_FETCH_LIMIT}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
                apiFetch(`/v2/government/resources/ambulances?limit=${VERIFICATION_FETCH_LIMIT}`, { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }),
                isDistrict ? apiFetch('/v2/government/verification/pending', { method: 'GET', ttlMs: 90000, staleWhileRevalidate: true }) : Promise.resolve(null),
            ]);
            setHospitals(hospitalRes.ok ? (hospitalRes.data?.data || []) : []);
            setAmbulances(ambulanceRes.ok ? (ambulanceRes.data?.data || []) : []);
            setPending(isDistrict && pendingRes?.ok ? (pendingRes.data?.data || []) : []);
            localStorage.setItem(cacheKey, JSON.stringify({
                hospitals: hospitalRes.ok ? (hospitalRes.data?.data || []) : [],
                ambulances: ambulanceRes.ok ? (ambulanceRes.data?.data || []) : [],
                pending: isDistrict && pendingRes?.ok ? (pendingRes.data?.data || []) : [],
            }));
        } finally {
            if (withSpinner) setLoading(false);
        }
    };

    useEffect(() => {
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setHospitals(parsed.hospitals || []);
                setAmbulances(parsed.ambulances || []);
                setPending(parsed.pending || []);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache failures
        }
        setPendingPage(1);
        setVerifiedHospitalPage(1);
        setWaitingHospitalPage(1);
        setVerifiedAmbulancePage(1);
        setWaitingAmbulancePage(1);
        loadAll(!hasCache);
    }, [isDistrict]);

    const approveRequest = async (id) => {
        const res = await apiFetch(`/v2/government/verification/${id}/approve`, { method: 'POST' });
        if (res.ok) {
            await loadAll(true);
        }
    };

    const rejectRequest = async (id) => {
        const res = await apiFetch(`/v2/government/verification/${id}/reject`, {
            method: 'POST',
            body: JSON.stringify({ notes: 'Rejected by compliance team.' }),
        });
        if (res.ok) {
            await loadAll(true);
        }
    };

    const pendingIndex = useMemo(() => new Set(pending.map((item) => `${item.entity_type}:${item.entity_id}`)), [pending]);
    const hospitalMap = useMemo(() => new Map(hospitals.map((item) => [item.id, item])), [hospitals]);
    const ambulanceMap = useMemo(() => new Map(ambulances.map((item) => [item.id, item])), [ambulances]);
    const pendingDetails = useMemo(() => (
        pending.map((item) => {
            const entity = item.entity_type === 'hospital'
                ? hospitalMap.get(item.entity_id)
                : ambulanceMap.get(item.entity_id);
            return { ...item, entity };
        })
    ), [pending, hospitalMap, ambulanceMap]);

    const verifiedHospitals = useMemo(() => hospitals.filter((item) => item.verified), [hospitals]);
    const waitingHospitals = useMemo(() => hospitals.filter((item) => !item.verified), [hospitals]);
    const verifiedAmbulances = useMemo(() => ambulances.filter((item) => item.verified), [ambulances]);
    const waitingAmbulances = useMemo(() => ambulances.filter((item) => !item.verified), [ambulances]);

    const visiblePending = useMemo(() => pendingDetails.slice(0, pendingPage * VERIFICATION_PAGE_SIZE), [pendingDetails, pendingPage]);
    const visibleVerifiedHospitals = useMemo(
        () => verifiedHospitals.slice(0, Math.min(VERIFICATION_RENDER_LIMIT, verifiedHospitalPage * VERIFICATION_PAGE_SIZE)),
        [verifiedHospitals, verifiedHospitalPage]
    );
    const visibleWaitingHospitals = useMemo(
        () => waitingHospitals.slice(0, Math.min(VERIFICATION_RENDER_LIMIT, waitingHospitalPage * VERIFICATION_PAGE_SIZE)),
        [waitingHospitals, waitingHospitalPage]
    );
    const visibleVerifiedAmbulances = useMemo(
        () => verifiedAmbulances.slice(0, Math.min(VERIFICATION_RENDER_LIMIT, verifiedAmbulancePage * VERIFICATION_PAGE_SIZE)),
        [verifiedAmbulances, verifiedAmbulancePage]
    );
    const visibleWaitingAmbulances = useMemo(
        () => waitingAmbulances.slice(0, Math.min(VERIFICATION_RENDER_LIMIT, waitingAmbulancePage * VERIFICATION_PAGE_SIZE)),
        [waitingAmbulances, waitingAmbulancePage]
    );

    const statusFor = (entity, type) => {
        if (entity?.verified) return { label: 'Verified', color: 'green' };
        const key = `${type}:${entity?.id}`;
        if (pendingIndex.has(key)) return { label: 'Pending', color: 'yellow' };
        return { label: 'Unverified', color: 'gray' };
    };

    const openDetails = (entity, type, request = null) => {
        if (!entity && !request) return;
        setSelected({ type, entity, request });
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">Verification Center</h3>
                        <p className="text-xs text-slate-500">Track pending requests and verified assets.</p>
                    </div>
                    <button className="px-3 py-2 text-xs font-bold bg-slate-900 text-white rounded" onClick={() => loadAll(true)}>
                        Refresh
                    </button>
                </div>
            </DashboardCard>

            {isDistrict && (
                <DashboardCard>
                    <div className="flex items-center justify-between mb-3">
                        <h3 className="text-lg font-bold text-slate-900">Pending Approvals</h3>
                    </div>
                    {loading ? (
                        <LoadingSpinner />
                    ) : pending.length === 0 ? (
                        <p className="text-sm text-slate-500">No pending verifications.</p>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                            {visiblePending.map((item) => {
                                const entityLabel = item.entity?.name || item.entity?.code || item.entity_id;
                                const status = statusFor(item.entity || { id: item.entity_id }, item.entity_type);
                                return (
                                    <div key={item.id} className="border rounded-lg p-4 bg-white hover:border-slate-300 transition">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <p className="font-semibold text-slate-800">{entityLabel}</p>
                                                <p className="text-xs text-slate-500">{item.entity_type} · {item.entity_id}</p>
                                            </div>
                                            <StatusPill text={status.label} color={status.color} />
                                        </div>
                                        <p className="text-xs text-slate-500 mt-2">{item.notes || 'No notes provided.'}</p>
                                        <div className="flex flex-wrap gap-2 mt-3">
                                            <button className="text-xs font-semibold text-slate-700" onClick={() => openDetails(item.entity, item.entity_type, item)}>
                                                View details
                                            </button>
                                            <button className="text-xs font-semibold text-green-600" onClick={() => approveRequest(item.id)}>
                                                Approve
                                            </button>
                                            <button className="text-xs font-semibold text-rose-600" onClick={() => rejectRequest(item.id)}>
                                                Reject
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                    {pendingDetails.length > visiblePending.length && (
                        <div className="mt-4 flex justify-center">
                            <button
                                className="text-xs font-semibold text-slate-600 px-3 py-2 rounded bg-slate-100 hover:bg-slate-200"
                                onClick={() => setPendingPage((prev) => prev + 1)}
                            >
                                Load more
                            </button>
                        </div>
                    )}
                </DashboardCard>
            )}

            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Verified Hospitals</h3>
                {loading ? (
                    <LoadingSpinner />
                ) : verifiedHospitals.length === 0 ? (
                    <p className="text-sm text-slate-500">No verified hospitals yet.</p>
                ) : (
                    <div className="max-h-[320px] overflow-y-auto pr-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {visibleVerifiedHospitals.map((item) => (
                            <div
                                key={item.id}
                                className="border rounded-lg p-4 bg-white hover:border-slate-300 transition cursor-pointer"
                                onClick={() => openDetails(item, 'hospital')}
                            >
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-slate-800">{item.name}</p>
                                        <p className="text-xs text-slate-500">{item.city}, {item.state}</p>
                                    </div>
                                    <StatusPill text="Verified" color="green" />
                                </div>
                                <p className="text-xs text-slate-500 mt-2">Beds: {item.beds_available}/{item.beds_total} · Load {Math.round((item.load_score || 0) * 100)}%</p>
                            </div>
                        ))}
                    </div>
                )}
                {verifiedHospitals.length > visibleVerifiedHospitals.length && (
                    <div className="mt-3 flex justify-center">
                        <button
                            className="text-xs font-semibold text-slate-600 px-3 py-2 rounded bg-slate-100 hover:bg-slate-200"
                            onClick={() => setVerifiedHospitalPage((prev) => prev + 1)}
                        >
                            Load more
                        </button>
                    </div>
                )}
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Hospitals Waiting for Verification</h3>
                {loading ? (
                    <LoadingSpinner />
                ) : waitingHospitals.length === 0 ? (
                    <p className="text-sm text-slate-500">All hospitals are verified.</p>
                ) : (
                    <div className="max-h-[320px] overflow-y-auto pr-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {visibleWaitingHospitals.map((item) => {
                            const status = statusFor(item, 'hospital');
                            return (
                                <div
                                    key={item.id}
                                    className="border rounded-lg p-4 bg-white hover:border-slate-300 transition cursor-pointer"
                                    onClick={() => openDetails(item, 'hospital')}
                                >
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="font-semibold text-slate-800">{item.name}</p>
                                            <p className="text-xs text-slate-500">{item.city}, {item.state}</p>
                                        </div>
                                        <StatusPill text={status.label} color={status.color} />
                                    </div>
                                    <p className="text-xs text-slate-500 mt-2">Beds: {item.beds_available}/{item.beds_total} · Load {Math.round((item.load_score || 0) * 100)}%</p>
                                </div>
                            );
                        })}
                    </div>
                )}
                {waitingHospitals.length > visibleWaitingHospitals.length && (
                    <div className="mt-3 flex justify-center">
                        <button
                            className="text-xs font-semibold text-slate-600 px-3 py-2 rounded bg-slate-100 hover:bg-slate-200"
                            onClick={() => setWaitingHospitalPage((prev) => prev + 1)}
                        >
                            Load more
                        </button>
                    </div>
                )}
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Verified Ambulances</h3>
                {loading ? (
                    <LoadingSpinner />
                ) : verifiedAmbulances.length === 0 ? (
                    <p className="text-sm text-slate-500">No verified ambulances yet.</p>
                ) : (
                    <div className="max-h-[320px] overflow-y-auto pr-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {visibleVerifiedAmbulances.map((item) => (
                            <div
                                key={item.id}
                                className="border rounded-lg p-4 bg-white hover:border-slate-300 transition cursor-pointer"
                                onClick={() => openDetails(item, 'ambulance')}
                            >
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-slate-800">{item.code}</p>
                                        <p className="text-xs text-slate-500">Status: {item.status}</p>
                                    </div>
                                    <StatusPill text="Verified" color="green" />
                                </div>
                                <p className="text-xs text-slate-500 mt-2">Lat {item.lat?.toFixed(3)} · Lng {item.lng?.toFixed(3)}</p>
                            </div>
                        ))}
                    </div>
                )}
                {verifiedAmbulances.length > visibleVerifiedAmbulances.length && (
                    <div className="mt-3 flex justify-center">
                        <button
                            className="text-xs font-semibold text-slate-600 px-3 py-2 rounded bg-slate-100 hover:bg-slate-200"
                            onClick={() => setVerifiedAmbulancePage((prev) => prev + 1)}
                        >
                            Load more
                        </button>
                    </div>
                )}
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Ambulances Waiting for Verification</h3>
                {loading ? (
                    <LoadingSpinner />
                ) : waitingAmbulances.length === 0 ? (
                    <p className="text-sm text-slate-500">All ambulances are verified.</p>
                ) : (
                    <div className="max-h-[320px] overflow-y-auto pr-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {visibleWaitingAmbulances.map((item) => {
                            const status = statusFor(item, 'ambulance');
                            return (
                                <div
                                    key={item.id}
                                    className="border rounded-lg p-4 bg-white hover:border-slate-300 transition cursor-pointer"
                                    onClick={() => openDetails(item, 'ambulance')}
                                >
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="font-semibold text-slate-800">{item.code}</p>
                                            <p className="text-xs text-slate-500">Status: {item.status}</p>
                                        </div>
                                        <StatusPill text={status.label} color={status.color} />
                                    </div>
                                    <p className="text-xs text-slate-500 mt-2">Lat {item.lat?.toFixed(3)} · Lng {item.lng?.toFixed(3)}</p>
                                </div>
                            );
                        })}
                    </div>
                )}
                {waitingAmbulances.length > visibleWaitingAmbulances.length && (
                    <div className="mt-3 flex justify-center">
                        <button
                            className="text-xs font-semibold text-slate-600 px-3 py-2 rounded bg-slate-100 hover:bg-slate-200"
                            onClick={() => setWaitingAmbulancePage((prev) => prev + 1)}
                        >
                            Load more
                        </button>
                    </div>
                )}
            </DashboardCard>

            {selected && (
                <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl w-full max-w-2xl shadow-xl">
                        <div className="flex items-center justify-between px-6 py-4 border-b">
                            <div>
                                <p className="text-xs text-slate-500 uppercase">Verification Detail</p>
                                <h4 className="text-lg font-bold text-slate-900">{selected.entity?.name || selected.entity?.code || selected.request?.entity_id}</h4>
                            </div>
                            <button className="text-slate-400 hover:text-slate-700" onClick={() => setSelected(null)}>
                                <i className="fas fa-times"></i>
                            </button>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-700">
                                <div>
                                    <p className="text-xs uppercase text-slate-400">Entity Type</p>
                                    <p className="font-semibold">{selected.type}</p>
                                </div>
                                <div>
                                    <p className="text-xs uppercase text-slate-400">Entity ID</p>
                                    <p className="font-semibold">{selected.entity?.id || selected.request?.entity_id}</p>
                                </div>
                                {selected.type === 'hospital' && selected.entity && (
                                    <>
                                        <div>
                                            <p className="text-xs uppercase text-slate-400">Location</p>
                                            <p className="font-semibold">{selected.entity.city}, {selected.entity.state}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs uppercase text-slate-400">Beds</p>
                                            <p className="font-semibold">{selected.entity.beds_available}/{selected.entity.beds_total}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs uppercase text-slate-400">Load Score</p>
                                            <p className="font-semibold">{Math.round((selected.entity.load_score || 0) * 100)}%</p>
                                        </div>
                                    </>
                                )}
                                {selected.type === 'ambulance' && selected.entity && (
                                    <>
                                        <div>
                                            <p className="text-xs uppercase text-slate-400">Status</p>
                                            <p className="font-semibold">{selected.entity.status}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs uppercase text-slate-400">Coordinates</p>
                                            <p className="font-semibold">{selected.entity.lat?.toFixed(3)}, {selected.entity.lng?.toFixed(3)}</p>
                                        </div>
                                    </>
                                )}
                            </div>
                            {selected.request?.notes && (
                                <div className="bg-slate-50 border rounded-lg p-3 text-sm text-slate-600">
                                    <p className="text-xs uppercase text-slate-400">Request Notes</p>
                                    <p className="mt-1">{selected.request.notes}</p>
                                </div>
                            )}
                            {isDistrict && selected.request && (
                                <div className="flex gap-2">
                                    <button className="px-3 py-2 text-xs font-bold bg-emerald-600 text-white rounded" onClick={() => approveRequest(selected.request.id)}>
                                        Approve
                                    </button>
                                    <button className="px-3 py-2 text-xs font-bold bg-rose-600 text-white rounded" onClick={() => rejectRequest(selected.request.id)}>
                                        Reject
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export const GovernmentDisasterCenter = () => {
    const [recent, setRecent] = useState([]);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ type: 'manual', zone: 'Zone A', severity: 'High', reason: '' });
    const [broadcastMessage, setBroadcastMessage] = useState('Evacuate priority zones and activate disaster response.');
    const [center, setCenter] = useState([12.9716, 77.5946]);
    const [activeTab, setActiveTab] = useState('control');
    const [actionLog, setActionLog] = useState(null);
    const [history, setHistory] = useState(() => {
        const cached = localStorage.getItem('gov_disaster_history');
        if (cached) {
            try {
                return JSON.parse(cached);
            } catch (error) {
                return [];
            }
        }
        return [
            { id: 'hist-1', action: 'Cluster Scan', detail: 'No cluster above threshold', status: 'clear', time: 'Earlier today' },
            { id: 'hist-2', action: 'Manual Trigger', detail: 'Flood warning in Zone B', status: 'alert', time: 'Yesterday' },
            { id: 'hist-3', action: 'Broadcast', detail: 'Evacuation notice pushed', status: 'broadcast', time: '2 days ago' },
        ];
    });

    const disasterGraph = useMemo(() => buildDisasterGraph(recent), [recent]);
    const trendData = useMemo(() => {
        const items = recent.slice(0, 7).reverse();
        if (!items.length) return [{ label: 'T-0', value: 0 }];
        return items.map((item, idx) => ({
            label: `T-${items.length - idx}`,
            value: severityScore(item.severity),
        }));
    }, [recent]);

    const pushHistory = (entry) => {
        setHistory((prev) => {
            const next = [entry, ...prev].slice(0, 25);
            localStorage.setItem('gov_disaster_history', JSON.stringify(next));
            return next;
        });
    };

    const loadRecent = async () => {
        setLoading(true);
        const res = await apiFetch('/v2/government/disaster/recent', { method: 'GET' });
        setRecent(res.ok ? (res.data?.data || []) : []);
        setLoading(false);
    };

    useEffect(() => {
        loadRecent();
        navigator.geolocation.getCurrentPosition(
            (pos) => setCenter([pos.coords.latitude, pos.coords.longitude]),
            () => null,
        );
    }, []);

    const detectCluster = async () => {
        const res = await apiFetch('/v2/government/disaster/detect', { method: 'POST' });
        if (res.ok) {
            const entry = res.data?.disaster
                ? { id: `hist-${Date.now()}`, action: 'Cluster Scan', detail: `Cluster detected: ${res.data.disaster.type} (${res.data.disaster.severity})`, status: 'alert', time: new Date().toLocaleString() }
                : { id: `hist-${Date.now()}`, action: 'Cluster Scan', detail: 'No cluster above threshold', status: 'clear', time: new Date().toLocaleString() };
            setActionLog(entry);
            pushHistory(entry);
            loadRecent();
        }
    };

    const triggerManual = async () => {
        const res = await apiFetch('/v2/government/disaster/trigger', {
            method: 'POST',
            body: JSON.stringify({ ...form, lat: center[0], lng: center[1] }),
        });
        if (res.ok) {
            const entry = {
                id: `hist-${Date.now()}`,
                action: 'Manual Trigger',
                detail: `${form.type || 'Manual'} · ${form.zone} · ${form.severity}`,
                status: 'alert',
                time: new Date().toLocaleString(),
            };
            setActionLog(entry);
            pushHistory(entry);
            loadRecent();
        }
    };

    const broadcast = async () => {
        const res = await apiFetch('/v2/government/disaster/broadcast', {
            method: 'POST',
            body: JSON.stringify({ message: broadcastMessage }),
        });
        if (res.ok) {
            const entry = {
                id: `hist-${Date.now()}`,
                action: 'Broadcast',
                detail: broadcastMessage,
                status: 'broadcast',
                time: new Date().toLocaleString(),
            };
            setActionLog(entry);
            pushHistory(entry);
        }
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase text-slate-500">Disaster Management</p>
                        <p className="text-lg font-bold text-slate-800">Detect clusters, trigger events, broadcast actions.</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            className={`px-3 py-2 text-xs font-bold rounded ${activeTab === 'control' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'}`}
                            onClick={() => setActiveTab('control')}
                        >
                            Control
                        </button>
                        <button
                            className={`px-3 py-2 text-xs font-bold rounded ${activeTab === 'history' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'}`}
                            onClick={() => setActiveTab('history')}
                        >
                            History
                        </button>
                        <button className="px-3 py-2 text-xs font-bold bg-slate-900 text-white rounded" onClick={() => loadRecent()}>
                            Refresh
                        </button>
                    </div>
                </div>
            </DashboardCard>

            {activeTab === 'history' ? (
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">Action History</h3>
                    {history.length === 0 ? (
                        <p className="text-sm text-slate-500">No disaster activity logged yet.</p>
                    ) : (
                        <div className="max-h-[360px] overflow-y-auto pr-2 space-y-3">
                            {history.map((item) => (
                                <div key={item.id} className="border rounded-lg p-3 bg-white">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="font-semibold text-slate-800">{item.action}</p>
                                            <p className="text-xs text-slate-500">{item.detail}</p>
                                        </div>
                                        <StatusPill
                                            text={item.status === 'broadcast' ? 'Broadcast' : item.status === 'alert' ? 'Alert' : 'Clear'}
                                            color={item.status === 'alert' ? 'red' : item.status === 'broadcast' ? 'blue' : 'green'}
                                        />
                                    </div>
                                    <p className="text-[11px] text-slate-400 mt-2">{item.time}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </DashboardCard>
            ) : null}

            {activeTab === 'control' ? (
                <>
                    {actionLog && (
                        <DashboardCard>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Last Action Result</h3>
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="font-semibold text-slate-800">{actionLog.action}</p>
                                    <p className="text-xs text-slate-500">{actionLog.detail}</p>
                                </div>
                                <StatusPill
                                    text={actionLog.status === 'broadcast' ? 'Broadcast' : actionLog.status === 'alert' ? 'Alert' : 'Clear'}
                                    color={actionLog.status === 'alert' ? 'red' : actionLog.status === 'broadcast' ? 'blue' : 'green'}
                                />
                            </div>
                            <p className="text-[11px] text-slate-400 mt-2">{actionLog.time}</p>
                        </DashboardCard>
                    )}

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">Cluster Detection</h3>
                    <p className="text-sm text-slate-500 mb-3">Run detection on active emergencies to identify disaster zones.</p>
                    <button className="px-3 py-2 text-xs font-bold bg-rose-600 text-white rounded" onClick={detectCluster}>
                        Detect Disaster Cluster
                    </button>
                </DashboardCard>
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">Manual Trigger</h3>
                    <div className="grid grid-cols-1 gap-2">
                        <input
                            className="border rounded p-2 text-sm"
                            placeholder="Disaster type"
                            value={form.type}
                            onChange={(event) => setForm({ ...form, type: event.target.value })}
                        />
                        <input
                            className="border rounded p-2 text-sm"
                            placeholder="Zone"
                            value={form.zone}
                            onChange={(event) => setForm({ ...form, zone: event.target.value })}
                        />
                        <select
                            className="border rounded p-2 text-sm"
                            value={form.severity}
                            onChange={(event) => setForm({ ...form, severity: event.target.value })}
                        >
                            <option value="Low">Low</option>
                            <option value="Medium">Medium</option>
                            <option value="High">High</option>
                            <option value="Critical">Critical</option>
                        </select>
                        <textarea
                            className="border rounded p-2 text-sm"
                            rows="2"
                            placeholder="Reason"
                            value={form.reason}
                            onChange={(event) => setForm({ ...form, reason: event.target.value })}
                        />
                        <button className="px-3 py-2 text-xs font-bold bg-indigo-600 text-white rounded" onClick={triggerManual}>
                            Trigger Disaster
                        </button>
                    </div>
                </DashboardCard>
                    </div>

                    <DashboardCard>
                        <h3 className="text-lg font-bold text-slate-900 mb-3">Broadcast Alert</h3>
                        <div className="flex flex-col gap-2">
                            <textarea
                                className="border rounded p-2 text-sm"
                                rows="2"
                                value={broadcastMessage}
                                onChange={(event) => setBroadcastMessage(event.target.value)}
                            />
                            <button className="px-3 py-2 text-xs font-bold bg-slate-900 text-white rounded" onClick={broadcast}>
                                Broadcast Message
                            </button>
                        </div>
                    </DashboardCard>

                    <DashboardCard>
                        <h3 className="text-lg font-bold text-slate-900 mb-3">Recent Disasters</h3>
                        {loading ? (
                            <LoadingSpinner />
                        ) : recent.length === 0 ? (
                            <p className="text-sm text-slate-500">No disaster events logged.</p>
                        ) : (
                            <div className="max-h-[320px] overflow-y-auto pr-2 space-y-2">
                                {recent.map((item) => (
                                    <div key={item.id} className="border rounded-lg p-3">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <p className="font-semibold text-slate-800">{item.disaster_type}</p>
                                                <p className="text-xs text-slate-500">{item.zone} · {item.started_at}</p>
                                            </div>
                                            <StatusPill text={item.severity} color={severityColor(item.severity)} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </DashboardCard>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <DashboardCard>
                            <h3 className="text-lg font-bold text-slate-900 mb-3">Disaster Graph</h3>
                            <div className="h-[240px] border rounded-lg bg-white">
                                {disasterGraph.nodes.length === 0 ? (
                                    <div className="h-full flex items-center justify-center text-sm text-slate-400">
                                        Disaster signals will appear after events are logged.
                                    </div>
                                ) : (
                                    <ReactFlow
                                        nodes={disasterGraph.nodes}
                                        edges={disasterGraph.edges}
                                        fitView
                                        nodesDraggable={false}
                                        nodesConnectable={false}
                                        zoomOnScroll={false}
                                        style={{ width: '100%', height: '100%' }}
                                    >
                                        <Background color="#e2e8f0" gap={16} />
                                        <Controls showInteractive={false} />
                                    </ReactFlow>
                                )}
                            </div>
                        </DashboardCard>
                        <SimpleLineChart title="Severity Trend" data={trendData} lineColor="rgba(244, 63, 94, 0.9)" />
                    </div>

                    <DashboardCard className="p-0 overflow-hidden">
                        <div className="h-[420px] w-full">
                            <MapContainer center={center} zoom={7} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
                                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                                {recent.map((item) => (
                                    item.lat && item.lng ? (
                                        <Marker key={item.id} position={[item.lat, item.lng]}>
                                            <Popup>
                                                <div className="text-xs">
                                                    <p className="font-semibold">{item.disaster_type}</p>
                                                    <p>{item.zone}</p>
                                                    <p>Severity: {item.severity}</p>
                                                </div>
                                            </Popup>
                                        </Marker>
                                    ) : null
                                ))}
                            </MapContainer>
                        </div>
                    </DashboardCard>
                </>
            ) : null}
        </div>
    );
};

export const GovernmentAIMLHub = () => (
    <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <OutbreakForecast />
            <AllocationPredictor />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <PolicyAdvisor />
            <AvailabilityPredictor />
        </div>
    </div>
);

export const GovernmentSimulationCenter = () => {
    const [sessionId, setSessionId] = useState('');
    const [phaseForm, setPhaseForm] = useState({ name: '', intensity: 'medium', count: 40, duration: 25 });
    const [phases, setPhases] = useState([]);
    const [afterAction, setAfterAction] = useState(null);
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('control');
    const { mode } = useDataMode();
    const [history, setHistory] = useState(() => {
        const cached = localStorage.getItem('gov_simulation_history');
        if (cached) {
            try {
                return JSON.parse(cached);
            } catch (error) {
                return [];
            }
        }
        return [
            { id: 'sim-1', action: 'Multi-phase run', detail: '3 phases, medium intensity', status: 'complete', time: 'Earlier today' },
            { id: 'sim-2', action: 'After-action report', detail: 'Critical count improved 12%', status: 'report', time: 'Yesterday' },
        ];
    });
    const demoPhases = useMemo(() => ([
        { name: 'Stability Check', intensity: 'low', count: 22, duration: 12 },
        { name: 'Surge Wave', intensity: 'high', count: 58, duration: 28 },
        { name: 'Recovery', intensity: 'medium', count: 40, duration: 22 },
    ]), []);
    const activePhases = useMemo(() => (
        (mode === 'demo' && phases.length === 0) ? demoPhases : phases
    ), [mode, phases, demoPhases]);
    const phaseSeries = useMemo(() => (
        activePhases.map((phase, index) => ({
            label: phase.name || `Phase ${index + 1}`,
            value: Number(phase.count) || 0,
        }))
    ), [activePhases]);
    const simulationGraph = useMemo(() => buildSimulationGraph(activePhases, afterAction), [activePhases, afterAction]);

    const pushHistory = (entry) => {
        setHistory((prev) => {
            const next = [entry, ...prev].slice(0, 25);
            localStorage.setItem('gov_simulation_history', JSON.stringify(next));
            return next;
        });
    };

    const addPhase = () => {
        if (!phaseForm.name) return;
        setPhases((prev) => [...prev, { ...phaseForm }]);
        setPhaseForm({ name: '', intensity: 'medium', count: 40, duration: 25 });
    };

    const startSession = async () => {
        if (mode === 'demo') {
            const demoId = `demo-sim-${Date.now()}`;
            setSessionId(demoId);
            pushHistory({
                id: `sim-${Date.now()}`,
                action: 'Session started',
                detail: `Session ${demoId}`,
                status: 'running',
                time: new Date().toLocaleString(),
            });
            return;
        }
        const res = await apiFetch('/v2/government/simulation/start', { method: 'POST', body: JSON.stringify({ intensity: 'medium' }) });
        if (res.ok) {
            setSessionId(res.data?.session_id || '');
            pushHistory({
                id: `sim-${Date.now()}`,
                action: 'Session started',
                detail: `Session ${res.data?.session_id || 'active'}`,
                status: 'running',
                time: new Date().toLocaleString(),
            });
        }
    };

    const runMultiPhase = async () => {
        setLoading(true);
        try {
            if (mode === 'demo') {
                pushHistory({
                    id: `sim-${Date.now()}`,
                    action: 'Multi-phase run',
                    detail: `${activePhases.length} phases · ${activePhases.reduce((sum, phase) => sum + (Number(phase.count) || 0), 0)} incidents`,
                    status: 'complete',
                    time: new Date().toLocaleString(),
                });
                setLoading(false);
                return;
            }
            let id = sessionId;
            if (!id) {
                const res = await apiFetch('/v2/government/simulation/start', { method: 'POST', body: JSON.stringify({ intensity: 'medium' }) });
                id = res.ok ? res.data?.session_id : '';
                setSessionId(id || '');
            }
            if (!id) return;
            await apiFetch('/v2/government/simulation/multi-phase', {
                method: 'POST',
                body: JSON.stringify({ session_id: id, phases, auto_close: false }),
            });
            pushHistory({
                id: `sim-${Date.now()}`,
                action: 'Multi-phase run',
                detail: `${phases.length} phases · ${phases.reduce((sum, phase) => sum + (Number(phase.count) || 0), 0)} incidents`,
                status: 'complete',
                time: new Date().toLocaleString(),
            });
        } finally {
            setLoading(false);
        }
    };

    const stopSession = async () => {
        if (!sessionId) return;
        if (mode === 'demo') {
            pushHistory({
                id: `sim-${Date.now()}`,
                action: 'Session stopped',
                detail: `Session ${sessionId}`,
                status: 'stopped',
                time: new Date().toLocaleString(),
            });
            return;
        }
        await apiFetch(`/v2/government/simulation/stop/${sessionId}`, { method: 'POST' });
        pushHistory({
            id: `sim-${Date.now()}`,
            action: 'Session stopped',
            detail: `Session ${sessionId}`,
            status: 'stopped',
            time: new Date().toLocaleString(),
        });
    };

    const generateReport = async () => {
        if (!sessionId) return;
        if (mode === 'demo') {
            const report = {
                summary: { total: 118, critical: 16, response_gap_minutes: 11 },
                recommendations: ['Deploy surge ICU teams', 'Activate mobile triage unit', 'Increase standby ambulances'],
            };
            setAfterAction(report);
            localStorage.setItem('gov_simulation_report', JSON.stringify(report));
            pushHistory({
                id: `sim-${Date.now()}`,
                action: 'After-action report',
                detail: `Critical ${report.summary.critical} · Gap ${report.summary.response_gap_minutes}m`,
                status: 'report',
                time: new Date().toLocaleString(),
            });
            return;
        }
        const res = await apiFetch(`/v2/government/simulation/after-action/${sessionId}`, { method: 'POST' });
        if (res.ok) {
            setAfterAction(res.data?.report || null);
            if (res.data?.report) {
                localStorage.setItem('gov_simulation_report', JSON.stringify(res.data.report));
            }
            pushHistory({
                id: `sim-${Date.now()}`,
                action: 'After-action report',
                detail: `Critical ${res.data?.report?.summary?.critical || 0} · Gap ${res.data?.report?.summary?.response_gap_minutes || 0}m`,
                status: 'report',
                time: new Date().toLocaleString(),
            });
        }
    };

    useEffect(() => {
        if (afterAction) return;
        try {
            const cached = localStorage.getItem('gov_simulation_report');
            if (cached) {
                setAfterAction(JSON.parse(cached));
            }
        } catch (error) {
            // ignore cache errors
        }
    }, [afterAction]);

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase text-slate-500">Simulation Control</p>
                        <p className="text-lg font-bold text-slate-800">Multi-phase scenario orchestration</p>
                    </div>
                    <div className="flex gap-2">
                        <button
                            className={`px-3 py-2 text-xs font-bold rounded ${activeTab === 'control' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'}`}
                            onClick={() => setActiveTab('control')}
                        >
                            Control
                        </button>
                        <button
                            className={`px-3 py-2 text-xs font-bold rounded ${activeTab === 'history' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600'}`}
                            onClick={() => setActiveTab('history')}
                        >
                            History
                        </button>
                        <button className="px-3 py-2 text-xs font-bold bg-slate-900 text-white rounded" onClick={startSession}>
                            Start Session
                        </button>
                        <button className="px-3 py-2 text-xs font-bold bg-rose-600 text-white rounded" onClick={stopSession}>
                            Stop
                        </button>
                    </div>
                </div>
                <p className="text-xs text-slate-500 mt-2">Session ID: {sessionId || 'Not started'}</p>
            </DashboardCard>

            {activeTab === 'history' ? (
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">Simulation History</h3>
                    {history.length === 0 ? (
                        <p className="text-sm text-slate-500">No simulation history logged yet.</p>
                    ) : (
                        <div className="max-h-[360px] overflow-y-auto pr-2 space-y-3">
                            {history.map((item) => (
                                <div key={item.id} className="border rounded-lg p-3 bg-white">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="font-semibold text-slate-800">{item.action}</p>
                                            <p className="text-xs text-slate-500">{item.detail}</p>
                                        </div>
                                        <StatusPill
                                            text={item.status === 'report' ? 'Report' : item.status === 'running' ? 'Running' : item.status === 'stopped' ? 'Stopped' : 'Complete'}
                                            color={item.status === 'report' ? 'blue' : item.status === 'running' ? 'yellow' : item.status === 'stopped' ? 'gray' : 'green'}
                                        />
                                    </div>
                                    <p className="text-[11px] text-slate-400 mt-2">{item.time}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </DashboardCard>
            ) : null}

            {activeTab === 'control' ? (
                <>

            <DashboardCard>
                <h3 className="text-lg font-bold text-slate-900 mb-3">Phase Builder</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
                    <input
                        className="border rounded p-2 text-sm"
                        placeholder="Phase name"
                        value={phaseForm.name}
                        onChange={(event) => setPhaseForm({ ...phaseForm, name: event.target.value })}
                    />
                    <select
                        className="border rounded p-2 text-sm"
                        value={phaseForm.intensity}
                        onChange={(event) => setPhaseForm({ ...phaseForm, intensity: event.target.value })}
                    >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="extreme">Extreme</option>
                    </select>
                    <input
                        className="border rounded p-2 text-sm"
                        type="number"
                        placeholder="Incident count"
                        value={phaseForm.count}
                        onChange={(event) => setPhaseForm({ ...phaseForm, count: Number(event.target.value) })}
                    />
                    <input
                        className="border rounded p-2 text-sm"
                        type="number"
                        placeholder="Duration (min)"
                        value={phaseForm.duration}
                        onChange={(event) => setPhaseForm({ ...phaseForm, duration: Number(event.target.value) })}
                    />
                </div>
                <button className="px-3 py-2 text-xs font-bold bg-indigo-600 text-white rounded" onClick={addPhase}>
                    Add Phase
                </button>
                {activePhases.length > 0 && (
                    <div className="mt-4 space-y-2">
                        {activePhases.map((phase, idx) => (
                            <div key={`${phase.name}-${idx}`} className="border rounded-lg p-3">
                                <div className="flex items-center justify-between">
                                    <p className="font-semibold text-slate-800">{phase.name}</p>
                                    <StatusPill text={phase.intensity} color={impactColor(phase.intensity)} />
                                </div>
                                <p className="text-xs text-slate-500">{phase.count} incidents · {phase.duration} min</p>
                            </div>
                        ))}
                    </div>
                )}
                <div className="mt-4 flex gap-2">
                    <button className="px-4 py-2 text-xs font-bold bg-slate-900 text-white rounded" onClick={runMultiPhase} disabled={loading || activePhases.length === 0}>
                        {loading ? 'Running...' : 'Run Multi-Phase'}
                    </button>
                    <button className="px-4 py-2 text-xs font-bold bg-emerald-600 text-white rounded" onClick={generateReport}>
                        Generate After-Action
                    </button>
                </div>
            </DashboardCard>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">Scenario Graph</h3>
                    <div className="h-[260px] border rounded-lg bg-white">
                        {simulationGraph.nodes.length === 0 ? (
                            <div className="h-full flex items-center justify-center text-sm text-slate-400">
                                Add phases to generate the orchestration graph.
                            </div>
                        ) : (
                            <ReactFlow
                                nodes={simulationGraph.nodes}
                                edges={simulationGraph.edges}
                                fitView
                                nodesDraggable={false}
                                nodesConnectable={false}
                                zoomOnScroll={false}
                                style={{ width: '100%', height: '100%' }}
                            >
                                <Background color="#e2e8f0" gap={18} />
                                <Controls showInteractive={false} />
                            </ReactFlow>
                        )}
                    </div>
                </DashboardCard>
                <SimpleLineChart
                    title="Phase Pressure"
                    data={phaseSeries.length ? phaseSeries : [{ label: 'Phase 1', value: 0 }]}
                    lineColor="rgba(14, 116, 144, 0.9)"
                />
            </div>

            {afterAction && (
                <DashboardCard>
                    <h3 className="text-lg font-bold text-slate-900 mb-3">After-Action Report</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <p className="text-xs text-slate-500">Total Incidents</p>
                            <p className="text-2xl font-bold text-slate-900">{afterAction.summary?.total || 0}</p>
                        </div>
                        <div>
                            <p className="text-xs text-slate-500">Critical</p>
                            <p className="text-2xl font-bold text-rose-600">{afterAction.summary?.critical || 0}</p>
                        </div>
                        <div>
                            <p className="text-xs text-slate-500">Response Gap</p>
                            <p className="text-2xl font-bold text-slate-900">{afterAction.summary?.response_gap_minutes || 0}m</p>
                        </div>
                    </div>
                    <div className="mt-4">
                        <p className="text-xs font-bold uppercase text-slate-500">Recommendations</p>
                        <ul className="list-disc pl-4 text-sm text-slate-600 mt-2">
                            {afterAction.recommendations?.map((item, idx) => (
                                <li key={`${item}-${idx}`}>{item}</li>
                            ))}
                        </ul>
                    </div>
                </DashboardCard>
            )}
                </>
            ) : null}
        </div>
    );
};
