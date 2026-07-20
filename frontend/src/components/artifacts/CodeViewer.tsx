import React from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

export function CodeViewer({ artifact }: { artifact: any }) {
  return (
    <SyntaxHighlighter
      style={vscDarkPlus}
      language={artifact.metadata?.language as string || 'typescript'}
      PreTag="div"
      className="rounded-lg"
    >
      {artifact.content}
    </SyntaxHighlighter>
  );
}
