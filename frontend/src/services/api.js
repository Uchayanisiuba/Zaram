const API_BASE = 'http://127.0.0.1:8000';

export const zaramAPI = {
  // Chat Endpoints
  async sendMessage(text, characterId, modelId) {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        character_id: characterId,
        brain_id: modelId,
      }),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  },

  // Get audio file
  getAudioUrl(filename) {
    return `${API_BASE}/audio/${filename}`;
  },

  // Knowledge/File Upload (placeholder for future implementation)
  async uploadFile(file, fileType) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_type', fileType);

    const response = await fetch(`${API_BASE}/knowledge/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return response.json();
  },

  // Semantic search in knowledge base (placeholder)
  async searchKnowledge(query) {
    const response = await fetch(`${API_BASE}/knowledge/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      throw new Error(`Search failed: ${response.status}`);
    }

    return response.json();
  },

  // Memory endpoints (placeholder for future backend implementation)
  async saveMemory(memory) {
    // Will be implemented when Memory Service backend is ready
    return { id: `mem_${Date.now()}`, ...memory };
  },

  async deleteMemory(memoryId) {
    // Will be implemented when Memory Service backend is ready
    return { success: true };
  },
};
