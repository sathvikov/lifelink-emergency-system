import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { useAuth } from '../context/AuthContext';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { apiFetch } from '../config/api';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const buildQuery = (params) => {
    const searchParams = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') return;
        searchParams.append(key, String(value));
    });
    const query = searchParams.toString();
    return query ? `?${query}` : '';
};

// --- 2. HELPER: PORTAL COMPONENT ---
// This moves the modal outside the dashboard layout so it sits on top of the navbar
const ModalPortal = ({ children }) => {
    return ReactDOM.createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/70 backdrop-blur-sm animate-fade-in"></div>
            <div className="relative z-10 w-full max-w-4xl max-h-[90vh] overflow-y-auto custom-scrollbar rounded-2xl shadow-2xl">
                {children}
            </div>
        </div>,
        document.body
    );
};

const HospitalPatients = () => {
    const { user } = useAuth();
    
    // State
    const [patients, setPatients] = useState([]);
    const [intakeQueue, setIntakeQueue] = useState([]);
    const [loading, setLoading] = useState(false);
    const [intakeSearch, setIntakeSearch] = useState('');
    const [intakeSortBy, setIntakeSortBy] = useState('createdAt');
    const [intakeSortDir, setIntakeSortDir] = useState('desc');
    
    // UI States
    const [selectedPatient, setSelectedPatient] = useState(null);
    const [isAdmitOpen, setIsAdmitOpen] = useState(false);
    
    // AI States
    const [aiRecovery, setAiRecovery] = useState(null);
    const [aiStay, setAiStay] = useState(null);
    const [loadingAI, setLoadingAI] = useState(false);
    const [triageResults, setTriageResults] = useState({});
    const [triageLoading, setTriageLoading] = useState({});

    // Form State
    const [newPatient, setNewPatient] = useState({
        name: '', age: '', gender: 'Male', dept: 'General', room: '', condition: '', severity: 'Stable', oxygen: '98', heartRate: '80', bp: '120/80', symptoms: ''
    });

    // 1. Fetch Patients
    useEffect(() => {
        const fetchRealPatients = async () => {
            if (!user?.id) return;
            try {
                const intakeQuery = buildQuery({
                    hospitalId: user.id,
                    search: intakeSearch,
                    sort_by: intakeSortBy,
                    sort_dir: intakeSortDir
                });
                const [patientsRes, intakeRes] = await Promise.all([
                    apiFetch(`/api/dashboard/hospital/patients/${user.id}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/emergency/intake${intakeQuery}`, { method: 'GET' })
                ]);
                setPatients(Array.isArray(patientsRes.data) ? patientsRes.data : []);
                setIntakeQueue(intakeRes.ok ? (intakeRes.data?.data || []) : []);
            } catch (err) { console.error("Fetch Error:", err); }
        };
        fetchRealPatients();
    }, [user?.id, intakeSearch, intakeSortBy, intakeSortDir]);

    // 2. Chart Helpers
    const getDeptData = () => {
        const counts = {};
        patients.forEach(p => { counts[p.dept] = (counts[p.dept] || 0) + 1; });
        return Object.keys(counts).map(key => ({ name: key, value: counts[key] }));
    };

    const getAgeData = () => {
        const groups = { '0-18': 0, '19-40': 0, '41-60': 0, '60+': 0 };
        patients.forEach(p => {
            if (p.age <= 18) groups['0-18']++;
            else if (p.age <= 40) groups['19-40']++;
            else if (p.age <= 60) groups['41-60']++;
            else groups['60+']++;
        });
        return Object.keys(groups).map(key => ({ name: key, count: groups[key] }));
    };

    // 3. Admit Submit
    const handleAdmitSubmit = async (e) => {
        e.preventDefault();
        try {
            const res = await apiFetch('/api/hospital-ops/emergency/intake', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId: user.id,
                    name: newPatient.name,
                    age: Number(newPatient.age),
                    gender: newPatient.gender,
                    symptoms: newPatient.symptoms || newPatient.condition,
                    severity: newPatient.severity,
                    department: newPatient.dept,
                    contact: ''
                })
            });
            if (res.ok) {
                setIntakeQueue((prev) => [res.data, ...prev]);
                setIsAdmitOpen(false);
                setNewPatient({ name: '', age: '', gender: 'Male', dept: 'General', room: '', condition: '', severity: 'Stable', oxygen: '98', heartRate: '80', bp: '120/80', symptoms: '' });
            }
        } catch (err) { alert("Failed to admit patient"); }
    };

    const handleIntakeUpdate = async (id, status) => {
        setIntakeQueue((prev) => {
            const next = prev.map((item) => (item._id || item.id) === id ? { ...item, status } : item);
            if (status === 'Admitted') {
                const moved = prev.find((item) => (item._id || item.id) === id);
                if (moved) {
                    setPatients((pPrev) => [moved, ...pPrev]);
                }
            }
            return next;
        });
        await apiFetch(`/api/hospital-ops/emergency/intake/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
    };

    const runTriage = async (patient) => {
        const pid = patient._id || patient.id;
        if (!pid) return;
        setTriageLoading((prev) => ({ ...prev, [pid]: true }));
        try {
            const res = await apiFetch('/api/hospital/triage', {
                method: 'POST',
                body: JSON.stringify({
                    symptoms: patient.symptoms || patient.condition || 'Emergency',
                    severity_hint: patient.severity
                })
            });
            if (res.ok) {
                setTriageResults((prev) => ({ ...prev, [pid]: res.data }));
            }
        } finally {
            setTriageLoading((prev) => ({ ...prev, [pid]: false }));
        }
    };

    // 4. View & AI
    // Inside HospitalPatients.jsx -> handleViewPatient
const handleViewPatient = async (patient) => {
    setSelectedPatient(patient);
    setLoadingAI(true);

    try {
        const payload = {
            age: patient.age,
            bmi: 24,
            heart_rate: patient.heartRate || 75,
            blood_pressure: 120,
            diagnosis: patient.condition || 'General',
            treatment_type: 'Standard'
        };
        const [recRes, stayRes] = await Promise.all([
            apiFetch('/api/hospital/patient/recovery', {
                method: 'POST',
                body: JSON.stringify(payload)
            }),
            apiFetch('/api/hospital/patient/stay', {
                method: 'POST',
                body: JSON.stringify(payload)
            })
        ]);

        setAiRecovery(recRes.ok ? recRes.data : { error: recRes.data?.error || 'Recovery prediction failed' });
        setAiStay(stayRes.ok ? stayRes.data : { error: stayRes.data?.error || 'Stay prediction failed' });
    } catch (err) {
        console.error("AI Insight Error", err);
        setAiRecovery({ error: `Failed to get recovery prediction: ${err.message}` });
        setAiStay({ error: `Failed to get stay prediction: ${err.message}` });
    } finally {
        setLoadingAI(false);
    }
};

    return (
        <div className="space-y-6 animate-fade-in pb-10">
            
            {/* CHARTS */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="font-bold text-lg text-slate-800 mb-4">Patients by Department</h3>
                    <div className="h-64">
                        <ResponsiveContainer>
                            <PieChart>
                                <Pie data={getDeptData()} cx="50%" cy="50%" outerRadius={80} dataKey="value" label>
                                    {getDeptData().map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                                </Pie>
                                <Tooltip />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="font-bold text-lg text-slate-800 mb-4">Age Demographics</h3>
                    <div className="h-64">
                        <ResponsiveContainer>
                            <BarChart data={getAgeData()}>
                                <XAxis dataKey="name" />
                                <YAxis allowDecimals={false} />
                                <Tooltip cursor={{fill: 'transparent'}} />
                                <Bar dataKey="count" fill="#8884d8" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                    <div>
                        <h3 className="font-bold text-xl text-slate-800">Emergency Intake Queue</h3>
                        <p className="text-xs text-gray-500">{intakeQueue.length} patients awaiting triage</p>
                    </div>
                </div>
                <div className="px-6 pb-4">
                    <div className="flex flex-col md:flex-row gap-2">
                        <input
                            className="p-2 border rounded w-full"
                            placeholder="Search intake"
                            value={intakeSearch}
                            onChange={(e) => setIntakeSearch(e.target.value)}
                        />
                        <select
                            className="p-2 border rounded"
                            value={intakeSortBy}
                            onChange={(e) => setIntakeSortBy(e.target.value)}
                        >
                            <option value="createdAt">Newest</option>
                            <option value="severity">Severity</option>
                            <option value="status">Status</option>
                            <option value="dept">Department</option>
                        </select>
                        <select
                            className="p-2 border rounded"
                            value={intakeSortDir}
                            onChange={(e) => setIntakeSortDir(e.target.value)}
                        >
                            <option value="desc">Desc</option>
                            <option value="asc">Asc</option>
                        </select>
                    </div>
                </div>
                <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
                    <table className="min-w-full text-left text-sm">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="px-6 py-4 font-bold text-slate-600">Patient</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Symptoms</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Severity</th>
                                <th className="px-6 py-4 font-bold text-slate-600">AI Band</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Status</th>
                                <th className="px-6 py-4 text-right font-bold text-slate-600">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {intakeQueue.length === 0 ? (
                                <tr><td className="px-6 py-4 text-gray-500" colSpan={6}>No intake cases</td></tr>
                            ) : (
                                intakeQueue.map((p) => (
                                    <tr key={p._id || p.id}>
                                        <td className="px-6 py-4 font-semibold text-slate-800">{p.name}</td>
                                        <td className="px-6 py-4 text-slate-600">{p.condition || p.symptoms}</td>
                                        <td className="px-6 py-4">
                                            <span className={`px-2 py-1 rounded text-xs font-bold ${p.severity === 'Critical' ? 'bg-red-100 text-red-700' : p.severity === 'High' ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700'}`}>
                                                {p.severity || 'Medium'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-slate-600">
                                            {triageResults[p._id || p.id]?.predicted_severity ? (
                                                <span className="text-xs font-semibold text-indigo-600">{triageResults[p._id || p.id].predicted_severity}</span>
                                            ) : (
                                                <button
                                                    className="text-xs text-indigo-600"
                                                    onClick={() => runTriage(p)}
                                                    disabled={triageLoading[p._id || p.id]}
                                                >
                                                    {triageLoading[p._id || p.id] ? 'Analyzing...' : 'Run AI triage'}
                                                </button>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-slate-600">{p.status || 'Intake'}</td>
                                        <td className="px-6 py-4 text-right">
                                            <button className="text-indigo-600 text-xs font-bold" onClick={() => handleIntakeUpdate(p._id || p.id, 'Admitted')}>Admit</button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* LIST */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                    <div>
                        <h3 className="font-bold text-xl text-slate-800">Admitted Patients Directory</h3>
                        <p className="text-xs text-gray-500">Managing {patients.length} active records</p>
                    </div>
                    <button 
                        onClick={() => setIsAdmitOpen(true)}
                        className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700 shadow flex items-center gap-2"
                    >
                        <i className="fas fa-plus"></i> Admit New Patient
                    </button>
                </div>
                
                <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
                    <table className="min-w-full text-left text-sm">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="px-6 py-4 font-bold text-slate-600">Name / Age</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Department</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Room</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Condition</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Status</th>
                                <th className="px-6 py-4 text-right font-bold text-slate-600">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {patients.map((p, idx) => (
                                <tr key={p._id || idx} className="hover:bg-blue-50/50 transition">
                                    <td className="px-6 py-4">
                                        <p className="font-bold text-slate-800">{p.name}</p>
                                        <p className="text-xs text-slate-500">{p.age} yrs • {p.gender}</p>
                                    </td>
                                    <td className="px-6 py-4 text-slate-700">{p.dept}</td>
                                    <td className="px-6 py-4"><span className="bg-slate-100 px-2 py-1 rounded text-xs font-bold">{p.room}</span></td>
                                    <td className="px-6 py-4 text-slate-700">{p.condition}</td>
                                    <td className="px-6 py-4">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                                            p.severity === 'Critical' ? 'bg-red-100 text-red-700' : 
                                            p.severity === 'High' ? 'bg-orange-100 text-orange-700' : 
                                            'bg-green-100 text-green-700'
                                        }`}>
                                            {p.severity}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <button onClick={() => handleViewPatient(p)} className="text-indigo-600 font-bold hover:underline">View AI Insights</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* ADMIT MODAL (USING PORTAL) */}
            {isAdmitOpen && (
                <ModalPortal>
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden border-t-4 border-blue-600 animate-zoom-in">
                        <div className="bg-slate-50 p-4 flex justify-between items-center border-b">
                            <h3 className="font-bold text-lg text-slate-800">Admit New Patient</h3>
                            <button onClick={() => setIsAdmitOpen(false)} className="text-gray-400 hover:text-red-500"><i className="fas fa-times text-xl"></i></button>
                        </div>
                        <form onSubmit={handleAdmitSubmit} className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Full Name</label><input required className="w-full p-2 border rounded" value={newPatient.name} onChange={e=>setNewPatient({...newPatient, name: e.target.value})} /></div>
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Age</label><input required type="number" className="w-full p-2 border rounded" value={newPatient.age} onChange={e=>setNewPatient({...newPatient, age: e.target.value})} /></div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Gender</label><select className="w-full p-2 border rounded bg-white" value={newPatient.gender} onChange={e=>setNewPatient({...newPatient, gender: e.target.value})}><option>Male</option><option>Female</option></select></div>
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Department</label><select className="w-full p-2 border rounded bg-white" value={newPatient.dept} onChange={e=>setNewPatient({...newPatient, dept: e.target.value})}><option>General</option><option>Cardiology</option><option>Neurology</option><option>Trauma</option><option>ICU</option></select></div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Room No</label><input required className="w-full p-2 border rounded" value={newPatient.room} onChange={e=>setNewPatient({...newPatient, room: e.target.value})} /></div>
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Severity</label><select className="w-full p-2 border rounded bg-white" value={newPatient.severity} onChange={e=>setNewPatient({...newPatient, severity: e.target.value})}><option>Stable</option><option>Moderate</option><option>High</option><option>Critical</option></select></div>
                            </div>
                            <div><label className="text-xs font-bold text-gray-500 uppercase">Symptoms</label><input className="w-full p-2 border rounded" placeholder="e.g. Chest pain, dizziness" value={newPatient.symptoms} onChange={e=>setNewPatient({...newPatient, symptoms: e.target.value})} /></div>
                            <div><label className="text-xs font-bold text-gray-500 uppercase">Medical Condition</label><input required className="w-full p-2 border rounded" placeholder="e.g. Cardiac Arrest" value={newPatient.condition} onChange={e=>setNewPatient({...newPatient, condition: e.target.value})} /></div>
                            
                            <div className="grid grid-cols-3 gap-4 bg-slate-50 p-3 rounded border">
                                <div><label className="text-xs font-bold text-gray-500">Oxygen %</label><input type="number" className="w-full p-1 border rounded bg-white" value={newPatient.oxygen} onChange={e=>setNewPatient({...newPatient, oxygen: e.target.value})} /></div>
                                <div><label className="text-xs font-bold text-gray-500">Heart Rate</label><input type="number" className="w-full p-1 border rounded bg-white" value={newPatient.heartRate} onChange={e=>setNewPatient({...newPatient, heartRate: e.target.value})} /></div>
                                <div><label className="text-xs font-bold text-gray-500">BP</label><input className="w-full p-1 border rounded bg-white" value={newPatient.bp} onChange={e=>setNewPatient({...newPatient, bp: e.target.value})} /></div>
                            </div>

                            <button className="w-full bg-blue-600 text-white py-3 rounded font-bold hover:bg-blue-700 shadow-lg">Confirm Admission</button>
                        </form>
                    </div>
                </ModalPortal>
            )}

            {/* VIEW DETAILS MODAL (USING PORTAL) */}
            {selectedPatient && (
                <ModalPortal>
                    <div className="bg-white rounded-2xl w-full overflow-hidden border-t-8 border-indigo-600 animate-zoom-in">
                        <div className="bg-slate-900 text-white p-6 flex justify-between items-start">
                            <div className="flex gap-4 items-center">
                                <div className="w-16 h-16 bg-blue-500 rounded-full flex items-center justify-center text-2xl font-bold">{selectedPatient.name.charAt(0)}</div>
                                <div><h2 className="text-2xl font-bold">{selectedPatient.name}</h2><p className="text-slate-300 text-sm">{selectedPatient.gender}, {selectedPatient.age} yrs • Admitted: {selectedPatient.admitDate ? new Date(selectedPatient.admitDate).toLocaleDateString() : 'Just Now'}</p></div>
                            </div>
                            <button onClick={() => setSelectedPatient(null)} className="text-white/70 hover:text-white"><i className="fas fa-times text-2xl"></i></button>
                        </div>
                        <div className="p-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
                             <div className="lg:col-span-1 space-y-6">
                                <div><h4 className="text-xs font-bold text-slate-500 uppercase mb-2">Vitals</h4><div className="grid grid-cols-2 gap-3"><div className="p-3 bg-slate-50 rounded border text-center"><p className="text-xs text-slate-400">Oxygen</p><p className="text-xl font-bold text-blue-600">{selectedPatient.oxygen}%</p></div><div className="p-3 bg-slate-50 rounded border text-center"><p className="text-xs text-slate-400">HR</p><p className="text-xl font-bold text-red-500">{selectedPatient.heartRate} bpm</p></div></div></div>
                                <div><h4 className="text-xs font-bold text-slate-500 uppercase mb-2">Info</h4><ul className="text-sm space-y-2 text-slate-700"><li className="flex justify-between border-b pb-1"><span>Room:</span> <b>{selectedPatient.room}</b></li><li className="flex justify-between border-b pb-1"><span>Condition:</span> <b>{selectedPatient.condition}</b></li><li className="flex justify-between border-b pb-1"><span>Dept:</span> <b>{selectedPatient.dept}</b></li></ul></div>
                             </div>
<div className="lg:col-span-2 space-y-6">
    <h3 className="font-bold text-xl text-indigo-700 flex items-center gap-2">
        <i className="fas fa-robot"></i> AI Recovery Analytics
    </h3>
    
    {loadingAI ? (
        <div className="p-10 text-center">
            <i className="fas fa-dna fa-spin text-3xl text-indigo-500 mb-3"></i>
            <p className="font-bold text-slate-600">Analyzing Medical Data...</p>
        </div>
    ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 1. Recovery Probability */}
            <div className="bg-gradient-to-br from-green-50 to-emerald-100 p-5 rounded-xl border border-green-200">
                <p className="text-xs font-bold text-green-800 uppercase mb-1">Recovery Probability</p>
                {aiRecovery?.error ? (
                    <div className="text-sm text-red-600 font-semibold">
                        <i className="fas fa-exclamation-circle mr-2"></i>{aiRecovery.error}
                    </div>
                ) : (
                    <>
                        <h2 className="text-4xl font-extrabold text-green-700 mb-2">
                            {aiRecovery?.recovery_probability !== undefined ? `${(aiRecovery.recovery_probability * 100).toFixed(1)}%` : '--'}
                        </h2>
                        <p className="text-sm font-bold text-green-900">
                            {aiRecovery?.recovery_probability !== undefined 
                                ? (aiRecovery.recovery_probability > 0.7 ? 'High probability of recovery' : aiRecovery.recovery_probability > 0.4 ? 'Moderate probability' : 'Low probability')
                                : 'Analyzing...'}
                        </p>
                    </>
                )}
            </div>

            {/* 2. Est. Stay Duration */}
            <div className="bg-gradient-to-br from-blue-50 to-indigo-100 p-5 rounded-xl border border-blue-200">
                <p className="text-xs font-bold text-blue-800 uppercase mb-1">Est. Stay Duration</p>
                {aiStay?.error ? (
                    <div className="text-sm text-red-600 font-semibold">
                        <i className="fas fa-exclamation-circle mr-2"></i>{aiStay.error}
                    </div>
                ) : (
                    <>
                        <h2 className="text-4xl font-extrabold text-blue-700 mb-2">
                            {aiStay?.predicted_stay_days !== undefined ? aiStay.predicted_stay_days : '--'} 
                            <span className="text-lg ml-1">Days</span>
                        </h2>
                        <p className="text-xs text-blue-800 italic">
                            {aiStay?.predicted_stay_days !== undefined 
                                ? `Expected discharge in approximately ${aiStay.predicted_stay_days} days`
                                : 'Calculating...'}
                        </p>
                    </>
                )}
            </div>
        </div>
    )}
</div>
                        </div>
                    </div>
                </ModalPortal>
            )}
        </div>
    );
};

export default HospitalPatients;