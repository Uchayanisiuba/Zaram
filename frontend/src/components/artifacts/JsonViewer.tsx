import React from 'react';

export function JsonViewer({ artifact }: { artifact: any }) {
  let parsed: any;
  try {
    parsed = JSON.parse(artifact.content);
  } catch {
    parsed = { raw: artifact.content };
  }
  return (
    <pre className="whitespace-pre-wrap font-mono text-sm text-white/80 leading-relaxed">
      {JSON.stringify(parsed, null, 2)}
    </pre>
  );
}
