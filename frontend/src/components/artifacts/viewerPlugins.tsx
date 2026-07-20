import React from 'react';
import { MarkdownViewer } from './MarkdownViewer';
import { CodeViewer } from './CodeViewer';
import { ImageViewer } from './ImageViewer';
import { PDFViewer } from './PDFViewer';
import { TextViewer } from './TextViewer';
import { JsonViewer } from './JsonViewer';
import { CsvViewer } from './CsvViewer';
import { viewerRegistry, type ArtifactViewerPlugin } from './viewerRegistry';
import type { Artifact } from '@/types/artifacts';

export const MarkdownPlugin: ArtifactViewerPlugin = {
  type: 'markdown',
  render: (artifact) => <MarkdownViewer artifact={artifact} />,
  canEdit: true,
};

export const CodePlugin: ArtifactViewerPlugin = {
  type: 'code',
  render: (artifact) => <CodeViewer artifact={artifact} />,
  canEdit: true,
};

export const ImagePlugin: ArtifactViewerPlugin = {
  type: 'image',
  render: (artifact) => <ImageViewer artifact={artifact} />,
};

export const PDFPlugin: ArtifactViewerPlugin = {
  type: 'pdf',
  render: (artifact) => <PDFViewer artifact={artifact} />,
};

export const TextPlugin: ArtifactViewerPlugin = {
  type: 'text',
  render: (artifact) => <TextViewer artifact={artifact} />,
  canEdit: true,
};

export const JsonPlugin: ArtifactViewerPlugin = {
  type: 'json',
  render: (artifact) => <JsonViewer artifact={artifact} />,
  canEdit: true,
};

export const CsvPlugin: ArtifactViewerPlugin = {
  type: 'csv',
  render: (artifact) => <CsvViewer artifact={artifact} />,
  canEdit: true,
};

export function registerDefaultViewers() {
  [MarkdownPlugin, CodePlugin, ImagePlugin, PDFPlugin, TextPlugin, JsonPlugin, CsvPlugin].forEach((plugin) => {
    viewerRegistry.register(plugin);
  });
}
