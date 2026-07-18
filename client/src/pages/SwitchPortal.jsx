import React from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import { useAuth } from '../context/AuthContext';
import { useDataMode } from '../context/DataModeContext';

const portals = [
    { key: 'public', title: 'Public', desc: 'Health dashboard, SOS, AI assistant', icon: 'fa-user-shield' },
    { key: 'hospital', title: 'Hospital', desc: 'Emergency intake, resources, analytics', icon: 'fa-hospital' },
    { key: 'ambulance', title: 'Ambulance', desc: 'Dispatch, tracking, route optimization', icon: 'fa-ambulance' },
    { key: 'government', title: 'Government', desc: 'City analytics, policies, oversight', icon: 'fa-landmark' },
];

const SwitchPortal = () => {
    const navigate = useNavigate();
    const { user, login } = useAuth();
    const { mode } = useDataMode();
    const currentRole = user?.role?.toLowerCase();

    if (currentRole && mode !== 'demo') {
        if (currentRole === 'hospital') {
            navigate('/dashboard/hospital/roles', { replace: true });
            return null;
        }
        if (currentRole === 'government') {
            navigate('/dashboard/government/roles', { replace: true });
            return null;
        }
        if (currentRole === 'ambulance') {
            navigate('/dashboard/ambulance/roles', { replace: true });
            return null;
        }
    }

    const handlePortal = (role) => {
        const targetRole = String(role || '').toLowerCase();
        if (!targetRole) return;

        if (mode === 'demo') {
            if (['hospital', 'government', 'ambulance'].includes(targetRole)) {
                navigate(`/demo/role/${targetRole}`);
                return;
            }
            const demoUsers = {
                public: { id: 'demo-public', name: 'Demo Citizen', role: 'public' },
                hospital: { id: 'demo-hospital', name: 'Demo Hospital Admin', role: 'hospital', subRole: 'ceo' },
                ambulance: { id: 'demo-ambulance', name: 'Demo Ambulance Ops', role: 'ambulance', subRole: 'dispatcher' },
                government: { id: 'demo-government', name: 'Demo Gov Operator', role: 'government', subRole: 'national_admin' },
            };
            const demoUser = demoUsers[targetRole] || demoUsers.public;
            login(demoUser, 'demo-token');
            if (targetRole === 'hospital') {
                navigate('/dashboard/hospital');
                return;
            }
            if (targetRole === 'government') {
                navigate('/dashboard/government');
                return;
            }
            if (targetRole === 'ambulance') {
                navigate('/dashboard/ambulance');
                return;
            }
            navigate('/dashboard/public');
            return;
        }

        if (targetRole === currentRole) {
            if (targetRole === 'hospital') {
                navigate(user?.subRole ? '/dashboard/hospital' : '/dashboard/hospital/roles');
                return;
            }
            if (targetRole === 'government') {
                navigate(user?.subRole ? '/dashboard/government' : '/dashboard/government/roles');
                return;
            }
            if (targetRole === 'ambulance') {
                navigate(user?.subRole ? '/dashboard/ambulance' : '/dashboard/ambulance/roles');
                return;
            }
            navigate('/dashboard/public');
            return;
        }
        navigate('/login');
    };

    return (
        <div className="min-h-screen gradient-background-universal flex items-center justify-center px-6">
            <Card className="max-w-4xl w-full">
                <div className="mb-6">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="text-xs font-semibold text-slate-500 hover:text-sky-600 flex items-center gap-2"
                    >
                        <i className="fas fa-arrow-left"></i>
                        Back to dashboard
                    </button>
                </div>
                <div className="text-center mb-8">
                    <p className="text-xs font-bold uppercase text-slate-500">Switch Portal</p>
                    <h2 className="text-3xl font-extrabold text-slate-900 font-display mt-2">Choose your workspace</h2>
                    <p className="text-slate-600 mt-2">Switch portals without being logged out.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-5">
                    {portals.map((portal) => (
                        <button
                            key={portal.key}
                            type="button"
                            onClick={() => handlePortal(portal.key)}
                            className="text-left bg-white/80 backdrop-blur-xl p-6 rounded-2xl shadow-lg border border-white/60 hover:-translate-y-1 transition-all"
                        >
                            <div className="text-sky-600 text-3xl mb-4">
                                <i className={`fas ${portal.icon}`}></i>
                            </div>
                            <h3 className="text-lg font-semibold text-slate-900">{portal.title} Portal</h3>
                            <p className="text-sm text-slate-600 mt-2">{portal.desc}</p>
                            {portal.key === currentRole && (
                                <p className="text-xs text-emerald-600 mt-3 font-semibold">Current portal</p>
                            )}
                        </button>
                    ))}
                </div>
            </Card>
        </div>
    );
};

export default SwitchPortal;
