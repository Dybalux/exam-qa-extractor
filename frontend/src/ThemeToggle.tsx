import { useTheme } from './theme.ts'

export function SunIcon({ size = 18, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  )
}

export function MoonIcon({ size = 18, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  )
}

export function ThemeToggle({ className }: { className?: string }) {
  const { preference, resolvedTheme, toggleTheme, setPreference } = useTheme()
  const isDark = resolvedTheme === 'dark'
  const isSystem = preference === 'system'

  return (
    <div className={`theme-switch${className ? ` ${className}` : ''}`} role="group" aria-label="Selector de tema">
      <button
        type="button"
        className="theme-toggle"
        onClick={toggleTheme}
        aria-label={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
        title={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
      >
        <span className="theme-toggle-icon" aria-hidden="true">
          {isDark ? <MoonIcon /> : <SunIcon />}
        </span>
        <span className="theme-toggle-text">
          {isDark ? 'Modo oscuro' : 'Modo claro'}
        </span>
      </button>

      <button
        type="button"
        className={`theme-auto-pill${isSystem ? ' is-active' : ''}`}
        onClick={() => setPreference('system')}
        aria-label="Usar tema del sistema"
        title={isSystem ? 'Sincronizado con el sistema' : 'Usar tema del sistema'}
      >
        Auto
      </button>
    </div>
  )
}
