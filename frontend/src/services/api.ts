// Use environment variable for API URL, fallback to localhost
const BASE_URL = (import.meta as any).env.VITE_AUTH_API_URL || 'http://localhost:8001';

async function handleResponse(res: Response) {
  if (!res.ok) {
    let errorMessage = 'An error occurred';
    try {
      const errorData = await res.json();
      let detail = errorData.detail || errorData.message || errorData;
      if (typeof detail === 'object') {
        errorMessage = JSON.stringify(detail);
      } else {
        errorMessage = String(detail);
      }
    } catch {
      errorMessage = await res.text() || `HTTP ${res.status}: ${res.statusText}`;
    }
    throw new Error(errorMessage);
  }
  try {
    return await res.json();
  } catch {
    throw new Error('Invalid response from server');
  }
}

export const api = {
  async register(username: string, password: string) {
    const res = await fetch(`${BASE_URL}/api/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    return handleResponse(res);
  },

  async login(username: string, password: string) {
    const res = await fetch(`${BASE_URL}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    return handleResponse(res);
  },

  async uploadImage(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    
    const res = await fetch(`${BASE_URL}/api/upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: formData,
    });
    return handleResponse(res);
  },

  async getWardrobe() {
    const res = await fetch(`${BASE_URL}/api/wardrobe`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
    });
    return handleResponse(res);
  },

  async deleteItem(itemId: string | number) {
    const res = await fetch(`${BASE_URL}/api/wardrobe/${itemId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
    });
    return handleResponse(res);
  },

  async suggest(prompt: string, skin_tone?: string, body_shape?: string) {
    const res = await fetch(`${BASE_URL}/api/suggest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ prompt, skin_tone, body_shape }),
    });
    return handleResponse(res);
  },

  async getProfile() {
    const res = await fetch(`${BASE_URL}/api/profile`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
    });
    return handleResponse(res);
  },

  async updateProfile(body_shape?: string, skin_tone?: string, profile_picture?: File) {
    const formData = new FormData();
    if (body_shape) formData.append('body_shape', body_shape);
    if (skin_tone) formData.append('skin_tone', skin_tone);
    if (profile_picture) formData.append('profile_picture', profile_picture);

    const res = await fetch(`${BASE_URL}/api/profile`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: formData,
    });
    return handleResponse(res);
  },

  async updateWardrobeItem(itemId: string, category: string, formality: string, fit: string) {
    const res = await fetch(`${BASE_URL}/api/wardrobe/${itemId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ category, formality, fit }),
    });
    return handleResponse(res);
  },

  async getHistory() {
    const res = await fetch(`${BASE_URL}/api/history`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
    });
    return handleResponse(res);
  },

  async deleteHistoryItem(comboId: string) {
    const res = await fetch(`${BASE_URL}/api/history/${comboId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
    });
    return handleResponse(res);
  }
};
