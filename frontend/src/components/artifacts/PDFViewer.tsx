import React from 'react';

export function PDFViewer({ artifact }: { artifact: any }) {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="w-full max-w-2xl h-[80vh] rounded-lg border border-white/10 overflow-hidden">
        <iframe
          src={artifact.content}
          title={artifact.name}
          className="w-full h-full"
        />
      </div>
    </div>
  );
}
