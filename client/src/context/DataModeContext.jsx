import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const DataModeContext = createContext(null);
const STORAGE_KEY = 'lifelink_data_mode';

const normalizeMode = (value) => (value === 'demo' ? 'demo' : 'real');

export const DataModeProvider = ({ children }) => {
    const [mode, setMode] = useState(() => {
        if (typeof window === 'undefined') return 'real';
        const stored = localStorage.getItem(STORAGE_KEY);
        return normalizeMode(stored || 'real');
    });

    useEffect(() => {
        if (typeof window === 'undefined') return;
        localStorage.setItem(STORAGE_KEY, mode);
    }, [mode]);

    const value = useMemo(() => ({
        mode,
        setMode: (next) => setMode(normalizeMode(next)),
    }), [mode]);

    return (
        <DataModeContext.Provider value={value}>
            {children}
        </DataModeContext.Provider>
    );
};

export const useDataMode = () => {
    const context = useContext(DataModeContext);
    if (!context) {
        throw new Error('useDataMode must be used within a DataModeProvider');
    }
    return context;
};
