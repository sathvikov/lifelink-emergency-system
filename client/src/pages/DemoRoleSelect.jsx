import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import RoleCard from '../components/ui/RoleCard';
import { useAuth } from '../context/AuthContext';
import { useDataMode } from '../context/DataModeContext';

const roleSets = {
    government: [
        { key: 'national_admin', title: 'National Admin', desc: 'National oversight and policy execution', icon: 'fa-landmark' },
        { key: 'state_admin', title: 'State Admin', desc: 'State operations and compliance monitoring', icon: 'fa-flag' },
        { key: 'district_admin', title: 'District Admin', desc: 'District response coordination and audits', icon: 'fa-building-columns' },
        { key: 'supervisory_authority', title: 'Supervisory Authority', desc: 'Hospital oversight and governance', icon: 'fa-shield-halved' },
    ],
    hospital: [
        { key: 'ceo', title: 'CEO', desc: 'Full access across all hospital modules', icon: 'fa-crown' },
        { key: 'finance', title: 'Finance', desc: 'Billing and revenue analytics', icon: 'fa-coins' },
        { key: 'emergency', title: 'Emergency', desc: 'Live emergency intake and dispatch', icon: 'fa-ambulance' },
        { key: 'opd', title: 'OPD', desc: 'Outpatient workflows and scheduling', icon: 'fa-user-doctor' },
        { key: 'icu', title: 'ICU', desc: 'Critical care monitoring', icon: 'fa-heart-pulse' },
        { key: 'radiology', title: 'Radiology', desc: 'Imaging and scans', icon: 'fa-x-ray' },
        { key: 'ot', title: 'OT', desc: 'Operation theatre control', icon: 'fa-user-nurse' },
    ],
    ambulance: [],
};

const DemoRoleSelect = () => {
    const navigate = useNavigate();
    const { portal } = useParams();
    const { login } = useAuth();
    const { mode } = useDataMode();

    const portalKey = String(portal || '').toLowerCase();
    const roles = roleSets[portalKey] || [];

    if (mode !== 'demo') {
        navigate('/login', { replace: true });
        return null;
    }

    if (portalKey === 'ambulance') {
        login({ id: 'demo-ambulance', name: 'Demo Ambulance Ops', role: 'ambulance' }, 'demo-token');
        navigate('/dashboard/ambulance', { replace: true });
        return null;
    }

    if (!roles.length) {
        navigate('/', { replace: true });
        return null;
    }

    const handleSelect = (subRole) => {
        const demoUsers = {
            public: { id: 'demo-public', name: 'Demo Citizen', role: 'public' },
            hospital: { id: 'demo-hospital', name: 'Demo Hospital Admin', role: 'hospital' },
            ambulance: { id: 'demo-ambulance', name: 'Demo Ambulance Ops', role: 'ambulance' },
            government: { id: 'demo-government', name: 'Demo Gov Operator', role: 'government' },
        };
        const baseUser = demoUsers[portalKey] || demoUsers.public;
        login({ ...baseUser, subRole }, 'demo-token');

        if (portalKey === 'hospital') {
            navigate('/dashboard/hospital');
            return;
        }
        if (portalKey === 'government') {
            navigate('/dashboard/government');
            return;
        }
        if (portalKey === 'ambulance') {
            navigate('/dashboard/ambulance');
            return;
        }
        navigate('/dashboard/public');
    };

    return (
        <div className="min-h-screen gradient-background-universal flex items-center justify-center px-4 sm:px-6 py-10">
            <Card className="max-w-4xl w-full max-h-[calc(100vh-3rem)] overflow-y-auto sm:max-h-none sm:overflow-visible">
                <div className="mb-6">
                    <button
                        onClick={() => navigate('/')}
                        className="text-xs font-semibold text-slate-500 hover:text-sky-600 flex items-center gap-2"
                    >
                        <i className="fas fa-arrow-left"></i>
                        Back to home
                    </button>
                </div>
                <div className="text-center mb-8">
                    <p className="text-xs font-bold uppercase text-slate-500">Demo Role Selection</p>
                    <h2 className="text-3xl font-extrabold text-slate-900 font-display mt-2">Choose your role</h2>
                    <p className="text-slate-600 mt-2">Select your demo workspace to continue.</p>
                </div>

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
            </Card>
        </div>
    );
};

export default DemoRoleSelect;
