import React, { useEffect, useState } from 'react';
import Card from './ui/Card';
import Button from './ui/Button';
import { apiFetch } from '../config/api';

const AmbulanceApprovalPanel = () => {
    const [pending, setPending] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchPending = async () => {
        setLoading(true);
        const { ok, data } = await apiFetch('/v2/government/ambulance/pending');
        if (ok) {
            setPending(data);
        }
        setLoading(false);
    };

    useEffect(() => { fetchPending(); }, []);

    const handleApprove = async (id) => {
        if (!window.confirm('Approve this ambulance account?')) return;
        const { ok } = await apiFetch(`/v2/government/ambulance/verify/${id}`, { method: 'PUT' });
        if (ok) {
            fetchPending();
        }
    };

    return (
        <Card>
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-lg font-bold text-slate-900">Ambulance Approval Panel</h3>
                    <p className="text-sm text-slate-500">Verify ambulance teams before granting access.</p>
                </div>
                <span className="text-xs font-bold uppercase text-slate-500">{pending.length} pending</span>
            </div>

            {loading ? (
                <p className="text-sm text-slate-500">Loading...</p>
            ) : pending.length === 0 ? (
                <div className="text-sm text-slate-500">All ambulance accounts are verified.</div>
            ) : (
                <div className="space-y-3">
                    {pending.map((item) => (
                        <div key={item._id} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100">
                            <div>
                                <p className="font-semibold text-slate-800">{item.name}</p>
                                <p className="text-xs text-slate-500">{item.email}</p>
                                <p className="text-xs text-slate-400">Base: {item.ambulanceProfile?.base || 'N/A'}</p>
                            </div>
                            <Button size="sm" onClick={() => handleApprove(item._id)}>
                                Verify
                            </Button>
                        </div>
                    ))}
                </div>
            )}
        </Card>
    );
};

export default AmbulanceApprovalPanel;
