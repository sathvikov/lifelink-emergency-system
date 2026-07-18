import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config/api';
import { useDataMode } from '../context/DataModeContext';

const Login = () => {
    const navigate = useNavigate();
    const { login } = useAuth();
    const { mode } = useDataMode();
    
    // Default role is public
    const [formData, setFormData] = useState({ email: '', hospitalId: '', password: '', role: 'public' });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const demoDefaults = useMemo(() => ({
        public: { email: 'demo.public@lifelink.ai', hospitalId: '', password: 'demo1234' },
        hospital: { email: '', hospitalId: 'HOSP-DEMO-001', password: 'demo1234' },
        ambulance: { email: 'demo.ambulance@lifelink.ai', hospitalId: '', password: 'demo1234' },
        government: { email: 'demo.gov@lifelink.ai', hospitalId: '', password: 'demo1234' },
    }), []);

    useEffect(() => {
        try {
            const storedRole = sessionStorage.getItem('lifelink_login_role');
            if (storedRole) {
                setFormData((prev) => ({ ...prev, role: storedRole }));
                sessionStorage.removeItem('lifelink_login_role');
            }
        } catch (error) {
            // ignore storage errors
        }
    }, []);

    useEffect(() => {
        if (mode !== 'demo') return;
        const defaults = demoDefaults[formData.role] || demoDefaults.public;
        setFormData((prev) => ({
            ...prev,
            email: defaults.email,
            hospitalId: defaults.hospitalId,
            password: defaults.password,
        }));
    }, [mode, formData.role, demoDefaults]);

    const handleDemoLogin = () => {
        if (['hospital', 'government'].includes(formData.role)) {
            navigate(`/demo/role/${formData.role}`);
            return;
        }
        const demoUsers = {
            public: { id: 'demo-public', name: 'Demo Citizen', role: 'public' },
            hospital: { id: 'demo-hospital', name: 'Demo Hospital Admin', role: 'hospital', subRole: 'ceo' },
            ambulance: { id: 'demo-ambulance', name: 'Demo Ambulance Ops', role: 'ambulance', subRole: 'dispatcher' },
            government: { id: 'demo-government', name: 'Demo Gov Operator', role: 'government', subRole: 'national_admin' },
        };
        const demoUser = demoUsers[formData.role] || demoUsers.public;
        login(demoUser, 'demo-token');
        if (demoUser.role === 'hospital') {
            navigate('/dashboard/hospital');
            return;
        }
        if (demoUser.role === 'government') {
            navigate('/dashboard/government');
            return;
        }
        if (demoUser.role === 'ambulance') {
            navigate('/dashboard/ambulance');
            return;
        }
        navigate('/dashboard/public');
    };

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (mode === 'demo') {
                handleDemoLogin();
                setLoading(false);
                return;
            }
            if (!API_BASE_URL) {
                setError('API URL not configured. Set VITE_API_URL in client/.env (e.g. http://localhost:3010) and restart Vite.');
                return;
            }

            if (formData.role === 'hospital' && !formData.hospitalId.trim()) {
                setError('Hospital ID is required for hospital login.');
                return;
            }

            if (formData.role !== 'hospital' && !formData.email.trim()) {
                setError('Email is required for this portal.');
                return;
            }

            const payload = {
                password: formData.password,
                role: formData.role,
                ...(formData.role === 'hospital'
                    ? { hospitalId: formData.hospitalId.trim() }
                    : { email: formData.email.trim() })
            };

            const res = await fetch(`${API_BASE_URL}/v2/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                const message = data.detail || data.error || data.message || 'Login failed';
                if (res.status === 403) {
                    throw new Error(message || 'Awaiting Government Verification');
                }
                throw new Error(message);
            }

            if (!data.user || !data.user.role || !data.token) {
                throw new Error('Invalid server response: missing user or token.');
            }

            const userRole = data.user.role.toLowerCase();
            const userForSession = (userRole === 'hospital' || userRole === 'government')
                ? { ...data.user, subRole: null }
                : data.user;

            login(userForSession, data.token);

            if (userRole === 'hospital') {
                navigate('/dashboard/hospital/roles');
            } else if (userRole === 'government') {
                navigate('/dashboard/government/roles');
            } else if (userRole === 'ambulance') {
                navigate('/dashboard/ambulance');
            } else {
                navigate('/dashboard/public');
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
        <div className="min-h-screen flex items-center justify-center px-4 py-6 sm:py-10 bg-gradient-to-br from-blue-50 to-indigo-100 font-sans">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden relative animate-fade-in border border-white/50 max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-h-none sm:overflow-visible">
                
                {/* Top Blue Bar */}
                <div className="h-2 bg-gradient-to-r from-blue-600 to-indigo-600 w-full"></div>

                <div className="p-6 sm:p-8">
                    {/* Header */}
                    <div className="text-center mb-8">
                        <div className="w-16 h-16 bg-blue-600 rounded-2xl mx-auto flex items-center justify-center text-white text-3xl shadow-lg mb-4">
                            <i className="fas fa-sign-in-alt"></i>
                        </div>
                        <h2 className="text-3xl font-bold text-gray-800 tracking-tight">Welcome Back</h2>
                        <p className="text-gray-500 text-sm mt-1">Select your portal to continue</p>
                    </div>

                    {/* ROLE SELECTOR TABS */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-1 bg-slate-100 p-1.5 rounded-xl mb-6">
                        {['public', 'hospital', 'ambulance', 'government'].map((r) => (
                            <button
                                key={r}
                                type="button"
                                onClick={() => setFormData({ ...formData, role: r })}
                                className={`py-2 text-[11px] sm:text-xs font-bold uppercase tracking-wide rounded-lg transition-all duration-200 ${
                                    formData.role === r
                                        ? 'bg-white text-blue-700 shadow-sm ring-1 ring-black/5'
                                        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
                                }`}
                            >
                                {r}
                            </button>
                        ))}
                    </div>

                    {formData.role === 'hospital' && (
                        <div className="space-y-1">
                            <label className="text-xs font-bold text-gray-500 uppercase ml-1">Hospital ID</label>
                            <div className="relative">
                                <i className="fas fa-hospital-symbol absolute left-4 top-3.5 text-gray-400"></i>
                                <input
                                    name="hospitalId"
                                    type="text"
                                    required
                                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition"
                                    placeholder="Enter hospital registration ID"
                                    value={formData.hospitalId}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                    )}

                    {/* Error Box */}
                    {error && (
                        <div className="mb-6 p-4 bg-red-50 text-red-600 text-sm font-semibold rounded-xl border border-red-100 flex items-center gap-3 animate-shake">
                            <i className="fas fa-exclamation-circle text-lg"></i>
                            {error}
                        </div>
                    )}

                    {/* Form */}
                    <form onSubmit={handleSubmit} className="space-y-5">
                        {formData.role !== 'hospital' && (
                            <div className="space-y-1">
                                <label className="text-xs font-bold text-gray-500 uppercase ml-1">Email Address</label>
                                <div className="relative">
                                    <i className="fas fa-envelope absolute left-4 top-3.5 text-gray-400"></i>
                                    <input
                                        name="email"
                                        type="email"
                                        required
                                        className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition"
                                        placeholder="name@example.com"
                                        value={formData.email}
                                        onChange={handleChange}
                                    />
                                </div>
                            </div>
                        )}

                        <div className="space-y-1">
                            <label className="text-xs font-bold text-gray-500 uppercase ml-1">Password</label>
                            <div className="relative">
                                <i className="fas fa-lock absolute left-4 top-3.5 text-gray-400"></i>
                                <input
                                    name="password"
                                    type="password"
                                    required
                                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition"
                                    placeholder="••••••••"
                                    value={formData.password}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold py-3.5 rounded-xl shadow-lg hover:shadow-xl transition transform hover:scale-[1.02] active:scale-95 flex justify-center items-center gap-2"
                        >
                            {loading ? <><i className="fas fa-spinner fa-spin"></i> Processing...</> : 'Login Securely'}
                        </button>
                        {mode === 'demo' && (
                            <button
                                type="button"
                                onClick={handleDemoLogin}
                                className="w-full bg-slate-900 text-white font-bold py-3.5 rounded-xl shadow-lg hover:bg-slate-800 transition"
                            >
                                Continue with Demo
                            </button>
                        )}
                    </form>

                    <div className="mt-8 text-center pt-6 border-t border-slate-100">
                        <p className="text-gray-500 text-sm">
                            New here?{' '}
                            <Link to="/signup" className="text-blue-600 font-bold hover:underline">
                                Create an account
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Login;