import { useRef, useState } from 'react';
import { useZaram } from '../../hooks/useZaram';

export const Knowledge = () => {
  const {
    knowledgeItems,
    addKnowledgeItem,
    deleteKnowledgeItem,
    searchKnowledge,
    searchQuery,
  } = useZaram();

  const fileInputRef = useRef(null);
  const [uploadError, setUploadError] = useState(null);

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setUploadError(null);

    for (const file of files) {
      try {
        // Validate file type
        const validTypes = [
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'text/plain',
          'application/vnd.openxmlformats-officedocument.presentationml.presentation',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'image/jpeg',
          'image/png',
          'audio/mpeg',
          'audio/wav',
        ];

        if (!validTypes.includes(file.type)) {
          throw new Error(`${file.name}: Unsupported file type`);
        }

        // Create knowledge item (actual upload will be implemented with backend)
        addKnowledgeItem({
          name: file.name,
          type: file.type,
          size: file.size,
          status: 'indexed',
        });
      } catch (error) {
        setUploadError(error.message);
      }
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const filteredItems = knowledgeItems.filter(item =>
    searchQuery === ''
      ? true
      : item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-cyan-950/30 p-6 space-y-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 mb-2">Knowledge Vault</h2>
          <p className="text-sm text-slate-400">Upload documents, images, and files for semantic search and RAG-based retrieval</p>
        </div>

        {/* Upload Area */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className="p-6 border-2 border-dashed border-cyan-500/30 rounded-lg bg-cyan-500/5 hover:bg-cyan-500/10 transition-colors cursor-pointer text-center"
        >
          <svg className="w-8 h-8 text-cyan-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm font-medium text-slate-200">Drop files or click to upload</p>
          <p className="text-xs text-slate-500 mt-1">PDF, DOCX, TXT, PPTX, XLSX, Images, Audio</p>
        </div>

        {/* Search */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search knowledge base..."
            onChange={(e) => searchKnowledge(e.target.value)}
            className="w-full px-4 py-2 pl-10 text-sm bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-100 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30"
          />
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {/* Error Message */}
        {uploadError && (
          <div className="p-3 bg-red-950/30 border border-red-500/30 rounded-lg text-red-300 text-sm">
            {uploadError}
          </div>
        )}
      </div>

      {/* Knowledge Items List */}
      <div className="flex-1 overflow-y-auto p-6 space-y-3">
        {filteredItems.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <p className="mb-2">
              {knowledgeItems.length === 0 ? 'No files uploaded yet' : 'No results found'}
            </p>
            <p className="text-xs text-slate-600">
              {knowledgeItems.length === 0 ? 'Upload documents to build your knowledge base' : 'Try a different search query'}
            </p>
          </div>
        ) : (
          filteredItems.map(item => (
            <div
              key={item.id}
              className="p-4 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:border-cyan-500/30 transition-all"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 flex-1">
                  {/* File Icon */}
                  <div className="p-2 bg-slate-700/50 rounded text-cyan-400 flex-shrink-0">
                    {item.type.includes('pdf') && '📄'}
                    {item.type.includes('word') && '📝'}
                    {item.type.includes('presentation') && '📊'}
                    {item.type.includes('spreadsheet') && '📈'}
                    {item.type.includes('image') && '🖼️'}
                    {item.type.includes('audio') && '🎵'}
                    {item.type === 'text/plain' && '📋'}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">{item.name}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-xs text-slate-500">
                        {(item.size / 1024).toFixed(1)} KB
                      </span>
                      <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-300">
                        ✓ Indexed
                      </span>
                      <span className="text-xs text-slate-500">
                        {new Date(item.uploadedAt).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Delete Button */}
                <button
                  onClick={() => deleteKnowledgeItem(item.id)}
                  className="p-2 hover:bg-red-500/20 rounded text-red-400 transition-colors flex-shrink-0"
                  title="Delete file"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={handleFileSelect}
        accept=".pdf,.docx,.txt,.pptx,.xlsx,.jpg,.jpeg,.png,.mp3,.wav"
        className="hidden"
      />
    </div>
  );
};
