import React from 'react';
import { Markdown } from '@/components/common/Markdown';

export function MarkdownViewer({ artifact }: { artifact: any }) {
  return <Markdown content={artifact.content} />;
}
