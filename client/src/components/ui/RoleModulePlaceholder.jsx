import React from 'react';
import { DashboardCard } from '../Common';

const RoleModulePlaceholder = ({ title, description, highlights = [] }) => (
    <div className="space-y-6">
        <div>
            <p className="text-xs font-bold uppercase text-slate-500">Module</p>
            <h2 className="text-2xl font-extrabold text-slate-900">{title}</h2>
            {description && <p className="text-slate-600 mt-2">{description}</p>}
        </div>

        {highlights.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {highlights.map((item, index) => (
                    <DashboardCard key={`${item.label}-${index}`}>
                        <p className="text-xs font-bold uppercase text-slate-500">{item.label}</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">{item.value}</p>
                        {item.caption && (
                            <p className="text-xs text-slate-400 mt-2">{item.caption}</p>
                        )}
                    </DashboardCard>
                ))}
            </div>
        )}

        <div className="bg-white/70 border border-slate-200 rounded-2xl p-5 text-sm text-slate-600">
            <p className="font-semibold text-slate-800">Demo Module</p>
            <p className="mt-2">
                This section is a front-end placeholder for role-specific workflows. Hook it to
                live data sources when the backend APIs are ready.
            </p>
        </div>
    </div>
);

export default RoleModulePlaceholder;
