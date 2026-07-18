import React, { useEffect, useState } from 'react';
import { apiFetch } from '../config/api';
import { DashboardCard, LoadingSpinner, StatusPill } from './Common';

export const GovernmentReports = () => {
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ title: '', scope: 'State', summary: '' });
    const [saving, setSaving] = useState(false);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [sortBy, setSortBy] = useState('createdAt');
    const [sortDir, setSortDir] = useState('desc');

    const load = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (search) params.set('search', search);
            if (statusFilter) params.set('status', statusFilter);
            if (sortBy) params.set('sort_by', sortBy);
            if (sortDir) params.set('sort_dir', sortDir);
            const qs = params.toString();
            const res = await apiFetch(`/api/government-ops/reports${qs ? `?${qs}` : ''}`, { method: 'GET' });
            setReports(res.ok ? (res.data?.data || []) : []);
        } catch (err) {
            setReports([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const handleCreate = async () => {
        if (!form.title || !form.scope) return;
        setSaving(true);
        try {
            const res = await apiFetch('/api/government-ops/reports', {
                method: 'POST',
                body: JSON.stringify(form)
            });
            if (res.ok) {
                setReports((prev) => [res.data, ...prev]);
                setForm({ title: '', scope: 'State', summary: '' });
            }
        } finally {
            setSaving(false);
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Reports Center</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Report Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                <select className="p-2 border rounded" value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}>
                    <option>National</option>
                    <option>State</option>
                    <option>District</option>
                </select>
                <button className="bg-indigo-600 text-white rounded" onClick={handleCreate} disabled={saving}>
                    {saving ? 'Generating...' : 'Generate Report'}
                </button>
            </div>
            <div className="flex flex-col md:flex-row md:items-center gap-2 mb-4">
                <input className="p-2 border rounded flex-1" placeholder="Search reports" value={search} onChange={(e) => setSearch(e.target.value)} />
                <select className="p-2 border rounded" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="">All Status</option>
                    <option>Ready</option>
                    <option>Queued</option>
                </select>
                <select className="p-2 border rounded" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                    <option value="createdAt">Newest</option>
                    <option value="title">Title</option>
                    <option value="status">Status</option>
                </select>
                <select className="p-2 border rounded" value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
                <button className="bg-slate-900 text-white px-3 rounded" onClick={load}>Apply</button>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3">
                    {reports.length === 0 ? (
                        <div className="text-sm text-gray-500">No reports generated yet.</div>
                    ) : (
                        reports.map((report) => (
                            <div key={report._id || report.id} className="border rounded p-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-gray-800">{report.title}</p>
                                        <p className="text-xs text-gray-500">Scope: {report.scope}</p>
                                    </div>
                                    <StatusPill text={report.status || 'Ready'} color="green" />
                                </div>
                                <p className="text-sm text-gray-600 mt-2">{report.summary}</p>
                            </div>
                        ))
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const GovernmentComplianceMonitoring = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [form, setForm] = useState({ hospitalId: '', status: 'Open', findings: '', owner: '' });
    const [saving, setSaving] = useState(false);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [ownerFilter, setOwnerFilter] = useState('');
    const [sortBy, setSortBy] = useState('createdAt');
    const [sortDir, setSortDir] = useState('desc');

    const load = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (search) params.set('search', search);
            if (statusFilter) params.set('status', statusFilter);
            if (ownerFilter) params.set('owner', ownerFilter);
            if (sortBy) params.set('sort_by', sortBy);
            if (sortDir) params.set('sort_dir', sortDir);
            const qs = params.toString();
            const res = await apiFetch(`/api/government-ops/compliance${qs ? `?${qs}` : ''}`, { method: 'GET' });
            setItems(res.ok ? (res.data?.data || []) : []);
        } catch (err) {
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const handleCreate = async () => {
        if (!form.hospitalId || !form.status) return;
        setSaving(true);
        try {
            const res = await apiFetch('/api/government-ops/compliance', {
                method: 'POST',
                body: JSON.stringify(form)
            });
            if (res.ok) {
                setItems((prev) => [res.data, ...prev]);
                setForm({ hospitalId: '', status: 'Open', findings: '', owner: '' });
            }
        } finally {
            setSaving(false);
        }
    };

    const updateStatus = async (id, status) => {
        try {
            const res = await apiFetch(`/api/government-ops/compliance/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({ status })
            });
            if (res.ok) {
                setItems((prev) => prev.map((item) => (item._id || item.id) === id ? res.data : item));
            }
        } catch (err) {
            // Keep current
        }
    };

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Compliance Monitoring</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                <input className="p-2 border rounded" placeholder="Hospital ID" value={form.hospitalId} onChange={(e) => setForm({ ...form, hospitalId: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Owner" value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} />
                <input className="p-2 border rounded" placeholder="Findings" value={form.findings} onChange={(e) => setForm({ ...form, findings: e.target.value })} />
                <button className="bg-indigo-600 text-white rounded" onClick={handleCreate} disabled={saving}>
                    {saving ? 'Saving...' : 'Add Finding'}
                </button>
            </div>
            <div className="flex flex-col md:flex-row md:items-center gap-2 mb-4">
                <input className="p-2 border rounded flex-1" placeholder="Search compliance" value={search} onChange={(e) => setSearch(e.target.value)} />
                <input className="p-2 border rounded" placeholder="Owner" value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value)} />
                <select className="p-2 border rounded" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="">All Status</option>
                    <option>Open</option>
                    <option>Resolved</option>
                </select>
                <select className="p-2 border rounded" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                    <option value="createdAt">Newest</option>
                    <option value="status">Status</option>
                    <option value="hospitalId">Hospital</option>
                </select>
                <select className="p-2 border rounded" value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
                <button className="bg-slate-900 text-white px-3 rounded" onClick={load}>Apply</button>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3">
                    {items.length === 0 ? (
                        <div className="text-sm text-gray-500">No compliance findings yet.</div>
                    ) : (
                        items.map((item) => (
                            <div key={item._id || item.id} className="border rounded p-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-gray-800">Hospital {item.hospitalId}</p>
                                        <p className="text-xs text-gray-500">Owner: {item.owner || 'Unassigned'}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <StatusPill text={item.status || 'Open'} color={item.status === 'Resolved' ? 'green' : 'yellow'} />
                                        <button className="text-xs text-indigo-600" onClick={() => updateStatus(item._id || item.id, 'Resolved')}>Resolve</button>
                                    </div>
                                </div>
                                <p className="text-sm text-gray-600 mt-2">{item.findings || 'No findings notes.'}</p>
                            </div>
                        ))
                    )}
                </div>
            )}
        </DashboardCard>
    );
};

export const GovernmentHospitalMonitoring = () => {
    const [hospitals, setHospitals] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [sortBy, setSortBy] = useState('name');
    const [sortDir, setSortDir] = useState('asc');

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                const params = new URLSearchParams();
                if (search) params.set('search', search);
                if (sortBy) params.set('sort_by', sortBy);
                if (sortDir) params.set('sort_dir', sortDir);
                const qs = params.toString();
                const res = await apiFetch(`/api/government-ops/hospitals${qs ? `?${qs}` : ''}`, { method: 'GET' });
                setHospitals(res.ok ? (res.data?.data || []) : []);
            } catch (err) {
                setHospitals([]);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [search, sortBy, sortDir]);

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">Hospital Monitoring</h3>
            <div className="flex flex-col md:flex-row md:items-center gap-2 mb-4">
                <input className="p-2 border rounded flex-1" placeholder="Search hospitals" value={search} onChange={(e) => setSearch(e.target.value)} />
                <select className="p-2 border rounded" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                    <option value="name">Name</option>
                    <option value="availableBeds">Available beds</option>
                    <option value="totalBeds">Total beds</option>
                </select>
                <select className="p-2 border rounded" value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
                    <option value="asc">Asc</option>
                    <option value="desc">Desc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : (
                <div className="space-y-3">
                    {hospitals.length === 0 ? (
                        <div className="text-sm text-gray-500">No hospitals found.</div>
                    ) : (
                        hospitals.map((hospital) => (
                            <div key={hospital.id} className="border rounded p-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-semibold text-gray-800">{hospital.name}</p>
                                        <p className="text-xs text-gray-500">{hospital.location}</p>
                                    </div>
                                    <div className="text-right text-xs text-gray-500">
                                        <div>Total Beds: {hospital.beds?.totalBeds || 0}</div>
                                        <div>Available: {hospital.beds?.availableBeds || 0}</div>
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

export const GovernmentDistrictEmergencies = () => {
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [severityFilter, setSeverityFilter] = useState('');
    const [sortBy, setSortBy] = useState('createdAt');
    const [sortDir, setSortDir] = useState('desc');

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                const params = new URLSearchParams();
                if (search) params.set('search', search);
                if (severityFilter) params.set('severity', severityFilter);
                if (sortBy) params.set('sort_by', sortBy);
                if (sortDir) params.set('sort_dir', sortDir);
                const qs = params.toString();
                const res = await apiFetch(`/api/government-ops/emergencies${qs ? `?${qs}` : ''}`, { method: 'GET' });
                setAlerts(res.ok ? (res.data?.data || []) : []);
            } catch (err) {
                setAlerts([]);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [search, severityFilter, sortBy, sortDir]);

    return (
        <DashboardCard>
            <h3 className="text-lg font-bold text-gray-900 mb-4">District Emergencies</h3>
            <div className="flex flex-col md:flex-row md:items-center gap-2 mb-4">
                <input className="p-2 border rounded flex-1" placeholder="Search emergencies" value={search} onChange={(e) => setSearch(e.target.value)} />
                <select className="p-2 border rounded" value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
                    <option value="">All Severity</option>
                    <option>Critical</option>
                    <option>High</option>
                    <option>Medium</option>
                    <option>Low</option>
                </select>
                <select className="p-2 border rounded" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                    <option value="createdAt">Newest</option>
                    <option value="emergencyType">Severity</option>
                </select>
                <select className="p-2 border rounded" value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
                    <option value="desc">Desc</option>
                    <option value="asc">Asc</option>
                </select>
            </div>
            {loading ? (
                <LoadingSpinner />
            ) : alerts.length === 0 ? (
                <div className="text-sm text-gray-500">No emergencies reported.</div>
            ) : (
                <div className="space-y-3">
                    {alerts.map((alert) => (
                        <div key={alert._id} className="border rounded p-3">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="font-semibold text-gray-800">{alert.message}</p>
                                    <p className="text-xs text-gray-500">{alert.locationDetails || 'Unknown location'}</p>
                                </div>
                                <StatusPill text={alert.emergencyType || 'Medium'} color={alert.emergencyType === 'Critical' ? 'red' : 'yellow'} />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </DashboardCard>
    );
};
