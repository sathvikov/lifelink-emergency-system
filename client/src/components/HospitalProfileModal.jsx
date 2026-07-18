import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../config/api';

const HospitalProfileModal = ({ onClose, variant = 'modal' }) => {
    const { user } = useAuth(); 
    const isPanel = variant === 'panel';
    
    // Initial State - Optimized for Organization Data
    const [formData, setFormData] = useState({
        name: '', 
        email: '', 
        phone: '', 
        location: '',
        regNumber: '', 
        totalBeds: '', 
        ambulances: '', 
        specialties: '', 
        type: 'General',
        website: '',
        password: '' // Optional update
    });
    
    const [loading, setLoading] = useState(false);
    const [msg, setMsg] = useState('');

    useEffect(() => {
        // Fetch latest hospital details on mount
        const fetchDetails = async () => {
            try {
                // We use the public endpoint to get current details
                const { ok, data } = await apiFetch(`/api/dashboard/public/${user.id}/full`, { method: 'GET' });
                if (!ok) {
                    throw new Error('Failed to load hospital profile');
                }
                
                // Pre-fill form (Check if hospitalProfile exists, otherwise fallback to root user data)
                const hp = data.hospitalProfile || {};
                
                setFormData({
                    name: user.name || '',
                    email: user.email || '',
                    phone: user.phone || '',
                    location: user.location || '',
                    regNumber: hp.regNumber || '',
                    totalBeds: hp.totalBeds || '',
                    ambulances: hp.ambulances || '',
                    specialties: hp.specialties ? hp.specialties.join(', ') : '',
                    type: hp.type || 'General',
                    website: hp.website || '',
                    password: ''
                });
            } catch (err) { console.error("Failed to load profile", err); }
        };
        fetchDetails();
    }, [user]);

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        setLoading(true);
        setMsg('');

        try {
            const payload = { ...formData };
            if (!payload.password) delete payload.password;

            const { ok, status, data: result } = await apiFetch(`/api/dashboard/profile/${user.id}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            if (!ok) throw new Error(result?.message || `Profile update failed (${status})`);

            // Update Local Storage with new Name
            const updatedUser = { ...user, ...result.user };
            localStorage.setItem('user', JSON.stringify(updatedUser));
            
            setMsg('Hospital Profile Updated Successfully!');
            
            // Reload to reflect changes
            setTimeout(() => { window.location.reload(); }, 800);

        } catch (err) {
            setMsg(err.message || 'Update Failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={isPanel ? 'w-full' : 'fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 backdrop-blur-sm animate-fade-in'}>
            <div className={isPanel
                ? 'bg-white rounded-2xl shadow-lg w-full max-w-4xl mx-auto overflow-hidden flex flex-col'
                : 'bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]'}
            >
                
                {/* Header - Teal Theme for Hospitals */}
                <div className="bg-gradient-to-r from-teal-600 to-cyan-700 p-6 text-white shrink-0 flex justify-between items-start">
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <i className="fas fa-hospital-alt"></i> Edit Facility Profile
                        </h2>
                        <p className="text-teal-100 text-sm opacity-90">Manage operational capacity and contact details.</p>
                    </div>
                    {!isPanel && onClose && (
                        <button type="button" onClick={onClose} className="text-white/70 hover:text-white p-2 transition">
                            <i className="fas fa-times text-xl"></i>
                        </button>
                    )}
                </div>

                <div className={isPanel ? 'p-8' : 'overflow-y-auto p-8 custom-scrollbar'}>
                    <form onSubmit={handleSubmit} className="space-y-6">
                        
                        {/* Status Message */}
                        {msg && <div className={`p-3 rounded text-center text-sm font-bold ${msg.includes('Updated') ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{msg}</div>}
                        
                        {/* Section 1: Organization Identity */}
                        <div>
                            <h3 className="text-xs font-bold text-teal-600 uppercase mb-3 border-b pb-1">Organization Details</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="label-text">Hospital Name</label>
                                    <input name="name" value={formData.name} onChange={handleChange} className="input-field" placeholder="e.g. City General Hospital" />
                                </div>
                                <div>
                                    <label className="label-text">Official Reg. Number</label>
                                    <input name="regNumber" value={formData.regNumber} onChange={handleChange} className="input-field bg-gray-50 font-mono text-sm" placeholder="Govt ID" />
                                </div>
                                <div>
                                    <label className="label-text">Admin Email</label>
                                    <input name="email" value={formData.email} onChange={handleChange} className="input-field" />
                                </div>
                                <div>
                                    <label className="label-text">Website URL</label>
                                    <input name="website" value={formData.website} onChange={handleChange} className="input-field" placeholder="www.hospital.com" />
                                </div>
                            </div>
                        </div>

                        {/* Section 2: Contact & Location */}
                        <div>
                            <h3 className="text-xs font-bold text-teal-600 uppercase mb-3 border-b pb-1">Location & Contact</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label className="label-text">Emergency Hotline</label>
                                    <input name="phone" value={formData.phone} onChange={handleChange} className="input-field" placeholder="+91..." />
                                </div>
                                <div>
                                    <label className="label-text">City / Address</label>
                                    <input name="location" value={formData.location} onChange={handleChange} className="input-field" placeholder="City, State" />
                                </div>
                            </div>
                        </div>

                        {/* Section 3: Operational Capacity */}
                        <div>
                            <h3 className="text-xs font-bold text-teal-600 uppercase mb-3 border-b pb-1">Operational Capacity</h3>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <label className="label-text">Total Beds</label>
                                    <input type="number" name="totalBeds" value={formData.totalBeds} onChange={handleChange} className="input-field" />
                                </div>
                                <div>
                                    <label className="label-text">Active Ambulances</label>
                                    <input type="number" name="ambulances" value={formData.ambulances} onChange={handleChange} className="input-field" />
                                </div>
                                <div>
                                    <label className="label-text">Facility Type</label>
                                    <select name="type" value={formData.type} onChange={handleChange} className="input-field">
                                        <option>General</option>
                                        <option>Trauma Center</option>
                                        <option>Multi-Specialty</option>
                                        <option>Clinic</option>
                                    </select>
                                </div>
                            </div>
                            <div className="mt-4">
                                <label className="label-text">Specialties (Comma Separated)</label>
                                <input name="specialties" value={formData.specialties} onChange={handleChange} className="input-field" placeholder="Cardiology, Orthopedics, Neurology..." />
                            </div>
                        </div>

                        {/* Section 4: Security */}
                        <div className="pt-2 border-t mt-2">
                            <label className="label-text">Update Password (Optional)</label>
                            <input name="password" type="password" value={formData.password} onChange={handleChange} className="input-field" placeholder="Leave blank to keep current password" />
                        </div>
                        
                        <div className="pt-4">
                            <button type="submit" disabled={loading} className="w-full py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold shadow-md hover:shadow-lg transition flex justify-center items-center gap-2">
                                {loading ? <><i className="fas fa-spinner fa-spin"></i> Saving...</> : 'Save Facility Profile'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            {/* Embedded CSS for this component scope */}
            <style>{`
                .label-text { display: block; font-size: 0.75rem; font-weight: 700; color: #4b5563; margin-bottom: 0.25rem; text-transform: uppercase; letter-spacing: 0.05em; }
                .input-field { width: 100%; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; background-color: #f9fafb; outline: none; transition: all 0.2s; font-size: 0.875rem; }
                .input-field:focus { box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.2); border-color: #14b8a6; background-color: white; }
            `}</style>
        </div>
    );
};

export default HospitalProfileModal;