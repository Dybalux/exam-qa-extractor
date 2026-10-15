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
    <div className="notice notice-info" role="status" style={{ marginBottom: 'var(--s-5)' }}>
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
          <span>Exam Study</span>
        </Link>
        <nav className="nav" aria-label="Principal">
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/exams">Exámenes</NavLink>
          <NavLink to="/questions">Preguntas</NavLink>
          <NavLink to="/practice">Práctica</NavLink>
          <NavLink to="/analytics">Estadísticas</NavLink>
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
