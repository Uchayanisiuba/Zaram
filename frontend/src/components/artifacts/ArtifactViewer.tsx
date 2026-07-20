import React from 'react';
import { motion } from 'framer-motion';
import { useArtifactStore } from '@/stores/artifactStore';
import { viewerRegistry } from './viewerRegistry';
import { Markdown } from '@/components/common/Markdown';
import type { Artifact } from '@/types/artifacts';

function downloadContent(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ArtifactViewer() {
  const openArtifactId = useArtifactStore((s) => s.openArtifactId);
  const artifacts = useArtifactStore((s) => s.artifacts);
  const closeArtifact = useArtifactStore((s) => s.closeArtifact);

  const artifact = openArtifactId ? artifacts.get(openArtifactId) : null;

  if (!artifact) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-white/50">
        <p className="text-sm">No artifact open</p>
        <p className="text-xs mt-1">Select an artifact to view</p>
      </div>
    );
  }

  const plugin = viewerRegistry.get(artifact.type);
  if (!plugin) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-white/50">
        <p className="text-sm">No viewer for type: {artifact.type}</p>
      </div>
    );
  }

  const handleDownload = () => {
    const extMap: Record<string, string> = {
      text: 'txt',
      markdown: 'md',
      code: 'txt',
      image: 'png',
      pdf: 'pdf',
      csv: 'csv',
      json: 'json',
      html: 'html',
      audio: 'mp3',
      video: 'mp4',
    };
    const mimeMap: Record<string, string> = {
      text: 'text/plain',
      markdown: 'text/markdown',
      code: 'text/plain',
      image: 'image/png',
      pdf: 'application/pdf',
      csv: 'text/csv',
      json: 'application/json',
      html: 'text/html',
      audio: 'audio/mpeg',
      video: 'video/mp4',
    };
    downloadContent(
      artifact.content,
      `${artifact.name}.${extMap[artifact.type] || 'txt'}`,
      mimeMap[artifact.type] || 'text/plain'
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col h-full"
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium truncate max-w-xs">{artifact.name}</h3>
          <span className="text-xs text-white/40 uppercase tracking-wider">{artifact.type}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleDownload}
            className="p-1.5 rounded hover:bg-white/10 text-white/60 hover:text-white"
            title="Download"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
          <button
            onClick={closeArtifact}
            className="p-1.5 rounded hover:bg-white/10 text-white/60 hover:text-white"
            title="Close"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {plugin.render(artifact)}
      </div>
    </motion.div>
  );
}
