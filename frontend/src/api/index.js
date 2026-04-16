import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

// Auth
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
}

// Tasks
export const tasksAPI = {
  list: (params) => api.get('/tasks', { params }),
  create: (data) => api.post('/tasks', data),
  get: (id) => api.get(`/tasks/${id}`),
  delete: (id) => api.delete(`/tasks/${id}`),
  regenerate: (id) => api.post(`/tasks/${id}/regenerate`),
}

// Files
export const filesAPI = {
  download: (resultId) => api.get(`/files/${resultId}/download`, { responseType: 'blob' }),
  preview: (resultId) => api.get(`/files/${resultId}/preview`),
}

// Admin
export const adminAPI = {
  stats: () => api.get('/admin/stats'),
  // LLM Configs
  getLLMConfigs: () => api.get('/admin/llm-configs'),
  createLLMConfig: (data) => api.post('/admin/llm-configs', data),
  updateLLMConfig: (id, data) => api.put(`/admin/llm-configs/${id}`, data),
  deleteLLMConfig: (id) => api.delete(`/admin/llm-configs/${id}`),
  // Knowledge
  getKnowledge: (agent_type) => api.get('/admin/knowledge', { params: { agent_type } }),
  createKnowledge: (data) => api.post('/admin/knowledge', data),
  updateKnowledge: (id, data) => api.put(`/admin/knowledge/${id}`, data),
  deleteKnowledge: (id) => api.delete(`/admin/knowledge/${id}`),
  // Users
  getUsers: () => api.get('/admin/users'),
  updateUserCredits: (id, data) => api.put(`/admin/users/${id}/credits`, data),
  updateUserStatus: (id, data) => api.put(`/admin/users/${id}/status`, data),
  getTasks: (params) => api.get('/admin/tasks', { params }),
  // Token Usage
  getTokenUsage: (params) => api.get('/admin/token-usage', { params }),
  getTokenUsageSummary: (params) => api.get('/admin/token-usage/summary', { params }),
  getTokenUsageFilters: () => api.get('/admin/token-usage/filters'),
  // PPT Provider
  getPPTProvider: () => api.get('/admin/ppt-provider'),
  savePPTProvider: (data) => api.put('/admin/ppt-provider', data),
  testPPTProvider: (provider) => api.post(
    '/admin/ppt-provider/test',
    { provider },
    { timeout: 330000 },   // Gamma can take 1-5 min to render
  ),
}

// Agents meta
export const agentsAPI = {
  list: () => api.get('/agents'),
}

export default api
