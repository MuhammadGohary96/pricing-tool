import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(sessionStorage.getItem('bf_access_token') || null)
  const user = ref(JSON.parse(sessionStorage.getItem('bf_user') || 'null'))
  const error = ref(null)

  const isAuthenticated = computed(() => !!user.value)
  const isDevMode = computed(() => !GOOGLE_CLIENT_ID)

  let tokenClient = null

  function initGoogleAuth() {
    if (!GOOGLE_CLIENT_ID) {
      error.value = 'VITE_GOOGLE_CLIENT_ID is not set. Add it to frontend/.env'
      return false
    }
    if (!window.google?.accounts?.oauth2) {
      error.value = 'Google Sign-In script not loaded. Check your internet connection.'
      return false
    }
    tokenClient = window.google.accounts.oauth2.initTokenClient({
      client_id: GOOGLE_CLIENT_ID,
      scope: 'email profile',
      callback: handleTokenResponse,
      error_callback: (err) => {
        error.value = err.message || 'Google Sign-In popup was closed or blocked.'
      },
    })
    return true
  }

  function login() {
    error.value = null
    if (!tokenClient) {
      if (!initGoogleAuth()) return
    }
    try {
      tokenClient.requestAccessToken()
    } catch (err) {
      error.value = `Google Sign-In failed: ${err.message}`
    }
  }

  function devLogin(email) {
    if (!email || !email.endsWith('@breadfast.com')) {
      error.value = 'Only @breadfast.com emails allowed'
      return
    }
    accessToken.value = null
    user.value = {
      email,
      name: email.split('@')[0],
      picture: null,
    }
    sessionStorage.setItem('bf_user', JSON.stringify(user.value))
    error.value = null
  }

  async function handleTokenResponse(response) {
    if (response.error) {
      error.value = response.error_description || response.error
      return
    }

    const token = response.access_token
    // Fetch user info from Google
    try {
      const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        error.value = 'Failed to fetch Google user info'
        return
      }
      const info = await res.json()

      // Validate @breadfast.com domain
      if (!info.email?.endsWith('@breadfast.com')) {
        error.value = `Access restricted to @breadfast.com accounts. Got: ${info.email}`
        // Revoke the token
        window.google.accounts.oauth2.revoke(token)
        return
      }

      accessToken.value = token
      user.value = {
        email: info.email,
        name: info.name || info.email.split('@')[0],
        picture: info.picture || null,
      }

      // Persist to sessionStorage
      sessionStorage.setItem('bf_access_token', token)
      sessionStorage.setItem('bf_user', JSON.stringify(user.value))
      error.value = null
    } catch (err) {
      error.value = 'Failed to verify Google account'
      console.error('[Auth]', err)
    }
  }

  function logout() {
    if (accessToken.value) {
      try {
        window.google?.accounts?.oauth2?.revoke(accessToken.value)
      } catch {}
    }
    accessToken.value = null
    user.value = null
    sessionStorage.removeItem('bf_access_token')
    sessionStorage.removeItem('bf_user')
  }

  // Silent token refresh (access tokens expire in ~1 hour)
  function refreshToken() {
    if (tokenClient) {
      tokenClient.requestAccessToken({ prompt: '' })
    }
  }

  return {
    accessToken,
    user,
    error,
    isAuthenticated,
    isDevMode,
    initGoogleAuth,
    login,
    devLogin,
    logout,
    refreshToken,
  }
})
