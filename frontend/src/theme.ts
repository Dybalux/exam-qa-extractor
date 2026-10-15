import { useState, useEffect, useCallback } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'theme'

export function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function getSavedPreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'light' || saved === 'dark' || saved === 'system') {
      return saved
    }
  } catch {
    // Ignore storage errors (e.g. sandboxed iframe or private mode)
  }
  return 'system'
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === 'system') {
    return getSystemTheme()
  }
  return preference
}

export function applyTheme(preference: ThemePreference): ResolvedTheme {
  const resolved = resolveTheme(preference)
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', resolved)
    document.documentElement.setAttribute('data-theme-preference', preference)
  }
  return resolved
}

export function useTheme() {
  const [preference, setPreferenceState] = useState<ThemePreference>(getSavedPreference)
  const [systemDark, setSystemDark] = useState<boolean>(() =>
    typeof window !== 'undefined'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
      : false,
  )

  const resolvedTheme: ResolvedTheme =
    preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  const setPreference = useCallback((newPref: ThemePreference) => {
    setPreferenceState(newPref)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, newPref)
    } catch {
      // Ignore storage errors
    }
    applyTheme(newPref)
  }, [])

  const toggleTheme = useCallback(() => {
    const next: ThemePreference = resolvedTheme === 'dark' ? 'light' : 'dark'
    setPreference(next)
  }, [resolvedTheme, setPreference])

  useEffect(() => {
    applyTheme(preference)
  }, [preference])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => {
      setSystemDark(e.matches)
    }
    media.addEventListener('change', handler)
    return () => media.removeEventListener('change', handler)
  }, [])

  return {
    preference,
    theme: resolvedTheme,
    resolvedTheme,
    setPreference,
    setTheme: setPreference,
    toggleTheme,
  }
}
