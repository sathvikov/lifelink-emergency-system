import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';
import { DashboardCard, LoadingSpinner, StatusPill } from './Common';

const sampleFamilyMembers = [
    {
        id: 'fam-1',
        name: 'Asha Rao',
        relation: 'Mother',
        phone: '9000000111',
        location: 'Bengaluru',
        conditions: ['Hypertension'],
        medication: 'Amlodipine',
        lastCheckIn: '2026-04-02T08:15:00Z',
        status: 'Safe'
    },
    {
        id: 'fam-2',
        name: 'Rakesh Rao',
        relation: 'Father',
        phone: '9000000222',
        location: 'Bengaluru',
        conditions: ['Diabetes'],
        medication: 'Metformin',
        lastCheckIn: '2026-04-01T19:40:00Z',
        status: 'Safe'
    },
    {
        id: 'fam-3',
        name: 'Meera Rao',
        relation: 'Sister',
        phone: '9000000333',
        location: 'Mysuru',
        conditions: ['Asthma'],
        medication: 'Inhaler',
        lastCheckIn: '2026-04-03T07:05:00Z',
        status: 'Needs Help'
    }
];

const safeJsonParse = (value, fallback) => {
    try {
        return JSON.parse(value);
    } catch (err) {
        return fallback;
    }
};

const getStorageKey = (userId) => (userId ? `lifelink:family:${userId}` : 'lifelink:family');

const FamilyMonitoring = () => {
    const { user } = useAuth();
    const [members, setMembers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState({ name: '', relation: '', phone: '', location: '' });
    const [useLocal, setUseLocal] = useState(false);
    const [insights, setInsights] = useState(null);

    const storageKey = getStorageKey(user?.id);

    const loadInsights = async () => {
        if (!user?.id) return;
        try {
            const res = await apiFetch(`/api/family/insights/${user.id}`, { method: 'GET' });
            setInsights(res.ok ? res.data : null);
        } catch (err) {
            setInsights(null);
        }
    };

    const loadMembers = async () => {
        if (!user?.id) return;
        setLoading(true);
        try {
            const res = await apiFetch(`/api/family/members/${user.id}`, { method: 'GET' });
            const list = res.ok ? (res.data?.data || []) : [];
            if (list.length > 0) {
                setMembers(list);
                setUseLocal(false);
                await loadInsights();
                setLoading(false);
                return;
            }
        } catch (err) {
            // fall through to local fallback
        }

        const saved = safeJsonParse(localStorage.getItem(storageKey), null);
        const fallback = Array.isArray(saved) && saved.length ? saved : sampleFamilyMembers;
        setMembers(fallback);
        setUseLocal(true);
        localStorage.setItem(storageKey, JSON.stringify(fallback));
        await loadInsights();
        setLoading(false);
    };

    useEffect(() => {
        loadMembers();
    }, [user?.id]);

    const handleAdd = async () => {
        if (!form.name || !form.relation || !user?.id) return;
        setSaving(true);

        if (useLocal) {
            const newMember = {
                id: `local-${Date.now()}`,
                name: form.name,
                relation: form.relation,
                phone: form.phone,
                location: form.location,
                conditions: [],
                medication: 'N/A',
                lastCheckIn: new Date().toISOString(),
                status: 'Safe'
            };
            const updated = [newMember, ...members];
            setMembers(updated);
            localStorage.setItem(storageKey, JSON.stringify(updated));
            setForm({ name: '', relation: '', phone: '', location: '' });
            setSaving(false);
            return;
        }

        try {
            const res = await apiFetch('/api/family/members', {
                method: 'POST',
                body: JSON.stringify({
                    userId: user.id,
                    name: form.name,
                    relation: form.relation,
                    phone: form.phone,
                    location: form.location
                })
            });
            if (res.ok) {
                setMembers((prev) => [res.data, ...prev]);
                setForm({ name: '', relation: '', phone: '', location: '' });
                await loadInsights();
            } else {
                setUseLocal(true);
            }
        } finally {
            setSaving(false);
        }
    };

    const updateMember = async (id, updates) => {
        if (useLocal) {
            setMembers((prev) => {
                const updated = prev.map((item) => (item._id || item.id) === id ? { ...item, ...updates } : item);
                localStorage.setItem(storageKey, JSON.stringify(updated));
                return updated;
            });
            return;
        }

        try {
            const res = await apiFetch(`/api/family/members/${id}`, {
                method: 'PATCH',
                body: JSON.stringify(updates)
            });
            if (res.ok) {
                setMembers((prev) => prev.map((item) => (item._id || item.id) === id ? res.data : item));
                await loadInsights();
            }
        } catch (err) {
            // keep optimistic
        }
    };

    const pushLocation = async (member) => {
        const lat = 12.97 + Math.random() * 0.05;
        const lng = 77.59 + Math.random() * 0.05;
        await apiFetch(`/api/family/members/${member._id || member.id}/location`, {
            method: 'PATCH',
            body: JSON.stringify({ latitude: lat, longitude: lng, label: 'Live location' })
        });
        loadMembers();
    };

    const pushVitals = async (member) => {
        const payload = {
            heart_rate: Math.floor(70 + Math.random() * 30),
            oxygen: Math.floor(92 + Math.random() * 5),
            blood_pressure: `${110 + Math.floor(Math.random() * 20)}/${70 + Math.floor(Math.random() * 10)}`,
            temperature: Number((36.4 + Math.random() * 0.8).toFixed(1))
        };
        await apiFetch(`/api/family/members/${member._id || member.id}/vitals`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        loadMembers();
    };

    const handleCheckIn = (id) => {
        updateMember(id, { lastCheckIn: new Date().toISOString(), status: 'Safe' });
    };

    const handleAlert = (id) => {
        updateMember(id, { status: 'Needs Help' });
    };

    return (
        <div className="space-y-6">
            <DashboardCard>
                <h3 className="text-lg font-bold text-gray-900 mb-4">Family Monitoring</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input
                        className="p-2 border rounded"
                        placeholder="Name"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        placeholder="Relation"
                        value={form.relation}
                        onChange={(e) => setForm({ ...form, relation: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        placeholder="Phone"
                        value={form.phone}
                        onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    />
                    <input
                        className="p-2 border rounded"
                        placeholder="Location"
                        value={form.location}
                        onChange={(e) => setForm({ ...form, location: e.target.value })}
                    />
                    <button
                        className="bg-indigo-600 text-white rounded"
                        onClick={handleAdd}
                        disabled={saving}
                    >
                        {saving ? 'Saving...' : 'Add Member'}
                    </button>
                </div>
            </DashboardCard>

            <DashboardCard>
                <div className="flex items-center justify-between mb-4">
                    <h4 className="font-bold text-gray-800">Member Status</h4>
                    <button className="text-xs text-slate-600" onClick={loadMembers}>Refresh</button>
                </div>
                {insights?.at_risk?.length > 0 && (
                    <div className="mb-4 text-xs text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                        At-risk members: {insights.at_risk.join(', ')}
                    </div>
                )}
                {loading ? (
                    <LoadingSpinner />
                ) : members.length === 0 ? (
                    <div className="text-sm text-gray-500">No family members added yet.</div>
                ) : (
                    <div className="space-y-3">
                        {members.map((member) => (
                            <div key={member._id || member.id} className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 border rounded-lg bg-white/70">
                                <div>
                                    <p className="font-semibold text-gray-800">{member.name}</p>
                                    <p className="text-xs text-gray-500">{member.relation} • {member.phone || 'No phone'}</p>
                                    <p className="text-xs text-gray-400">Last check-in: {member.lastCheckIn ? new Date(member.lastCheckIn).toLocaleString() : 'Never'}</p>
                                    {member.lastLocation?.label && (
                                        <p className="text-xs text-gray-400">Location: {member.lastLocation.label}</p>
                                    )}
                                </div>
                                <div className="flex items-center gap-2">
                                    <StatusPill text={member.status || 'Safe'} color={member.status === 'Needs Help' ? 'red' : 'green'} />
                                    <button className="text-xs text-indigo-600" onClick={() => handleCheckIn(member._id || member.id)}>Check-in</button>
                                    <button className="text-xs text-red-600" onClick={() => handleAlert(member._id || member.id)}>Alert</button>
                                    <button className="text-xs text-slate-600" onClick={() => pushLocation(member)}>Update location</button>
                                    <button className="text-xs text-slate-600" onClick={() => pushVitals(member)}>Update vitals</button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </DashboardCard>
        </div>
    );
};

export default FamilyMonitoring;
