import React from 'react';
import { AgentConsole } from './components/AgentConsole';

export function App() {
  return (
    <div className="w-full h-screen flex flex-col bg-zinc-950 text-zinc-200 font-ui overflow-hidden">
      {/* Main Agent Console - Web version without desktop title bar */}
      <AgentConsole isDesktop={false} />
    </div>
  );
}
