import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true); // Prevents "undefined role" on refresh

    useEffect(() => {
        const storedUser = sessionStorage.getItem('lifelink_user');
        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser));
            } catch (err) {
                sessionStorage.removeItem('lifelink_user');
            }
        } else {
            const cachedUser = localStorage.getItem('lifelink_user');
            if (cachedUser) {
                try {
                    setUser(JSON.parse(cachedUser));
                } catch (err) {
                    localStorage.removeItem('lifelink_user');
                }
            }
        }
        setLoading(false);
    }, []);

    const login = (userData, token) => {
        sessionStorage.setItem('lifelink_user', JSON.stringify(userData));
        sessionStorage.setItem('lifelink_token', token);
        localStorage.setItem('lifelink_user', JSON.stringify(userData));
        localStorage.setItem('lifelink_token', token);
        setUser(userData);
    };

    const updateUser = (updates) => {
        setUser((prev) => {
            if (!prev) return prev;
            const next = { ...prev, ...updates };
            sessionStorage.setItem('lifelink_user', JSON.stringify(next));
            localStorage.setItem('lifelink_user', JSON.stringify(next));
            return next;
        });
    };

    const logout = () => {
        sessionStorage.removeItem('lifelink_user');
        sessionStorage.removeItem('lifelink_token');
        localStorage.removeItem('lifelink_user');
        localStorage.removeItem('lifelink_token');
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, updateUser, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

// Exporting the hook at the bottom is standard practice
export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};