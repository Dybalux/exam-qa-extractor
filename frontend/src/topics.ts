import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type TopicOption } from './api.ts'

/** Builds a lookup function that resolves a topic slug to its display name. */
export function createTopicLookup(topics?: TopicOption[]): (slug: string) => string {
  const map = new Map((topics ?? []).map((t) => [t.slug, t.name]))
  return (slug: string) => map.get(slug) ?? slug
}

/**
 * Shared cached lookup for resolving topic slugs (e.g. `scheduling`) to
 * human-readable names (e.g. `Planificación de CPU`) across all views.
 */
export function useTopicLabel(): (slug: string) => string {
  const { data } = useQuery({
    queryKey: ['topics'],
    queryFn: api.topics,
    staleTime: 5 * 60_000,
  })
  return useMemo(() => createTopicLookup(data), [data])
}
