import React from 'react';
import Spinner from './Spinner';

const styles = {
    primary: 'bg-sky-600 text-white hover:bg-sky-700',
    secondary: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
    danger: 'bg-red-600 text-white hover:bg-red-700',
    ghost: 'bg-transparent text-slate-600 hover:bg-slate-100',
    ai: 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white hover:from-purple-700 hover:to-indigo-700',
};

const sizes = {
    sm: 'px-3 py-2 text-xs',
    md: 'px-4 py-2.5 text-sm',
    lg: 'px-5 py-3 text-base',
};

const Button = ({
    children,
    variant = 'primary',
    size = 'md',
    loading = false,
    className = '',
    ...props
}) => (
    <button
        type="button"
        disabled={loading || props.disabled}
        className={`inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-200 shadow-sm hover:shadow-md active:scale-95 ${styles[variant] || styles.primary} ${sizes[size] || sizes.md} ${className}`}
        {...props}
    >
        {loading && <Spinner size="sm" />}
        {children}
    </button>
);

export default Button;
