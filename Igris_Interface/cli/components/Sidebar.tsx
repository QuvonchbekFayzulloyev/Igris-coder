import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { useAgentConsoleStore } from '../../shared/store';
import { INITIAL_TREE, TreeNode } from '../../shared/constants';

export function Sidebar() {
  const { sidebarMode, setSidebarMode, selectedFile, setSelectedFile, setMainView } =
    useAgentConsoleStore();

  return (
    <Box
      flexDirection="column"
      width={30}
      borderStyle="single"
      borderColor="gray"
    >
      {/* Mode Tabs */}
      <Box paddingX={1} borderStyle="single" borderColor="gray">
        <Text
          color={sidebarMode === 'workspace' ? 'yellow' : 'gray'}
          bold={sidebarMode === 'workspace'}
        >
          Workspace
        </Text>
        <Text color="gray"> │ </Text>
        <Text
          color={sidebarMode === 'agent' ? 'yellow' : 'gray'}
          bold={sidebarMode === 'agent'}
        >
          Agent
        </Text>
      </Box>

      {/* Content */}
      <Box flexDirection="column" flex={1} overflowY="auto">
        {sidebarMode === 'workspace' ? (
          <FileTree
            tree={INITIAL_TREE}
            selectedFile={selectedFile}
            onFileSelect={(file) => {
              setSelectedFile(file);
              setMainView('preview');
            }}
          />
        ) : (
          <AgentPanel />
        )}
      </Box>
    </Box>
  );
}

function FileTree({
  tree,
  selectedFile,
  onFileSelect,
  depth = 0,
}: {
  tree: TreeNode[];
  selectedFile: string;
  onFileSelect: (file: string) => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(
    new Set(['.agent', 'src', 'src/agent'])
  );

  const toggle = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  };

  return (
    <Box flexDirection="column">
      {tree.map((node) => (
        <TreeNodeItem
          key={node.name}
          node={node}
          path={node.name}
          depth={depth}
          expanded={expanded}
          toggle={toggle}
          selectedFile={selectedFile}
          onFileSelect={onFileSelect}
        />
      ))}
    </Box>
  );
}

function TreeNodeItem({
  node,
  path,
  depth,
  expanded,
  toggle,
  selectedFile,
  onFileSelect,
}: {
  node: TreeNode;
  path: string;
  depth: number;
  expanded: Set<string>;
  toggle: (path: string) => void;
  selectedFile: string;
  onFileSelect: (file: string) => void;
}) {
  const isFolder = node.type === 'folder';
  const isOpen = expanded.has(path);
  const isSelected = !isFolder && path === selectedFile;
  const indent = '  '.repeat(depth);

  const statusIcon =
    node.status === 'modified' ? (
      <Text color="yellow">●</Text>
    ) : node.status === 'new' ? (
      <Text color="green">●</Text>
    ) : null;

  const folderIcon = isFolder ? (isOpen ? <Text color="gray">▾</Text> : <Text color="gray">▸</Text>) : null;
  const fileIcon = !isFolder ? <Text color="gray">  </Text> : null;

  return (
    <Box flexDirection="column">
      <Box
        paddingX={1}
        backgroundColor={isSelected ? 'gray' : undefined}
      >
        <Text>
          {indent}
          {folderIcon}
          {fileIcon}
          {node.special ? (
            <Text color="yellow">{node.name}</Text>
          ) : isSelected ? (
            <Text bold>{node.name}</Text>
          ) : (
            <Text color="gray">{node.name}</Text>
          )}
          {statusIcon && <Text> {statusIcon}</Text>}
        </Text>
      </Box>
      {isFolder &&
        isOpen &&
        node.children && (
          <FileTree
            tree={node.children}
            selectedFile={selectedFile}
            onFileSelect={onFileSelect}
            depth={depth + 1}
          />
        )}
    </Box>
  );
}

function AgentPanel() {
  const { stage, agentInfo, backendOnline } = useAgentConsoleStore();

  // Dp1 tuzatildi: hardcoded qwen3:8b / "39%" / "12.4K/32K" o'rniga REAL
  // backend status ko'rsatiladi (agentInfo — /api/status'dan yuklanadi).
  // Backend offline / hali yuklanmagan bo'lsa — yolg'on raqamlar o'rniga "—".
  const model = agentInfo?.model || (backendOnline ? 'yuklanmoqda…' : '—');
  const llmStatus = agentInfo
    ? agentInfo.llmAvailable
      ? 'via Ollama · local'
      : 'Ollama mavjud emas'
    : 'bridge ulanmagan';
  const memory = agentInfo
    ? agentInfo.memoryEnabled
      ? 'on (Igris_Memory)'
      : 'off'
    : '—';

  return (
    <Box flexDirection="column" padding={1}>
      <Box marginBottom={1}>
        <Text color="gray">Model</Text>
      </Box>
      <Box marginBottom={1}>
        <Text color="white" bold>
          {model}
        </Text>
      </Box>
      <Box marginBottom={1}>
        <Text color={agentInfo?.llmAvailable ? undefined : 'yellow'}>
          {llmStatus}
        </Text>
      </Box>

      <Box marginTop={1} marginBottom={1}>
        <Text color="gray">Memory (RAG)</Text>
      </Box>
      <Box marginBottom={1}>
        <Text color={agentInfo?.memoryEnabled ? 'green' : 'gray'}>{memory}</Text>
      </Box>

      <Box marginTop={1} marginBottom={1}>
        <Text color="gray">Pipeline stage</Text>
      </Box>
      <Box>
        {[0, 1, 2, 3, 4].map((i) => (
          <Text key={i}>
            {i < stage ? (
              <Text color="green">●</Text>
            ) : i === stage ? (
              <Text color="yellow">◉</Text>
            ) : (
              <Text color="gray">○</Text>
            )}
            {i < 4 && <Text color="gray"> </Text>}
          </Text>
        ))}
      </Box>
    </Box>
  );
}
