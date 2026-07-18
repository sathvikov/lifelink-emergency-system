import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config/api';

const Signup = () => {
    const navigate = useNavigate();
    const { login } = useAuth(); // Optional: Auto-login after signup if needed
    
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        password: '',
        phone: '',
        location: '',
        role: 'public', // Default role
        subRole: '',
        // Hospital Specific Fields
        regNumber: '',
        hospitalType: 'General',
        departmentRole: '',
        // Government Fields
        governmentLevel: '',
        // Ambulance Fields
        ambulanceBase: '',
        vehicleId: ''
    });

    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (!API_BASE_URL) {
                setError('API URL not configured. Set VITE_API_URL in client/.env (e.g. http://localhost:3010) and restart Vite.');
                return;
            }
            const res = await fetch(`${API_BASE_URL}/v2/auth/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                throw new Error(data.message || 'Signup failed');
            }

            // Logic: Hospitals are NOT auto-logged in (Pending Verification)
            if (formData.role === 'hospital') {
                alert("Registration Successful! Please wait for Government verification before logging in.");
                navigate('/login');
            } else if (formData.role === 'ambulance') {
                alert("Ambulance registration submitted. Awaiting Government verification.");
                navigate('/login');
            } else {
                // Public users might be auto-logged in or asked to login
                alert("Account Created Successfully!");
                navigate('/login');
            }

        } catch (err) {
            const msg = err.message || '';
            setError(msg === 'Failed to fetch'
                ? 'Cannot reach server. Ensure the backend is running on http://localhost:3010 and restart Vite if you changed .env.'
                : msg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-6 sm:py-10">
            <div className="bg-white p-6 sm:p-8 rounded-2xl shadow-xl w-full max-w-md animate-fade-in border border-slate-100 max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-h-none sm:overflow-visible">
                
                {/* Header */}
                <div className="text-center mb-8">
                    <div className="bg-gradient-to-tr from-blue-600 to-indigo-600 text-white w-12 h-12 rounded-lg flex items-center justify-center mx-auto mb-3 shadow-lg">
                        <i className="fas fa-heartbeat text-2xl"></i>
                    </div>
                    <h2 className="text-2xl font-bold text-slate-800">Create Account</h2>
                    <p className="text-slate-500 text-sm">Join the LifeLink Network</p>
                </div>

                {error && (
                    <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm font-bold rounded-lg border border-red-200 text-center">
                        <i className="fas fa-exclamation-circle mr-2"></i>{error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    
                    {/* Role Selector */}
                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">I am a...</label>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                            {['public', 'hospital', 'ambulance', 'government'].map((r) => (
                                <button
                                    key={r}
                                    type="button"
                                    onClick={() => setFormData({ ...formData, role: r, subRole: '' })}
                                    className={`py-2 text-xs sm:text-sm font-bold rounded-lg capitalize transition ${
                                        formData.role === r
                                            ? 'bg-blue-600 text-white shadow-md'
                                            : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                                    }`}
                                >
                                    {r}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Common Fields */}
                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                            {formData.role === 'hospital' ? 'Hospital Name' : 'Full Name'}
                        </label>
                        <input
                            name="name"
                            type="text"
                            required
                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                            placeholder={formData.role === 'hospital' ? "e.g. City General Hospital" : "e.g. John Doe"}
                            value={formData.name}
                            onChange={handleChange}
                        />
                    </div>

                    {(formData.role === 'government' || formData.role === 'ambulance') && (
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                                {formData.role === 'government' && 'Authority Level'}
                                {formData.role === 'ambulance' && 'Ambulance Role'}
                            </label>
                            <select
                                name="subRole"
                                value={formData.subRole}
                                onChange={handleChange}
                                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                            >
                                <option value="">Select role</option>
                                {formData.role === 'hospital' && ['ceo', 'finance', 'emergency', 'opd', 'icu', 'radiology', 'ot'].map((role) => (
                                    <option key={role} value={role}>{role.toUpperCase()}</option>
                                ))}
                                {formData.role === 'government' && ['national_admin', 'state_admin', 'district_admin', 'supervisory_authority'].map((role) => (
                                    <option key={role} value={role}>{role.replace('_', ' ').toUpperCase()}</option>
                                ))}
                                {formData.role === 'ambulance' && ['crew', 'dispatcher'].map((role) => (
                                    <option key={role} value={role}>{role.toUpperCase()}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Email Address</label>
                        <input
                            name="email"
                            type="email"
                            required
                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                            placeholder="name@example.com"
                            value={formData.email}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Phone</label>
                            <input
                                name="phone"
                                type="text"
                                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                                placeholder="+91..."
                                value={formData.phone}
                                onChange={handleChange}
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Location</label>
                            <input
                                name="location"
                                type="text"
                                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                                placeholder="City"
                                value={formData.location}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    {/* Hospital Specific Fields (Conditional) */}
                    {formData.role === 'hospital' && (
                        <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 animate-fade-in">
                            <h4 className="text-xs font-bold text-blue-800 uppercase mb-3 border-b border-blue-200 pb-1">Facility Details</h4>
                            <div className="space-y-3">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1">Govt. Registration Number</label>
                                    <input
                                        name="regNumber"
                                        type="text"
                                        required
                                        className="w-full p-2 bg-white border border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                        placeholder="e.g. KA-MH-1029"
                                        value={formData.regNumber}
                                        onChange={handleChange}
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1">Facility Type</label>
                                    <select 
                                        name="hospitalType" 
                                        value={formData.hospitalType} 
                                        onChange={handleChange}
                                        className="w-full p-2 bg-white border border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                    >
                                        <option>General</option>
                                        <option>Specialty</option>
                                        <option>Trauma Center</option>
                                        <option>Clinic</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1">Department Role</label>
                                    <input
                                        name="departmentRole"
                                        type="text"
                                        className="w-full p-2 bg-white border border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                        placeholder="e.g. Emergency"
                                        value={formData.departmentRole}
                                        onChange={handleChange}
                                    />
                                </div>
                            </div>
                        </div>
                    )}

                    {formData.role === 'government' && (
                        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 animate-fade-in">
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Government Level</label>
                            <input
                                name="governmentLevel"
                                type="text"
                                className="w-full p-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                                placeholder="e.g. State Admin"
                                value={formData.governmentLevel}
                                onChange={handleChange}
                            />
                        </div>
                    )}

                    {formData.role === 'ambulance' && (
                        <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-100 animate-fade-in">
                            <h4 className="text-xs font-bold text-emerald-800 uppercase mb-3 border-b border-emerald-200 pb-1">Ambulance Details</h4>
                            <div className="space-y-3">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1">Base Location</label>
                                    <input
                                        name="ambulanceBase"
                                        type="text"
                                        className="w-full p-2 bg-white border border-emerald-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 text-sm"
                                        placeholder="e.g. Central Depot"
                                        value={formData.ambulanceBase}
                                        onChange={handleChange}
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 mb-1">Vehicle ID</label>
                                    <input
                                        name="vehicleId"
                                        type="text"
                                        className="w-full p-2 bg-white border border-emerald-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 text-sm"
                                        placeholder="e.g. AMB-042"
                                        value={formData.vehicleId}
                                        onChange={handleChange}
                                    />
                                </div>
                            </div>
                        </div>
                    )}

                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Password</label>
                        <input
                            name="password"
                            type="password"
                            required
                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
                            placeholder="••••••••"
                            value={formData.password}
                            onChange={handleChange}
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl shadow-lg hover:shadow-xl transition transform hover:scale-[1.02] active:scale-95"
                    >
                        {loading ? <i className="fas fa-spinner fa-spin"></i> : 'Create Account'}
                    </button>
                </form>

                <div className="mt-6 text-center">
                    <p className="text-slate-500 text-sm">
                        Already have an account?{' '}
                        <Link to="/login" className="text-blue-600 font-bold hover:underline">
                            Login here
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
};

export default Signup;