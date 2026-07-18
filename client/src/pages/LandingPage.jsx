// client/src/pages/LandingPage.jsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDataMode } from '../context/DataModeContext';
import DataModeToggle from '../components/ui/DataModeToggle';

const LandingPage = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { mode } = useDataMode();

  const handlePortalClick = (role) => {
    if (mode === 'demo') {
      if (['hospital', 'government'].includes(role)) {
        navigate(`/demo/role/${role}`);
        return;
      }
      const demoUsers = {
        public: { id: 'demo-public', name: 'Demo Citizen', role: 'public' },
        hospital: { id: 'demo-hospital', name: 'Demo Hospital Admin', role: 'hospital', subRole: 'ceo' },
        ambulance: { id: 'demo-ambulance', name: 'Demo Ambulance Ops', role: 'ambulance', subRole: 'dispatcher' },
        government: { id: 'demo-government', name: 'Demo Gov Operator', role: 'government', subRole: 'national_admin' },
      };
      const demoUser = demoUsers[role] || demoUsers.public;
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
      return;
    }
    navigate('/login');
  };

  return (
    <div className="gradient-background-universal min-h-screen">
      {/* Header */}
      <header className="absolute inset-x-0 top-0 z-50">
        <nav className="flex items-center justify-between px-4 py-4 sm:p-6 lg:px-8">
          <div className="flex lg:flex-1">
            <a href="#" className="text-xl font-bold text-slate-800 hover:opacity-80">
              <i className="fas fa-heart-pulse mr-2 text-sky-500"></i>LifeLink
            </a>
          </div>
          <div className="hidden lg:flex lg:flex-1 lg:justify-end gap-4 items-center">
            <div className="mr-2">
              <DataModeToggle size="sm" />
            </div>
            <button onClick={() => navigate('/login')} className="text-sm font-semibold leading-6 text-gray-700 hover:text-sky-600">
              Log in <span aria-hidden="true">&rarr;</span>
            </button>
            <button onClick={() => navigate('/signup')} className="rounded-md bg-gradient-to-r from-sky-500 to-violet-500 px-4 py-2 text-sm font-semibold text-white shadow-md hover:scale-105 transition-transform">
              Sign Up
            </button>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <main className="isolate">
        <div className="relative min-h-screen pt-24 pb-12 sm:pt-0 sm:pb-0 flex items-center justify-center">
          <div className="mx-auto max-w-3xl text-center px-6 z-10 animate-fade-in">
            <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-7xl animate-slide-in-up font-display">
              Connecting Lives, Saving Lives
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-700 animate-slide-in-up delay-200">
              A unified platform for public health emergencies, connecting citizens, hospitals, and government for a safer tomorrow.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 animate-slide-in-up delay-300">
              <div className="flex items-center gap-3">
                <DataModeToggle size="md" />
              </div>
              <button onClick={() => navigate('/signup')} className="rounded-md bg-gradient-to-r from-sky-500 to-violet-500 px-6 py-3 text-base font-semibold text-white shadow-xl hover:scale-105 transition-transform animate-pulse-cta">
                Get Started
              </button>
              <p className="text-xs text-slate-500">Demo mode skips login and preloads sample data.</p>
            </div>
          </div>
        </div>

        {/* Features Section */}
        <section id="features" className="pb-16 -mt-16 sm:pb-24 sm:-mt-24">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mt-16 grid grid-cols-1 gap-8 md:grid-cols-3">
              {[
                { icon: 'fa-triangle-exclamation', title: 'Emergency Alerts', desc: 'Instantly notify the nearest hospital with your location.' },
                { icon: 'fa-droplet', title: 'Blood Donation', desc: 'Find available donors or see urgent blood requests.' },
                { icon: 'fa-chart-pie', title: 'Health Analytics', desc: 'AI-driven insights to predict and manage outbreaks.' }
              ].map((feature, i) => (
                <div key={feature.title} className="bg-white/60 backdrop-blur-xl p-8 rounded-2xl shadow-lg border border-white/50 hover:-translate-y-2 transition-transform duration-300">
                  <div className="text-sky-500 text-4xl mb-4"><i className={`fas ${feature.icon}`}></i></div>
                  <h3 className="text-xl font-semibold text-gray-900">{feature.title}</h3>
                  <p className="mt-2 text-gray-700">{feature.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Portal Section */}
        <section className="pb-24">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mb-10 text-center">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Portal Access</p>
              <h2 className="text-3xl font-extrabold text-slate-900 mt-2 font-display">Choose your LifeLink workspace</h2>
              <p className="text-slate-600 mt-3">Dedicated experiences for citizens, responders, and authorities.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {[
                { key: 'public', title: 'Public', desc: 'Health dashboard, SOS, AI assistant', icon: 'fa-user-shield' },
                { key: 'hospital', title: 'Hospital', desc: 'Emergency intake, resources, analytics', icon: 'fa-hospital' },
                { key: 'ambulance', title: 'Ambulance', desc: 'Dispatch, tracking, route optimization', icon: 'fa-ambulance' },
                { key: 'government', title: 'Government', desc: 'City analytics, policies, oversight', icon: 'fa-landmark' }
              ].map((portal) => (
                <button
                  key={portal.title}
                  onClick={() => handlePortalClick(portal.key)}
                  className="text-left bg-white/70 backdrop-blur-xl p-6 rounded-2xl shadow-lg border border-white/50 hover:-translate-y-2 transition-transform duration-300"
                >
                  <div className="text-sky-600 text-3xl mb-4"><i className={`fas ${portal.icon}`}></i></div>
                  <h3 className="text-lg font-semibold text-gray-900">{portal.title} Portal</h3>
                  <p className="text-sm text-gray-600 mt-2">{portal.desc}</p>
                  {mode === 'demo' && (
                    <p className="text-xs text-emerald-600 mt-3 font-semibold">Demo access enabled</p>
                  )}
                </button>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

export default LandingPage;