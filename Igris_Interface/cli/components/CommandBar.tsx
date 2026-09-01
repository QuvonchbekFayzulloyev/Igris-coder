import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';
import { useAgentConsoleStore } from '../../shared/store';
import { COMMANDS } from '../../shared/constants';

interface CommandBarProps {
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
}

export function CommandBar({ value, onChange, onClose }: CommandBarProps) {
  const { setMainView, toggleSidebar, toggleTerminal, setSettingsOpen } =
    useAgentConsoleStore();

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(value.toLowerCase())
  );

  const executeCommand = (label: string) => {
    switch (label) {
      case 'New session':
        // TODO: Implement new session
        break;
      case 'New file':
        // TODO: Implement new file
        break;
      case 'Open 2nd Brain':
        setMainView('brain');
        break;
      case 'Open Web AI Bridge':
        setMainView('webai');
        break;
      case 'Toggle terminal panel':
        toggleTerminal();
        break;
      case 'Open settings':
        setSettingsOpen(true);
        break;
      default:
        break;
    }
    onClose();
  };

  return (
    <Box flexDirection="column" padding={1}>
      <Box borderStyle="single" borderColor="yellow" flexDirection="column">
        <Box paddingX={1} borderStyle="single" borderColor="gray">
          <Text color="gray">❯ </Text>
          <TextInput
            value={value}
            onChange={onChange}
            onSubmit={(v) => {
              if (filtered.length > 0) {
                executeCommand(filtered[0].label);
              }
            }}
            placeholder="Type a command..."
          />
          <Text color="gray"> [Esc to close]</Text>
        </Box>

        <Box flexDirection="column" marginTop={1}>
          {filtered.length === 0 ? (
            <Text color="gray">No matching commands.</Text>
          ) : (
            filtered.map((cmd) => (
              <Box key={cmd.label} paddingX={1}>
                <Text color="white">{cmd.label}</Text>
                {cmd.hint && (
                  <Text color="gray"> {cmd.hint}</Text>
                )}
              </Box>
            ))
          )}
        </Box>
      </Box>
    </Box>
  );
}
