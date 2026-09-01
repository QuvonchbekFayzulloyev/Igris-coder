import React, { useState, useEffect } from 'react';
import { Box, Text, useInput, useApp } from 'ink';
import { useAgentConsoleStore } from '../shared/store';
import { STAGES } from '../shared/constants';
import { Sidebar } from './components/Sidebar';
import { ChatView } from './components/ChatView';
import { StatusBar } from './components/StatusBar';
import { CommandBar } from './components/CommandBar';

export function App() {
  const { exit } = useApp();
  const [showHelp, setShowHelp] = useState(false);
  const [commandMode, setCommandMode] = useState(false);
  const [command, setCommand] = useState('');

  const {
    mainView,
    setMainView,
    stage,
    sidebarOpen,
    toggleSidebar,
    terminalOpen,
    toggleTerminal,
  } = useAgentConsoleStore();

  // Dp1 tuzatildi: AgentPanel/StatusBar hardcoded fake data ko'rsatmasligi uchun
  // real backend status yuklanadi (model, LLM, RAG memory holati).
  useEffect(() => {
    const { loadAgentInfo } = useAgentConsoleStore.getState();
    loadAgentInfo();
  }, []);

  // Keyboard shortcuts
  useInput((input, key) => {
    // Ctrl+Q: Quit
    if (key.ctrl && input === 'q') {
      exit();
    }
    // Ctrl+K: Toggle command bar
    if (key.ctrl && input === 'k') {
      setCommandMode((v) => !v);
    }
    // Ctrl+B: Toggle sidebar
    if (key.ctrl && input === 'b') {
      toggleSidebar();
    }
    // Ctrl+`: Toggle terminal
    if (key.ctrl && input === '`') {
      toggleTerminal();
    }
    // F1: Toggle help
    if (key.f1) {
      setShowHelp((v) => !v);
    }
    // 1-4: Switch views
    if (input === '1') setMainView('chat');
    if (input === '2') setMainView('preview');
    if (input === '3') setMainView('brain');
    if (input === '4') setMainView('webai');
  });

  if (showHelp) {
    return <HelpScreen onExit={() => setShowHelp(false)} />;
  }

  if (commandMode) {
    return (
      <CommandBar
        value={command}
        onChange={setCommand}
        onClose={() => {
          setCommandMode(false);
          setCommand('');
        }}
      />
    );
  }

  return (
    <Box flexDirection="column" height="100%">
      {/* Header */}
      <Header />

      {/* Main Content */}
      <Box flexDirection="row" flex={1}>
        {/* Sidebar */}
        {sidebarOpen && <Sidebar />}

        {/* Main Area */}
        <Box flexDirection="column" flex={1}>
          {/* View Tabs */}
          <ViewTabs />

          {/* Pipeline Stepper */}
          <PipelineStepper current={stage} />

          {/* Content */}
          <Box flex={1}>
            {mainView === 'chat' && <ChatView />}
            {mainView === 'preview' && <PreviewView />}
            {mainView === 'brain' && <BrainView />}
            {mainView === 'webai' && <WebAIView />}
          </Box>
        </Box>
      </Box>

      {/* Status Bar */}
      <StatusBar />
    </Box>
  );
}

function Header() {
  return (
    <Box paddingX={1} paddingY={0} borderStyle="single" borderColor="gray">
      <Text bold color="yellow">
        ⬡ Agent Console
      </Text>
      <Text color="gray"> v1.0.0</Text>
      <Text color="gray"> │ </Text>
      <Text color="cyan">Ctrl+K</Text>
      <Text color="gray"> command bar</Text>
      <Text color="gray"> │ </Text>
      <Text color="cyan">F1</Text>
      <Text color="gray"> help</Text>
    </Box>
  );
}

function ViewTabs() {
  const { mainView, setMainView } = useAgentConsoleStore();
  const views = [
    { id: 'chat', label: '💬 Chat', key: '1' },
    { id: 'preview', label: '👁 Preview', key: '2' },
    { id: 'brain', label: '🧠 Brain', key: '3' },
    { id: 'webai', label: '🌐 Web AI', key: '4' },
  ];

  return (
    <Box paddingX={1} borderStyle="single" borderColor="gray">
      {views.map((v) => (
        <Box key={v.id} marginRight={2}>
          <Text
            color={mainView === v.id ? 'yellow' : 'gray'}
            bold={mainView === v.id}
          >
            {v.label}
          </Text>
          <Text color="gray"> [{v.key}]</Text>
        </Box>
      ))}
    </Box>
  );
}

function PipelineStepper({ current }: { current: number }) {
  return (
    <Box paddingX={1} borderStyle="single" borderColor="gray">
      {STAGES.map((stage, i) => {
        const state = i < current ? 'done' : i === current ? 'active' : 'pending';
        return (
          <React.Fragment key={stage}>
            <Text
              color={
                state === 'done'
                  ? 'green'
                  : state === 'active'
                    ? 'yellow'
                    : 'gray'
              }
              bold={state === 'active'}
            >
              {state === 'done' ? '●' : state === 'active' ? '◉' : '○'}{' '}
              {stage}
            </Text>
            {i < STAGES.length - 1 && <Text color="gray"> → </Text>}
          </React.Fragment>
        );
      })}
    </Box>
  );
}

function PreviewView() {
  return (
    <Box padding={1}>
      <Text color="gray">Preview view - Select a file from the sidebar</Text>
    </Box>
  );
}

function BrainView() {
  return (
    <Box padding={1}>
      <Text color="gray">2nd Brain - Knowledge graph view</Text>
    </Box>
  );
}

function WebAIView() {
  return (
    <Box padding={1}>
      <Text color="gray">Web AI Bridge - Browser automation view</Text>
    </Box>
  );
}

function HelpScreen({ onExit }: { onExit: () => void }) {
  return (
    <Box flexDirection="column" padding={1}>
      <Text bold color="yellow">
        ⬡ Agent Console - Help
      </Text>
      <Box marginTop={1}>
        <Text color="gray">Keyboard Shortcuts:</Text>
      </Box>
      <Box marginTop={1} flexDirection="column">
        <Text>
          <Text color="cyan">Ctrl+Q</Text> - Quit
        </Text>
        <Text>
          <Text color="cyan">Ctrl+K</Text> - Command bar
        </Text>
        <Text>
          <Text color="cyan">Ctrl+B</Text> - Toggle sidebar
        </Text>
        <Text>
          <Text color="cyan">Ctrl+`</Text> - Toggle terminal
        </Text>
        <Text>
          <Text color="cyan">F1</Text> - Toggle help
        </Text>
        <Text>
          <Text color="cyan">1-4</Text> - Switch views
        </Text>
      </Box>
      <Box marginTop={1}>
        <Text color="gray">Press any key to close help...</Text>
      </Box>
    </Box>
  );
}
