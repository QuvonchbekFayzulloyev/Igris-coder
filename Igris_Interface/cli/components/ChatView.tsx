import React, { useRef, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';
import { useAgentConsoleStore } from '../../shared/store';
import { ChatMessage } from '../../shared/constants';

export function ChatView() {
  const { messages, input, setInput, handleSend, scrollRef } =
    useAgentConsoleStore();

  return (
    <Box flexDirection="column" flex={1}>
      {/* Messages */}
      <Box flexDirection="column" flex={1} overflowY="auto" padding={1}>
        {messages.map((msg, i) => (
          <ChatMessageItem key={i} msg={msg} />
        ))}
      </Box>

      {/* Input */}
      <Box borderStyle="single" borderColor="gray" paddingX={1}>
        <Box flex={1}>
          <Text color="gray">❯ </Text>
          <TextInput
            value={input}
            onChange={setInput}
            onSubmit={handleSend}
            placeholder="Ask the agent, or describe a change..."
          />
        </Box>
        <Text color="gray">⏎</Text>
      </Box>

      {/* Hint */}
      <Box paddingX={1}>
        <Text color="gray">Enter to send │ Shift+Enter for newline</Text>
      </Box>
    </Box>
  );
}

function ChatMessageItem({ msg }: { msg: ChatMessage }) {
  if (msg.kind === 'toolcall') {
    return <ToolCallCard msg={msg} />;
  }

  if (msg.kind === 'drawing') {
    return (
      <Box marginBottom={1} flexDirection="column">
        <Text color="yellow">🖼 live build — {msg.path || 'drawing'}</Text>
        <Text color="gray">  Animated preview renders in the web chat (npm run dev).</Text>
      </Box>
    );
  }

  const isUser = msg.role === 'user';

  return (
    <Box marginBottom={1}>
      <Box flexDirection="column" flex={1}>
        {!isUser && (
          <Box marginBottom={1}>
            <Text color="yellow">✦ agent</Text>
          </Box>
        )}
        {!isUser && msg.warning && (
          <Box
            marginBottom={1}
            borderStyle="single"
            borderColor="red"
            paddingX={1}
            flexDirection="column"
          >
            <Text color="red">{msg.warning}</Text>
          </Box>
        )}
        <Box
          borderStyle={isUser ? undefined : 'single'}
          borderColor="gray"
          paddingX={1}
          backgroundColor={isUser ? 'gray' : undefined}
        >
          <Text color={isUser ? 'white' : 'gray'}>{msg.text}</Text>
        </Box>
      </Box>
    </Box>
  );
}

function ToolCallCard({ msg }: { msg: ChatMessage }) {
  const [open, setOpen] = React.useState(msg.status !== 'running');

  const statusIcon =
    msg.status === 'running' ? (
      <Text color="yellow">⟳</Text>
    ) : msg.status === 'done' ? (
      <Text color="green">✓</Text>
    ) : (
      <Text color="red">⚠</Text>
    );

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Box
        borderStyle="single"
        borderColor="gray"
        paddingX={1}
        flexDirection="column"
      >
        <Box>
          <Text>
            {statusIcon} <Text color="cyan">{msg.name}</Text>{' '}
            <Text color="gray">{msg.detail}</Text>
          </Text>
        </Box>

        {open && msg.diff && (
          <Box flexDirection="column" marginTop={1} borderStyle="single" borderColor="gray">
            {msg.diff.map((line, i) => (
              <Text key={i}>
                {line.startsWith('+') ? (
                  <Text color="green">{line}</Text>
                ) : line.startsWith('-') ? (
                  <Text color="red">{line}</Text>
                ) : (
                  <Text color="gray">{line}</Text>
                )}
              </Text>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}
