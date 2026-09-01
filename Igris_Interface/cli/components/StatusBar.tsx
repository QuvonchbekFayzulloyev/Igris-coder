import React from 'react';
import { Box, Text } from 'ink';
import { useAgentConsoleStore } from '../../shared/store';

export function StatusBar() {
  const { mainView, agentInfo, backendOnline } = useAgentConsoleStore();

  // Dp1 tuzatildi: hardcoded qwen3:8b / "ctx 12.4K" / "6.2 GB" o'rniga REAL
  // backend status (agentInfo). Offline — "—" ko'rsatiladi, yolg'on ma'lumot emas.
  const model = agentInfo?.model || (backendOnline ? 'yuklanmoqda…' : '—');
  const llm = agentInfo
    ? agentInfo.llmAvailable
      ? 'Ollama · local'
      : 'Ollama offline'
    : 'bridge ulanmagan';
  const memory = agentInfo
    ? agentInfo.memoryEnabled
      ? 'mem on'
      : 'mem off'
    : '';

  return (
    <Box
      paddingX={1}
      borderStyle="single"
      borderColor="gray"
      justifyContent="space-between"
    >
      <Box>
        <Text color="green">●</Text>
        <Text color="gray"> {llm}</Text>
        {memory && <Text color="gray"> │ </Text>}
        {memory && <Text color="cyan">{memory}</Text>}
        <Text color="gray"> │ </Text>
        <Text color="cyan">{model}</Text>
      </Box>
      <Box>
        <Text color="yellow">[{mainView}]</Text>
      </Box>
    </Box>
  );
}
