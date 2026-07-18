import React from 'react';
import SearchBar from '../ui/SearchBar';

const Navbar = ({
    user,
    onLogoClick,
    onLogout,
    onProfile,
    onNotifications,
    hasUnread,
    searchProps,
}) => (
    <header className="bg-white/95 backdrop-blur-md shadow-sm sticky top-0 z-40 border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16 gap-4">
                <button onClick={onLogoClick} className="flex items-center gap-3">
                    <div className="bg-gradient-to-tr from-sky-600 to-indigo-600 text-white p-2 rounded-lg shadow">
                        <i className="fas fa-heartbeat text-lg"></i>
                    </div>
                    <div className="text-left">
                        <h1 className="text-lg font-bold text-slate-900 font-display">LifeLink</h1>
                        <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
                            {user?.role ? `${user.role} portal` : 'Portal'}{user?.subRole ? ` • ${user.subRole}` : ''}
                        </p>
                    </div>
                </button>

                <div className="flex-1 max-w-xl hidden md:block">
                    <SearchBar {...searchProps} />
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={onNotifications}
                        className="relative p-2 rounded-full text-slate-500 hover:text-sky-600 hover:bg-slate-100 transition"
                    >
                        <i className="fas fa-bell"></i>
                        {hasUnread && <span className="absolute top-1 right-1 h-2.5 w-2.5 bg-red-500 rounded-full border-2 border-white"></span>}
                    </button>

                    <button
                        onClick={onProfile}
                        className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-full text-sm font-semibold text-slate-700"
                    >
                        <div className="w-7 h-7 rounded-full bg-sky-600 text-white flex items-center justify-center text-xs font-bold">
                            {user?.name?.charAt(0)?.toUpperCase() || 'U'}
                        </div>
                        <span className="hidden md:inline">{user?.name || 'User'}</span>
                    </button>

                    <button onClick={onLogout} className="text-red-500 hover:text-red-700 p-2 rounded-full hover:bg-red-50 transition" title="Logout">
                        <i className="fas fa-sign-out-alt"></i>
                    </button>
                </div>
            </div>
            <div className="md:hidden pb-3">
                <SearchBar {...searchProps} />
            </div>
        </div>
    </header>
);

export default Navbar;
