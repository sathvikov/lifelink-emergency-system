import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';

const GovernmentProfileModal = ({ onClose, variant = 'modal' }) => {
    const { user } = useAuth();
    const isPanel = variant === 'panel';
    
    // Government specific fields
    const [formData, setFormData] = useState({
        name: '', 
        email: '', 
        phone: '', 
        department: '', // e.g. Health Ministry
        zone: '',       // e.g. North Zone
        badgeId: '',    // e.g. GOVT-8821
        password: ''
    });
    
    const [loading, setLoading] = useState(false);
    const [msg, setMsg] = useState('');

    useEffect(() => {
        // Load current details
        setFormData({
            name: user.name || '',
            email: user.email || '',
            phone: user.phone || '',
            // If these fields exist in your User model under 'governmentProfile', access them here
            // For now, we simulate them or map to generic fields if you haven't updated the schema yet
            department: user.location || '', 
            zone: '', 
            badgeId: '',
            password: ''
        });
    }, [user]);

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const payload = { ...formData };
            if (!payload.password) delete payload.password;

            const { ok, status, data } = await apiFetch(`/api/dashboard/profile/${user.id}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            if (!ok) throw new Error(data?.message || `Update failed (${status})`);

            // Update local storage
            localStorage.setItem('user', JSON.stringify({ ...user, ...data.user }));
            setMsg('Official Profile Updated');
            setTimeout(() => { window.location.reload(); }, 1000);
        } catch (err) {
            setMsg('Update Failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={isPanel ? 'w-full' : 'fixed inset-0 bg-slate-900/80 z-50 flex items-center justify-center p-4 backdrop-blur-sm animate-fade-in'}>
            <div className={isPanel
                ? 'bg-white rounded-lg shadow-lg w-full max-w-3xl mx-auto overflow-hidden border-t-4 border-slate-700'
                : 'bg-white rounded-lg shadow-2xl w-full max-w-lg overflow-hidden border-t-4 border-slate-700'}
            >
                <div className="bg-slate-100 p-6 flex justify-between items-center border-b">
                    <div>
                        <h2 className="text-xl font-bold text-slate-800 uppercase tracking-wide">Authority Profile</h2>
                        <p className="text-xs text-slate-500 font-bold">Government of Karnataka</p>
                    </div>
                    {!isPanel && onClose && (
                        <button onClick={onClose} className="text-slate-400 hover:text-red-600 transition"><i className="fas fa-times text-xl"></i></button>
                    )}
                </div>

                <form onSubmit={handleSubmit} className={isPanel ? 'p-8 space-y-5' : 'p-8 space-y-5'}>
                    {msg && <div className="p-2 bg-green-100 text-green-800 text-center text-sm font-bold rounded">{msg}</div>}
                    
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Officer Name</label>
                            <input name="name" value={formData.name} onChange={handleChange} className="w-full p-2 border rounded bg-slate-50" />
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Official Email</label>
                            <input name="email" value={formData.email} onChange={handleChange} className="w-full p-2 border rounded bg-slate-50" />
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Department</label>
                            <input name="department" value={formData.department} onChange={handleChange} className="w-full p-2 border rounded" placeholder="Health Dept" />
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Zone</label>
                            <input name="zone" value={formData.zone} onChange={handleChange} className="w-full p-2 border rounded" placeholder="South Zone" />
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Badge ID</label>
                            <input name="badgeId" value={formData.badgeId} onChange={handleChange} className="w-full p-2 border rounded font-mono" placeholder="ID-882" />
                        </div>
                    </div>

                    <div className="pt-2 border-t mt-2">
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Update Password</label>
                        <input name="password" type="password" value={formData.password} onChange={handleChange} className="w-full p-2 border rounded" placeholder="New Password (Optional)" />
                    </div>

                    <button disabled={loading} className="w-full bg-slate-800 hover:bg-slate-900 text-white py-3 rounded font-bold transition">
                        {loading ? 'Updating Records...' : 'Save Official Details'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default GovernmentProfileModal;