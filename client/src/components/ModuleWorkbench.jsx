import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, API_BASE_URL } from '../config/api';
import { DashboardCard, ExplainabilityPanel, LoadingSpinner, StatusPill } from './Common';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts';

const sanitizeChannel = (key) => `module-${key.replace(/[^a-zA-Z0-9]+/g, '-').replace(/(^-|-$)/g, '').toLowerCase()}`;

const ModuleWorkbench = ({ moduleKey, title, description, realtimeChannel }) => {
    const [items, setItems] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [automations, setAutomations] = useState([]);
    const [analytics, setAnalytics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [priorityFilter, setPriorityFilter] = useState('');
    const [itemSortBy, setItemSortBy] = useState('createdAt');
    const [itemSortDir, setItemSortDir] = useState('desc');

    const [alertSearch, setAlertSearch] = useState('');
    const [alertStatusFilter, setAlertStatusFilter] = useState('');
    const [alertSeverityFilter, setAlertSeverityFilter] = useState('');
    const [alertSortBy, setAlertSortBy] = useState('createdAt');
    const [alertSortDir, setAlertSortDir] = useState('desc');

    const [automationSearch, setAutomationSearch] = useState('');
    const [automationEnabledFilter, setAutomationEnabledFilter] = useState('');
    const [automationSortBy, setAutomationSortBy] = useState('createdAt');
    const [automationSortDir, setAutomationSortDir] = useState('desc');

    const [itemForm, setItemForm] = useState({ title: '', summary: '', status: 'Open', priority: 'Medium' });
    const [editingId, setEditingId] = useState(null);
    const [editForm, setEditForm] = useState({ title: '', summary: '', status: 'Open', priority: 'Medium' });

    const [alertForm, setAlertForm] = useState({ message: '', severity: 'Medium' });
    const [automationForm, setAutomationForm] = useState({ name: '', trigger: 'On Update', action: 'Notify Team' });

    const [aiText, setAiText] = useState('');
    const [aiResult, setAiResult] = useState(null);
    const [aiLoading, setAiLoading] = useState(false);

    const socketRef = useRef(null);
    const channel = realtimeChannel || sanitizeChannel(moduleKey);

    const wsUrl = useMemo(() => {
        const base = API_BASE_URL || window.location.origin;
        if (!base) return '';
        return `${base.replace(/^http/, 'ws')}/v2/realtime/ws/${channel}`;
    }, [channel]);

    const loadItems = async () => {
        const params = new URLSearchParams();
        if (search) params.set('search', search);
        if (statusFilter) params.set('status', statusFilter);
        if (priorityFilter) params.set('priority', priorityFilter);
        if (itemSortBy) params.set('sort_by', itemSortBy);
        if (itemSortDir) params.set('sort_dir', itemSortDir);
        const qs = params.toString();
        const res = await apiFetch(`/v2/modules/${moduleKey}/items${qs ? `?${qs}` : ''}`, { method: 'GET' });
        setItems(res.ok ? (res.data?.data || []) : []);
    };

    const loadAlerts = async () => {
        const params = new URLSearchParams();
        if (alertSearch) params.set('search', alertSearch);
        if (alertStatusFilter) params.set('status', alertStatusFilter);
        if (alertSeverityFilter) params.set('severity', alertSeverityFilter);
        if (alertSortBy) params.set('sort_by', alertSortBy);
        if (alertSortDir) params.set('sort_dir', alertSortDir);
        const qs = params.toString();
        const res = await apiFetch(`/v2/modules/${moduleKey}/alerts${qs ? `?${qs}` : ''}`, { method: 'GET' });
        setAlerts(res.ok ? (res.data?.data || []) : []);
    };

    const loadAutomations = async () => {
        const params = new URLSearchParams();
        if (automationSearch) params.set('search', automationSearch);
        if (automationEnabledFilter) params.set('enabled', automationEnabledFilter);
        if (automationSortBy) params.set('sort_by', automationSortBy);
        if (automationSortDir) params.set('sort_dir', automationSortDir);
        const qs = params.toString();
        const res = await apiFetch(`/v2/modules/${moduleKey}/automations${qs ? `?${qs}` : ''}`, { method: 'GET' });
        setAutomations(res.ok ? (res.data?.data || []) : []);
    };

    const loadAnalytics = async () => {
        const res = await apiFetch(`/v2/modules/${moduleKey}/analytics`, { method: 'GET' });
        setAnalytics(res.ok ? res.data : null);
    };

    const loadAll = async () => {
        setLoading(true);
        try {
            await Promise.all([loadItems(), loadAlerts(), loadAutomations(), loadAnalytics()]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadAll();
    }, [moduleKey]);

    useEffect(() => {
        if (!wsUrl) return undefined;
        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onmessage = () => {
            loadAll();
        };

        return () => {
            socket.close();
        };
    }, [wsUrl]);

    const handleCreateItem = async () => {
        if (!itemForm.title) return;
        const res = await apiFetch(`/v2/modules/${moduleKey}/items`, {
            method: 'POST',
            body: JSON.stringify(itemForm)
        });
        if (res.ok) {
            setItemForm({ title: '', summary: '', status: 'Open', priority: 'Medium' });
            loadItems();
        }
    };

    const startEdit = (item) => {
        setEditingId(item._id || item.id);
        setEditForm({
            title: item.title || '',
            summary: item.summary || '',
            status: item.status || 'Open',
            priority: item.priority || 'Medium'
        });
    };

    const handleUpdateItem = async () => {
        if (!editingId) return;
        const res = await apiFetch(`/v2/modules/${moduleKey}/items/${editingId}`, {
            method: 'PATCH',
            body: JSON.stringify(editForm)
        });
        if (res.ok) {
            setEditingId(null);
            loadItems();
        }
    };

    const handleDeleteItem = async (id) => {
        await apiFetch(`/v2/modules/${moduleKey}/items/${id}`, { method: 'DELETE' });
        loadItems();
    };

    const handleCreateAlert = async () => {
        if (!alertForm.message) return;
        const res = await apiFetch(`/v2/modules/${moduleKey}/alerts`, {
            method: 'POST',
            body: JSON.stringify(alertForm)
        });
        if (res.ok) {
            setAlertForm({ message: '', severity: 'Medium' });
            loadAlerts();
        }
    };

    const handleToggleAlert = async (alert) => {
        const id = alert._id || alert.id;
        const status = alert.status === 'Resolved' ? 'Open' : 'Resolved';
        await apiFetch(`/v2/modules/${moduleKey}/alerts/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
        loadAlerts();
    };

    const handleCreateAutomation = async () => {
        if (!automationForm.name) return;
        const res = await apiFetch(`/v2/modules/${moduleKey}/automations`, {
            method: 'POST',
            body: JSON.stringify(automationForm)
        });
        if (res.ok) {
            setAutomationForm({ name: '', trigger: 'On Update', action: 'Notify Team' });
            loadAutomations();
        }
    };

    const handleToggleAutomation = async (automation) => {
        const id = automation._id || automation.id;
        await apiFetch(`/v2/modules/${moduleKey}/automations/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ enabled: !automation.enabled })
        });
        loadAutomations();
    };

    const handleRunAutomation = async (automation) => {
        const id = automation._id || automation.id;
        await apiFetch(`/v2/modules/${moduleKey}/automations/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ lastRun: new Date().toISOString() })
        });
        loadAutomations();
    };

    const handleAi = async () => {
        if (!aiText.trim()) return;
        setAiLoading(true);
        setAiResult(null);
        try {
            const res = await apiFetch(`/v2/modules/${moduleKey}/ai`, {
                method: 'POST',
                body: JSON.stringify({ text: aiText })
            });
            if (res.ok) {
                setAiResult(res.data);
            }
        } finally {
            setAiLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900">{title}</h3>
                        {description && <p className="text-sm text-gray-500">{description}</p>}
                    </div>
                    <div className="text-xs text-gray-400">Channel: {channel}</div>
                </div>
            </DashboardCard>

            {loading ? (
                <LoadingSpinner />
            ) : (
                <>
                    <DashboardCard>
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
                            <h4 className="font-bold text-gray-800">Operational Data</h4>
                            <div className="flex flex-wrap gap-2">
                                <input
                                    className="p-2 border rounded"
                                    placeholder="Search"
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                />
                                <select className="p-2 border rounded" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                                    <option value="">All Status</option>
                                    <option>Open</option>
                                    <option>In Progress</option>
                                    <option>Resolved</option>
                                </select>
                                <select className="p-2 border rounded" value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
                                    <option value="">All Priority</option>
                                    <option>Low</option>
                                    <option>Medium</option>
                                    <option>High</option>
                                    <option>Critical</option>
                                </select>
                                <select className="p-2 border rounded" value={itemSortBy} onChange={(e) => setItemSortBy(e.target.value)}>
                                    <option value="createdAt">Newest</option>
                                    <option value="updatedAt">Updated</option>
                                    <option value="priority">Priority</option>
                                    <option value="status">Status</option>
                                    <option value="title">Title</option>
                                </select>
                                <select className="p-2 border rounded" value={itemSortDir} onChange={(e) => setItemSortDir(e.target.value)}>
                                    <option value="desc">Desc</option>
                                    <option value="asc">Asc</option>
                                </select>
                                <button className="bg-slate-900 text-white px-3 rounded" onClick={loadItems}>Filter</button>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
                            <input
                                className="p-2 border rounded"
                                placeholder="Title"
                                value={itemForm.title}
                                onChange={(e) => setItemForm({ ...itemForm, title: e.target.value })}
                            />
                            <input
                                className="p-2 border rounded"
                                placeholder="Summary"
                                value={itemForm.summary}
                                onChange={(e) => setItemForm({ ...itemForm, summary: e.target.value })}
                            />
                            <select
                                className="p-2 border rounded"
                                value={itemForm.status}
                                onChange={(e) => setItemForm({ ...itemForm, status: e.target.value })}
                            >
                                <option>Open</option>
                                <option>In Progress</option>
                                <option>Resolved</option>
                            </select>
                            <select
                                className="p-2 border rounded"
                                value={itemForm.priority}
                                onChange={(e) => setItemForm({ ...itemForm, priority: e.target.value })}
                            >
                                <option>Low</option>
                                <option>Medium</option>
                                <option>High</option>
                                <option>Critical</option>
                            </select>
                            <button className="bg-indigo-600 text-white rounded" onClick={handleCreateItem}>Add Item</button>
                        </div>

                        <div className="space-y-3">
                            {items.length === 0 ? (
                                <div className="text-sm text-gray-500">No records yet.</div>
                            ) : (
                                items.map((item) => (
                                    <div key={item._id || item.id} className="border rounded p-3">
                                        {editingId === (item._id || item.id) ? (
                                            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                                                <input
                                                    className="p-2 border rounded"
                                                    value={editForm.title}
                                                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                                                />
                                                <input
                                                    className="p-2 border rounded"
                                                    value={editForm.summary}
                                                    onChange={(e) => setEditForm({ ...editForm, summary: e.target.value })}
                                                />
                                                <select
                                                    className="p-2 border rounded"
                                                    value={editForm.status}
                                                    onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                                                >
                                                    <option>Open</option>
                                                    <option>In Progress</option>
                                                    <option>Resolved</option>
                                                </select>
                                                <select
                                                    className="p-2 border rounded"
                                                    value={editForm.priority}
                                                    onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                                                >
                                                    <option>Low</option>
                                                    <option>Medium</option>
                                                    <option>High</option>
                                                    <option>Critical</option>
                                                </select>
                                                <button className="bg-slate-900 text-white rounded" onClick={handleUpdateItem}>Save</button>
                                            </div>
                                        ) : (
                                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                                                <div>
                                                    <p className="font-semibold text-gray-800">{item.title}</p>
                                                    <p className="text-xs text-gray-500">{item.summary}</p>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <StatusPill text={item.status || 'Open'} color={item.status === 'Resolved' ? 'green' : 'yellow'} />
                                                    <StatusPill text={item.priority || 'Medium'} color={item.priority === 'Critical' ? 'red' : 'blue'} />
                                                    <button className="text-xs text-indigo-600" onClick={() => startEdit(item)}>Edit</button>
                                                    <button className="text-xs text-red-600" onClick={() => handleDeleteItem(item._id || item.id)}>Delete</button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </DashboardCard>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <DashboardCard>
                            <h4 className="font-bold text-gray-800 mb-4">Analytics</h4>
                            {analytics ? (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-3 gap-3">
                                        <div className="bg-white/70 border rounded p-3">
                                            <p className="text-xs text-gray-500">Total</p>
                                            <p className="text-lg font-bold text-gray-900">{analytics.summary?.total || 0}</p>
                                        </div>
                                        <div className="bg-white/70 border rounded p-3">
                                            <p className="text-xs text-gray-500">Open</p>
                                            <p className="text-lg font-bold text-indigo-600">{analytics.summary?.open || 0}</p>
                                        </div>
                                        <div className="bg-white/70 border rounded p-3">
                                            <p className="text-xs text-gray-500">Critical</p>
                                            <p className="text-lg font-bold text-red-600">{analytics.summary?.critical || 0}</p>
                                        </div>
                                    </div>
                                    <div className="h-40">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={analytics.series?.byStatus || []}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                                <XAxis dataKey="label" />
                                                <YAxis allowDecimals={false} />
                                                <Tooltip />
                                                <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <div className="h-40">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={analytics.series?.timeline || []}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                                <XAxis dataKey="label" />
                                                <YAxis allowDecimals={false} />
                                                <Tooltip />
                                                <Line type="monotone" dataKey="value" stroke="#16a34a" strokeWidth={2} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-sm text-gray-500">Analytics unavailable.</div>
                            )}
                        </DashboardCard>

                        <DashboardCard>
                            <h4 className="font-bold text-gray-800 mb-4">AI Insights</h4>
                            <textarea
                                className="w-full border rounded p-3 min-h-[120px]"
                                placeholder="Describe the situation for AI analysis"
                                value={aiText}
                                onChange={(e) => setAiText(e.target.value)}
                            />
                            <button className="mt-3 bg-purple-600 text-white rounded px-4 py-2" onClick={handleAi} disabled={aiLoading}>
                                {aiLoading ? 'Analyzing...' : 'Run AI'}
                            </button>
                            {aiResult && (
                                <div className="mt-4 border rounded p-3 bg-white/70">
                                    <p className="font-semibold text-gray-800">Classification: {aiResult.classification}</p>
                                    <p className="text-xs text-gray-500">Confidence: {aiResult.confidence}</p>
                                    <p className="text-sm text-gray-700 mt-2">{aiResult.recommendation}</p>
                                    <ExplainabilityPanel meta={aiResult.meta} />
                                </div>
                            )}
                        </DashboardCard>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <DashboardCard>
                            <h4 className="font-bold text-gray-800 mb-4">Alerts & Notifications</h4>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                                <input
                                    className="p-2 border rounded"
                                    placeholder="Alert message"
                                    value={alertForm.message}
                                    onChange={(e) => setAlertForm({ ...alertForm, message: e.target.value })}
                                />
                                <select
                                    className="p-2 border rounded"
                                    value={alertForm.severity}
                                    onChange={(e) => setAlertForm({ ...alertForm, severity: e.target.value })}
                                >
                                    <option>Low</option>
                                    <option>Medium</option>
                                    <option>High</option>
                                    <option>Critical</option>
                                </select>
                                <button className="bg-slate-900 text-white rounded" onClick={handleCreateAlert}>Send Alert</button>
                            </div>
                            <div className="flex flex-wrap gap-2 mb-4">
                                <input
                                    className="p-2 border rounded"
                                    placeholder="Search alerts"
                                    value={alertSearch}
                                    onChange={(e) => setAlertSearch(e.target.value)}
                                />
                                <select className="p-2 border rounded" value={alertStatusFilter} onChange={(e) => setAlertStatusFilter(e.target.value)}>
                                    <option value="">All Status</option>
                                    <option>Open</option>
                                    <option>Resolved</option>
                                </select>
                                <select className="p-2 border rounded" value={alertSeverityFilter} onChange={(e) => setAlertSeverityFilter(e.target.value)}>
                                    <option value="">All Severity</option>
                                    <option>Low</option>
                                    <option>Medium</option>
                                    <option>High</option>
                                    <option>Critical</option>
                                </select>
                                <select className="p-2 border rounded" value={alertSortBy} onChange={(e) => setAlertSortBy(e.target.value)}>
                                    <option value="createdAt">Newest</option>
                                    <option value="updatedAt">Updated</option>
                                    <option value="severity">Severity</option>
                                    <option value="status">Status</option>
                                </select>
                                <select className="p-2 border rounded" value={alertSortDir} onChange={(e) => setAlertSortDir(e.target.value)}>
                                    <option value="desc">Desc</option>
                                    <option value="asc">Asc</option>
                                </select>
                                <button className="bg-slate-900 text-white px-3 rounded" onClick={loadAlerts}>Apply</button>
                            </div>
                            <div className="space-y-3">
                                {alerts.length === 0 ? (
                                    <div className="text-sm text-gray-500">No alerts.</div>
                                ) : (
                                    alerts.map((alert) => (
                                        <div key={alert._id || alert.id} className="border rounded p-3 flex items-center justify-between">
                                            <div>
                                                <p className="font-semibold text-gray-800">{alert.message}</p>
                                                <p className="text-xs text-gray-500">{alert.severity}</p>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <StatusPill text={alert.status || 'Open'} color={alert.status === 'Resolved' ? 'green' : 'yellow'} />
                                                <button className="text-xs text-indigo-600" onClick={() => handleToggleAlert(alert)}>Toggle</button>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </DashboardCard>

                        <DashboardCard>
                            <h4 className="font-bold text-gray-800 mb-4">Automation</h4>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                                <input
                                    className="p-2 border rounded"
                                    placeholder="Automation name"
                                    value={automationForm.name}
                                    onChange={(e) => setAutomationForm({ ...automationForm, name: e.target.value })}
                                />
                                <input
                                    className="p-2 border rounded"
                                    placeholder="Trigger"
                                    value={automationForm.trigger}
                                    onChange={(e) => setAutomationForm({ ...automationForm, trigger: e.target.value })}
                                />
                                <input
                                    className="p-2 border rounded"
                                    placeholder="Action"
                                    value={automationForm.action}
                                    onChange={(e) => setAutomationForm({ ...automationForm, action: e.target.value })}
                                />
                                <button className="bg-indigo-600 text-white rounded" onClick={handleCreateAutomation}>Add Automation</button>
                            </div>
                            <div className="flex flex-wrap gap-2 mb-4">
                                <input
                                    className="p-2 border rounded"
                                    placeholder="Search automations"
                                    value={automationSearch}
                                    onChange={(e) => setAutomationSearch(e.target.value)}
                                />
                                <select className="p-2 border rounded" value={automationEnabledFilter} onChange={(e) => setAutomationEnabledFilter(e.target.value)}>
                                    <option value="">All States</option>
                                    <option value="true">Enabled</option>
                                    <option value="false">Paused</option>
                                </select>
                                <select className="p-2 border rounded" value={automationSortBy} onChange={(e) => setAutomationSortBy(e.target.value)}>
                                    <option value="createdAt">Newest</option>
                                    <option value="updatedAt">Updated</option>
                                    <option value="name">Name</option>
                                    <option value="enabled">State</option>
                                </select>
                                <select className="p-2 border rounded" value={automationSortDir} onChange={(e) => setAutomationSortDir(e.target.value)}>
                                    <option value="desc">Desc</option>
                                    <option value="asc">Asc</option>
                                </select>
                                <button className="bg-slate-900 text-white px-3 rounded" onClick={loadAutomations}>Apply</button>
                            </div>
                            <div className="space-y-3">
                                {automations.length === 0 ? (
                                    <div className="text-sm text-gray-500">No automation rules.</div>
                                ) : (
                                    automations.map((automation) => (
                                        <div key={automation._id || automation.id} className="border rounded p-3 flex items-center justify-between">
                                            <div>
                                                <p className="font-semibold text-gray-800">{automation.name}</p>
                                                <p className="text-xs text-gray-500">{automation.trigger} → {automation.action}</p>
                                                {automation.lastRun && (
                                                    <p className="text-xs text-gray-400">Last run: {new Date(automation.lastRun).toLocaleString()}</p>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <StatusPill text={automation.enabled ? 'Enabled' : 'Paused'} color={automation.enabled ? 'green' : 'gray'} />
                                                <button className="text-xs text-indigo-600" onClick={() => handleToggleAutomation(automation)}>Toggle</button>
                                                <button className="text-xs text-slate-600" onClick={() => handleRunAutomation(automation)}>Run</button>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </DashboardCard>
                    </div>
                </>
            )}
        </div>
    );
};

export default ModuleWorkbench;
