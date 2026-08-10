import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import { usePaletteStore } from '@/stores/paletteStore';
import { glass } from '@/theme/glass';
import { depth } from '@/theme/depth';
import type { Command } from '@/runtime/commands/registry';

interface CommandPaletteProps {
  commands: Command[];
  onSelect: (command: Command) => void;
}

const CommandPalette = ({ commands, onSelect }: CommandPaletteProps) => {
  const { isOpen, closePalette, togglePalette } = usePaletteStore();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);

  const filteredCommands = commands.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  const executeCommand = (command: Command) => {
    closePalette();
    onSelect(command);
  };

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    } else {
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
          e.preventDefault();
          togglePalette();
        }
        return;
      }

      if (e.key === 'Escape') closePalette();
      if (e.key === 'ArrowDown') {
        setSelectedIndex((i) => (i + 1) % filteredCommands.length);
      }
      if (e.key === 'ArrowUp') {
        setSelectedIndex((i) => (i - 1 + filteredCommands.length) % filteredCommands.length);
      }
      if (e.key === 'Enter') {
        if (filteredCommands[selectedIndex]) {
          executeCommand(filteredCommands[selectedIndex]);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, closePalette, togglePalette, filteredCommands, selectedIndex]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          className="fixed inset-0 flex items-start justify-center pt-24"
          style={{ zIndex: depth.palette }}
          onClick={closePalette}
        >
          <div
            className="w-full max-w-xl rounded-lg overflow-hidden"
            style={{
              background: glass.background,
              border: `1px solid ${glass.border}`,
              boxShadow: glass.shadow,
              backdropFilter: `blur(${glass.blur})`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              type="text"
              placeholder="Ask Zaram or type a command..."
              className="w-full bg-transparent p-4 text-lg text-neutral-200 placeholder-neutral-500 focus:outline-none"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {filteredCommands.length > 0 && (
              <div className="border-t border-white/10 p-2">
                {filteredCommands.map((command, index) => (
                  <div
                    key={command.id}
                    className={`p-2 rounded-md cursor-pointer text-sm ${
                      selectedIndex === index
                        ? 'bg-white/10 text-neutral-200'
                        : 'text-neutral-400'
                    }`}
                    onClick={() => executeCommand(command)}
                  >
                    {command.label}
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CommandPalette;