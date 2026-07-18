import React from 'react';
import Sidebar from './Sidebar';
import MobileDrawer from './MobileDrawer';

const ResponsiveSidebar = ({ isOpen, onClose, ...sidebarProps }) => (
  <>
    <div className="hidden lg:block">
      <Sidebar {...sidebarProps} />
    </div>
    <MobileDrawer open={isOpen} onClose={onClose}>
      <Sidebar {...sidebarProps} className="h-full w-72" />
    </MobileDrawer>
  </>
);

export default ResponsiveSidebar;
