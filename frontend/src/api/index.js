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
  // Username + password (legacy / backup)
  login:    (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me:       () => api.get('/auth/me'),
  updateMyProfile: (data) => api.put('/auth/me/profile', data),

  // Public config — which tabs to show
  getPublicConfig: () => api.get('/auth/config/public'),

  // OTP delivery (used before email/phone register or login)
  sendOtp: (data) => api.post('/auth/otp/send', data),

  // Email OTP flow
  registerEmail:  (data) => api.post('/auth/register/email', data),
  loginEmailOtp:  (data) => api.post('/auth/login/email-otp', data),

  // Phone SMS flow
  registerPhone:  (data) => api.post('/auth/register/phone', data),
  loginPhoneOtp:  (data) => api.post('/auth/login/phone-otp', data),

  // Google OAuth
  googleAuthUrl:  () => api.get('/auth/google/url'),
  googleCallback: (data) => api.post('/auth/google/callback', data),
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
  // Build a direct browser-download URL with the JWT as a query parameter.
  // This lets the browser handle the transfer natively — no timeout, native
  // progress bar, no memory overhead, resumable via Range. Best for files >10MB.
  downloadUrl: (resultId) => {
    const token = localStorage.getItem('token') || ''
    return `/api/files/${resultId}/download?token=${encodeURIComponent(token)}`
  },
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
  uploadKnowledge: (formData, agentType) => api.post(`/admin/knowledge/upload?agent_type=${encodeURIComponent(agentType || 'strategy')}`, formData, { timeout: 120000, headers: { 'Content-Type': 'multipart/form-data' } }),
  importSeedKnowledge: () => api.post('/admin/knowledge/import-seed', {}, { timeout: 60000 }),
  getKnowledgeStats: () => api.get('/admin/knowledge/stats'),
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
  // Logo Provider
  getLogoProvider: () => api.get('/admin/logo-provider'),
  saveLogoProvider: (data) => api.put('/admin/logo-provider', data),
  testLogoProvider: (provider) => api.post(
    '/admin/logo-provider/test',
    { provider },
    { timeout: 120000 },
  ),

  // Poster Provider
  getPosterProvider: () => api.get('/admin/poster-provider'),
  savePosterProvider: (data) => api.put('/admin/poster-provider', data),
  testPosterProvider: (provider) => api.post(
    '/admin/poster-provider/test',
    { provider },
    { timeout: 300000 },  // FLUX can take 1-2min
  ),

  // ─── Auth / Registration policy (admin) ───
  getAuthConfig:      () => api.get('/admin/auth/config'),
  saveAuthConfig:     (data) => api.put('/admin/auth/config', data),
  getSmsProvider:     () => api.get('/admin/auth/sms-provider'),
  saveSmsProvider:    (data) => api.put('/admin/auth/sms-provider', data),
  testSmsProvider:    (target) => api.post('/admin/auth/sms-provider/test', { target }, { timeout: 30000 }),
  getEmailProvider:   () => api.get('/admin/auth/email-provider'),
  saveEmailProvider:  (data) => api.put('/admin/auth/email-provider', data),
  testEmailProvider:  (target) => api.post('/admin/auth/email-provider/test', { target }, { timeout: 60000 }),
  getGoogleOAuth:     () => api.get('/admin/auth/google-oauth'),
  saveGoogleOAuth:    (data) => api.put('/admin/auth/google-oauth', data),

  // User approval
  getPendingUsers:    () => api.get('/admin/users/pending'),
  approveUser:        (id) => api.post(`/admin/users/${id}/approve`),
  rejectUser:         (id) => api.post(`/admin/users/${id}/reject`),
  getUserDetail:      (id) => api.get(`/admin/users/${id}`),
  updateUserProfile:  (id, data) => api.put(`/admin/users/${id}/profile`, data),
  adjustUserTier:     (id, data) => api.put(`/admin/users/${id}/tier`, data),

  // ─── Membership plans + config ───
  getPlans:             () => api.get('/admin/membership/plans'),
  createPlan:           (data) => api.post('/admin/membership/plans', data),
  updatePlan:           (id, data) => api.put(`/admin/membership/plans/${id}`, data),
  deletePlan:           (id) => api.delete(`/admin/membership/plans/${id}`),
  getMembershipConfig:  () => api.get('/admin/membership/config'),
  saveMembershipConfig: (data) => api.put('/admin/membership/config', data),

  // ─── Credits cost config ───
  getCreditsConfig:   () => api.get('/admin/credits-config'),
  saveCreditsConfig:  (data) => api.put('/admin/credits-config', data),

  // ─── Payment orders + providers ───
  getOrders:            (status) => api.get('/admin/payment/orders', { params: status ? { status } : {} }),
  confirmOrder:         (orderNo) => api.post(`/admin/payment/orders/${orderNo}/confirm`),
  refundOrder:          (orderNo, notes) => api.post(`/admin/payment/orders/${orderNo}/refund`, { notes: notes || '' }),
  cancelOrderAdmin:     (orderNo) => api.post(`/admin/payment/orders/${orderNo}/cancel`),
  getPaymentProviders:  () => api.get('/admin/payment/providers'),
  savePaymentProviders: (data) => api.put('/admin/payment/providers', data),
}

// Logo
export const logoAPI = {
  generate: (data) => api.post('/logo/generate', data),
  progressUrl: (id, token) => `/api/logo/progress/${id}?token=${token}`,
  // Browser-native download URL (JWT in query string, no timeout)
  downloadUrl: (id, format) => {
    const token = localStorage.getItem('token') || ''
    return `/api/logo/download/${id}?format=${encodeURIComponent(format)}&token=${encodeURIComponent(token)}`
  },
}

// Poster
export const posterAPI = {
  generate:    (data) => api.post('/poster/generate', data),
  progressUrl: (id, token) => `/api/poster/progress/${id}?token=${token}`,
  downloadUrl: (id) => {
    const token = localStorage.getItem('token') || ''
    return `/api/poster/download/${id}?token=${encodeURIComponent(token)}`
  },
  fileUrl: (fname) => `/api${fname.startsWith('/') ? fname : '/poster/file/' + fname}`,
  history: (page = 1, page_size = 10) => api.get('/poster/history', { params: { page, page_size } }),
}

// Agents meta
export const agentsAPI = {
  list: () => api.get('/agents'),
}

// Membership (user-facing)
export const membershipAPI = {
  plans:        () => api.get('/membership/plans'),
  me:           () => api.get('/membership/me'),
  publicConfig: () => api.get('/membership/config/public'),
}

// Payment (user-facing)
export const paymentAPI = {
  createOrder:    (data) => api.post('/payment/orders', data),
  myOrders:       () => api.get('/payment/orders'),
  getOrder:       (orderNo) => api.get(`/payment/orders/${orderNo}`),
  cancelOrder:    (orderNo) => api.post(`/payment/orders/${orderNo}/cancel`),
  markPaying:     (orderNo) => api.post(`/payment/orders/${orderNo}/mark-paying`),
  publicChannels: () => api.get('/payment/channels/public'),
}

export default api
