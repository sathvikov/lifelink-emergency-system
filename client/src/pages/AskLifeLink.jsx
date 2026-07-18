import React, { useEffect, useState } from 'react';
import DashboardLayout from '../layout/DashboardLayout';
import { DashboardCard } from '../components/Common';
import { apiFetch } from '../config/api';

const AskLifeLink = () => {
    const [query, setQuery] = useState('');
    const [answer, setAnswer] = useState('');
    const [context, setContext] = useState([]);
    const [loading, setLoading] = useState(false);
    const [location, setLocation] = useState(null);

    useEffect(() => {
        if (typeof navigator === 'undefined' || !navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
            (pos) => setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
            () => setLocation(null),
            { enableHighAccuracy: true }
        );
    }, []);

    const handleAsk = async (e) => {
        e.preventDefault();
        if (!query.trim()) return;
        setLoading(true);
        setAnswer('');
        setContext([]);
        const trimmed = query.trim();
        const cacheKey = `lifelink:ask-cache:${trimmed.toLowerCase()}`;

        try {
            if (typeof navigator !== 'undefined' && navigator.onLine === false) {
                const cached = localStorage.getItem(cacheKey);
                if (cached) {
                    const parsed = JSON.parse(cached);
                    setAnswer(parsed.answer || 'Offline response cached.');
                    setContext(parsed.context || []);
                } else {
                    setAnswer('Offline mode: reconnect to access LifeLink AI.');
                }
                return;
            }

            const normalized = trimmed.toLowerCase();
            const wantsNearestHospital = normalized.includes('hospital')
                && (normalized.includes('nearest') || normalized.includes('nearby'));
            if (wantsNearestHospital && location) {
                const res = await apiFetch(
                    `/v2/hospital/nearby?lat=${location.lat}&lng=${location.lng}&limit=5&radius_km=50&include_eta=true`,
                    { method: 'GET', timeoutMs: 15000 }
                );
                const hospitals = res.ok ? (res.data?.hospitals || []) : [];
                const answerText = hospitals.length
                    ? `Nearest hospitals near you:\n${hospitals.map((item, index) => (
                        `${index + 1}. ${item.name} — ${item.distance_km} km, beds ${item.beds_available}/${item.beds_total}, ETA ${Math.round((item.eta_seconds || 0) / 60)} min`
                    )).join('\n')}`
                    : 'No hospitals found nearby. Try enabling location or expanding your search.';
                setAnswer(answerText);
                setContext([]);
                localStorage.setItem(cacheKey, JSON.stringify({ answer: answerText, context: [] }));
                return;
            }

            const res = await apiFetch('/v2/agents/ask', {
                method: 'POST',
                body: JSON.stringify({
                    query: trimmed,
                    ...(location ? { latitude: location.lat, longitude: location.lng } : {})
                }),
                timeoutMs: 35000,
            });
            if (!res.ok) throw new Error(res.data?.detail || 'Unable to answer');
            const answerText = res.data?.answer || 'No response';
            setAnswer(answerText);
            setContext(res.data?.contextUsed || []);
            localStorage.setItem(cacheKey, JSON.stringify({ answer: answerText, context: res.data?.contextUsed || [] }));
        } catch (err) {
            const message = err?.name === 'AbortError' || /aborted/i.test(err?.message || '')
                ? 'LifeLink AI timed out. Try again with a shorter question.'
                : (err.message || 'Ask LifeLink failed');
            setAnswer(message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <DashboardLayout title="Ask LifeLink">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <DashboardCard className="lg:col-span-2">
                    <h2 className="text-2xl font-bold text-gray-900 mb-4">Ask LifeLink AI</h2>
                    <p className="text-sm text-gray-600 mb-6">Query operational intelligence, patient risk insights, and hospital readiness in natural language.</p>
                    <form onSubmit={handleAsk} className="space-y-4">
                        <textarea
                            className="w-full h-28 p-4 bg-white/80 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500"
                            placeholder="Example: Find nearest ICU bed with availability above 5"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-gradient-to-r from-sky-600 to-indigo-600 text-white font-semibold py-3 rounded-xl shadow-lg hover:shadow-xl transition"
                        >
                            {loading ? 'Consulting agents...' : 'Ask LifeLink'}
                        </button>
                    </form>
                    {answer && (
                        <div className="mt-6 p-4 rounded-xl bg-white/90 border border-slate-200">
                            <p className="text-xs font-bold text-slate-500 uppercase">Answer</p>
                            <p className="mt-2 text-gray-800 whitespace-pre-line">{answer}</p>
                        </div>
                    )}
                </DashboardCard>

                <DashboardCard>
                    <h3 className="text-lg font-bold text-gray-900 mb-3">Context Used</h3>
                    {context.length === 0 && (
                        <p className="text-sm text-gray-500">No contextual documents returned.</p>
                    )}
                    <div className="space-y-3">
                        {context.map((item, idx) => (
                            <div key={idx} className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                                <p className="text-xs text-gray-500">Score: {item.score?.toFixed?.(3) ?? 'n/a'}</p>
                                <p className="text-sm text-gray-800 mt-1 line-clamp-4">{item.content}</p>
                            </div>
                        ))}
                    </div>
                </DashboardCard>
            </div>
        </DashboardLayout>
    );
};

export default AskLifeLink;
