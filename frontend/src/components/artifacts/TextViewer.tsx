import React from 'react';

export function TextViewer({ artifact }: { artifact: any }) {
  return (
    <pre className="whitespace-pre-wrap font-mono text-sm text-white/80 leading-relaxed">
      {artifact.content}
    </pre>
  );
}
