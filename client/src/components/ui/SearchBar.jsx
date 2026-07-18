import React from 'react';

const SearchBar = ({
    mode = 'db',
    showModeToggle = true,
    query = '',
    onQueryChange,
    onModeChange,
    onSubmit,
    loading = false,
}) => {
    const isAi = mode === 'ai';
    const modeLabel = isAi ? 'LifeLink AI' : 'Database Search';

    return (
        <form
            onSubmit={(e) => {
                e.preventDefault();
                onSubmit?.();
            }}
            className={`flex items-center gap-2 px-3 py-2 rounded-2xl border shadow-sm transition-all duration-200 w-full overflow-hidden ${
                isAi ? 'bg-gradient-to-r from-purple-50 to-indigo-50 border-purple-200' : 'bg-white/80 border-slate-200'
            }`}
        >
            {showModeToggle ? (
                <button
                    type="button"
                    onClick={() => onModeChange?.(isAi ? 'db' : 'ai')}
                    className={`text-[11px] font-bold uppercase tracking-wide px-3 py-1 rounded-full transition shrink-0 ${
                        isAi ? 'bg-purple-600 text-white' : 'bg-slate-100 text-slate-600'
                    }`}
                >
                    {modeLabel}
                </button>
            ) : (
                <span className="text-[11px] font-bold uppercase tracking-wide px-3 py-1 rounded-full bg-slate-100 text-slate-600 shrink-0">
                    {modeLabel}
                </span>
            )}
            <input
                className="flex-1 min-w-0 bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400"
                placeholder={isAi ? 'Ask LifeLink AI…' : 'Search records…'}
                value={query}
                onChange={(e) => onQueryChange?.(e.target.value)}
            />
            <button
                type="submit"
                disabled={loading}
                className={`text-xs font-semibold px-3 py-1.5 rounded-full transition shrink-0 ${
                    isAi ? 'bg-purple-600 text-white' : 'bg-sky-600 text-white'
                }`}
            >
                {loading ? 'Searching…' : 'Go'}
            </button>
        </form>
    );
};

export default SearchBar;
