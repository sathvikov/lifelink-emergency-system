import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { getAuthToken } from './config/api';

// Pages
const Signup = lazy(() => import('./pages/Signup'));
const Login = lazy(() => import('./pages/Login'));
const PublicDashboard = lazy(() => import('./pages/PublicDashboard'));
const HospitalDashboard = lazy(() => import('./pages/HospitalDashboard'));
const GovernmentDashboard = lazy(() => import('./pages/GovernmentDashboard'));
const AmbulanceDashboard = lazy(() => import('./pages/AmbulanceDashboard'));
const LandingPage = lazy(() => import('./pages/LandingPage'));
const ApiTest = lazy(() => import('./pages/ApiTest'));
const HospitalRoleSelect = lazy(() => import('./pages/HospitalRoleSelect'));
const GovernmentRoleSelect = lazy(() => import('./pages/GovernmentRoleSelect'));
const DemoRoleSelect = lazy(() => import('./pages/DemoRoleSelect'));
const SwitchPortal = lazy(() => import('./pages/SwitchPortal'));

// Protected Route Component
// ... existing imports

const ProtectedRoute = ({ children, allowedRoles }) => {
    const { user, loading } = useAuth();
    
    // 1. Wait for the AuthProvider to check sessionStorage
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="flex flex-col items-center gap-4">
                    <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
                    <p className="text-gray-500 font-medium">Authenticating...</p>
                </div>
            </div>
        );
    }
    
    // 2. If session check is done and no user exists
    if (!user) {
        return <Navigate to="/login" replace />;
    }

    // 3. If there is no auth token, force login again
    if (!getAuthToken()) {
        return <Navigate to="/login" replace />;
    }

    // 4. Check for role authorization (normalized to lowercase)
    if (allowedRoles && !allowedRoles.includes(user.role.toLowerCase())) {
        return <Navigate to="/" replace />;
    }

    return children;
};

const DashboardRedirect = () => {
    const { user } = useAuth();
    const role = user?.role?.toLowerCase();
    const hasSubRole = Boolean(user?.subRole);

    if (role === 'hospital') {
        return <Navigate to={hasSubRole ? '/dashboard/hospital' : '/dashboard/hospital/roles'} replace />;
    }
    if (role === 'government') {
        return <Navigate to={hasSubRole ? '/dashboard/government' : '/dashboard/government/roles'} replace />;
    }
    if (role === 'ambulance') {
        return <Navigate to="/dashboard/ambulance" replace />;
    }
    return <Navigate to="/dashboard/public" replace />;
};

// ... keep rest of App component as provided

const PageLoader = () => (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
            <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-slate-800"></div>
            <p className="text-sm text-slate-500 font-medium">Loading...</p>
        </div>
    </div>
);

const App = () => {
    return (
        <AuthProvider>
            <Router>
                <Suspense fallback={<PageLoader />}>
                <Routes>
                    {/* Public Routes */}
                    <Route path="/" element={<LandingPage />} />
                    <Route path="/signup" element={<Signup />} />
                    <Route path="/login" element={<Login />} />

                    {/* Protected: Public User Dashboard */}
                    <Route
                        path="/dashboard"
                        element={
                            <ProtectedRoute>
                                <DashboardRedirect />
                            </ProtectedRoute>
                        }
                    />

                    <Route 
                        path="/dashboard/public" 
                        element={
                            <ProtectedRoute allowedRoles={['public']}>
                                <PublicDashboard />
                            </ProtectedRoute>
                        } 
                    />

                    <Route
                        path="/dashboard/public/:module"
                        element={
                            <ProtectedRoute allowedRoles={['public']}>
                                <PublicDashboard />
                            </ProtectedRoute>
                        }
                    />

                    {/* Demo Role Select */}
                    <Route path="/demo/role/:portal" element={<DemoRoleSelect />} />

                    {/* Protected: Hospital Dashboard */}
                    <Route 
                        path="/dashboard/hospital" 
                        element={
                            <ProtectedRoute allowedRoles={['hospital']}>
                                <HospitalDashboard />
                            </ProtectedRoute>
                        } 
                    />

                    <Route
                        path="/dashboard/hospital/roles"
                        element={
                            <ProtectedRoute allowedRoles={['hospital']}>
                                <HospitalRoleSelect />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/dashboard/hospital/:module"
                        element={
                            <ProtectedRoute allowedRoles={['hospital']}>
                                <HospitalDashboard />
                            </ProtectedRoute>
                        }
                    />

                    {/* Protected: Government Dashboard */}
                    <Route 
                        path="/dashboard/government" 
                        element={
                            <ProtectedRoute allowedRoles={['government']}>
                                <GovernmentDashboard />
                            </ProtectedRoute>
                        } 
                    />

                    <Route
                        path="/dashboard/government/roles"
                        element={
                            <ProtectedRoute allowedRoles={['government']}>
                                <GovernmentRoleSelect />
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/dashboard/government/:module"
                        element={
                            <ProtectedRoute allowedRoles={['government']}>
                                <GovernmentDashboard />
                            </ProtectedRoute>
                        }
                    />

                    {/* Protected: Ambulance Dashboard */}
                    <Route
                        path="/dashboard/ambulance"
                        element={
                            <ProtectedRoute allowedRoles={['ambulance']}>
                                <AmbulanceDashboard />
                            </ProtectedRoute>
                        }
                    />

                    <Route path="/dashboard/ambulance/roles" element={<Navigate to="/dashboard/ambulance" replace />} />

                    <Route
                        path="/dashboard/ambulance/:module"
                        element={
                            <ProtectedRoute allowedRoles={['ambulance']}>
                                <AmbulanceDashboard />
                            </ProtectedRoute>
                        }
                    />

                    {/* API Test Page */}
                    <Route path="/api-test" element={<ApiTest />} />

                    {/* Switch Portal */}
                    <Route
                        path="/switch-portal"
                        element={
                            <ProtectedRoute>
                                <SwitchPortal />
                            </ProtectedRoute>
                        }
                    />

                    {/* Fallback */}
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
                </Suspense>
            </Router>
        </AuthProvider>
    );
};

export default App;