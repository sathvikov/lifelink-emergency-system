import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';

const ProfileModal = ({ onClose, variant = 'modal' }) => {
    const { user } = useAuth(); 
    const isPanel = variant === 'panel';
    
    const [formData, setFormData] = useState({
        name: '', email: '', phone: '', age: '', bloodGroup: '', location: '', medicalHistory: '', password: ''
    });
    const [loading, setLoading] = useState(false);
    const [msg, setMsg] = useState('');

    useEffect(() => {
        if (!user) return;
        setFormData((prev) => ({
            ...prev,
            name: user.name || prev.name || '',
            email: user.email || prev.email || '',
            phone: user.phone || prev.phone || '',
            bloodGroup: user.bloodGroup || prev.bloodGroup || '',
            location: user.location || prev.location || ''
        }));
    }, [user]);

    useEffect(() => {
        const fetchDetails = async () => {
            if (!user?.id) return;
            try {
                const { ok, data } = await apiFetch(`/api/dashboard/public/${user.id}/full`, { method: 'GET' });
                if (!ok) throw new Error('Failed to load user profile details');
                
                setFormData({
                    name: user.name || '',
                    email: user.email || '',
                    phone: data.healthRecords?.contact || user.phone || '',
                    age: data.healthRecords?.age || '',
                    bloodGroup: data.healthRecords?.bloodGroup || user.bloodGroup || '',
                    location: user.location || '',
                    medicalHistory: Array.isArray(data.healthRecords?.conditions) 
                        ? data.healthRecords.conditions.join(', ') 
                        : (data.healthRecords?.conditions || ''),
                    password: ''
                });
            } catch (err) { console.error("Failed to load profile", err); }
        };
        fetchDetails();
    }, [user?.id]);

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        // 1. STOP THE PAGE REFRESH IMMEDIATELY
        e.preventDefault();
        e.stopPropagation();

        setLoading(true);
        setMsg('');

        try {
            const payload = { ...formData };
            if (!payload.password) delete payload.password;

            // 2. SEND DATA
            const { ok, status, data: result } = await apiFetch(`/api/dashboard/profile/${user.id}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });

            if (!ok) throw new Error(result?.message || `Update failed (${status})`);

            // 3. UPDATE LOCAL STORAGE
            const updatedUser = { ...user, ...result.user };
            localStorage.setItem('user', JSON.stringify(updatedUser));
            
            setMsg('Saved Successfully!');
            
            // 4. WAIT, THEN RELOAD
            setTimeout(() => {
                window.location.reload(); 
            }, 800);

        } catch (err) {
            console.error("Save Error:", err);
            setMsg(err.message || 'Update Failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={isPanel ? 'w-full' : 'fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 backdrop-blur-sm animate-fade-in'}>
            <div className={isPanel
                ? 'bg-white rounded-2xl shadow-lg w-full max-w-3xl mx-auto overflow-hidden relative flex flex-col'
                : 'bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden relative flex flex-col max-h-[90vh]'}
            >
                <div className="bg-gradient-to-r from-blue-700 to-indigo-700 p-6 text-white shrink-0 flex justify-between items-start">
                    <div><h2 className="text-2xl font-bold">Edit Full Profile</h2><p className="text-blue-100 text-sm opacity-80">Update your personal & medical details</p></div>
                    {!isPanel && onClose && (
                        <button type="button" onClick={onClose} className="text-white/70 hover:text-white p-2"><i className="fas fa-times text-xl"></i></button>
                    )}
                </div>

                <div className={isPanel ? 'p-6' : 'overflow-y-auto p-6 custom-scrollbar'}>
                    <form onSubmit={handleSubmit} className="space-y-5">
                        {msg && <div className={`p-3 rounded text-center text-sm font-bold ${msg.includes('Success') ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{msg}</div>}
                        
                        <div><h3 className="text-xs font-bold text-indigo-600 uppercase mb-3 border-b pb-1">Account Details</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div><label className="block text-xs font-bold text-gray-500 mb-1">Full Name</label><input name="name" value={formData.name} onChange={handleChange} className="w-full p-2.5 border rounded bg-gray-50 focus:ring-2 focus:ring-blue-200 outline-none" /></div>
                                <div><label className="block text-xs font-bold text-gray-500 mb-1">Email</label><input name="email" type="email" value={formData.email} onChange={handleChange} className="w-full p-2.5 border rounded bg-gray-50 focus:ring-2 focus:ring-blue-200 outline-none" /></div>
                            </div>
                        </div>

                        <div><h3 className="text-xs font-bold text-indigo-600 uppercase mb-3 border-b pb-1">Personal Info</h3>
                            <div className="grid grid-cols-2 gap-4">
                                <div><label className="block text-xs font-bold text-gray-500 mb-1">Phone</label><input name="phone" value={formData.phone} onChange={handleChange} className="w-full p-2.5 border rounded bg-gray-50" /></div>
                                <div><label className="block text-xs font-bold text-gray-500 mb-1">Location</label><input name="location" value={formData.location} onChange={handleChange} className="w-full p-2.5 border rounded bg-gray-50" /></div>
                                <div><label className="block text-xs font-bold text-gray-500 mb-1">Age</label><input name="age" type="number" value={formData.age} onChange={handleChange} className="w-full p-2.5 border rounded bg-gray-50" /></div>
                                <div><label className="block text-xs font-bold text-gray-500 mb-1">Blood Group</label>
                                    <select name="bloodGroup" value={formData.bloodGroup} onChange={handleChange} className="w-full p-2.5 border rounded bg-gray-50">
                                        <option value="">Select</option>
                                        {['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'].map(bg => <option key={bg} value={bg}>{bg}</option>)}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <div><h3 className="text-xs font-bold text-indigo-600 uppercase mb-3 border-b pb-1">Medical Profile</h3>
                            <label className="block text-xs font-bold text-gray-500 mb-1">Conditions / Allergies</label>
                            <textarea name="medicalHistory" value={formData.medicalHistory} onChange={handleChange} className="w-full p-3 border rounded bg-gray-50 h-20 text-sm" />
                        </div>

                        <div className="pt-2"><label className="block text-xs font-bold text-gray-500 mb-1">New Password (Optional)</label><input name="password" type="password" value={formData.password} onChange={handleChange} className="w-full p-2.5 border rounded bg-gray-50" placeholder="Leave blank to keep current" /></div>
                        
                        {/* BUTTON MUST BE TYPE="SUBMIT" */}
                        <div className="pt-4 border-t">
                            <button type="submit" disabled={loading} className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold shadow flex justify-center items-center gap-2">
                                {loading ? <><i className="fas fa-spinner fa-spin"></i> Saving...</> : 'Save All Changes'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
};

export default ProfileModal;