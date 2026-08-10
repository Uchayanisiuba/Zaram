import React from 'react';
import { glass } from '@/theme/glass';

interface CommandInputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const CommandInput: React.FC<CommandInputProps> = (props) => {
  return (
    <input
      {...props}
      style={{
        ...props.style,
        background: glass.background,
        border: `1px solid ${glass.border}`,
        borderRadius: '8px',
        padding: '12px 16px',
        width: '100%',
        color: 'white',
        fontSize: '16px',
        boxShadow: glass.shadow,
        backdropFilter: `blur(${glass.blur})`,
      }}
    />
  );
};

export default CommandInput;