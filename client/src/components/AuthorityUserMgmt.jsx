import React, { useState, useEffect } from 'react';
import { DashboardCard, LoadingSpinner } from './Common';
import { apiFetch } from '../config/api';

const AuthorityUserMgmt = () => {
    const [pending, setPending] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchPending = async () => {
        try {
            const { data } = await apiFetch('/api/dashboard/admin/pending-hospitals', { method: 'GET' });
            setPending(data);
        } catch (err) { console.error(err); } 
        finally { setLoading(false); }
    };

    useEffect(() => { fetchPending(); }, []);

    const handleApprove = async (id) => {
        if(!window.confirm("Verify this facility for the LifeLink Network?")) return;
        try {
            const res = await apiFetch(`/api/dashboard/admin/verify/${id}`, { method: 'PUT' });
            if (res.ok) {
                alert("Hospital successfully verified and notified.");
                fetchPending(); 
            }
        } catch (err) { alert("Verification request failed."); }
    };

    return (
        <DashboardCard>
            <div className="flex justify-between items-center mb-6">
                <h3 className="font-bold text-xl text-slate-800">License Verification Queue</h3>
                <span className="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-xs font-bold">
                    {pending.length} Requests Found
                </span>
            </div>

            {loading ? <LoadingSpinner /> : pending.length === 0 ? (
                <div className="text-center py-20 bg-slate-50 rounded-2xl border-2 border-dashed">
                    <i className="fas fa-certificate text-slate-200 text-6xl mb-4"></i>
                    <p className="text-slate-400 font-medium">All hospitals are currently verified.</p>
                </div>
            ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-100">
                    <table className="min-w-full text-left text-sm">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="px-6 py-4 font-bold text-slate-600">Facility Details</th>
                                <th className="px-6 py-4 font-bold text-slate-600">License ID</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Jurisdiction</th>
                                <th className="px-6 py-4 text-right font-bold text-slate-600">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {pending.map(h => (
                                <tr key={h._id} className="hover:bg-slate-50/50 transition">
                                    <td className="px-6 py-4">
                                        <p className="font-bold text-slate-800">{h.name}</p>
                                        <p className="text-xs text-slate-400">{h.email}</p>
                                    </td>
                                    <td className="px-6 py-4 font-mono text-xs text-indigo-600">
                                        {h.hospitalProfile?.regNumber || 'PENDING_AUDIT'}
                                    </td>
                                    <td className="px-6 py-4 text-slate-500">{h.location}</td>
                                    <td className="px-6 py-4 text-right">
                                        <button 
                                            onClick={() => handleApprove(h._id)}
                                            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-xs font-bold shadow-md transition"
                                        >
                                            Verify License
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </DashboardCard>
    );
};

export default AuthorityUserMgmt;