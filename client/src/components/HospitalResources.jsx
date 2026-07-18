import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { useAuth } from '../context/AuthContext';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts';
import { apiFetch } from '../config/api';
const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#6366f1', '#14b8a6'];

const buildQuery = (params) => {
    const searchParams = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') return;
        searchParams.append(key, String(value));
    });
    const query = searchParams.toString();
    return query ? `?${query}` : '';
};

// --- HELPER: MODAL PORTAL COMPONENT ---
// This forces the modal to render attached to document.body, bypassing all z-index issues
const ModalPortal = ({ children }) => {
    return ReactDOM.createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            {/* Backdrop with Blur */}
            <div className="absolute inset-0 bg-slate-900/70 backdrop-blur-sm animate-fade-in"></div>
            {/* Modal Content */}
            <div className="relative z-10 w-full max-w-md">
                {children}
            </div>
        </div>,
        document.body
    );
};

const HospitalResources = () => {
    const { user } = useAuth();
    const hospitalId = user?._id || user?.id;
    
    // Data States
    const [resources, setResources] = useState([]);
    const [equipment, setEquipment] = useState([]);
    const [equipmentRows, setEquipmentRows] = useState([]);
    const [equipmentSearch, setEquipmentSearch] = useState('');
    const [equipmentSortBy, setEquipmentSortBy] = useState('createdAt');
    const [equipmentSortDir, setEquipmentSortDir] = useState('desc');
    const [beds, setBeds] = useState(null);
    const [staff, setStaff] = useState({ available: 0, total: 0 });
    const [vendorLeadTimes, setVendorLeadTimes] = useState([]);
    const [supplyRisk, setSupplyRisk] = useState([]);
    
    // UI States
    const [isAddOpen, setIsAddOpen] = useState(false);
    
    // AI Modal States
    const [isAiModalOpen, setIsAiModalOpen] = useState(false); 
    const [aiLoading, setAiLoading] = useState(false);         
    const [aiResult, setAiResult] = useState(null);            
    const [aiError, setAiError] = useState(null);              
    const [selectedItemName, setSelectedItemName] = useState('');

    // Form State
    const [newItem, setNewItem] = useState({
        name: '', category: 'Medicine', quantity: '', unit: 'units', minThreshold: '10'
    });
    const [newEquipment, setNewEquipment] = useState({
        name: '', category: 'Equipment', quantity: '', minThreshold: '1'
    });
    const [vendorForm, setVendorForm] = useState({
        resourceName: '',
        category: 'Supply',
        vendorName: '',
        leadTimeDays: ''
    });

    // 1. Fetch Resources
    useEffect(() => {
        const fetchResources = async () => {
            if (!hospitalId) return;
            try {
                const equipmentQuery = buildQuery({
                    hospitalId,
                    search: equipmentSearch,
                    sort_by: equipmentSortBy,
                    sort_dir: equipmentSortDir
                });
                const [res, equipmentRes] = await Promise.all([
                    apiFetch(`/api/hospital-ops/ceo/resources?hospitalId=${hospitalId}`, { method: 'GET' }),
                    apiFetch(`/api/hospital-ops/equipment${equipmentQuery}`, { method: 'GET' })
                ]);
                if (res.ok) {
                    setResources(res.data?.inventory || []);
                    setEquipment(res.data?.equipment || []);
                    setBeds(res.data?.beds || null);
                    setStaff(res.data?.staff || { available: 0, total: 0 });
                    setVendorLeadTimes(res.data?.vendorLeadTimes || []);
                    setSupplyRisk(res.data?.supplyRisk || []);
                }
                const equipmentItems = equipmentRes.ok ? (equipmentRes.data?.data || []) : (res.data?.equipment || []);
                setEquipmentRows(equipmentItems);
            } catch (err) { console.error("Resource fetch error:", err); }
        };
        fetchResources();
    }, [hospitalId, equipmentSearch, equipmentSortBy, equipmentSortDir]);

    // 2. Chart Helpers
    const getCategoryData = () => {
        const data = {};
        const addItem = (item, fallbackCategory) => {
            if (!item) return;
            const category = (item.category || fallbackCategory || 'Uncategorized').toString().trim() || 'Uncategorized';
            const amount = Number(item.quantity || 0);
            data[category] = (data[category] || 0) + amount;
        };
        resources.forEach((item) => addItem(item));
        equipment.forEach((item) => addItem(item, 'Equipment'));
        return Object.keys(data).map((key) => ({ name: key, count: data[key] }));
    };

    const getLowStockData = () => {
        const lowResources = resources
            .filter((item) => Number(item.quantity) <= Number(item.minThreshold ?? 0))
            .map((item) => ({ name: item.name, quantity: Number(item.quantity), threshold: Number(item.minThreshold ?? 0) }));
        const lowEquipment = equipment
            .filter((item) => Number(item.quantity) <= Number(item.minThreshold ?? 1))
            .map((item) => ({ name: item.name, quantity: Number(item.quantity), threshold: Number(item.minThreshold ?? 1) }));
        return [...lowResources, ...lowEquipment];
    };

    // 3. Add Item Handler
    const handleAddSubmit = async (e) => {
        e.preventDefault();
        try {
            const res = await apiFetch('/api/dashboard/hospital/resource/add', {
                method: 'POST',
                body: JSON.stringify({ ...newItem, hospitalId })
            });
            if (res.ok) {
                setResources([res.data, ...resources]);
                setIsAddOpen(false);
                setNewItem({ name: '', category: 'Medicine', quantity: '', unit: 'units', minThreshold: '10' });
            }
        } catch (err) { alert("Failed to add resource"); }
    };

    const handleAddEquipment = async (e) => {
        e.preventDefault();
        if (!hospitalId || !newEquipment.name) return;
        try {
            const res = await apiFetch('/api/hospital-ops/equipment', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    name: newEquipment.name,
                    category: newEquipment.category,
                    quantity: Number(newEquipment.quantity),
                    minThreshold: Number(newEquipment.minThreshold)
                })
            });
            if (res.ok) {
                setEquipment((prev) => [res.data, ...prev]);
                setEquipmentRows((prev) => [res.data, ...prev]);
                setNewEquipment({ name: '', category: 'Equipment', quantity: '', minThreshold: '1' });
            }
        } catch (err) { alert('Failed to add equipment'); }
    };

    // 4. AI Analysis Handler
    const runAIAnalysis = async (e, item) => {
        e.preventDefault();
        e.stopPropagation();

        setIsAiModalOpen(true);
        setAiLoading(true);
        setAiError(null);
        setAiResult(null);
        setSelectedItemName(item.name);

        try {
            const res = await apiFetch('/api/hospital/inventory', {
                method: 'POST',
                body: JSON.stringify({
                    name: item.name,
                    quantity: Number(item.quantity),
                    category: item.category,
                    minThreshold: Number(item.minThreshold)
                })
            });
            if (!res.ok) {
                setAiError("AI Service Unavailable. Please ensure the Python backend is running.");
                setAiLoading(false);
                return;
            }
            setAiResult(res.data);
            setAiLoading(false);
        } catch (err) {
            console.error(err);
            setAiError("Connection Error. AI Service Unreachable.");
            setAiLoading(false);
        }
    };

    const closeAiModal = () => {
        setIsAiModalOpen(false);
        setAiResult(null);
        setAiError(null);
    };

    const handleAddVendorLead = async (e) => {
        e.preventDefault();
        if (!hospitalId || !vendorForm.resourceName || !vendorForm.leadTimeDays) return;
        try {
            const res = await apiFetch('/api/hospital-ops/ceo/resources/vendors', {
                method: 'POST',
                body: JSON.stringify({
                    hospitalId,
                    resourceName: vendorForm.resourceName,
                    category: vendorForm.category,
                    vendorName: vendorForm.vendorName,
                    leadTimeDays: Number(vendorForm.leadTimeDays)
                })
            });
            if (res.ok) {
                setVendorLeadTimes((prev) => [res.data, ...prev]);
                setVendorForm({ resourceName: '', category: 'Supply', vendorName: '', leadTimeDays: '' });
            }
        } catch (err) { alert('Failed to add vendor lead time'); }
    };

    return (
        <div className="space-y-6 animate-fade-in pb-10">
            
            {/* CHARTS */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="font-bold text-lg text-slate-800 mb-4">Inventory Overview (Log Scale)</h3>
                    <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={getCategoryData()}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="name" style={{fontSize: '12px', fontWeight:'bold'}} />
                                <YAxis scale="sqrt" style={{fontSize: '12px'}} /> 
                                <Tooltip cursor={{fill: '#f1f5f9'}} />
                                <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={50} name="Total Units">
                                    {getCategoryData().map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2 text-red-600">
                            <i className="fas fa-exclamation-triangle"></i> Critical Stock Levels
                        </h3>
                        <span className="text-xs bg-red-50 text-red-600 px-2 py-1 rounded font-bold">{getLowStockData().length} Items Low</span>
                    </div>
                    <div className="h-72 overflow-y-auto custom-scrollbar">
                        {getLowStockData().length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-green-500 opacity-60">
                                <i className="fas fa-check-circle text-5xl mb-3"></i>
                                <span className="font-bold">Inventory Healthy</span>
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height={Math.max(300, getLowStockData().length * 60)}>
                                <BarChart data={getLowStockData()} layout="vertical">
                                    <XAxis type="number" hide />
                                    <YAxis dataKey="name" type="category" width={110} style={{fontSize: '11px', fontWeight: 'bold'}} />
                                    <Tooltip />
                                    <Bar dataKey="quantity" fill="#ef4444" barSize={20} radius={[0, 4, 4, 0]} label={{ position: 'right', fill: '#ef4444', fontSize: 12 }} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>

            {beds && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-white p-4 rounded-xl shadow-sm border">
                        <p className="text-xs text-gray-500">ICU Beds</p>
                        <p className="text-2xl font-bold text-gray-900">{beds.icu?.occupied || 0}/{beds.icu?.total || 0}</p>
                    </div>
                    <div className="bg-white p-4 rounded-xl shadow-sm border">
                        <p className="text-xs text-gray-500">Emergency Beds</p>
                        <p className="text-2xl font-bold text-gray-900">{beds.emergency?.occupied || 0}/{beds.emergency?.total || 0}</p>
                    </div>
                    <div className="bg-white p-4 rounded-xl shadow-sm border">
                        <p className="text-xs text-gray-500">General Beds</p>
                        <p className="text-2xl font-bold text-gray-900">{beds.general?.occupied || 0}/{beds.general?.total || 0}</p>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="font-bold text-lg text-slate-800 mb-4">Vendor Lead Times</h3>
                    <form className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4" onSubmit={handleAddVendorLead}>
                        <input
                            className="p-2 border rounded"
                            placeholder="Resource"
                            value={vendorForm.resourceName}
                            onChange={(e) => setVendorForm({ ...vendorForm, resourceName: e.target.value })}
                        />
                        <input
                            className="p-2 border rounded"
                            placeholder="Category"
                            value={vendorForm.category}
                            onChange={(e) => setVendorForm({ ...vendorForm, category: e.target.value })}
                        />
                        <input
                            className="p-2 border rounded"
                            placeholder="Vendor"
                            value={vendorForm.vendorName}
                            onChange={(e) => setVendorForm({ ...vendorForm, vendorName: e.target.value })}
                        />
                        <div className="flex gap-2">
                            <input
                                className="p-2 border rounded w-full"
                                type="number"
                                placeholder="Lead days"
                                value={vendorForm.leadTimeDays}
                                onChange={(e) => setVendorForm({ ...vendorForm, leadTimeDays: e.target.value })}
                            />
                            <button className="bg-slate-900 text-white rounded px-3" type="submit">Add</button>
                        </div>
                    </form>
                    {vendorLeadTimes.length === 0 ? (
                        <div className="text-sm text-gray-500">No vendor lead times added yet.</div>
                    ) : (
                        <div className="space-y-2 max-h-[240px] overflow-y-auto pr-2">
                            {vendorLeadTimes.slice(0, 6).map((item) => (
                                <div key={item._id || item.id} className="flex items-center justify-between text-sm border rounded px-3 py-2">
                                    <span className="text-gray-600">{item.resourceName}</span>
                                    <span className="font-semibold text-gray-900">{item.leadTimeDays} days</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 className="font-bold text-lg text-slate-800 mb-4">Supply Risk Watch</h3>
                    {supplyRisk.length === 0 ? (
                        <div className="text-sm text-gray-500">No high-risk supplies right now.</div>
                    ) : (
                        <div className="space-y-2 max-h-[240px] overflow-y-auto pr-2">
                            {supplyRisk.map((item) => (
                                <div key={`${item.resource}-${item.leadTimeDays}`} className="text-sm border rounded px-3 py-2 bg-amber-50 border-amber-200">
                                    <span className="font-semibold text-amber-900">{item.resource}</span>
                                    <span className="text-amber-700"> • {item.leadTimeDays} day lead time</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                    <h3 className="font-bold text-xl text-slate-800">Equipment Inventory</h3>
                    <span className="text-xs text-gray-500">Staff available {staff.available}/{staff.total}</span>
                </div>
                <div className="px-6 pb-4">
                    <div className="flex flex-col md:flex-row gap-2">
                        <input
                            className="p-2 border rounded w-full"
                            placeholder="Search equipment"
                            value={equipmentSearch}
                            onChange={(e) => setEquipmentSearch(e.target.value)}
                        />
                        <select
                            className="p-2 border rounded"
                            value={equipmentSortBy}
                            onChange={(e) => setEquipmentSortBy(e.target.value)}
                        >
                            <option value="createdAt">Newest</option>
                            <option value="name">Name</option>
                            <option value="category">Category</option>
                            <option value="quantity">Quantity</option>
                            <option value="status">Status</option>
                        </select>
                        <select
                            className="p-2 border rounded"
                            value={equipmentSortDir}
                            onChange={(e) => setEquipmentSortDir(e.target.value)}
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
                                <th className="px-6 py-4 font-bold text-slate-600">Equipment</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Category</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Quantity</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {equipmentRows.length === 0 ? (
                                <tr><td className="px-6 py-4 text-gray-500" colSpan={4}>No equipment data</td></tr>
                            ) : (
                                equipmentRows.map((item) => (
                                    <tr key={item._id || item.id}>
                                        <td className="px-6 py-4 font-semibold text-slate-800">{item.name}</td>
                                        <td className="px-6 py-4 text-slate-600">{item.category}</td>
                                        <td className="px-6 py-4 text-slate-600">{item.quantity}</td>
                                        <td className="px-6 py-4"><span className="text-xs font-bold text-green-700">{item.status || 'Available'}</span></td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                <form onSubmit={handleAddEquipment} className="p-6 border-t grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input className="p-2 border rounded" placeholder="Equipment name" value={newEquipment.name} onChange={(e) => setNewEquipment({ ...newEquipment, name: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Category" value={newEquipment.category} onChange={(e) => setNewEquipment({ ...newEquipment, category: e.target.value })} />
                    <input className="p-2 border rounded" placeholder="Quantity" type="number" value={newEquipment.quantity} onChange={(e) => setNewEquipment({ ...newEquipment, quantity: e.target.value })} />
                    <button className="bg-indigo-600 text-white rounded" type="submit">Add Equipment</button>
                </form>
            </div>

            {/* TABLE */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                    <h3 className="font-bold text-xl text-slate-800">Hospital Supply Chain</h3>
                    <button onClick={() => setIsAddOpen(true)} className="bg-indigo-600 text-white px-5 py-2.5 rounded-lg text-sm font-bold hover:bg-indigo-700 shadow flex items-center gap-2">
                        <i className="fas fa-plus-circle"></i> Add Supplies
                    </button>
                </div>
                <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
                    <table className="min-w-full text-left text-sm">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="px-6 py-4 font-bold text-slate-600">Item Name</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Category</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Stock</th>
                                <th className="px-6 py-4 font-bold text-slate-600">Status</th>
                                <th className="px-6 py-4 text-right font-bold text-slate-600">AI Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {resources.map((r, idx) => {
                                const isLow = Number(r.quantity) <= Number(r.minThreshold);
                                return (
                                    <tr key={r._id || idx} className="hover:bg-indigo-50/30 transition">
                                        <td className="px-6 py-4 font-bold text-slate-800">{r.name}</td>
                                        <td className="px-6 py-4">
                                            <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${
                                                r.category === 'Medicine' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                                                r.category === 'Blood' ? 'bg-red-50 text-red-700 border-red-200' :
                                                r.category === 'Organ' ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-gray-50 text-gray-700 border-gray-200'
                                            }`}>{r.category}</span>
                                        </td>
                                        <td className="px-6 py-4 font-mono text-slate-700">{r.quantity} {r.unit}</td>
                                        <td className="px-6 py-4">
                                            {isLow ? <span className="text-red-600 font-bold flex items-center gap-1"><i className="fas fa-arrow-down"></i> Critical</span> : 
                                            <span className="text-green-600 font-bold flex items-center gap-1"><i className="fas fa-check"></i> Healthy</span>}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button 
                                                type="button"
                                                onClick={(e) => runAIAnalysis(e, r)} 
                                                className="bg-indigo-50 text-indigo-700 hover:bg-indigo-600 hover:text-white px-4 py-1.5 rounded-lg font-bold transition shadow-sm border border-indigo-100"
                                            >
                                                <i className="fas fa-magic mr-1"></i> Predict
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* ADD ITEM MODAL (USING PORTAL) */}
            {isAddOpen && (
                <ModalPortal>
                    <div className="bg-white rounded-2xl shadow-2xl w-full border-t-8 border-indigo-600 animate-zoom-in">
                        <div className="p-5 flex justify-between items-center border-b">
                            <h3 className="font-bold text-xl text-slate-800">Add Inventory</h3>
                            <button onClick={() => setIsAddOpen(false)}><i className="fas fa-times text-xl text-gray-400 hover:text-red-500"></i></button>
                        </div>
                        <form onSubmit={handleAddSubmit} className="p-6 space-y-5 bg-slate-50 rounded-b-2xl">
                            <div><label className="text-xs font-bold text-gray-500 uppercase">Item Name</label><input required className="w-full p-3 border rounded-lg" value={newItem.name} onChange={e=>setNewItem({...newItem, name: e.target.value})} /></div>
                            <div className="grid grid-cols-2 gap-4">
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Category</label><select className="w-full p-3 border rounded-lg" value={newItem.category} onChange={e=>setNewItem({...newItem, category: e.target.value})}><option>Medicine</option><option>Blood</option><option>Organ</option><option>Equipment</option></select></div>
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Unit</label><input className="w-full p-3 border rounded-lg" placeholder="e.g. boxes" value={newItem.unit} onChange={e=>setNewItem({...newItem, unit: e.target.value})} /></div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div><label className="text-xs font-bold text-gray-500 uppercase">Quantity</label><input required type="number" className="w-full p-3 border rounded-lg font-bold" value={newItem.quantity} onChange={e=>setNewItem({...newItem, quantity: e.target.value})} /></div>
                                <div><label className="text-xs font-bold text-red-500 uppercase">Min Threshold</label><input required type="number" className="w-full p-3 border border-red-200 bg-red-50 rounded-lg text-red-900" value={newItem.minThreshold} onChange={e=>setNewItem({...newItem, minThreshold: e.target.value})} /></div>
                            </div>
                            <button className="w-full bg-indigo-600 text-white py-3.5 rounded-xl font-bold hover:bg-indigo-700 shadow-lg">Confirm & Add</button>
                        </form>
                    </div>
                </ModalPortal>
            )}

            {/* AI PREDICTION MODAL (USING PORTAL) */}
            {isAiModalOpen && (
                <ModalPortal>
                    <div className="bg-white rounded-2xl shadow-2xl w-full overflow-hidden relative border-t-8 border-indigo-500 transform transition-all animate-zoom-in">
                        
                        {/* 1. LOADING STATE */}
                        {aiLoading && (
                            <div className="p-12 text-center">
                                <div className="relative w-20 h-20 mx-auto mb-6">
                                    <div className="absolute inset-0 border-4 border-slate-100 rounded-full"></div>
                                    <div className="absolute inset-0 border-4 border-indigo-500 rounded-full border-t-transparent animate-spin"></div>
                                    <i className="fas fa-robot absolute inset-0 flex items-center justify-center text-indigo-500 text-2xl"></i>
                                </div>
                                <h3 className="text-xl font-bold text-slate-800">Analyzing {selectedItemName}...</h3>
                                <p className="text-slate-500 mt-2 text-sm">Calculating depletion rate & supply chain data</p>
                            </div>
                        )}

                        {/* 2. ERROR STATE */}
                        {!aiLoading && aiError && (
                             <div className="p-8 text-center animate-slide-in-up">
                                <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto text-4xl shadow-xl mb-6 bg-red-100 text-red-600">
                                    <i className="fas fa-times-circle"></i>
                                </div>
                                <h3 className="text-xl font-bold text-slate-800 mb-2">Analysis Failed</h3>
                                <p className="text-red-600 bg-red-50 p-3 rounded-lg text-sm">{aiError}</p>
                                <button onClick={closeAiModal} className="mt-6 w-full bg-slate-800 text-white py-3 rounded-xl font-bold">Close</button>
                             </div>
                        )}

                        {/* 3. SUCCESS RESULT STATE */}
                        {!aiLoading && !aiError && aiResult && (
    <div className="animate-slide-in-up">
        {/* Check if the AI actually returned an error from Python logic */}
        {aiResult.error ? (
            <div className="p-8 text-center">
                <i className="fas fa-exclamation-triangle text-orange-500 text-4xl mb-4"></i>
                <h3 className="text-lg font-bold">AI Processing Error</h3>
                <p className="text-sm text-gray-500 bg-gray-50 p-3 rounded mt-2">{aiResult.error}</p>
                <button onClick={closeAiModal} className="mt-6 w-full bg-slate-800 text-white py-3 rounded-xl font-bold">Close</button>
            </div>
        ) : aiResult?.status === 'queued' ? (
            <div className="p-10 text-center space-y-4">
                <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto text-4xl shadow-xl mb-4 bg-yellow-100 text-yellow-700">
                    <i className="fas fa-hourglass-half"></i>
                </div>
                <h3 className="text-xl font-bold text-slate-800">Prediction queued</h3>
                <p className="text-sm text-slate-500 max-w-md mx-auto">Inventory prediction is being processed in the background. Try again after a few seconds or refresh the resource list once the task finishes.</p>
                <button onClick={closeAiModal} className="mt-4 w-full bg-slate-900 hover:bg-black text-white py-3.5 rounded-xl font-bold shadow-lg transition">Close</button>
            </div>
        ) : (
            <>
                <div className="absolute top-4 right-4">
                    <button onClick={closeAiModal} className="text-slate-300 hover:text-slate-500"><i className="fas fa-times text-xl"></i></button>
                </div>
                <div className="p-8 text-center pb-6">
                    {/* SAFE ACCESS: aiResult?.status?.includes prevents the blank page crash */}
                    <div className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto text-4xl shadow-xl mb-6 border-4 border-white ring-4 ${aiResult?.status?.includes('Critical') || aiResult?.status?.includes('Low') ? 'bg-red-100 text-red-600 ring-red-50' : 'bg-emerald-100 text-emerald-600 ring-emerald-50'}`}>
                        <i className={`fas ${aiResult?.status?.includes('Critical') || aiResult?.status?.includes('Low') ? 'fa-exclamation-triangle' : 'fa-check-circle'}`}></i>
                    </div>
                    <h2 className="text-2xl font-extrabold text-slate-800">{aiResult.item || aiResult.item_name || selectedItemName}</h2>
                    <p className={`font-bold mt-2 inline-block px-3 py-1 rounded-full text-xs uppercase tracking-wide ${aiResult?.status?.includes('Critical') || aiResult?.status?.includes('Low') ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
                        Status: {aiResult.status || 'Unknown'}
                    </p>
                </div>
                <div className="bg-slate-50 px-8 py-6 border-t border-b border-slate-100">
                    <div className="grid grid-cols-2 gap-6 mb-4">
                        <div className="text-center">
                            <p className="text-[10px] font-bold text-slate-400 uppercase">Stockout In</p>
                            <p className="text-3xl font-extrabold text-indigo-600 mt-1">{typeof aiResult.days_left === 'number' ? (aiResult.days_left > 900 ? '99+' : aiResult.days_left) : aiResult.days_left || 'N/A'} <span className="text-sm text-slate-400">Days</span></p>
                        </div>
                        <div className="text-center border-l border-slate-200">
                            <p className="text-[10px] font-bold text-slate-400 uppercase">Usage Rate</p>
                            <p className="text-3xl font-extrabold text-indigo-600 mt-1">{aiResult.usage_rate_per_day || 'N/A'}</p>
                            <p className="text-xs text-slate-500">Units / Day</p>
                        </div>
                    </div>
                    <div className={`p-4 rounded-xl text-sm font-bold border flex items-start gap-3 text-left ${aiResult?.status?.includes('Critical') || aiResult?.status?.includes('Low') ? 'bg-red-50 text-red-800 border-red-100' : 'bg-blue-50 text-blue-800 border-blue-100'}`}>
                        <i className="fas fa-lightbulb mt-1 text-lg"></i>
                        <div>
                            <span className="block text-xs opacity-70 uppercase mb-0.5">AI Recommendation</span>
                            {aiResult.recommendation || 'No recommendation available yet.'}
                        </div>
                    </div>
                </div>
                <div className="p-6">
                    <button onClick={closeAiModal} className="w-full bg-slate-900 hover:bg-black text-white py-3.5 rounded-xl font-bold shadow-lg transition">Acknowledge & Close</button>
                </div>
            </>
        )}
    </div>
)}
                    </div>
                </ModalPortal>
            )}
        </div>
    );
};

export default HospitalResources;