import React, { useEffect, useRef, useCallback } from 'react';
import { AgentConsole } from './components/AgentConsole';
import { StatusBar } from './components/StatusBar';
import { useAgentConsoleStore } from '../shared/store';
import { useMenu, MenuItem } from './components/ContextMenu';

export function App() {
  const mainView = useAgentConsoleStore((s) => s.mainView);
  const setMainView = useAgentConsoleStore((s) => s.setMainView);
  const setPaletteOpen = useAgentConsoleStore((s) => s.setPaletteOpen);
  const setSettingsOpen = useAgentConsoleStore((s) => s.setSettingsOpen);
  const toggleSidebar = useAgentConsoleStore((s) => s.toggleSidebar);
  const toggleRightSidebar = useAgentConsoleStore((s) => s.toggleRightSidebar);
  const sidebarOpen = useAgentConsoleStore((s) => s.sidebarOpen);
  const rightSidebarOpen = useAgentConsoleStore((s) => s.rightSidebarOpen);
  const menu = useMenu();

  // Butun UI uchun umumiy o'ng-tugma menyusi — har bir view'ga xos elementlar
  // bilan (view'lar o'z menyusini qo'shsa, umumiy menyu chizilmaydi).
  const onGlobalContextMenu = useCallback((e: React.MouseEvent) => {
    // Sahifa o'z menyusini chizgan bo'lsa (defaultPrevented) — aralashmaymiz
    if (e.defaultPrevented) return;
    e.preventDefault();
    const items: MenuItem[] = [
      { id: 'palette', label: 'Buyruqlar paneli', icon: '⌘', hint: 'Ctrl+K', action: () => setPaletteOpen(true) },
      { id: 'settings', label: 'Sozlamalar', icon: '⚙', action: () => setSettingsOpen(true) },
      { separator: true },
      { id: 'sb', label: sidebarOpen ? 'Chap panelni yopish' : 'Chap panelni ochish', icon: '▤', action: toggleSidebar },
      { id: 'rsb', label: rightSidebarOpen ? 'O‘ng panelni yopish' : 'O‘ng panelni ochish', icon: '▥', action: toggleRightSidebar },
      { separator: true },
      { id: 'reload', label: 'Interfeysni yangilash', icon: '↻', action: () => window.location.reload() },
    ];
    // Joriy view'ga xos navigatsiya
    const views: { id: typeof mainView; label: string; icon: string }[] = [
      { id: 'chat', label: 'Chat', icon: '💬' },
      { id: 'preview', label: 'Preview', icon: '👁' },
      { id: 'brain', label: '2nd Brain', icon: '🧠' },
      { id: 'webai', label: 'Web AI', icon: '🌐' },
      { id: 'quality', label: 'Quality', icon: '📊' },
    ];
    for (const v of views) {
      if (v.id !== mainView) {
        items.push({ id: `view-${v.id}`, label: `${v.label} ga o‘tish`, icon: v.icon, action: () => setMainView(v.id) });
      }
    }
    menu.open(e.clientX, e.clientY, items);
  }, [mainView, setMainView, setPaletteOpen, setSettingsOpen, toggleSidebar, toggleRightSidebar, sidebarOpen, rightSidebarOpen, menu]);

  return (
    <div className="w-full h-screen flex flex-col bg-zinc-950 text-zinc-200 font-ui overflow-hidden" onContextMenu={onGlobalContextMenu}>
      {/* Main Agent Console - Web version without desktop title bar */}
      <AgentConsole isDesktop={false} />
      <StatusBar />
    </div>
  );
}
