import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation, type LinkProps } from 'react-router-dom'
import { ThemeToggle } from './ThemeToggle.tsx'

export { ThemeToggle }

// ── Button ────────────────────────────────────────────────
type Variant = 'primary' | 'quiet' | 'danger'

function btnClass(variant: Variant, large?: boolean, small?: boolean, extra?: string) {
  return `btn btn-${variant}${large ? ' btn-lg' : ''}${small ? ' btn-sm' : ''}${extra ? ` ${extra}` : ''}`
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  large?: boolean
  small?: boolean
}

export function Button({ variant = 'primary', large, small, className, ...rest }: ButtonProps) {
  return <button className={btnClass(variant, large, small, className)} {...rest} />
}

export function ButtonLink({
  variant = 'primary',
  large,
  small,
  className,
  ...rest
}: LinkProps & { variant?: Variant; large?: boolean; small?: boolean }) {
  return <Link className={btnClass(variant, large, small, className)} {...rest} />
}

// ── Card ──────────────────────────────────────────────────
export function Card({
  title,
  aside,
  flat,
  children,
}: {
  title?: string
  aside?: ReactNode
  flat?: boolean
  children: ReactNode
}) {
  return (
    <section className={`card${flat ? ' card-flat' : ''}`}>
      {title && (
        <div className="card-head">
          <h2>{title}</h2>
          {aside}
        </div>
      )}
      {children}
    </section>
  )
}

// ── Page header, states ───────────────────────────────────
export function PageHead({ title, lead }: { title: string; lead?: string }) {
  return (
    <header className="page-head">
      <h1>{title}</h1>
      {lead && <p>{lead}</p>}
    </header>
  )
}

export function ErrorNotice({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : 'Algo salió mal.'
  return (
    <div className="notice" role="alert">
      {message}
    </div>
  )
}

/** One-off success message passed through router state (`navigate(to, { state: { flash } })`). */
export function Flash() {
  const flash = (useLocation().state as { flash?: string } | null)?.flash
  if (!flash) return null
  return (
    <div className="notice notice-info" role="status">
      {flash}
    </div>
  )
}

export function Loading() {
  return <div className="skeleton" aria-busy="true" aria-label="Cargando" />
}

// ── Layout ────────────────────────────────────────────────
export function Layout() {
  return (
    <div className="shell">
      <aside className="rail">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M5 13l5 5 9-12"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <span className="brand-title">Exam Study</span>
        </Link>
        <nav className="nav" aria-label="Principal">
          <NavLink to="/" end>
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="3" width="7" height="9" rx="1.5" />
              <rect x="14" y="3" width="7" height="5" rx="1.5" />
              <rect x="14" y="12" width="7" height="9" rx="1.5" />
              <rect x="3" y="16" width="7" height="5" rx="1.5" />
            </svg>
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/exams">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="8" y1="13" x2="16" y2="13" />
              <line x1="8" y1="17" x2="13" y2="17" />
            </svg>
            <span>Exámenes</span>
          </NavLink>
          <NavLink to="/questions">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>Preguntas</span>
          </NavLink>
          <NavLink to="/practice">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <span>Práctica</span>
          </NavLink>
          <NavLink to="/analytics">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="18" y1="20" x2="18" y2="10" />
              <line x1="12" y1="20" x2="12" y2="4" />
              <line x1="6" y1="20" x2="6" y2="14" />
            </svg>
            <span>Estadísticas</span>
          </NavLink>
        </nav>
        <div className="rail-foot">
          <ThemeToggle />
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}

