import React, { useEffect, useMemo, useState } from 'react';
import {
    PieChart,
    Pie,
    Cell,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';
import { DashboardCard, LoadingSpinner, StatusPill } from './Common';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const HospitalOverview = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [metrics, setMetrics] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const cacheKey = hospitalId ? `hospital_overview_${hospitalId}` : 'hospital_overview';

    const load = async (withSpinner = false) => {
        if (!hospitalId) {
            setMetrics(null);
            setAlerts([]);
            setLoading(false);
            return;
        }
        const showSpinner = withSpinner === true && !metrics;
        if (showSpinner) setLoading(true);
        try {
            const [metricsRes, feedRes] = await Promise.all([
                apiFetch(`/api/hospital-ops/ceo/global-metrics?hospitalId=${hospitalId}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/emergency/feed?hospitalId=${hospitalId}`, { method: 'GET' })
            ]);
            setMetrics(metricsRes.ok ? metricsRes.data : null);
            setAlerts(feedRes.ok ? (feedRes.data?.data || []) : []);
            if (metricsRes.ok || feedRes.ok) {
                localStorage.setItem(cacheKey, JSON.stringify({
                    metrics: metricsRes.ok ? metricsRes.data : null,
                    alerts: feedRes.ok ? (feedRes.data?.data || []) : [],
                }));
            }
        } finally {
            if (showSpinner) setLoading(false);
        }
    };

    useEffect(() => {
        let hasCache = false;
        try {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const parsed = JSON.parse(cached);
                setMetrics(parsed.metrics || null);
                setAlerts(parsed.alerts || []);
                setLoading(false);
                hasCache = true;
            }
        } catch (error) {
            // ignore cache errors
        }
        load(!hasCache);
    }, [hospitalId]);

    const handleUpdateEmergency = async (id, status) => {
        setAlerts((prev) => prev.map((item) => (item._id || item.id) === id ? { ...item, status } : item));
        await apiFetch(`/api/hospital-ops/emergency/feed/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
    };

    const deptData = useMemo(() => {
        const byDept = metrics?.patients?.by_department || {};
        return Object.keys(byDept).map((key) => ({ name: key, value: byDept[key] }));
    }, [metrics]);

    const bedData = useMemo(() => {
        const beds = metrics?.beds || {};
        return [
            { name: 'ICU', value: beds.icu?.occupied || 0 },
            { name: 'Emergency', value: beds.emergency?.occupied || 0 },
            { name: 'General', value: beds.general?.occupied || 0 },
        ];
    }, [metrics]);

    const kpiSignals = metrics?.kpiSignals || {};
    const benchmarks = metrics?.benchmarks || {};
    const externalBenchmarks = benchmarks.external || {};

    if (loading && !metrics) {
        return <LoadingSpinner />;
    }

    return (
        <div className="space-y-6 animate-fade-in pb-10">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <DashboardCard>
                    <p className="text-xs font-bold text-gray-500 uppercase">Total Patients</p>
                    <p className="text-2xl font-bold text-gray-900">{metrics?.patients?.total || 0}</p>
                    <p className="text-xs text-gray-400">OPD/ICU/Emergency combined</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs font-bold text-gray-500 uppercase">Bed Occupancy</p>
                    <p className="text-2xl font-bold text-gray-900">{metrics?.beds?.occupied || 0}/{metrics?.beds?.total || 0}</p>
                    <p className="text-xs text-gray-400">Available {metrics?.beds?.available || 0}</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs font-bold text-gray-500 uppercase">Revenue (Daily/Weekly)</p>
                    <p className="text-2xl font-bold text-gray-900">₹{metrics?.revenue?.daily || 0}</p>
                    <p className="text-xs text-gray-400">Weekly ₹{metrics?.revenue?.weekly || 0}</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs font-bold text-gray-500 uppercase">Staff Availability</p>
                    <p className="text-2xl font-bold text-gray-900">{metrics?.staff?.available || 0}/{metrics?.staff?.total || 0}</p>
                    <p className="text-xs text-gray-400">On-duty coverage</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs font-bold text-gray-500 uppercase">Emergency Load</p>
                    <p className="text-2xl font-bold text-gray-900">{metrics?.emergency?.active || 0}</p>
                    <p className="text-xs text-gray-400">Critical {metrics?.emergency?.critical || 0}</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs font-bold text-gray-500 uppercase">Ambulance Flow</p>
                    <p className="text-2xl font-bold text-gray-900">In {metrics?.ambulance?.inbound || 0}</p>
                    <p className="text-xs text-gray-400">Out {metrics?.ambulance?.outbound || 0}</p>
                </DashboardCard>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DashboardCard>
                    <h3 className="font-bold text-lg text-gray-900 mb-4">Department Load</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie data={deptData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label>
                                    {deptData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                                <Legend verticalAlign="bottom" height={36} />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </DashboardCard>
                <DashboardCard>
                    <h3 className="font-bold text-lg text-gray-900 mb-4">Bed Occupancy by Unit</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={bedData}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="name" />
                                <YAxis allowDecimals={false} />
                                <Tooltip />
                                <Bar dataKey="value" fill="#2563eb" radius={[6, 6, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </DashboardCard>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DashboardCard>
                    <h3 className="font-bold text-lg text-gray-900 mb-3">KPI Signals</h3>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="bg-slate-50 border border-slate-200 rounded p-3">
                            <p className="text-xs text-gray-500">Occupancy rate</p>
                            <p className="text-xl font-bold text-gray-900">{kpiSignals.occupancyRate || 0}%</p>
                        </div>
                        <div className="bg-slate-50 border border-slate-200 rounded p-3">
                            <p className="text-xs text-gray-500">Staff coverage</p>
                            <p className="text-xl font-bold text-gray-900">{kpiSignals.staffCoverage || 0}%</p>
                        </div>
                        <div className="bg-slate-50 border border-slate-200 rounded p-3">
                            <p className="text-xs text-gray-500">Revenue trend</p>
                            <p className="text-xl font-bold text-gray-900">{kpiSignals.revenueTrend || 'Stable'}</p>
                        </div>
                        <div className="bg-slate-50 border border-slate-200 rounded p-3">
                            <p className="text-xs text-gray-500">Emergency load</p>
                            <p className="text-xl font-bold text-gray-900">{kpiSignals.emergencyLoad || 0}</p>
                        </div>
                    </div>
                </DashboardCard>

                <DashboardCard>
                    <h3 className="font-bold text-lg text-gray-900 mb-3">Benchmark Comparison</h3>
                    <div className="space-y-3 text-sm">
                        <div className="flex items-center justify-between">
                            <span className="text-gray-500">Internal avg occupancy</span>
                            <span className="font-semibold text-gray-900">{benchmarks.internal?.avgOccupancyRate || 0}%</span>
                        </div>
                        {Object.keys(externalBenchmarks).length === 0 ? (
                            <div className="text-xs text-gray-400">No external benchmarks loaded for {benchmarks.region || 'region'}.</div>
                        ) : (
                            Object.entries(externalBenchmarks).map(([metric, value]) => (
                                <div key={metric} className="flex items-center justify-between">
                                    <span className="text-gray-500">{metric}</span>
                                    <span className="font-semibold text-gray-900">{value}</span>
                                </div>
                            ))
                        )}
                    </div>
                </DashboardCard>
            </div>

            {metrics?.ai?.anomalies?.length > 0 && (
                <DashboardCard>
                    <h3 className="font-bold text-lg text-gray-900 mb-3">AI Alerts</h3>
                    <div className="space-y-2">
                        {metrics.ai.anomalies.map((alert, idx) => (
                            <div key={`${alert}-${idx}`} className="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                                {alert}
                            </div>
                        ))}
                    </div>
                </DashboardCard>
            )}

            <DashboardCard>
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="font-bold text-lg text-gray-900">Live Emergency Feed</h3>
                        <p className="text-sm text-gray-500">Active cases requiring rapid triage.</p>
                    </div>
                    <span className="text-xs text-gray-400">Updated {new Date().toLocaleTimeString()}</span>
                </div>
                {alerts.length === 0 ? (
                    <div className="text-sm text-gray-500">No active emergencies.</div>
                ) : (
                    <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                        {alerts.map((alert) => (
                            <div key={alert._id || alert.id} className="border rounded p-3 bg-white/70">
                                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                                    <div>
                                        <p className="font-semibold text-gray-800">{alert.patientName || 'Emergency case'}</p>
                                        <p className="text-xs text-gray-500">{alert.location || 'Unknown'} • {alert.symptoms}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <StatusPill text={alert.severity || 'High'} color={alert.severity === 'Critical' ? 'red' : 'yellow'} />
                                        <StatusPill text={alert.status || 'Unassigned'} color={alert.status === 'Resolved' ? 'green' : 'blue'} />
                                        <button className="text-xs text-indigo-600" onClick={() => handleUpdateEmergency(alert._id || alert.id, 'Assigned')}>
                                            Assign
                                        </button>
                                        <button className="text-xs text-green-600" onClick={() => handleUpdateEmergency(alert._id || alert.id, 'Resolved')}>
                                            Resolve
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export default HospitalOverview;