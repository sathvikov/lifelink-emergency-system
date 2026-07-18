import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import RoleCard from '../components/ui/RoleCard';
import Card from '../components/ui/Card';
import { apiFetch } from '../config/api';
import { useDataMode } from '../context/DataModeContext';

const roles = [
    { key: 'national_admin', title: 'National Admin', desc: 'National oversight and policy execution', icon: 'fa-landmark' },
    { key: 'state_admin', title: 'State Admin', desc: 'State operations and compliance monitoring', icon: 'fa-flag' },
    { key: 'district_admin', title: 'District Admin', desc: 'District response coordination and audits', icon: 'fa-building-columns' },
    { key: 'supervisory_authority', title: 'Supervisory Authority', desc: 'Hospital oversight and governance', icon: 'fa-shield-halved' },
];

const GovernmentRoleSelect = () => {
    const { login, user } = useAuth();
    const { mode } = useDataMode();
    const navigate = useNavigate();
    const location = useLocation();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const allowSwitch = new URLSearchParams(location.search).get('switch') === '1';

    useEffect(() => {
        if (!allowSwitch && user?.subRole && user?.role === 'government') {
            navigate('/dashboard/government', { replace: true });
        }
    }, [allowSwitch, user?.subRole, user?.role, navigate]);

    useEffect(() => {
        if (mode !== 'real') return;
        const token = sessionStorage.getItem('lifelink_token') || localStorage.getItem('lifelink_token');
        if (token === 'demo-token') {
            setError('Please login again for real data access.');
        }
    }, [mode]);

    const handleSelect = async (subRole) => {
        setLoading(true);
        setError('');
        if (mode === 'demo') {
            const demoUser = user || { id: 'demo-government', name: 'Demo Gov Operator', role: 'government' };
            login({ ...demoUser, role: 'government', subRole }, 'demo-token');
            navigate('/dashboard/government');
            setLoading(false);
            return;
        }
        try {
            const { ok, data, status } = await apiFetch('/v2/auth/select-role', {
                method: 'POST',
                body: JSON.stringify({ subRole })
            });
            if (!ok) {
                const message = data.detail || data.error || 'Role selection failed';
                if (status === 401) {
                    setError('Session expired. Please login again.');
                } else {
                    setError(message);
                }
                setLoading(false);
                return;
            }
            const nextUser = { ...data.user, role: 'government', subRole: data.user?.subRole || subRole };
            const token = data.token || sessionStorage.getItem('lifelink_token') || localStorage.getItem('lifelink_token') || '';
            login(nextUser, token);
            navigate('/dashboard/government');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen gradient-background-universal flex items-center justify-center px-4 sm:px-6 py-10">
            <Card className="max-w-4xl w-full max-h-[calc(100vh-3rem)] overflow-y-auto sm:max-h-none sm:overflow-visible">
                <div className="mb-6">
                    <button
                        onClick={() => navigate('/login')}
                        className="text-xs font-semibold text-slate-500 hover:text-sky-600 flex items-center gap-2"
                    >
                        <i className="fas fa-arrow-left"></i>
                        Back to login
                    </button>
                </div>
                <div className="text-center mb-8">
                    <p className="text-xs font-bold uppercase text-slate-500">Government Role Selection</p>
                    <h2 className="text-3xl font-extrabold text-slate-900 font-display mt-2">Choose your authority level</h2>
                    <p className="text-slate-600 mt-2">Select the operational scope you manage.</p>
                </div>

                {error && <div className="mb-4 text-sm text-red-600 text-center">{error}</div>}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    {roles.map((role) => (
                        <RoleCard
                            key={role.key}
                            title={role.title}
                            description={role.desc}
                            icon={role.icon}
                            onSelect={() => handleSelect(role.key)}
                        />
                    ))}
                </div>

                {loading && <p className="text-center text-sm text-slate-500 mt-6">Applying role...</p>}
            </Card>
        </div>
    );
};

export default GovernmentRoleSelect;
