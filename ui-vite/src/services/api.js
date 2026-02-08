// src/services/api.js

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEFAULT_TIMEOUT_MS = 8000;

const toErrorMessage = (data, fallback) => {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  return data.detail || data.message || fallback;
};

const parseResponseBody = async (response) => {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  try {
    return await response.text();
  } catch {
    return null;
  }
};

const requestJson = async (url, options = {}, config = {}) => {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal } = config;
  const controller = new AbortController();
  let timeoutId;

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  if (timeoutMs > 0) {
    timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  }

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });

    const body = await parseResponseBody(response);

    if (!response.ok) {
      const message = toErrorMessage(body, `Request failed with status ${response.status}`);
      const error = new Error(message);
      error.status = response.status;
      error.body = body;
      throw error;
    }

    return body;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Request timed out or was cancelled');
    }
    throw error;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
};

export const analyzeProfile = async (profileData, options = {}) => {
  try {
    return await requestJson(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData)
    }, options);
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

export const getCareerRecommendations = async (processedProfile, options = {}) => {
  try {
    return await requestJson(`${API_BASE_URL}/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(processedProfile)
    }, options);
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

export const sendChatMessage = async (message, chatHistory = [], options = {}) => {
  try {
    return await requestJson(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, chatHistory })
    }, options);
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

export const getCareerLibrary = async (options = {}) => {
  try {
    return await requestJson(`${API_BASE_URL}/career-library`, {
      method: 'GET'
    }, options);
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};
