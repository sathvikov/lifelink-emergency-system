import React from 'react';

const Sidebar = ({
    items = [],
    activeKey,
    onSelect,
    user,
    onProfile,
    onNotifications,
    onLogout,
    onSwitchRole,
    hasUnread,
    onLogoClick,
    className = '',
}) => {
    const isNotificationsActive = activeKey === 'notifications';
    const isProfileActive = activeKey === 'profile';

    return (
        <aside className={`w-full lg:w-72 lg:h-screen lg:overflow-y-auto lg:sticky lg:top-0 bg-white/90 backdrop-blur border-b lg:border-b-0 lg:border-r border-slate-200 flex flex-col ${className}`}>
        <div className="px-5 py-6 border-b border-slate-200">
            <button onClick={onLogoClick} className="flex items-center gap-3 text-left">
                <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg shadow">
                    <i className="fas fa-heartbeat text-lg"></i>
                </div>
                <div>
                    <h1 className="text-lg font-bold text-slate-900 font-display">LifeLink</h1>
                    <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
                        {user?.role ? `${user.role} portal` : 'Portal'}{user?.subRole ? ` • ${user.subRole}` : ''}
                    </p>
                </div>
            </button>
        </div>

        <nav className="flex-1 px-4 pb-6 space-y-2">
            {items.map((item) => (
                <button
                    key={item.key}
                    type="button"
                    onClick={() => onSelect?.(item.key)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold text-left transition ${
                        activeKey === item.key
                            ? 'bg-sky-600 text-white shadow-md'
                            : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
                    }`}
                >
                    <i className={`fas ${item.icon}`}></i>
                    <span className="flex-1">{item.label}</span>
                </button>
            ))}
        </nav>

        <div className="px-4 py-5 border-t border-slate-200 space-y-2">
            {onNotifications && (
                <button
                    onClick={onNotifications}
                    className={`w-full flex items-center justify-between px-4 py-2.5 rounded-xl text-sm font-semibold transition ${
                        isNotificationsActive
                            ? 'bg-sky-600 text-white shadow-md'
                            : 'text-slate-700 bg-slate-50 hover:bg-slate-100'
                    }`}
                >
                    <span className="flex items-center gap-2">
                        <i className={`fas fa-bell ${isNotificationsActive ? 'text-white' : 'text-slate-500'}`}></i>
                        Notifications
                    </span>
                    {hasUnread && (
                        <span className={`h-2.5 w-2.5 rounded-full border-2 ${
                            isNotificationsActive ? 'border-sky-600 bg-white' : 'border-white bg-red-500'
                        }`}></span>
                    )}
                </button>
            )}

            {onSwitchRole && (
                <button
                    onClick={onSwitchRole}
                    className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 transition"
                >
                    <i className="fas fa-arrows-rotate"></i>
                    Switch Role
                </button>
            )}

            {onProfile && (
                <button
                    onClick={onProfile}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold transition ${
                        isProfileActive
                            ? 'bg-sky-600 text-white shadow-md'
                            : 'text-slate-700 bg-slate-50 hover:bg-slate-100'
                    }`}
                >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                        isProfileActive ? 'bg-white text-sky-700' : 'bg-sky-600 text-white'
                    }`}>
                        {user?.name?.charAt(0)?.toUpperCase() || 'U'}
                    </div>
                    <span className="truncate">{user?.name || 'User'}</span>
                </button>
            )}

            {onLogout && (
                <button
                    onClick={onLogout}
                    className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-red-600 bg-red-50 hover:bg-red-100 transition"
                >
                    <i className="fas fa-sign-out-alt"></i>
                    Logout
                </button>
            )}
        </div>
        </aside>
    );
};

export default Sidebar;
