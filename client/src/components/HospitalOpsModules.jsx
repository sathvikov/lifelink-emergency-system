import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL, apiFetch, getAuthToken } from '../config/api';
import { DashboardCard, ExplainabilityPanel, LoadingSpinner, ProgressBar, StatusPill } from './Common';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

const _toInt = (value, fallback = 0) => {
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? fallback : parsed;
};

const _nowLabel = () => new Date().toLocaleString();

const buildQuery = (params) => {
    const searchParams = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
        if (value === undefined || value === null) return;
        const text = String(value).trim();
        if (!text) return;
        searchParams.set(key, text);
    });
    const qs = searchParams.toString();
    return qs ? `?${qs}` : '';
};


export const HospitalDepartmentAnalytics = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [logForm, setLogForm] = useState({
        department: 'Emergency',
        avgTreatmentMinutes: '',
        dischargeRate: '',
        delayRate: '',
        throughputPerHour: '',
        queueLength: ''
    });

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                if (!hospitalId) {
                    setStats(null);
                    return;
                }
                const res = await apiFetch(`/api/hospital-ops/ceo/department-performance?hospitalId=${hospitalId}`, { method: 'GET' });
                setStats(res.ok ? res.data : null);
            } catch (err) {
                setStats(null);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [hospitalId]);

    const handleAddLog = async () => {
        if (!hospitalId || !logForm.department) return;
        const payload = {
            hospitalId,
            department: logForm.department,
            avgTreatmentMinutes: Number(logForm.avgTreatmentMinutes || 0),
            dischargeRate: Number(logForm.dischargeRate || 0),
            delayRate: Number(logForm.delayRate || 0),
            throughputPerHour: logForm.throughputPerHour === '' ? null : Number(logForm.throughputPerHour),
            queueLength: logForm.queueLength === '' ? null : Number(logForm.queueLength),
        };
        await apiFetch('/api/hospital-ops/ceo/department-performance/logs', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        setLogForm({ department: 'Emergency', avgTreatmentMinutes: '', dischargeRate: '', delayRate: '', throughputPerHour: '', queueLength: '' });
        const res = await apiFetch(`/api/hospital-ops/ceo/department-performance?hospitalId=${hospitalId}`, { method: 'GET' });
        setStats(res.ok ? res.data : null);
    };

    const departmentData = useMemo(() => {
        if (stats?.departments?.length) {
            return stats.departments.map((item) => ({
                name: item.department,
                value: _toInt(item.score, 0)
            }));
        }
        return [];
    }, [stats]);

    return (
        <div className="space-y-6">
            <DashboardCard>
                <h4 className="font-bold text-gray-800 mb-3">Capture Department Log</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <select
                        className="p-2 border rounded"
                        value={logForm.department}
                        onChange={(e) => setLogForm({ ...logForm, department: e.target.value })}
                    >
                        <option>Emergency</option>
                        <option>ICU</option>
                        <option>OPD</option>
                        <option>Radiology</option>
                        <option>Surgery</option>
                        <option>General</option>
                    </select>
                    <input
                        className="p-2 border rounded"
                        type="number"
                        placeholder="Avg treatment (mins)"
                        value={logForm.avgTreatmentMinutes}
                        onChange={(e) => setLogForm({ ...logForm, avgTreatmentMinutes: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        type="number"
                        placeholder="Discharge rate (0-1)"
                        value={logForm.dischargeRate}
                        onChange={(e) => setLogForm({ ...logForm, dischargeRate: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        type="number"
                        placeholder="Delay rate (0-1)"
                        value={logForm.delayRate}
                        onChange={(e) => setLogForm({ ...logForm, delayRate: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        type="number"
                        placeholder="Throughput / hr"
                        value={logForm.throughputPerHour}
                        onChange={(e) => setLogForm({ ...logForm, throughputPerHour: e.target.value })}
                    />
                    <div className="flex gap-2">
                        <input
                            className="p-2 border rounded w-full"
                            type="number"
                            placeholder="Queue length"
                            value={logForm.queueLength}
                            onChange={(e) => setLogForm({ ...logForm, queueLength: e.target.value })}
                        />
                        <button
                            className="bg-slate-900 text-white rounded px-3"
                            type="button"
                            onClick={handleAddLog}
                        >
                            Save
                        </button>
                    </div>
                </div>
            </DashboardCard>

            <DashboardCard>
                <div className="flex justify-between items-center mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">Department Analytics</h3>
                        <p className="text-sm text-gray-500">Utilization, throughput, and LOS trends across departments.</p>
                    </div>
                    <span className="text-xs text-gray-400">Updated {_nowLabel()}</span>
                </div>
                {loading ? (
                    <LoadingSpinner />
                ) : departmentData.length === 0 ? (
                    <div className="text-sm text-gray-500">No department performance data yet.</div>
                ) : (
                    <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={departmentData}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="name" />
                                <YAxis allowDecimals={false} />
                                <Tooltip />
                                <Bar dataKey="value" fill="#2563eb" radius={[6, 6, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </DashboardCard>
            {stats?.departments?.length ? (
                <DashboardCard>
                    <h4 className="font-bold text-gray-800 mb-3">Performance Ranking</h4>
                    {stats?.bottlenecks?.length ? (
                        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                            Bottlenecks: {stats.bottlenecks.join(', ')}
                        </div>
                    ) : null}
                    <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                        {stats.departments.map((dept) => (
                            <div key={dept.department} className="border rounded p-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
                                <div>
                                    <p className="font-semibold text-gray-800">{dept.department}</p>
                                    <p className="text-xs text-gray-500">Patients {dept.patients} • Avg time {dept.avgTreatmentMinutes ?? 'N/A'} mins • Throughput {dept.throughputPerHour ?? 'N/A'}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <StatusPill text={`${dept.dischargeRate ?? 0}% discharge`} color="green" />
                                    <StatusPill text={`${dept.delayRate ?? 0}% delays`} color={(dept.delayRate || 0) > 12 ? 'red' : 'yellow'} />
                                    <StatusPill text={`Score ${dept.score ?? 0}`} color={(dept.score || 0) > 75 ? 'green' : 'blue'} />
                                </div>
                            </div>
                        ))}
                    </div>
                </DashboardCard>
            ) : null}
        </div>
    );
};

export const HospitalFinanceOverview = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [summary, setSummary] = useState(null);
    const [claims, setClaims] = useState([]);
    const [payerDelays, setPayerDelays] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                if (isActive) {
                    setSummary(null);
                    setClaims([]);
                    setLoading(false);
                }
                return;
            }
            setLoading(true);
            try {
                const [revenueRes, claimsRes, delayRes] = await Promise.all([
                    apiFetch(`/api/hospital-ops/finance/revenue?hospitalId=${hospitalId}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/finance/claims?hospitalId=${hospitalId}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/finance/payer-delays?hospitalId=${hospitalId}`, { method: 'GET' })
                ]);
                if (isActive) {
                    setSummary(revenueRes.ok ? revenueRes.data : null);
                    setClaims(claimsRes.ok ? (claimsRes.data?.data || []) : []);
                    setPayerDelays(delayRes.ok ? delayRes.data : null);
                }
            } finally {
                if (isActive) setLoading(false);
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId]);

    const monthlySeries = summary?.monthlySeries || [];
    const latestMonth = monthlySeries.length ? monthlySeries[monthlySeries.length - 1] : null;
    const previousMonth = monthlySeries.length > 1 ? monthlySeries[monthlySeries.length - 2] : null;
    const monthDelta = previousMonth?.value
        ? ((latestMonth?.value || 0) - previousMonth.value) / previousMonth.value * 100
        : 0;

    const pendingClaims = claims.filter((claim) => (claim.status || '').toLowerCase() !== 'approved');
    const claimsByMonth = claims.reduce((acc, claim) => {
        const createdAt = claim.createdAt ? new Date(claim.createdAt) : null;
        if (!createdAt || Number.isNaN(createdAt.getTime())) return acc;
        const label = createdAt.toLocaleString('en-US', { month: 'short' });
        acc[label] = (acc[label] || 0) + Number(claim.amount || 0);
        return acc;
    }, {});

    const chartData = monthlySeries.map((row) => ({
        month: row.label,
        revenue: Number(row.value || 0),
        claims: Number(claimsByMonth[row.label] || 0)
    }));

    const utilization = summary?.totalRevenue
        ? Math.round((Number(summary.totalExpenses || 0) / Number(summary.totalRevenue || 1)) * 100)
        : 0;

    return (
        <div className="space-y-6">
            {loading ? (
                <LoadingSpinner />
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <DashboardCard>
                            <p className="text-xs text-gray-500">Monthly Revenue</p>
                            <p className="text-2xl font-bold text-gray-900">₹{latestMonth?.value || 0}</p>
                            <p className={`text-xs ${monthDelta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {monthDelta >= 0 ? '+' : ''}{monthDelta.toFixed(1)}% vs last month
                            </p>
                        </DashboardCard>
                        <DashboardCard>
                            <p className="text-xs text-gray-500">Claims Pending</p>
                            <p className="text-2xl font-bold text-gray-900">{pendingClaims.length}</p>
                            <p className="text-xs text-amber-600">Open claims in review</p>
                        </DashboardCard>
                        <DashboardCard>
                            <p className="text-xs text-gray-500">Operating Cost</p>
                            <p className="text-2xl font-bold text-gray-900">₹{summary?.totalExpenses || 0}</p>
                            <p className="text-xs text-indigo-600">Utilization {utilization}%</p>
                        </DashboardCard>
                    </div>

                    <DashboardCard>
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Revenue vs Claims</h3>
                        {chartData.length === 0 ? (
                            <div className="text-sm text-gray-500">No finance activity yet.</div>
                        ) : (
                            <div className="h-72 overflow-hidden">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="month" />
                                        <YAxis />
                                        <Tooltip />
                                        <Bar dataKey="revenue" fill="#16a34a" radius={[6, 6, 0, 0]} />
                                        <Bar dataKey="claims" fill="#f97316" radius={[6, 6, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </DashboardCard>

                    <DashboardCard>
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Payer Delay Insights</h3>
                        {!payerDelays ? (
                            <div className="text-sm text-gray-500">No payer delay data yet.</div>
                        ) : (
                            <div className="space-y-3">
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-500">Average delay</span>
                                    <span className="font-semibold text-gray-900">{payerDelays.averageDelayDays || 0} days</span>
                                </div>
                                {(payerDelays.insurers || []).length === 0 ? (
                                    <div className="text-xs text-gray-400">No insurer-level delay data.</div>
                                ) : (
                                    payerDelays.insurers.map((item) => (
                                        <div key={item.insurer} className="flex items-center justify-between text-sm border rounded px-3 py-2">
                                            <span className="text-gray-600">{item.insurer}</span>
                                            <span className="font-semibold text-gray-900">{item.avgDelayDays} days</span>
                                        </div>
                                    ))
                                )}
                            </div>
                        )}
                    </DashboardCard>
                </>
            )}
        </div>
    );
};

export const HospitalStaffManagement = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [staff, setStaff] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [newStaff, setNewStaff] = useState({ name: '', department: 'Emergency', role: 'Nurse', availability: true });
    const [skillSummary, setSkillSummary] = useState(null);
    const [optimizer, setOptimizer] = useState(null);
    const [staffSearch, setStaffSearch] = useState('');
    const [staffSortBy, setStaffSortBy] = useState('createdAt');
    const [staffSortDir, setStaffSortDir] = useState('desc');

    const fetchStaff = async () => {
        if (!hospitalId) {
            setStaff([]);
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const staffQuery = buildQuery({
                hospitalId,
                search: staffSearch,
                sort_by: staffSortBy,
                sort_dir: staffSortDir
            });
            const [res, skillRes, optimizerRes] = await Promise.all([
                apiFetch(`/api/hospital-ops/staff${staffQuery}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/staff/skills/summary?hospitalId=${hospitalId}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/staff/optimizer?hospitalId=${hospitalId}`, { method: 'GET' })
            ]);
            const items = res.ok ? (res.data?.data || []) : [];
            setStaff(items.map((item) => ({
                id: item._id || item.id,
                name: item.name || 'Staff',
                department: item.department || 'General',
                role: item.role || 'Doctor',
                availability: item.availability !== false
            })));
            setSkillSummary(skillRes.ok ? skillRes.data : null);
            setOptimizer(optimizerRes.ok ? optimizerRes.data : null);
        } catch (err) {
            setStaff([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStaff();
    }, [hospitalId, staffSearch, staffSortBy, staffSortDir]);

    const handleAdd = () => {
        if (!newStaff.name) return;
        apiFetch('/api/hospital-ops/staff', {
            method: 'POST',
            body: JSON.stringify({
                hospitalId,
                name: newStaff.name,
                department: newStaff.department,
                role: newStaff.role,
                availability: newStaff.availability
            })
        }).then((res) => {
            if (res.ok) {
                setStaff((prev) => [{
                    id: res.data._id || res.data.id,
                    name: res.data.name,
                    department: res.data.department,
                    role: res.data.role,
                    availability: res.data.availability !== false
                }, ...prev]);
            }
        });
        setNewStaff({ name: '', department: 'Emergency', role: 'Nurse', availability: true });
    };

    const handleToggle = (id) => {
        setStaff((prev) => {
            const target = prev.find((item) => item.id === id);
            const nextAvailability = target ? !target.availability : true;
            apiFetch(`/api/hospital-ops/staff/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({ availability: nextAvailability })
            });
            return prev.map((item) => item.id === id ? { ...item, availability: nextAvailability } : item);
        });
    };

    const handleRemove = (id) => {
        setStaff((prev) => prev.filter((item) => item.id !== id));
        apiFetch(`/api/hospital-ops/staff/${id}`, { method: 'DELETE' });
    };

    const handleSave = async () => {
        if (!hospitalId) return;
        setSaving(true);
        try {
            await Promise.all(
                staff.map((item) => apiFetch(`/api/hospital-ops/staff/${item.id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({
                        name: item.name,
                        department: item.department,
                        availability: item.availability,
                        role: item.role
                    })
                }))
            );
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-4">Staff Management</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input
                        className="p-2 border rounded"
                        placeholder="Name"
                        value={newStaff.name}
                        onChange={(e) => setNewStaff({ ...newStaff, name: e.target.value })}
                    />
                    <select
                        className="p-2 border rounded"
                        value={newStaff.department}
                        onChange={(e) => setNewStaff({ ...newStaff, department: e.target.value })}
                    >
                        <option>Emergency</option>
                        <option>ICU</option>
                        <option>OPD</option>
                        <option>Radiology</option>
                        <option>Surgery</option>
                    </select>
                    <select
                        className="p-2 border rounded"
                        value={newStaff.role}
                        onChange={(e) => setNewStaff({ ...newStaff, role: e.target.value })}
                    >
                        <option>Doctor</option>
                        <option>Nurse</option>
                        <option>Technician</option>
                        <option>Support</option>
                    </select>
                    <button
                        type="button"
                        className="bg-indigo-600 text-white rounded px-4"
                        onClick={handleAdd}
                    >
                        Add Staff
                    </button>
                </div>
            </DashboardCard>

            <DashboardCard>
                <div className="flex items-center justify-between mb-4">
                    <h4 className="font-bold text-gray-800">Active Staff</h4>
                    <button
                        type="button"
                        className="text-xs bg-slate-900 text-white px-3 py-2 rounded"
                        onClick={handleSave}
                        disabled={saving}
                    >
                        {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                </div>
                <div className="flex flex-col md:flex-row gap-2 mb-4">
                    <input
                        className="p-2 border rounded w-full"
                        placeholder="Search staff"
                        value={staffSearch}
                        onChange={(e) => setStaffSearch(e.target.value)}
                    />
                    <select
                        className="p-2 border rounded"
                        value={staffSortBy}
                        onChange={(e) => setStaffSortBy(e.target.value)}
                    >
                        <option value="createdAt">Newest</option>
                        <option value="name">Name</option>
                        <option value="department">Department</option>
                        <option value="role">Role</option>
                        <option value="availability">Availability</option>
                    </select>
                    <select
                        className="p-2 border rounded"
                        value={staffSortDir}
                        onChange={(e) => setStaffSortDir(e.target.value)}
                    >
                        <option value="desc">Desc</option>
                        <option value="asc">Asc</option>
                    </select>
                </div>
                {loading ? (
                    <LoadingSpinner />
                ) : (
                    <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                        {staff.length === 0 ? (
                            <div className="text-sm text-gray-500">No staff records loaded.</div>
                        ) : (
                            staff.map((item) => (
                                <div key={item.id} className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 border rounded-lg bg-white/70">
                                    <div>
                                        <p className="font-semibold text-gray-800">{item.name}</p>
                                        <p className="text-xs text-gray-500">{item.department} • {item.role}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <StatusPill text={item.availability ? 'Available' : 'Off Duty'} color={item.availability ? 'green' : 'gray'} />
                                        <button className="text-xs text-indigo-600" onClick={() => handleToggle(item.id)}>Toggle</button>
                                        <button className="text-xs text-red-500" onClick={() => handleRemove(item.id)}>Remove</button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </DashboardCard>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DashboardCard>
                    <h4 className="font-bold text-gray-800 mb-3">Skill Mix Summary</h4>
                    {!skillSummary ? (
                        <div className="text-sm text-gray-500">No skill tags recorded yet.</div>
                    ) : (
                        <div className="space-y-2 max-h-[240px] overflow-y-auto pr-2">
                            {(skillSummary.skills || []).length === 0 ? (
                                <div className="text-sm text-gray-500">No skills captured.</div>
                            ) : (
                                skillSummary.skills.slice(0, 6).map((item) => (
                                    <div key={item.skill} className="flex items-center justify-between text-sm border rounded px-3 py-2">
                                        <span className="text-gray-600">{item.skill}</span>
                                        <span className="font-semibold text-gray-900">{item.count}</span>
                                    </div>
                                ))
                            )}
                            {(skillSummary.recommendations || []).length > 0 && (
                                <div className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                                    {skillSummary.recommendations.join(' ')}
                                </div>
                            )}
                        </div>
                    )}
                </DashboardCard>

                <DashboardCard>
                    <h4 className="font-bold text-gray-800 mb-3">Staff Optimizer</h4>
                    {!optimizer ? (
                        <div className="text-sm text-gray-500">No optimizer insights yet.</div>
                    ) : (
                        <div className="space-y-2">
                            {(optimizer.recommendations || []).map((rec, idx) => (
                                <div key={`${rec.department}-${idx}`} className="border rounded px-3 py-2 text-sm">
                                    <p className="font-semibold text-gray-800">{rec.department}</p>
                                    <p className="text-xs text-gray-500">{rec.action} • {rec.reason}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </DashboardCard>
            </div>
        </div>
    );
};

export const HospitalReports = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [reports, setReports] = useState([]);
    const [ingestedReports, setIngestedReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [workingKey, setWorkingKey] = useState(null);
    const [ingestForm, setIngestForm] = useState({ name: '', category: 'General', content: '' });
    const [ingesting, setIngesting] = useState(false);
    const [ingestSearch, setIngestSearch] = useState('');
    const [ingestSortBy, setIngestSortBy] = useState('generatedAt');
    const [ingestSortDir, setIngestSortDir] = useState('desc');

    const load = async () => {
        if (!hospitalId) {
            setReports([]);
            setIngestedReports([]);
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const ingestQuery = buildQuery({
                hospitalId,
                search: ingestSearch,
                sort_by: ingestSortBy,
                sort_dir: ingestSortDir
            });
            const [res, ingestRes] = await Promise.all([
                apiFetch(`/api/hospital-ops/reports?hospitalId=${hospitalId}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/reports/ingested${ingestQuery}`, { method: 'GET' })
            ]);
            setReports(res.ok ? (res.data?.data || []) : []);
            setIngestedReports(ingestRes.ok ? (ingestRes.data?.data || []) : []);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [hospitalId, ingestSearch, ingestSortBy, ingestSortDir]);

    const handleGenerate = async (reportKey) => {
        if (!hospitalId || !reportKey) return;
        setWorkingKey(reportKey);
        try {
            const res = await apiFetch('/api/hospital-ops/reports/generate', {
                method: 'POST',
                body: JSON.stringify({ hospitalId, reportKey })
            });
            if (res.ok) {
                await load();
            }
        } finally {
            setWorkingKey(null);
        }
    };

    const handleDownload = async (report) => {
        if (!report?.id) return;
        const token = getAuthToken();
        const res = await fetch(`${API_BASE_URL}/api/hospital-ops/reports/${report.id}/download`, {
            headers: token ? { Authorization: `Bearer ${token}` } : undefined
        });
        if (!res.ok) return;
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        const safeName = (report.name || 'report').toLowerCase().replace(/\s+/g, '_');
        anchor.href = url;
        anchor.download = `${safeName}.txt`;
        anchor.click();
        window.URL.revokeObjectURL(url);
    };

    const handleIngest = async () => {
        if (!hospitalId || !ingestForm.name || !ingestForm.content) return;
        setIngesting(true);
        try {
            const res = await apiFetch('/api/hospital-ops/reports/ingest', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    name: ingestForm.name,
                    category: ingestForm.category,
                    content: ingestForm.content
                })
            });
            if (res.ok) {
                setIngestedReports((prev) => [res.data, ...prev]);
                setIngestForm({ name: '', category: 'General', content: '' });
            }
        } finally {
            setIngesting(false);
        }
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-4">Reports Center</h3>
                {loading ? (
                    <LoadingSpinner />
                ) : reports.length === 0 ? (
                    <div className="text-sm text-gray-500">No reports available yet.</div>
                ) : (
                    <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                        {reports.map((report) => (
                            <div key={report.reportKey || report.id} className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 border rounded-lg">
                                <div>
                                    <p className="font-semibold text-gray-800">{report.name}</p>
                                    <p className="text-xs text-gray-500">
                                        Last generated: {report.generatedAt ? new Date(report.generatedAt).toLocaleDateString() : 'Not generated'}
                                    </p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <StatusPill text={report.status || 'Draft'} color={report.status === 'Ready' ? 'green' : 'yellow'} />
                                    <button
                                        className="text-xs text-indigo-600"
                                        onClick={() => handleGenerate(report.reportKey)}
                                        disabled={workingKey === report.reportKey}
                                    >
                                        {workingKey === report.reportKey ? 'Generating...' : 'Generate'}
                                    </button>
                                    <button
                                        className={`text-xs ${report.status === 'Ready' ? 'text-gray-700' : 'text-gray-400'}`}
                                        onClick={() => handleDownload(report)}
                                        disabled={report.status !== 'Ready'}
                                    >
                                        Download
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-3">Ingest External Report</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                    <input
                        className="p-2 border rounded"
                        placeholder="Report name"
                        value={ingestForm.name}
                        onChange={(e) => setIngestForm({ ...ingestForm, name: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        placeholder="Category"
                        value={ingestForm.category}
                        onChange={(e) => setIngestForm({ ...ingestForm, category: e.target.value })}
                    />
                    <button
                        className="bg-indigo-600 text-white rounded"
                        onClick={handleIngest}
                        disabled={ingesting}
                    >
                        {ingesting ? 'Ingesting...' : 'Ingest Report'}
                    </button>
                </div>
                <textarea
                    className="w-full p-3 border rounded text-sm"
                    placeholder="Paste report content here..."
                    rows="4"
                    value={ingestForm.content}
                    onChange={(e) => setIngestForm({ ...ingestForm, content: e.target.value })}
                />
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-3">Ingested Reports</h3>
                <div className="flex flex-col md:flex-row gap-2 mb-3">
                    <input
                        className="p-2 border rounded w-full"
                        placeholder="Search ingested reports"
                        value={ingestSearch}
                        onChange={(e) => setIngestSearch(e.target.value)}
                    />
                    <select
                        className="p-2 border rounded"
                        value={ingestSortBy}
                        onChange={(e) => setIngestSortBy(e.target.value)}
                    >
                        <option value="generatedAt">Newest</option>
                        <option value="name">Name</option>
                        <option value="category">Category</option>
                        <option value="status">Status</option>
                    </select>
                    <select
                        className="p-2 border rounded"
                        value={ingestSortDir}
                        onChange={(e) => setIngestSortDir(e.target.value)}
                    >
                        <option value="desc">Desc</option>
                        <option value="asc">Asc</option>
                    </select>
                </div>
                {ingestedReports.length === 0 ? (
                    <div className="text-sm text-gray-500">No ingested reports yet.</div>
                ) : (
                    <div className="space-y-2 max-h-[360px] overflow-y-auto pr-2">
                        {ingestedReports.slice(0, 6).map((report) => (
                            <div key={report._id || report.id} className="border rounded p-3">
                                <p className="font-semibold text-gray-800">{report.name || 'Report'}</p>
                                <p className="text-xs text-gray-500">{report.category || 'General'} • {report.generatedAt ? new Date(report.generatedAt).toLocaleString() : 'Recent'}</p>
                                {report.summary && (
                                    <p className="text-sm text-gray-600 mt-2">{report.summary}</p>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export const HospitalBillingSystem = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [invoices, setInvoices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ patientName: '', department: 'General', amount: '' });
    const [fraudAlerts, setFraudAlerts] = useState([]);
    const [invoiceSearch, setInvoiceSearch] = useState('');
    const [invoiceSortBy, setInvoiceSortBy] = useState('createdAt');
    const [invoiceSortDir, setInvoiceSortDir] = useState('desc');

    const load = async () => {
        if (!hospitalId) return;
        setLoading(true);
        try {
            const invoiceQuery = buildQuery({
                hospitalId,
                search: invoiceSearch,
                sort_by: invoiceSortBy,
                sort_dir: invoiceSortDir
            });
            const [invoiceRes, revenueRes] = await Promise.all([
                apiFetch(`/api/hospital-ops/finance/invoices${invoiceQuery}`, { method: 'GET' }),
                apiFetch(`/api/hospital-ops/finance/revenue?hospitalId=${hospitalId}`, { method: 'GET' })
            ]);
            setInvoices(invoiceRes.ok ? (invoiceRes.data?.data || []) : []);
            setFraudAlerts(revenueRes.ok ? (revenueRes.data?.fraudAlerts || []) : []);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [hospitalId, invoiceSearch, invoiceSortBy, invoiceSortDir]);

    const handleCreate = async () => {
        if (!hospitalId || !form.patientName || !form.amount) return;
        const res = await apiFetch('/api/hospital-ops/finance/invoices', {
            method: 'POST',
            body: JSON.stringify({
                hospitalId,
                patientName: form.patientName,
                department: form.department,
                amount: Number(form.amount)
            })
        });
        if (res.ok) {
            setInvoices((prev) => [res.data, ...prev]);
            setForm({ patientName: '', department: 'General', amount: '' });
        }
    };

    const updateInvoice = async (id, status) => {
        await apiFetch(`/api/hospital-ops/finance/invoices/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
        setInvoices((prev) => prev.map((inv) => (inv._id || inv.id) === id ? { ...inv, status } : inv));
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Billing System</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Patient name" value={form.patientName} onChange={(e) => setForm({ ...form, patientName: e.target.value })} />
                <select className="p-2 border rounded" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
                    <option>General</option>
                    <option>Emergency</option>
                    <option>ICU</option>
                    <option>OPD</option>
                    <option>Radiology</option>
                </select>
                <input className="p-2 border rounded" type="number" placeholder="Amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
                <button className="bg-indigo-600 text-white rounded" onClick={handleCreate}>Generate Invoice</button>
            </div>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search invoices"
                    value={invoiceSearch}
                    onChange={(e) => setInvoiceSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={invoiceSortBy}
                    onChange={(e) => setInvoiceSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="amount">Amount</option>
                    <option value="status">Status</option>
                    <option value="department">Department</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={invoiceSortDir}
                    onChange={(e) => setInvoiceSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                    {invoices.length === 0 ? (
                        <div className="text-sm text-gray-500">No invoices yet.</div>
                    ) : (
                        invoices.map((inv) => (
                            <div key={inv._id || inv.id} className="border rounded p-3 flex items-center justify-between">
                                <div>
                                    <p className="font-semibold text-gray-800">{inv.patientName}</p>
                                    <p className="text-xs text-gray-500">{inv.department} • ₹{inv.amount}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <StatusPill text={inv.status || 'Unpaid'} color={inv.status === 'Paid' ? 'green' : 'yellow'} />
                                    <button className="text-xs text-green-600" onClick={() => updateInvoice(inv._id || inv.id, 'Paid')}>Mark Paid</button>
                                    <button className="text-xs text-red-600" onClick={() => updateInvoice(inv._id || inv.id, 'Refunded')}>Refund</button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
            {fraudAlerts.length > 0 && (
                <div className="mt-4 border rounded p-3 bg-red-50 text-red-700 text-sm">
                    <p className="font-semibold mb-2">Fraud Alerts</p>
                    {fraudAlerts.map((alert, idx) => (
                        <div key={`${alert}-${idx}`}>{alert}</div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalRevenueAnalytics = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [expense, setExpense] = useState({ category: 'Supplies', amount: '' });

    const load = async () => {
        if (!hospitalId) return;
        setLoading(true);
        try {
            const res = await apiFetch(`/api/hospital-ops/finance/revenue?hospitalId=${hospitalId}`, { method: 'GET' });
            setSummary(res.ok ? res.data : null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [hospitalId]);

    const addExpense = async () => {
        if (!hospitalId || !expense.amount) return;
        await apiFetch('/api/hospital-ops/finance/expenses', {
            method: 'POST',
            body: JSON.stringify({ hospitalId, category: expense.category, amount: Number(expense.amount) })
        });
        setExpense({ category: 'Supplies', amount: '' });
        load();
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Revenue Analytics</h3>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-4 max-h-[520px] overflow-y-auto pr-2">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className="border rounded p-3">
                            <p className="text-xs text-gray-500">Total Revenue</p>
                            <p className="text-xl font-bold text-gray-900">₹{summary?.totalRevenue || 0}</p>
                        </div>
                        <div className="border rounded p-3">
                            <p className="text-xs text-gray-500">Total Expenses</p>
                            <p className="text-xl font-bold text-gray-900">₹{summary?.totalExpenses || 0}</p>
                        </div>
                        <div className="border rounded p-3">
                            <p className="text-xs text-gray-500">Profit</p>
                            <p className="text-xl font-bold text-gray-900">₹{summary?.profit || 0}</p>
                        </div>
                    </div>
                    <div>
                        <p className="text-sm text-gray-500 mb-2">Department Breakdown</p>
                        <div className="space-y-2">
                            {(summary?.departmentBreakdown || []).map((dept) => (
                                <div key={dept.department} className="flex items-center justify-between border rounded p-2">
                                    <span className="text-sm text-gray-700">{dept.department}</span>
                                    <span className="text-sm font-semibold text-gray-900">₹{dept.amount}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="h-48 overflow-hidden">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={summary?.dailySeries || []}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="label" />
                                    <YAxis />
                                    <Tooltip />
                                    <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="h-48 overflow-hidden">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={summary?.monthlySeries || []}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="label" />
                                    <YAxis />
                                    <Tooltip />
                                    <Line type="monotone" dataKey="value" stroke="#16a34a" strokeWidth={2} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            )}
            <div className="mt-4 border-t pt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                <input className="p-2 border rounded" placeholder="Expense category" value={expense.category} onChange={(e) => setExpense({ ...expense, category: e.target.value })} />
                <input className="p-2 border rounded" type="number" placeholder="Amount" value={expense.amount} onChange={(e) => setExpense({ ...expense, amount: e.target.value })} />
                <button className="bg-slate-900 text-white rounded" onClick={addExpense}>Add Expense</button>
            </div>
        </DashboardCard>
    );
};

export const HospitalInsuranceClaims = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [claims, setClaims] = useState([]);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ invoiceId: '', insurer: '', amount: '' });
    const [claimSearch, setClaimSearch] = useState('');
    const [claimSortBy, setClaimSortBy] = useState('createdAt');
    const [claimSortDir, setClaimSortDir] = useState('desc');

    const load = async () => {
        if (!hospitalId) return;
        setLoading(true);
        try {
            const claimQuery = buildQuery({
                hospitalId,
                search: claimSearch,
                sort_by: claimSortBy,
                sort_dir: claimSortDir
            });
            const res = await apiFetch(`/api/hospital-ops/finance/claims${claimQuery}`, { method: 'GET' });
            setClaims(res.ok ? (res.data?.data || []) : []);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, [hospitalId, claimSearch, claimSortBy, claimSortDir]);

    const createClaim = async () => {
        if (!hospitalId || !form.invoiceId || !form.amount) return;
        const res = await apiFetch('/api/hospital-ops/finance/claims', {
            method: 'POST',
            body: JSON.stringify({ hospitalId, invoiceId: form.invoiceId, insurer: form.insurer, amount: Number(form.amount) })
        });
        if (res.ok) {
            setClaims((prev) => [res.data, ...prev]);
            setForm({ invoiceId: '', insurer: '', amount: '' });
        }
    };

    const updateClaim = async (id, status) => {
        await apiFetch(`/api/hospital-ops/finance/claims/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
        setClaims((prev) => prev.map((claim) => (claim._id || claim.id) === id ? { ...claim, status } : claim));
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Insurance Claims</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Invoice ID" value={form.invoiceId} onChange={(e) => setForm({ ...form, invoiceId: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Insurer" value={form.insurer} onChange={(e) => setForm({ ...form, insurer: e.target.value })} />
                <input className="p-2 border rounded" type="number" placeholder="Amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
                <button className="bg-indigo-600 text-white rounded" onClick={createClaim}>Create Claim</button>
            </div>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search claims"
                    value={claimSearch}
                    onChange={(e) => setClaimSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={claimSortBy}
                    onChange={(e) => setClaimSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="amount">Amount</option>
                    <option value="status">Status</option>
                    <option value="insurer">Insurer</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={claimSortDir}
                    onChange={(e) => setClaimSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                    {claims.length === 0 ? (
                        <div className="text-sm text-gray-500">No claims filed.</div>
                    ) : (
                        claims.map((claim) => (
                            <div key={claim._id || claim.id} className="border rounded p-3 flex items-center justify-between">
                                <div>
                                    <p className="font-semibold text-gray-800">{claim.insurer || 'Insurer'}</p>
                                    <p className="text-xs text-gray-500">Invoice {claim.invoiceId} • ₹{claim.amount}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <StatusPill text={claim.status || 'Submitted'} color={claim.status === 'Approved' ? 'green' : 'yellow'} />
                                    <button className="text-xs text-green-600" onClick={() => updateClaim(claim._id || claim.id, 'Approved')}>Approve</button>
                                    <button className="text-xs text-red-600" onClick={() => updateClaim(claim._id || claim.id, 'Rejected')}>Reject</button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalLiveEmergencyFeed = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [surgeInsight, setSurgeInsight] = useState(null);
    const [triageResults, setTriageResults] = useState({});
    const [triageLoading, setTriageLoading] = useState({});
    const [imagingForms, setImagingForms] = useState({});
    const [dispatchForms, setDispatchForms] = useState({});
    const [dispatchStatus, setDispatchStatus] = useState('');
    const [feedSearch, setFeedSearch] = useState('');
    const [feedSortBy, setFeedSortBy] = useState('createdAt');
    const [feedSortDir, setFeedSortDir] = useState('desc');

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                if (!hospitalId) {
                    setAlerts([]);
                    return;
                }
                const feedQuery = buildQuery({
                    hospitalId,
                    search: feedSearch,
                    sort_by: feedSortBy,
                    sort_dir: feedSortDir
                });
                const [res, surgeRes] = await Promise.all([
                    apiFetch(`/api/hospital-ops/emergency/feed${feedQuery}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/ceo/ai-insights?hospitalId=${hospitalId}`, { method: 'GET' })
                ]);
                setAlerts(res.ok ? (res.data?.data || []) : []);
                setSurgeInsight(surgeRes.ok ? surgeRes.data : null);
            } catch (err) {
                setAlerts([]);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [hospitalId, feedSearch, feedSortBy, feedSortDir]);

    const updateStatus = async (alertId, status) => {
        setAlerts((prev) => prev.map((item) => item._id === alertId || item.id === alertId ? { ...item, status } : item));
        try {
            await apiFetch(`/api/hospital-ops/emergency/feed/${alertId}`, {
                method: 'PATCH',
                body: JSON.stringify({ status })
            });
        } catch (err) {
            // Keep optimistic update
        }
    };

    const runTriage = async (alert) => {
        const alertId = alert._id || alert.id;
        if (!alertId) return;
        setTriageLoading((prev) => ({ ...prev, [alertId]: true }));
        try {
            const res = await apiFetch('/api/hospital/triage', {
                method: 'POST',
                body: JSON.stringify({
                    symptoms: alert.symptoms || alert.message || 'Emergency',
                    severity_hint: alert.severity,
                })
            });
            if (res.ok) {
                setTriageResults((prev) => ({ ...prev, [alertId]: res.data }));
            }
        } finally {
            setTriageLoading((prev) => ({ ...prev, [alertId]: false }));
        }
    };

    const saveImaging = async (alertId) => {
        const form = imagingForms[alertId];
        if (!form?.modality && !form?.bodyPart && !form?.priority) return;
        await apiFetch(`/api/hospital-ops/emergency/feed/${alertId}`, {
            method: 'PATCH',
            body: JSON.stringify({
                imagingMeta: {
                    modality: form.modality,
                    bodyPart: form.bodyPart,
                    priority: form.priority,
                }
            })
        });
        setAlerts((prev) => prev.map((item) => (item._id || item.id) === alertId ? {
            ...item,
            imagingMeta: {
                modality: form.modality,
                bodyPart: form.bodyPart,
                priority: form.priority,
            }
        } : item));
    };

    const dispatchAmbulance = async (alertId) => {
        const form = dispatchForms[alertId];
        if (!form?.ambulanceId || !hospitalId) return;
        setDispatchStatus('Dispatching ambulance...');
        try {
            const res = await apiFetch('/api/hospital-ops/emergency/dispatch', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    ambulanceId: form.ambulanceId,
                    eventId: alertId,
                    pickup: form.pickup || 'Emergency pickup',
                    destination: form.destination || 'Hospital',
                    etaMinutes: form.etaMinutes ? Number(form.etaMinutes) : undefined,
                })
            });
            setDispatchStatus(res.ok ? 'Dispatch created.' : 'Dispatch failed.');
        } catch (err) {
            setDispatchStatus('Dispatch failed.');
        }
        setTimeout(() => setDispatchStatus(''), 4000);
    };

    return (
        <DashboardCard>
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h3 className="text-lg font-bold text-gray-900">Live Emergency Feed</h3>
                    <p className="text-sm text-gray-500">Incoming SOS and triage updates.</p>
                </div>
                <span className="text-xs text-gray-400">Updated {_nowLabel()}</span>
            </div>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search emergencies"
                    value={feedSearch}
                    onChange={(e) => setFeedSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={feedSortBy}
                    onChange={(e) => setFeedSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="severity">Severity</option>
                    <option value="status">Status</option>
                    <option value="priority">Priority</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={feedSortDir}
                    onChange={(e) => setFeedSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {surgeInsight && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                        <p className="text-xs text-gray-500">Emergency surge risk</p>
                        <p className="text-lg font-bold text-gray-900">{surgeInsight.emergency_spike_risk || 'Low'}</p>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                        <p className="text-xs text-gray-500">Predicted inflow</p>
                        <p className="text-lg font-bold text-gray-900">{surgeInsight.predicted_inflow || 0}</p>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded p-3">
                        <p className="text-xs text-gray-500">Bed strategy</p>
                        <p className="text-xs font-semibold text-gray-700">{surgeInsight.bed_allocation_strategy || 'Maintain standard allocation'}</p>
                    </div>
                </div>
            )}
            {dispatchStatus && (
                <div className="text-xs text-indigo-600 mb-3">{dispatchStatus}</div>
            )}
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 max-h-[520px] overflow-y-auto pr-2">
                    {alerts.length === 0 ? (
                        <div className="text-sm text-gray-500">No alerts at the moment.</div>
                    ) : (
                        alerts.map((alert) => (
                            <div key={alert._id || alert.id} className="border rounded-lg p-3 bg-white/70">
                                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                                    <div>
                                        <p className="font-semibold text-gray-800">{alert.message || 'Emergency alert'}</p>
                                        <p className="text-xs text-gray-500">{alert.locationDetails || alert.location || 'Unknown location'}</p>
                                        {alert.imagingMeta && (
                                            <p className="text-xs text-slate-500">Imaging: {alert.imagingMeta.modality || 'N/A'} {alert.imagingMeta.bodyPart ? `• ${alert.imagingMeta.bodyPart}` : ''}</p>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <StatusPill text={alert.severity || 'High'} color={alert.severity === 'Critical' ? 'red' : 'yellow'} />
                                        <StatusPill text={alert.status || 'Pending'} color={alert.status === 'Resolved' ? 'green' : 'blue'} />
                                        <button className="text-xs text-indigo-600" onClick={() => updateStatus(alert._id || alert.id, 'Resolved')}>Resolve</button>
                                    </div>
                                </div>
                                <div className="mt-3 grid grid-cols-1 lg:grid-cols-3 gap-3 text-sm">
                                    <div className="border rounded p-2">
                                        <p className="text-xs text-gray-500 mb-1">AI triage assist</p>
                                        {triageResults[alert._id || alert.id] ? (
                                            <p className="text-xs text-gray-700">Predicted severity: {triageResults[alert._id || alert.id].predicted_severity || 'Pending'}</p>
                                        ) : (
                                            <button
                                                className="text-xs text-indigo-600"
                                                onClick={() => runTriage(alert)}
                                                disabled={triageLoading[alert._id || alert.id]}
                                            >
                                                {triageLoading[alert._id || alert.id] ? 'Analyzing...' : 'Run AI triage'}
                                            </button>
                                        )}
                                    </div>
                                    <div className="border rounded p-2">
                                        <p className="text-xs text-gray-500 mb-1">Imaging metadata</p>
                                        <div className="grid grid-cols-3 gap-2">
                                            <input
                                                className="border rounded px-2 py-1 text-xs"
                                                placeholder="Modality"
                                                value={imagingForms[alert._id || alert.id]?.modality || ''}
                                                onChange={(e) => setImagingForms((prev) => ({
                                                    ...prev,
                                                    [alert._id || alert.id]: { ...prev[alert._id || alert.id], modality: e.target.value }
                                                }))}
                                            />
                                            <input
                                                className="border rounded px-2 py-1 text-xs"
                                                placeholder="Body part"
                                                value={imagingForms[alert._id || alert.id]?.bodyPart || ''}
                                                onChange={(e) => setImagingForms((prev) => ({
                                                    ...prev,
                                                    [alert._id || alert.id]: { ...prev[alert._id || alert.id], bodyPart: e.target.value }
                                                }))}
                                            />
                                            <input
                                                className="border rounded px-2 py-1 text-xs"
                                                placeholder="Priority"
                                                value={imagingForms[alert._id || alert.id]?.priority || ''}
                                                onChange={(e) => setImagingForms((prev) => ({
                                                    ...prev,
                                                    [alert._id || alert.id]: { ...prev[alert._id || alert.id], priority: e.target.value }
                                                }))}
                                            />
                                        </div>
                                        <button className="mt-2 text-xs text-indigo-600" onClick={() => saveImaging(alert._id || alert.id)}>Save imaging</button>
                                    </div>
                                    <div className="border rounded p-2">
                                        <p className="text-xs text-gray-500 mb-1">Dispatch ambulance</p>
                                        <div className="grid grid-cols-3 gap-2">
                                            <input
                                                className="border rounded px-2 py-1 text-xs"
                                                placeholder="Ambulance ID"
                                                value={dispatchForms[alert._id || alert.id]?.ambulanceId || ''}
                                                onChange={(e) => setDispatchForms((prev) => ({
                                                    ...prev,
                                                    [alert._id || alert.id]: { ...prev[alert._id || alert.id], ambulanceId: e.target.value }
                                                }))}
                                            />
                                            <input
                                                className="border rounded px-2 py-1 text-xs"
                                                placeholder="Pickup"
                                                value={dispatchForms[alert._id || alert.id]?.pickup || ''}
                                                onChange={(e) => setDispatchForms((prev) => ({
                                                    ...prev,
                                                    [alert._id || alert.id]: { ...prev[alert._id || alert.id], pickup: e.target.value }
                                                }))}
                                            />
                                            <input
                                                className="border rounded px-2 py-1 text-xs"
                                                placeholder="ETA (min)"
                                                value={dispatchForms[alert._id || alert.id]?.etaMinutes || ''}
                                                onChange={(e) => setDispatchForms((prev) => ({
                                                    ...prev,
                                                    [alert._id || alert.id]: { ...prev[alert._id || alert.id], etaMinutes: e.target.value }
                                                }))}
                                            />
                                        </div>
                                        <button className="mt-2 text-xs text-indigo-600" onClick={() => dispatchAmbulance(alert._id || alert.id)}>Dispatch</button>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalOPDScheduling = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [appointments, setAppointments] = useState([]);
    const [insights, setInsights] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [rescheduleTimes, setRescheduleTimes] = useState({});
    const [appointmentSearch, setAppointmentSearch] = useState('');
    const [appointmentSortBy, setAppointmentSortBy] = useState('createdAt');
    const [appointmentSortDir, setAppointmentSortDir] = useState('desc');
    const [form, setForm] = useState({
        patient: '',
        doctor: '',
        time: '',
        appointmentType: 'New',
        channel: 'Walk-in',
        expectedDurationMinutes: '20',
        reason: '',
        notes: '',
    });

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setAppointments([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const appointmentQuery = buildQuery({
                    hospitalId,
                    search: appointmentSearch,
                    sort_by: appointmentSortBy,
                    sort_dir: appointmentSortDir
                });
                const [res, insightRes] = await Promise.all([
                    apiFetch(`/api/hospital-ops/opd/appointments${appointmentQuery}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/opd/appointments/insights?hospitalId=${hospitalId}`, { method: 'GET' })
                ]);
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setAppointments(data);
                    setInsights(insightRes.ok ? insightRes.data : null);
                }
            } catch (err) {
                if (isActive) {
                    setAppointments([]);
                    setInsights(null);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, appointmentSearch, appointmentSortBy, appointmentSortDir]);

    const refreshInsights = async () => {
        if (!hospitalId) return;
        const res = await apiFetch(`/api/hospital-ops/opd/appointments/insights?hospitalId=${hospitalId}`, { method: 'GET' });
        setInsights(res.ok ? res.data : null);
    };

    const handleAdd = async () => {
        if (!form.patient || !form.doctor || !form.time || !hospitalId) return;
        setSubmitting(true);
        try {
            const res = await apiFetch('/api/hospital-ops/opd/appointments', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    patient: form.patient,
                    doctor: form.doctor,
                    time: form.time,
                    status: 'Scheduled',
                    appointmentType: form.appointmentType,
                    channel: form.channel,
                    expectedDurationMinutes: Number(form.expectedDurationMinutes || 20),
                    reason: form.reason,
                    notes: form.notes,
                })
            });
            if (res.ok) {
                setAppointments((prev) => [res.data, ...prev]);
                refreshInsights();
                setForm({
                    patient: '',
                    doctor: '',
                    time: '',
                    appointmentType: 'New',
                    channel: 'Walk-in',
                    expectedDurationMinutes: '20',
                    reason: '',
                    notes: '',
                });
            }
        } finally {
            setSubmitting(false);
        }
    };
    const demandScore = insights?.demandScore || 0;
    const seasonCoverageScore = insights?.seasonCoverageScore || 0;
    const weekdayVolume = insights?.weekdayVolume || [];
    const seasonCoverage = insights?.seasonCoverage || [];

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">OPD Demand Monitor</h3>
                        <p className="text-sm text-gray-500">Live appointment pressure and seasonality coverage.</p>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                        Live refresh
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div className="border rounded p-3">
                        <p className="text-xs text-gray-500">Next 7 days</p>
                        <p className="text-2xl font-bold text-gray-900">{insights?.next7Days || 0}</p>
                        <p className="text-xs text-gray-400">Peak day: {insights?.peakDay || 'Mon'}</p>
                    </div>
                    <div className="border rounded p-3">
                        <p className="text-xs text-gray-500">Demand score</p>
                        <p className="text-2xl font-bold text-gray-900">{demandScore}</p>
                        <ProgressBar value={demandScore} colorClass="bg-indigo-500" />
                    </div>
                    <div className="border rounded p-3">
                        <p className="text-xs text-gray-500">Seasonality coverage</p>
                        <p className="text-2xl font-bold text-gray-900">{seasonCoverageScore}%</p>
                        <ProgressBar value={seasonCoverageScore} colorClass="bg-emerald-500" />
                    </div>
                </div>
                {weekdayVolume.length ? (
                    <div className="h-52">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={weekdayVolume}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="label" />
                                <YAxis allowDecimals={false} />
                                <Tooltip />
                                <Bar dataKey="value" fill="#2563eb" radius={[6, 6, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                ) : (
                    <div className="text-sm text-gray-500">No appointment volume signals yet.</div>
                )}
                {seasonCoverage.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                        {seasonCoverage.map((item) => (
                            <span key={item.label} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-full">
                                {item.label}: {item.value}
                            </span>
                        ))}
                    </div>
                ) : null}
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-4">OPD Scheduling</h3>
                <div className="flex flex-col md:flex-row gap-2 mb-4">
                    <input
                        className="p-2 border rounded w-full"
                        placeholder="Search appointments"
                        value={appointmentSearch}
                        onChange={(e) => setAppointmentSearch(e.target.value)}
                    />
                    <select
                        className="p-2 border rounded"
                        value={appointmentSortBy}
                        onChange={(e) => setAppointmentSortBy(e.target.value)}
                    >
                        <option value="createdAt">Newest</option>
                        <option value="time">Time</option>
                        <option value="status">Status</option>
                        <option value="patient">Patient</option>
                        <option value="doctor">Doctor</option>
                    </select>
                    <select
                        className="p-2 border rounded"
                        value={appointmentSortDir}
                        onChange={(e) => setAppointmentSortDir(e.target.value)}
                    >
                        <option value="desc">Desc</option>
                        <option value="asc">Asc</option>
                    </select>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
                    <input className="p-2 border rounded" placeholder="Patient" value={form.patient} onChange={(e) => setForm({ ...form, patient: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Doctor" value={form.doctor} onChange={(e) => setForm({ ...form, doctor: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} />
                    <button className="bg-blue-600 text-white rounded" onClick={handleAdd} disabled={submitting}>
                        {submitting ? 'Saving...' : 'Add'}
                    </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                    <select className="p-2 border rounded" value={form.appointmentType} onChange={(e) => setForm({ ...form, appointmentType: e.target.value })}>
                        <option>New</option>
                        <option>Follow-up</option>
                        <option>Procedure</option>
                    </select>
                    <select className="p-2 border rounded" value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>
                        <option>Walk-in</option>
                        <option>Online</option>
                        <option>Referral</option>
                    </select>
                    <input
                        className="p-2 border rounded"
                        type="number"
                        placeholder="Duration (mins)"
                        value={form.expectedDurationMinutes}
                        onChange={(e) => setForm({ ...form, expectedDurationMinutes: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        placeholder="Reason"
                        value={form.reason}
                        onChange={(e) => setForm({ ...form, reason: e.target.value })}
                    />
                </div>
                <textarea
                    className="w-full border rounded p-2 text-sm mb-4"
                    placeholder="Notes"
                    rows="2"
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
                {loading ? (
                    <LoadingSpinner />
                ) : (
                    <div className="space-y-3 max-h-[520px] overflow-y-auto pr-2">
                        {appointments.length === 0 ? (
                            <div className="text-sm text-gray-500">No appointments logged.</div>
                        ) : (
                            appointments.map((item) => (
                                <div key={item._id || item.id} className="border rounded p-3">
                                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                                        <div>
                                            <p className="font-semibold text-gray-800">{item.patient}</p>
                                            <p className="text-xs text-gray-500">{item.doctor} • {item.time}</p>
                                            <p className="text-xs text-gray-400">{item.appointmentType || 'New'} • {item.channel || 'Walk-in'} • {item.expectedDurationMinutes || 20} mins</p>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <StatusPill text={item.status || 'Scheduled'} color={item.status === 'Completed' ? 'green' : item.status === 'Canceled' ? 'red' : 'blue'} />
                                            <input
                                                className="border rounded px-2 py-1 text-xs"
                                                placeholder="New time"
                                                value={rescheduleTimes[item._id || item.id] || ''}
                                                onChange={(e) => setRescheduleTimes((prev) => ({ ...prev, [item._id || item.id]: e.target.value }))}
                                            />
                                            <button
                                                className="text-xs text-indigo-600"
                                                onClick={async () => {
                                                    const id = item._id || item.id;
                                                    const newTime = rescheduleTimes[id];
                                                    const payload = newTime ? { status: 'Rescheduled', time: newTime } : { status: 'Rescheduled' };
                                                    setAppointments((prev) => prev.map((row) => (row._id || row.id) === id ? { ...row, ...payload } : row));
                                                    await apiFetch(`/api/hospital-ops/opd/appointments/${id}`, {
                                                        method: 'PATCH',
                                                        body: JSON.stringify(payload)
                                                    });
                                                    refreshInsights();
                                                }}
                                            >
                                                Reschedule
                                            </button>
                                            <button
                                                className="text-xs text-green-600"
                                                onClick={async () => {
                                                    const id = item._id || item.id;
                                                    setAppointments((prev) => prev.map((row) => (row._id || row.id) === id ? { ...row, status: 'Completed' } : row));
                                                    await apiFetch(`/api/hospital-ops/opd/appointments/${id}`, {
                                                        method: 'PATCH',
                                                        body: JSON.stringify({ status: 'Completed' })
                                                    });
                                                    refreshInsights();
                                                }}
                                            >
                                                Complete
                                            </button>
                                            <button
                                                className="text-xs text-red-600"
                                                onClick={async () => {
                                                    const id = item._id || item.id;
                                                    await apiFetch(`/api/hospital-ops/opd/appointments/${id}`, { method: 'DELETE' });
                                                    setAppointments((prev) => prev.filter((row) => (row._id || row.id) !== id));
                                                    refreshInsights();
                                                }}
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export const HospitalDoctorManagement = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [doctors, setDoctors] = useState([]);
    const [coverage, setCoverage] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [form, setForm] = useState({ name: '', specialty: '', shift: 'Morning', schedule: '' });
    const [doctorSearch, setDoctorSearch] = useState('');
    const [doctorSortBy, setDoctorSortBy] = useState('createdAt');
    const [doctorSortDir, setDoctorSortDir] = useState('desc');

    const refreshCoverage = async () => {
        if (!hospitalId) return;
        const res = await apiFetch(`/api/hospital-ops/opd/doctors/coverage?hospitalId=${hospitalId}`, { method: 'GET' });
        setCoverage(res.ok ? res.data : null);
    };

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setDoctors([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const doctorQuery = buildQuery({
                    hospitalId,
                    search: doctorSearch,
                    sort_by: doctorSortBy,
                    sort_dir: doctorSortDir
                });
                const [res, coverageRes] = await Promise.all([
                    apiFetch(`/api/hospital-ops/opd/doctors${doctorQuery}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/opd/doctors/coverage?hospitalId=${hospitalId}`, { method: 'GET' })
                ]);
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setDoctors(data);
                    setCoverage(coverageRes.ok ? coverageRes.data : null);
                }
            } catch (err) {
                if (isActive) {
                    setDoctors([]);
                    setCoverage(null);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, doctorSearch, doctorSortBy, doctorSortDir]);

    const handleAdd = async () => {
        if (!form.name || !form.specialty || !hospitalId) return;
        setSubmitting(true);
        try {
            const res = await apiFetch('/api/hospital-ops/opd/doctors', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    name: form.name,
                    specialty: form.specialty,
                    availability: true,
                    shift: form.shift,
                    schedule: form.schedule
                })
            });
            if (res.ok) {
                setDoctors((prev) => [res.data, ...prev]);
                setForm({ name: '', specialty: '', shift: 'Morning', schedule: '' });
                refreshCoverage();
            }
        } finally {
            setSubmitting(false);
        }
    };

    const toggle = async (id, availability) => {
        setDoctors((prev) => prev.map((doc) => (doc._id || doc.id) === id ? { ...doc, availability: !availability } : doc));
        try {
            await apiFetch(`/api/hospital-ops/opd/doctors/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({ availability: !availability })
            });
            refreshCoverage();
        } catch (err) {
            // Keep optimistic update
        }
    };

    const handleRemove = async (id) => {
        await apiFetch(`/api/hospital-ops/opd/doctors/${id}`, { method: 'DELETE' });
        setDoctors((prev) => prev.filter((doc) => (doc._id || doc.id) !== id));
        refreshCoverage();
    };
    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">Specialty Coverage</h3>
                        <p className="text-sm text-gray-500">Live roster balance and gap tracking.</p>
                    </div>
                    <div className="text-xs text-gray-400">Availability {coverage?.availabilityRate || 0}%</div>
                </div>
                {!coverage ? (
                    <div className="text-sm text-gray-500">No coverage signals yet.</div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="space-y-2">
                            {(coverage.specialtyCoverage || []).map((item) => (
                                <div key={item.specialty} className="flex items-center justify-between border rounded px-3 py-2 text-sm">
                                    <span className="text-gray-600">{item.specialty}</span>
                                    <span className="font-semibold text-gray-900">{item.available}/{item.total}</span>
                                </div>
                            ))}
                        </div>
                        <div className="space-y-2">
                            {(coverage.shiftCoverage || []).map((item) => (
                                <div key={item.shift} className="flex items-center justify-between border rounded px-3 py-2 text-sm">
                                    <span className="text-gray-600">{item.shift}</span>
                                    <span className="font-semibold text-gray-900">{item.count}</span>
                                </div>
                            ))}
                            {(coverage.coverageGaps || []).length > 0 && (
                                <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                                    Coverage gaps: {coverage.coverageGaps.join(', ')}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-4">Doctor Management</h3>
                <div className="flex flex-col md:flex-row gap-2 mb-4">
                    <input
                        className="p-2 border rounded w-full"
                        placeholder="Search doctors"
                        value={doctorSearch}
                        onChange={(e) => setDoctorSearch(e.target.value)}
                    />
                    <select
                        className="p-2 border rounded"
                        value={doctorSortBy}
                        onChange={(e) => setDoctorSortBy(e.target.value)}
                    >
                        <option value="createdAt">Newest</option>
                        <option value="name">Name</option>
                        <option value="specialty">Specialty</option>
                        <option value="availability">Availability</option>
                    </select>
                    <select
                        className="p-2 border rounded"
                        value={doctorSortDir}
                        onChange={(e) => setDoctorSortDir(e.target.value)}
                    >
                        <option value="desc">Desc</option>
                        <option value="asc">Asc</option>
                    </select>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
                    <input className="p-2 border rounded" placeholder="Doctor name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Specialty" value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} />
                    <select className="p-2 border rounded" value={form.shift} onChange={(e) => setForm({ ...form, shift: e.target.value })}>
                        <option>Morning</option>
                        <option>Afternoon</option>
                        <option>Night</option>
                    </select>
                    <button className="bg-indigo-600 text-white rounded" onClick={handleAdd} disabled={submitting}>
                        {submitting ? 'Saving...' : 'Add Doctor'}
                    </button>
                </div>
                <input
                    className="p-2 border rounded w-full mb-4"
                    placeholder="Schedule (ex: Mon-Fri 9am-1pm)"
                    value={form.schedule}
                    onChange={(e) => setForm({ ...form, schedule: e.target.value })}
                />
                {loading ? (
                    <LoadingSpinner />
                ) : (
                    <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                        {doctors.length === 0 ? (
                            <div className="text-sm text-gray-500">No doctors found.</div>
                        ) : (
                            doctors.map((doc) => (
                                <div key={doc._id || doc.id} className="flex flex-col md:flex-row md:items-center justify-between gap-3 border rounded p-3">
                                    <div>
                                        <p className="font-semibold text-gray-800">{doc.name}</p>
                                        <p className="text-xs text-gray-500">{doc.specialty} • {doc.normalizedShift || doc.shift || 'Unassigned'}</p>
                                        {doc.schedule && <p className="text-xs text-gray-400">{doc.schedule}</p>}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <StatusPill text={doc.availability ? 'Available' : 'Off Duty'} color={doc.availability ? 'green' : 'gray'} />
                                        <button className="text-xs text-indigo-600" onClick={() => toggle(doc._id || doc.id, doc.availability)}>
                                            Toggle
                                        </button>
                                        <button className="text-xs text-red-600" onClick={() => handleRemove(doc._id || doc.id)}>
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export const HospitalConsultationRecords = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [records, setRecords] = useState([]);
    const [insights, setInsights] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [form, setForm] = useState({ patient: '', doctor: '', notes: '', followUpDate: '' });
    const [consultSearch, setConsultSearch] = useState('');
    const [consultSortBy, setConsultSortBy] = useState('createdAt');
    const [consultSortDir, setConsultSortDir] = useState('desc');

    const refreshInsights = async () => {
        if (!hospitalId) return;
        const res = await apiFetch(`/api/hospital-ops/opd/consultations/insights?hospitalId=${hospitalId}`, { method: 'GET' });
        setInsights(res.ok ? res.data : null);
    };

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setRecords([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const consultQuery = buildQuery({
                    hospitalId,
                    search: consultSearch,
                    sort_by: consultSortBy,
                    sort_dir: consultSortDir
                });
                const [res, insightRes] = await Promise.all([
                    apiFetch(`/api/hospital-ops/opd/consultations${consultQuery}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/opd/consultations/insights?hospitalId=${hospitalId}`, { method: 'GET' })
                ]);
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setRecords(data);
                    setInsights(insightRes.ok ? insightRes.data : null);
                }
            } catch (err) {
                if (isActive) {
                    setRecords([]);
                    setInsights(null);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, consultSearch, consultSortBy, consultSortDir]);

    const handleAdd = async () => {
        if (!form.patient || !form.doctor || !form.notes || !hospitalId) return;
        setSubmitting(true);
        try {
            const res = await apiFetch('/api/hospital-ops/opd/consultations', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    patient: form.patient,
                    doctor: form.doctor,
                    notes: form.notes,
                    status: 'Open',
                    followUpDate: form.followUpDate || null
                })
            });
            if (res.ok) {
                setRecords((prev) => [res.data, ...prev]);
                refreshInsights();
                setForm({ patient: '', doctor: '', notes: '', followUpDate: '' });
            }
        } finally {
            setSubmitting(false);
        }
    };
    const coverage = insights?.summaryCoverage || 0;

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">Consultation Insights</h3>
                        <p className="text-sm text-gray-500">AI summary coverage and follow-up signals.</p>
                    </div>
                    <div className="text-xs text-gray-400">Coverage {coverage}%</div>
                </div>
                {insights ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="border rounded p-3">
                            <p className="text-xs text-gray-500">Records analyzed</p>
                            <p className="text-2xl font-bold text-gray-900">{insights.total || 0}</p>
                        </div>
                        <div className="border rounded p-3">
                            <p className="text-xs text-gray-500">Follow-ups flagged</p>
                            <p className="text-2xl font-bold text-gray-900">{insights.followUps || 0}</p>
                        </div>
                        <div className="border rounded p-3">
                            <p className="text-xs text-gray-500">Summary coverage</p>
                            <p className="text-2xl font-bold text-gray-900">{coverage}%</p>
                            <ProgressBar value={coverage} colorClass="bg-sky-500" />
                        </div>
                    </div>
                ) : (
                    <div className="text-sm text-gray-500">No consultation insights yet.</div>
                )}
                {(insights?.topKeywords || []).length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2">
                        {insights.topKeywords.map((item) => (
                            <span key={item.label} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-full">
                                {item.label}: {item.value}
                            </span>
                        ))}
                    </div>
                )}
            </DashboardCard>

            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-4">Consultation Records</h3>
                <div className="flex flex-col md:flex-row gap-2 mb-4">
                    <input
                        className="p-2 border rounded w-full"
                        placeholder="Search consultations"
                        value={consultSearch}
                        onChange={(e) => setConsultSearch(e.target.value)}
                    />
                    <select
                        className="p-2 border rounded"
                        value={consultSortBy}
                        onChange={(e) => setConsultSortBy(e.target.value)}
                    >
                        <option value="createdAt">Newest</option>
                        <option value="date">Date</option>
                        <option value="status">Status</option>
                        <option value="patient">Patient</option>
                        <option value="doctor">Doctor</option>
                    </select>
                    <select
                        className="p-2 border rounded"
                        value={consultSortDir}
                        onChange={(e) => setConsultSortDir(e.target.value)}
                    >
                        <option value="desc">Desc</option>
                        <option value="asc">Asc</option>
                    </select>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                    <input className="p-2 border rounded" placeholder="Patient" value={form.patient} onChange={(e) => setForm({ ...form, patient: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Doctor" value={form.doctor} onChange={(e) => setForm({ ...form, doctor: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Follow-up date" value={form.followUpDate} onChange={(e) => setForm({ ...form, followUpDate: e.target.value })} />
                </div>
                <textarea
                    className="w-full border rounded p-2 text-sm mb-3"
                    placeholder="Notes"
                    rows="2"
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
                <button className="bg-blue-600 text-white rounded px-4 py-2" onClick={handleAdd} disabled={submitting}>
                    {submitting ? 'Saving...' : 'Add Record'}
                </button>
                {loading ? (
                    <LoadingSpinner />
                ) : (
                    <div className="space-y-3 mt-4 max-h-[520px] overflow-y-auto pr-2">
                        {records.length === 0 ? (
                            <div className="text-sm text-gray-500">No consultations yet.</div>
                        ) : (
                            records.map((record) => (
                                <div key={record._id || record.id} className="border rounded p-3">
                                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                                        <div>
                                            <p className="font-semibold text-gray-800">{record.patient}</p>
                                            <p className="text-xs text-gray-500">{record.doctor} • {record.date}</p>
                                            {record.followUpDate && (
                                                <p className="text-xs text-indigo-500">Follow-up: {record.followUpDate}</p>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <StatusPill text={record.status || 'Open'} color={record.status === 'Closed' ? 'green' : record.status === 'Follow-up' ? 'blue' : 'yellow'} />
                                            <button
                                                className="text-xs text-green-600"
                                                onClick={async () => {
                                                    const id = record._id || record.id;
                                                    setRecords((prev) => prev.map((row) => (row._id || row.id) === id ? { ...row, status: 'Closed' } : row));
                                                    await apiFetch(`/api/hospital-ops/opd/consultations/${id}`, {
                                                        method: 'PATCH',
                                                        body: JSON.stringify({ status: 'Closed' })
                                                    });
                                                    refreshInsights();
                                                }}
                                            >
                                                Close
                                            </button>
                                            <button
                                                className="text-xs text-indigo-600"
                                                onClick={async () => {
                                                    const id = record._id || record.id;
                                                    setRecords((prev) => prev.map((row) => (row._id || row.id) === id ? { ...row, status: 'Follow-up' } : row));
                                                    await apiFetch(`/api/hospital-ops/opd/consultations/${id}`, {
                                                        method: 'PATCH',
                                                        body: JSON.stringify({ status: 'Follow-up' })
                                                    });
                                                    refreshInsights();
                                                }}
                                            >
                                                Follow-up
                                            </button>
                                            <button
                                                className="text-xs text-red-600"
                                                onClick={async () => {
                                                    const id = record._id || record.id;
                                                    await apiFetch(`/api/hospital-ops/opd/consultations/${id}`, { method: 'DELETE' });
                                                    setRecords((prev) => prev.filter((row) => (row._id || row.id) !== id));
                                                    refreshInsights();
                                                }}
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    </div>
                                    <p className="text-sm text-gray-600 mt-2">{record.notes}</p>
                                    {record.aiSummary && (
                                        <p className="text-xs text-slate-500 mt-2">AI summary: {record.aiSummary}</p>
                                    )}
                                    {record.followUpPlan && (
                                        <p className="text-xs text-amber-600 mt-1">{record.followUpPlan}</p>
                                    )}
                                    {(record.keywords || []).length > 0 && (
                                        <div className="flex flex-wrap gap-2 mt-2">
                                            {record.keywords.map((item) => (
                                                <span key={item} className="text-[11px] bg-slate-100 text-slate-600 px-2 py-1 rounded-full">{item}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export const HospitalOPDQueue = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [queue, setQueue] = useState([]);
    const [avgWait, setAvgWait] = useState(0);
    const [queuePressure, setQueuePressure] = useState(0);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ patientName: '', reason: '', priority: 'Normal', assignedDoctor: '' });
    const [assignmentDrafts, setAssignmentDrafts] = useState({});
    const [queueSearch, setQueueSearch] = useState('');
    const [queueSortBy, setQueueSortBy] = useState('createdAt');
    const [queueSortDir, setQueueSortDir] = useState('asc');

    const loadQueue = async (isActive) => {
        if (!hospitalId) {
            if (isActive) setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const queueQuery = buildQuery({
                hospitalId,
                search: queueSearch,
                sort_by: queueSortBy,
                sort_dir: queueSortDir
            });
            const res = await apiFetch(`/api/hospital-ops/opd/queue${queueQuery}`, { method: 'GET' });
            if (res.ok && isActive) {
                setQueue(res.data?.data || []);
                setAvgWait(res.data?.avgWaitMinutes || 0);
                setQueuePressure(res.data?.queuePressure || 0);
            }
        } finally {
            if (isActive) setLoading(false);
        }
    };

    useEffect(() => {
        let isActive = true;
        loadQueue(isActive);
        return () => { isActive = false; };
    }, [hospitalId, queueSearch, queueSortBy, queueSortDir]);

    const handleAdd = async () => {
        if (!hospitalId || !form.patientName) return;
        const res = await apiFetch('/api/hospital-ops/opd/queue', {
            method: 'POST',
            body: JSON.stringify({
                hospitalId,
                patientName: form.patientName,
                reason: form.reason,
                priority: form.priority,
                assignedDoctor: form.assignedDoctor
            })
        });
        if (res.ok) {
            setQueue((prev) => [...prev, res.data]);
            setForm({ patientName: '', reason: '', priority: 'Normal', assignedDoctor: '' });
        }
    };

    const updateQueue = async (id, status) => {
        setQueue((prev) => prev.map((item) => (item._id || item.id) === id ? { ...item, status } : item));
        await apiFetch(`/api/hospital-ops/opd/queue/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
        loadQueue(true);
    };

    const saveAssignment = async (id) => {
        const assignedDoctor = assignmentDrafts[id];
        if (assignedDoctor === undefined) return;
        setQueue((prev) => prev.map((item) => (item._id || item.id) === id ? { ...item, assignedDoctor } : item));
        await apiFetch(`/api/hospital-ops/opd/queue/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ assignedDoctor })
        });
        loadQueue(true);
    };

    const handleRemove = async (id) => {
        await apiFetch(`/api/hospital-ops/opd/queue/${id}`, { method: 'DELETE' });
        setQueue((prev) => prev.filter((item) => (item._id || item.id) !== id));
        loadQueue(true);
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">OPD Queue Live Monitor</h3>
                        <p className="text-sm text-gray-500">Average wait: {avgWait} minutes</p>
                    </div>
                    <div className="text-xs text-gray-400">Pressure {queuePressure}%</div>
                </div>
                <ProgressBar value={queuePressure} colorClass="bg-rose-500" />
            </DashboardCard>

            <DashboardCard>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                    <input className="p-2 border rounded" placeholder="Patient" value={form.patientName} onChange={(e) => setForm({ ...form, patientName: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Reason" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
                    <select className="p-2 border rounded" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                        <option>Normal</option>
                        <option>High</option>
                        <option>Critical</option>
                    </select>
                    <button className="bg-indigo-600 text-white rounded" onClick={handleAdd}>Add</button>
                </div>
                <div className="flex flex-col md:flex-row gap-2 mb-4">
                    <input
                        className="p-2 border rounded w-full"
                        placeholder="Search queue"
                        value={queueSearch}
                        onChange={(e) => setQueueSearch(e.target.value)}
                    />
                    <select
                        className="p-2 border rounded"
                        value={queueSortBy}
                        onChange={(e) => setQueueSortBy(e.target.value)}
                    >
                        <option value="createdAt">Check-in</option>
                        <option value="priority">Priority</option>
                        <option value="status">Status</option>
                        <option value="patientName">Patient</option>
                    </select>
                    <select
                        className="p-2 border rounded"
                        value={queueSortDir}
                        onChange={(e) => setQueueSortDir(e.target.value)}
                    >
                        <option value="asc">Asc</option>
                        <option value="desc">Desc</option>
                    </select>
                </div>
                <input
                    className="p-2 border rounded w-full mb-4"
                    placeholder="Assign doctor"
                    value={form.assignedDoctor}
                    onChange={(e) => setForm({ ...form, assignedDoctor: e.target.value })}
                />
                {loading ? (
                    <LoadingSpinner />
                ) : (
                    <div className="space-y-3 max-h-[520px] overflow-y-auto pr-2">
                        {queue.length === 0 ? (
                            <div className="text-sm text-gray-500">Queue is empty.</div>
                        ) : (
                            queue.map((item) => (
                                <div key={item._id || item.id} className="border rounded p-3">
                                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                                        <div>
                                            <p className="font-semibold text-gray-800">{item.patientName}</p>
                                            <p className="text-xs text-gray-500">{item.reason || 'General'} • {item.priority}</p>
                                            <p className="text-xs text-gray-400">
                                                ETA {item.predictedWaitMinutes || 0} min • Check-in {item.checkInAt ? new Date(item.checkInAt).toLocaleTimeString() : 'N/A'}
                                            </p>
                                            {item.assignedDoctor && (
                                                <p className="text-xs text-indigo-500">Assigned: {item.assignedDoctor}</p>
                                            )}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <StatusPill text={item.status || 'Waiting'} color={item.status === 'In Service' ? 'blue' : item.status === 'Completed' ? 'green' : 'yellow'} />
                                            <button className="text-xs text-indigo-600" onClick={() => updateQueue(item._id || item.id, 'In Service')}>Serve</button>
                                            <button className="text-xs text-green-600" onClick={() => updateQueue(item._id || item.id, 'Completed')}>Complete</button>
                                            <button className="text-xs text-amber-600" onClick={() => updateQueue(item._id || item.id, 'Canceled')}>Cancel</button>
                                            <button className="text-xs text-red-600" onClick={() => handleRemove(item._id || item.id)}>Delete</button>
                                        </div>
                                    </div>
                                    <div className="mt-2">
                                        <div className="flex gap-2">
                                            <input
                                                className="border rounded px-2 py-1 text-xs w-full"
                                                placeholder="Assign doctor"
                                                value={assignmentDrafts[item._id || item.id] ?? item.assignedDoctor ?? ''}
                                                onChange={(e) => setAssignmentDrafts((prev) => ({
                                                    ...prev,
                                                    [item._id || item.id]: e.target.value
                                                }))}
                                            />
                                            <button
                                                className="text-xs text-indigo-600"
                                                onClick={() => saveAssignment(item._id || item.id)}
                                            >
                                                Save
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export const HospitalICULiveMonitoring = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [patients, setPatients] = useState([]);
    const [loading, setLoading] = useState(true);
    const [riskScores, setRiskScores] = useState({});
    const [icuSearch, setIcuSearch] = useState('');
    const [icuSortBy, setIcuSortBy] = useState('createdAt');
    const [icuSortDir, setIcuSortDir] = useState('desc');

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setPatients([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const icuQuery = buildQuery({
                    hospitalId,
                    search: icuSearch,
                    sort_by: icuSortBy,
                    sort_dir: icuSortDir
                });
                const res = await apiFetch(`/api/hospital-ops/icu/patients${icuQuery}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setPatients(data);
                }
            } catch (err) {
                if (isActive) {
                    setPatients([]);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, icuSearch, icuSortBy, icuSortDir]);

    const assessRisk = async (patient) => {
        const id = patient._id || patient.id;
        const res = await apiFetch('/api/hospital-ops/icu/risk', {
            method: 'POST',
            body: JSON.stringify({ oxygen: patient.oxygen, heartRate: patient.heartRate })
        });
        if (res.ok) {
            setRiskScores((prev) => ({ ...prev, [id]: res.data }));
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">ICU Live Monitoring</h3>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search ICU patients"
                    value={icuSearch}
                    onChange={(e) => setIcuSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={icuSortBy}
                    onChange={(e) => setIcuSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="name">Name</option>
                    <option value="oxygen">Oxygen</option>
                    <option value="heartRate">Heart Rate</option>
                    <option value="status">Status</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={icuSortDir}
                    onChange={(e) => setIcuSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-4 max-h-[520px] overflow-y-auto pr-2">
                    {patients.map((patient) => (
                        <div key={patient._id || patient.id} className="border rounded-lg p-3">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="font-semibold text-gray-800">{patient.name}</p>
                                    <p className="text-xs text-gray-500">{patient._id || patient.id} • BP {patient.bp}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <StatusPill text={patient.status} color={patient.status === 'Critical' ? 'red' : 'green'} />
                                    <button className="text-xs text-indigo-600" onClick={() => assessRisk(patient)}>Assess</button>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 mt-3">
                                <div>
                                    <p className="text-xs text-gray-500">Oxygen {patient.oxygen}%</p>
                                    <ProgressBar value={patient.oxygen} colorClass={patient.oxygen < 92 ? 'bg-red-500' : 'bg-green-500'} />
                                </div>
                                <div>
                                    <p className="text-xs text-gray-500">Heart Rate {patient.heartRate} bpm</p>
                                    <ProgressBar value={Math.min(patient.heartRate, 140) / 1.4} colorClass="bg-indigo-500" />
                                </div>
                            </div>
                            {riskScores[patient._id || patient.id] && (
                                <div className="mt-3 text-xs text-gray-600">
                                    Risk: <span className="font-semibold">{riskScores[patient._id || patient.id].riskLevel}</span> ({riskScores[patient._id || patient.id].riskScore})
                                    <ExplainabilityPanel meta={riskScores[patient._id || patient.id].meta} />
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalICUAlerts = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [alertSearch, setAlertSearch] = useState('');
    const [alertSortBy, setAlertSortBy] = useState('createdAt');
    const [alertSortDir, setAlertSortDir] = useState('desc');

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setAlerts([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const alertQuery = buildQuery({
                    hospitalId,
                    search: alertSearch,
                    sort_by: alertSortBy,
                    sort_dir: alertSortDir
                });
                const res = await apiFetch(`/api/hospital-ops/icu/alerts${alertQuery}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setAlerts(data);
                }
            } catch (err) {
                if (isActive) {
                    setAlerts([]);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, alertSearch, alertSortBy, alertSortDir]);

    const updateStatus = async (id, status) => {
        setAlerts((prev) => prev.map((alert) => (alert._id || alert.id) === id ? { ...alert, status } : alert));
        try {
            await apiFetch(`/api/hospital-ops/icu/alerts/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({ status })
            });
        } catch (err) {
            // Keep optimistic update
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">ICU Critical Alerts</h3>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search alerts"
                    value={alertSearch}
                    onChange={(e) => setAlertSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={alertSortBy}
                    onChange={(e) => setAlertSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="severity">Severity</option>
                    <option value="status">Status</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={alertSortDir}
                    onChange={(e) => setAlertSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                    {alerts.map((alert) => (
                        <div key={alert._id || alert.id} className="flex items-center justify-between border rounded p-3">
                            <div>
                                <p className="font-semibold text-gray-800">{alert.message}</p>
                                <p className="text-xs text-gray-500">{alert.status || 'Active'}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <StatusPill text={alert.severity} color={alert.severity === 'Critical' ? 'red' : 'yellow'} />
                                <button className="text-xs text-indigo-600" onClick={() => updateStatus(alert._id || alert.id, 'Resolved')}>
                                    Resolve
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalICUVitals = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                if (isActive) {
                    setStats(null);
                    setLoading(false);
                }
                return;
            }
            try {
                const res = await apiFetch(`/api/hospital-ops/icu/vitals?hospitalId=${hospitalId}`, { method: 'GET' });
                if (res.ok && isActive) {
                    setStats(res.data);
                }
            } finally {
                if (isActive) setLoading(false);
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId]);

    if (loading) {
        return (
            <DashboardCard>
                <LoadingSpinner />
            </DashboardCard>
        );
    }

    const safeStats = stats || {
        average_oxygen: 0,
        average_heart_rate: 0,
        critical_patients: 0,
        patient_count: 0,
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">ICU Vitals Dashboard</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <DashboardCard>
                    <p className="text-xs text-gray-500">Average O2</p>
                    <p className="text-2xl font-bold text-gray-900">{safeStats.average_oxygen}%</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs text-gray-500">Avg Heart Rate</p>
                    <p className="text-2xl font-bold text-gray-900">{safeStats.average_heart_rate} bpm</p>
                </DashboardCard>
                <DashboardCard>
                    <p className="text-xs text-gray-500">Critical Patients</p>
                    <p className="text-2xl font-bold text-red-600">{safeStats.critical_patients}</p>
                </DashboardCard>
            </div>
            <div className="mt-4 text-sm text-gray-500">Last refreshed {_nowLabel()}</div>
        </DashboardCard>
    );
};

export const HospitalICURiskPanel = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [patients, setPatients] = useState([]);
    const [risks, setRisks] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) return;
            setLoading(true);
            try {
                const res = await apiFetch(`/api/hospital-ops/icu/patients?hospitalId=${hospitalId}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                if (!isActive) return;
                setPatients(data);
                const riskResults = await Promise.all(
                    data.map(async (patient) => {
                        const riskRes = await apiFetch('/api/hospital-ops/icu/risk', {
                            method: 'POST',
                            body: JSON.stringify({ oxygen: patient.oxygen, heartRate: patient.heartRate })
                        });
                        return {
                            patient,
                            risk: riskRes.ok ? riskRes.data : { riskScore: 0, riskLevel: 'Low' }
                        };
                    })
                );
                setRisks(riskResults.sort((a, b) => (b.risk.riskScore || 0) - (a.risk.riskScore || 0)));
            } finally {
                if (isActive) setLoading(false);
            }
        };
        load();
        return () => { isActive = false; };
    }, [hospitalId]);

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">AI ICU Risk Prediction</h3>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 max-h-[360px] overflow-y-auto pr-2">
                    {risks.length === 0 ? (
                        <div className="text-sm text-gray-500">No ICU patients available.</div>
                    ) : (
                        risks.slice(0, 6).map((item) => (
                            <div key={item.patient._id || item.patient.id} className="border rounded p-3 flex items-center justify-between">
                                <div>
                                    <p className="font-semibold text-gray-800">{item.patient.name}</p>
                                    <p className="text-xs text-gray-500">O2 {item.patient.oxygen}% • HR {item.patient.heartRate} bpm</p>
                                </div>
                                <StatusPill text={`${item.risk.riskLevel} (${item.risk.riskScore})`} color={item.risk.riskLevel === 'Critical' ? 'red' : item.risk.riskLevel === 'High' ? 'yellow' : 'green'} />
                            </div>
                        ))
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalRadiologyRequests = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [requests, setRequests] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [form, setForm] = useState({ patient: '', scan: '' });
    const [requestSearch, setRequestSearch] = useState('');
    const [requestSortBy, setRequestSortBy] = useState('createdAt');
    const [requestSortDir, setRequestSortDir] = useState('desc');

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setRequests([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const requestQuery = buildQuery({
                    hospitalId,
                    search: requestSearch,
                    sort_by: requestSortBy,
                    sort_dir: requestSortDir
                });
                const res = await apiFetch(`/api/hospital-ops/radiology/requests${requestQuery}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setRequests(data);
                }
            } catch (err) {
                if (isActive) {
                    setRequests([]);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, requestSearch, requestSortBy, requestSortDir]);

    const updateStatus = async (id, status) => {
        setRequests((prev) => prev.map((item) => (item._id || item.id) === id ? { ...item, status } : item));
        try {
            await apiFetch(`/api/hospital-ops/radiology/requests/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({ status })
            });
        } catch (err) {
            // Keep optimistic update
        }
    };

    const handleAdd = async () => {
        if (!hospitalId || !form.patient || !form.scan) return;
        setSubmitting(true);
        try {
            const res = await apiFetch('/api/hospital-ops/radiology/requests', {
                method: 'POST',
                body: JSON.stringify({ hospitalId, patient: form.patient, scan: form.scan, status: 'Queued' })
            });
            if (res.ok) {
                setRequests((prev) => [res.data, ...prev]);
                setForm({ patient: '', scan: '' });
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Scan Requests</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Patient" value={form.patient} onChange={(e) => setForm({ ...form, patient: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Scan Type" value={form.scan} onChange={(e) => setForm({ ...form, scan: e.target.value })} />
                <button className="bg-indigo-600 text-white rounded" onClick={handleAdd} disabled={submitting}>
                    {submitting ? 'Adding...' : 'Add Request'}
                </button>
            </div>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search requests"
                    value={requestSearch}
                    onChange={(e) => setRequestSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={requestSortBy}
                    onChange={(e) => setRequestSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="patient">Patient</option>
                    <option value="scan">Scan</option>
                    <option value="status">Status</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={requestSortDir}
                    onChange={(e) => setRequestSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                    {requests.map((req) => (
                        <div key={req._id || req.id} className="flex items-center justify-between border rounded p-3">
                            <div>
                                <p className="font-semibold text-gray-800">{req.patient}</p>
                                <p className="text-xs text-gray-500">{req.scan}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <StatusPill text={req.status || 'Queued'} color={req.status === 'Completed' ? 'green' : 'yellow'} />
                                <button className="text-xs text-indigo-600" onClick={() => updateStatus(req._id || req.id, 'Completed')}>
                                    Mark Done
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalRadiologyReportUpload = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [form, setForm] = useState({ patient: '', scan: '', file: null });
    const [reportSearch, setReportSearch] = useState('');
    const [reportSortBy, setReportSortBy] = useState('createdAt');
    const [reportSortDir, setReportSortDir] = useState('desc');

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const reportQuery = buildQuery({
                    hospitalId,
                    search: reportSearch,
                    sort_by: reportSortBy,
                    sort_dir: reportSortDir
                });
                const res = await apiFetch(`/api/hospital-ops/radiology/reports${reportQuery}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setReports(data);
                }
            } catch (err) {
                if (isActive) {
                    setReports([]);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, reportSearch, reportSortBy, reportSortDir]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.patient || !form.scan || !hospitalId) return;
        setSubmitting(true);
        try {
            const res = await apiFetch('/api/hospital-ops/radiology/reports', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    patient: form.patient,
                    scan: form.scan,
                    fileName: form.file?.name,
                    status: 'Uploaded'
                })
            });
            if (res.ok) {
                setReports((prev) => [res.data, ...prev]);
                setForm({ patient: '', scan: '', file: null });
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Report Upload</h3>
            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <input className="p-2 border rounded" placeholder="Patient" value={form.patient} onChange={(e) => setForm({ ...form, patient: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Scan Type" value={form.scan} onChange={(e) => setForm({ ...form, scan: e.target.value })} />
                <input className="p-2 border rounded" type="file" onChange={(e) => setForm({ ...form, file: e.target.files?.[0] })} />
                <button type="submit" className="bg-indigo-600 text-white rounded" disabled={submitting}>
                    {submitting ? 'Uploading...' : 'Upload'}
                </button>
            </form>
            <div className="flex flex-col md:flex-row gap-2 mt-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search reports"
                    value={reportSearch}
                    onChange={(e) => setReportSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={reportSortBy}
                    onChange={(e) => setReportSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="patient">Patient</option>
                    <option value="scan">Scan</option>
                    <option value="status">Status</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={reportSortDir}
                    onChange={(e) => setReportSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 mt-4 max-h-[420px] overflow-y-auto pr-2">
                    {reports.map((rep) => (
                        <div key={rep._id || rep.id} className="flex items-center justify-between border rounded p-3">
                            <div>
                                <p className="font-semibold text-gray-800">{rep.patient}</p>
                                <p className="text-xs text-gray-500">{rep.scan}{rep.fileName ? ` • ${rep.fileName}` : ''}</p>
                            </div>
                            <StatusPill text={rep.status || 'Uploaded'} color="green" />
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalRadiologyAIInsights = () => {
    const [text, setText] = useState('');
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleAnalyze = async (e) => {
        e.preventDefault();
        if (!text.trim()) return;
        setLoading(true);
        try {
            const res = await apiFetch('/api/analyze_report', {
                method: 'POST',
                body: JSON.stringify({ report_text: text })
            });
            setResult(res.ok ? res.data : { error: res.data?.error || 'Analysis failed' });
        } catch (err) {
            setResult({ error: 'Analysis failed' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">AI Scan Insights</h3>
            <form onSubmit={handleAnalyze} className="space-y-3">
                <textarea
                    className="w-full p-3 border rounded min-h-[120px]"
                    placeholder="Paste scan notes for AI summary"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                />
                <button className="bg-purple-600 text-white rounded px-4 py-2" type="submit" disabled={loading}>
                    {loading ? 'Analyzing...' : 'Analyze'}
                </button>
            </form>
            {result && (
                <div className="mt-4 border rounded p-3 bg-white/70">
                    {result.error ? (
                        <p className="text-sm text-red-600">{result.error}</p>
                    ) : (
                        <div>
                            <p className="font-semibold text-gray-800">{result.summary}</p>
                            <p className="text-xs text-gray-500">Risk: {result.risk_level || 'Unknown'} ({result.risk_score || 0})</p>
                        </div>
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalOTSurgeryScheduling = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [surgeries, setSurgeries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [form, setForm] = useState({ patient: '', procedure: '', time: '' });
    const [surgerySearch, setSurgerySearch] = useState('');
    const [surgerySortBy, setSurgerySortBy] = useState('createdAt');
    const [surgerySortDir, setSurgerySortDir] = useState('desc');

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                setSurgeries([]);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const surgeryQuery = buildQuery({
                    hospitalId,
                    search: surgerySearch,
                    sort_by: surgerySortBy,
                    sort_dir: surgerySortDir
                });
                const res = await apiFetch(`/api/hospital-ops/ot/surgeries${surgeryQuery}`, { method: 'GET' });
                const data = res.ok ? (res.data?.data || []) : [];
                if (isActive) {
                    setSurgeries(data);
                }
            } catch (err) {
                if (isActive) {
                    setSurgeries([]);
                }
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, surgerySearch, surgerySortBy, surgerySortDir]);

    const handleAdd = async () => {
        if (!form.patient || !form.procedure || !form.time || !hospitalId) return;
        setSubmitting(true);
        try {
            const res = await apiFetch('/api/hospital-ops/ot/surgeries', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    patient: form.patient,
                    procedure: form.procedure,
                    time: form.time,
                    status: 'Scheduled'
                })
            });
            if (res.ok) {
                setSurgeries((prev) => [res.data, ...prev]);
                setForm({ patient: '', procedure: '', time: '' });
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">OT Surgery Scheduling</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Patient" value={form.patient} onChange={(e) => setForm({ ...form, patient: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Procedure" value={form.procedure} onChange={(e) => setForm({ ...form, procedure: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} />
                <button className="bg-indigo-600 text-white rounded" onClick={handleAdd} disabled={submitting}>
                    {submitting ? 'Scheduling...' : 'Schedule'}
                </button>
            </div>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search surgeries"
                    value={surgerySearch}
                    onChange={(e) => setSurgerySearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={surgerySortBy}
                    onChange={(e) => setSurgerySortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="time">Time</option>
                    <option value="status">Status</option>
                    <option value="patient">Patient</option>
                    <option value="procedure">Procedure</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={surgerySortDir}
                    onChange={(e) => setSurgerySortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
                    {surgeries.map((surgery) => (
                        <div key={surgery._id || surgery.id} className="border rounded p-3 flex items-center justify-between">
                            <div>
                                <p className="font-semibold text-gray-800">{surgery.patient}</p>
                                <p className="text-xs text-gray-500">{surgery.procedure} • {surgery.time}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <StatusPill text={surgery.status || 'Scheduled'} color="blue" />
                                <button className="text-xs text-indigo-600" onClick={() => apiFetch(`/api/hospital-ops/ot/surgeries/${surgery._id || surgery.id}`, {
                                    method: 'PATCH',
                                    body: JSON.stringify({ status: 'In Progress' })
                                })}>Start</button>
                                <button className="text-xs text-green-600" onClick={() => apiFetch(`/api/hospital-ops/ot/surgeries/${surgery._id || surgery.id}`, {
                                    method: 'PATCH',
                                    body: JSON.stringify({ status: 'Completed' })
                                })}>Complete</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};

export const HospitalOTStaffAllocation = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    const [form, setForm] = useState({ department: 'Surgery', patient_load: 'High', shift: 'Day' });
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [history, setHistory] = useState([]);
    const [allocationSearch, setAllocationSearch] = useState('');
    const [allocationSortBy, setAllocationSortBy] = useState('createdAt');
    const [allocationSortDir, setAllocationSortDir] = useState('desc');

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            if (!hospitalId) {
                return;
            }
            try {
                const allocationQuery = buildQuery({
                    hospitalId,
                    search: allocationSearch,
                    sort_by: allocationSortBy,
                    sort_dir: allocationSortDir
                });
                const res = await apiFetch(`/api/hospital-ops/ot/allocations${allocationQuery}`, { method: 'GET' });
                if (res.ok && isActive) {
                    setHistory(res.data?.data || []);
                }
            } catch (err) {
                // Keep empty history
            }
        };
        load();
        return () => {
            isActive = false;
        };
    }, [hospitalId, allocationSearch, allocationSortBy, allocationSortDir]);

    const handleAllocate = async () => {
        if (!hospitalId) {
            setResult({ error: 'Hospital not available' });
            return;
        }
        setLoading(true);
        try {
            const res = await apiFetch('/api/hospital-ops/ot/allocations', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    department: form.department,
                    patient_load: form.patient_load,
                    shift: form.shift
                })
            });
            const data = res.data || {};
            if (!res.ok || data.error) {
                setResult({ error: data.error || 'Allocation failed' });
            } else {
                setResult(data);
                setHistory((prev) => [data, ...prev]);
            }
        } catch (err) {
            setResult({ error: 'Allocation failed' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">OT Staff Allocation</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <select className="p-2 border rounded" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
                    <option>Surgery</option>
                    <option>ICU</option>
                    <option>Emergency</option>
                </select>
                <select className="p-2 border rounded" value={form.patient_load} onChange={(e) => setForm({ ...form, patient_load: e.target.value })}>
                    <option>Low</option>
                    <option>Medium</option>
                    <option>High</option>
                </select>
                <select className="p-2 border rounded" value={form.shift} onChange={(e) => setForm({ ...form, shift: e.target.value })}>
                    <option>Day</option>
                    <option>Evening</option>
                    <option>Night</option>
                </select>
            </div>
            <div className="flex flex-col md:flex-row gap-2 mb-4">
                <input
                    className="p-2 border rounded w-full"
                    placeholder="Search allocations"
                    value={allocationSearch}
                    onChange={(e) => setAllocationSearch(e.target.value)}
                />
                <select
                    className="p-2 border rounded"
                    value={allocationSortBy}
                    onChange={(e) => setAllocationSortBy(e.target.value)}
                >
                    <option value="createdAt">Newest</option>
                    <option value="department">Department</option>
                    <option value="patient_load">Patient Load</option>
                    <option value="shift">Shift</option>
                </select>
                <select
                    className="p-2 border rounded"
                    value={allocationSortDir}
                    onChange={(e) => setAllocationSortDir(e.target.value)}
                >
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            <button className="bg-purple-600 text-white rounded px-4 py-2" onClick={handleAllocate} disabled={loading}>
                {loading ? 'Allocating...' : 'Allocate Staff'}
            </button>
            {result && (
                <div className="mt-4 border rounded p-3 bg-white/70">
                    {result.error ? (
                        <p className="text-sm text-red-600">{result.error}</p>
                    ) : (
                        <p className="text-sm text-gray-800">{result.allocation_decision || 'Allocation ready.'}</p>
                    )}
                </div>
            )}
            {history.length > 0 && (
                <div className="mt-4 space-y-2 max-h-[240px] overflow-y-auto pr-2">
                    {history.slice(0, 4).map((item) => (
                        <div key={item._id || item.id} className="border rounded p-2 text-xs text-gray-600">
                            <span className="font-semibold text-gray-800">{item.department}</span> • {item.shift} • {item.patient_load}
                            <div>{item.allocation_decision}</div>
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};
