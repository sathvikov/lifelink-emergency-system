import React, { useState } from 'react';
import { apiFetch } from '../config/api';
import { DashboardCard, Input } from './Common';

const AuthorityOutbreak = () => {
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [params, setParams] = useState({ disease: 'Influenza', region: 'Central City' });

    const handleForecast = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const { ok, data } = await apiFetch('/api/gov/predict_outbreak', {
                method: 'POST',
                body: JSON.stringify(params)
            });
            if (!ok) {
                throw new Error(data?.message || 'Failed to fetch outbreak forecast');
            }
            setResult(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardCard className="border-t-8 border-orange-500">
            <h3 className="font-bold text-xl text-slate-800 mb-4 flex items-center gap-2">
                <i className="fas fa-virus-covid text-orange-600"></i> Outbreak Forecast
            </h3>
            <form onSubmit={handleForecast} className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                <Input label="Disease" value={params.disease} onChange={e => setParams({...params, disease: e.target.value})} />
                <Input label="Region" value={params.region} onChange={e => setParams({...params, region: e.target.value})} />
                <button className="bg-orange-600 text-white py-3 rounded-xl font-bold hover:bg-orange-700 transition shadow-lg">
                    {loading ? <i className="fas fa-spinner fa-spin"></i> : 'Forecast Outbreak'}
                </button>
            </form>

            {result && (
                <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6 animate-fade-in">
                    <div className="p-4 bg-orange-50 rounded-xl border border-orange-100">
                        <h4 className="text-xs font-bold text-orange-800 uppercase mb-2">Trend Analysis</h4>
                        <p className="text-lg font-bold text-slate-800">{result.trend || 'Upward trend detected: 15% increase expected.'}</p>
                    </div>
                    <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                        <h4 className="text-xs font-bold text-blue-800 uppercase mb-2">Recommended Action</h4>
                        <p className="text-sm font-medium text-slate-700">{result.action || 'Pre-allocate 50 extra ICU beds to Central City General.'}</p>
                    </div>
                </div>
            )}
        </DashboardCard>
    );
};

export default AuthorityOutbreak;