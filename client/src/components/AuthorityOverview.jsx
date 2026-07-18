import React from 'react';
import { DashboardCard, SimpleBarChart, StatCard } from './Common';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const AuthorityOverview = () => {
    const barData = [
        { label: 'Accident', value: 45 }, { label: 'Cardiac', value: 30 }, { label: 'Respiratory', value: 15 }
    ];

    const pieData = [
        { name: 'Available', value: 28 }, { name: 'Occupied', value: 72 }
    ];
    const COLORS = ['#10b981', '#f59e0b'];

    return (
        <div className="space-y-6">
            {/* Expanded Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <StatCard title="Active SOS" value="24" icon="fa-bell" color="text-red-500" />
                <StatCard title="Avg Response" value="12.4m" icon="fa-clock" color="text-blue-500" />
                <StatCard title="Staff Online" value="1.2k" icon="fa-user-md" color="text-green-500" />
                <StatCard title="Critical Zones" value="3" icon="fa-triangle-exclamation" color="text-orange-500" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <SimpleBarChart title="Emergency Distribution" data={barData} barColorClass="bg-sky-500" />
                
                <DashboardCard>
                    <h3 className="font-bold text-lg mb-4">Regional Bed Capacity</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie data={pieData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                                    {pieData.map((entry, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                                </Pie>
                                <Tooltip />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </DashboardCard>
            </div>
        </div>
    );
};

export default AuthorityOverview;