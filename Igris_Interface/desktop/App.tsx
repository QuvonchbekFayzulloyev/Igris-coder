import React from 'react';
import { AgentConsole } from '../web/components/AgentConsole';
import { TitleBar } from './components/TitleBar';

export function App() {
  return (
    <div className="w-full h-screen flex flex-col bg-zinc-950 text-zinc-200 font-ui overflow-hidden">
      {/* Custom Title Bar */}
      <TitleBar />

      {/* Main Agent Console */}
      <AgentConsole isDesktop={true} />
    </div>
  );
}
