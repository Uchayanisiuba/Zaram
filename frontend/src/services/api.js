// Relative by default so the same-origin dev proxy (Vite) and the Electron
// production static server can forward API traffic to the backend without
// cross-origin issues. Override with VITE_API_BASE when needed.
export const API_BASE =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE) || '';

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

  async deleteMemory() {
    // Will be implemented when Memory Service backend is ready
    return { success: true };
  },

  // Artifact endpoints
  async listArtifacts(filters = {}) {
    const params = new URLSearchParams();
    if (filters.type) params.set('type', filters.type);
    if (filters.pinned !== undefined) params.set('pinned', String(filters.pinned));
    if (filters.search) params.set('search', filters.search);
    const response = await fetch(`${API_BASE}/artifacts?${params}`);
    if (!response.ok) throw new Error(`List artifacts failed: ${response.status}`);
    return response.json();
  },

  async getArtifact(id) {
    const response = await fetch(`${API_BASE}/artifacts/${id}`);
    if (!response.ok) throw new Error(`Get artifact failed: ${response.status}`);
    return response.json();
  },

  async createArtifact(data) {
    const response = await fetch(`${API_BASE}/artifacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error(`Create artifact failed: ${response.status}`);
    return response.json();
  },

  async updateArtifact(id, data) {
    const response = await fetch(`${API_BASE}/artifacts/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error(`Update artifact failed: ${response.status}`);
    return response.json();
  },

  async deleteArtifact(id) {
    const response = await fetch(`${API_BASE}/artifacts/${id}`, { method: 'DELETE' });
    if (!response.ok) throw new Error(`Delete artifact failed: ${response.status}`);
    return response.json();
  },

  async duplicateArtifact(id) {
    const response = await fetch(`${API_BASE}/artifacts/${id}/duplicate`, { method: 'POST' });
    if (!response.ok) throw new Error(`Duplicate artifact failed: ${response.status}`);
    return response.json();
  },

  async saveArtifactVersion(id) {
    const response = await fetch(`${API_BASE}/artifacts/${id}/versions/save`, { method: 'POST' });
    if (!response.ok) throw new Error(`Save version failed: ${response.status}`);
    return response.json();
  },

  async revertArtifactVersion(id, versionId) {
    const response = await fetch(`${API_BASE}/artifacts/${id}/versions/revert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version_id: versionId }),
    });
    if (!response.ok) throw new Error(`Revert version failed: ${response.status}`);
    return response.json();
  },

  async getArtifactStats() {
    const response = await fetch(`${API_BASE}/artifacts/stats/summary`);
    if (!response.ok) throw new Error(`Get stats failed: ${response.status}`);
    return response.json();
  },
};
