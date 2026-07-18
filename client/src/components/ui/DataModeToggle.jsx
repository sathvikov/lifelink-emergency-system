import React from 'react';
import { useDataMode } from '../../context/DataModeContext';
import { useAuth } from '../../context/AuthContext';

const DataModeToggle = ({ size = 'sm' }) => {
    const { mode, setMode } = useDataMode();
    const { logout } = useAuth();
    const isDemo = mode === 'demo';
    const baseClass = size === 'sm' ? 'text-xs px-3 py-2' : 'text-sm px-4 py-2';

    const ensureRealSession = () => {
        const token = sessionStorage.getItem('lifelink_token') || localStorage.getItem('lifelink_token');
        if (token === 'demo-token') {
            logout();
        }
    };

    return (
        <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-white/90 p-1">
            <button
                type="button"
                onClick={() => setMode('demo')}
                className={`${baseClass} rounded-full font-semibold transition ${isDemo ? 'bg-slate-900 text-white shadow' : 'text-slate-600 hover:bg-slate-100'}`}
            >
                Demo Data
            </button>
            <button
                type="button"
                onClick={() => {
                    ensureRealSession();
                    setMode('real');
                }}
                className={`${baseClass} rounded-full font-semibold transition ${!isDemo ? 'bg-slate-900 text-white shadow' : 'text-slate-600 hover:bg-slate-100'}`}
            >
                Real Data
            </button>
        </div>
    );
};

export default DataModeToggle;
