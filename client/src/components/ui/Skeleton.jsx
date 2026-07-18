import React from 'react';

const Skeleton = ({ className = '' }) => (
    <div className={`animate-pulse rounded-xl bg-slate-200/70 ${className}`} />
);

export default Skeleton;
