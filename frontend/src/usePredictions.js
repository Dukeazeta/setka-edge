import { useCallback, useEffect, useRef, useState } from 'react'

const POLL_MS = 60_000
const WAKE_TIMEOUT_MS = 90_000
const WAKE_RETRY_MS = 4_000

async function fetchPredictions(signal) {
  const res = await fetch('/api/predictions', { signal })
  if (!res.ok) throw new Error(`API responded ${res.status}`)
  return res.json()
}

export function usePredictions() {
  const [state, setState] = useState({
    status: 'loading',
    data: null,
    error: null,
    waking: false,
  })
  const timer = useRef(null)
  const wakeTimer = useRef(null)

  const load = useCallback(async (soft = false) => {
    if (soft) {
      try {
        const data = await fetchPredictions()
        setState((s) => ({ ...s, status: 'ready', data, error: null, waking: false }))
      } catch (err) {
        setState((s) => (s.data ? { ...s, error: err.message } : s))
      }
      return
    }

    setState({ status: 'loading', data: null, error: null, waking: true })
    const deadline = Date.now() + WAKE_TIMEOUT_MS

    while (Date.now() < deadline) {
      try {
        const data = await fetchPredictions()
        setState({ status: 'ready', data, error: null, waking: false })
        return
      } catch (err) {
        if (Date.now() + WAKE_RETRY_MS >= deadline) {
          setState({ status: 'error', data: null, error: err.message, waking: false })
          return
        }
        await new Promise((r) => {
          wakeTimer.current = setTimeout(r, WAKE_RETRY_MS)
        })
      }
    }
  }, [])

  const forceRefresh = useCallback(async () => {
    try {
      await fetch('/api/refresh', { method: 'POST' })
      setTimeout(() => load(true), 4000)
    } catch {
      /* surfaced by next poll */
    }
  }, [load])

  useEffect(() => {
    load()
    timer.current = setInterval(() => load(true), POLL_MS)
    return () => {
      clearInterval(timer.current)
      clearTimeout(wakeTimer.current)
    }
  }, [load])

  useEffect(() => {
    if (state.status !== 'ready' || !state.data?.refreshing) return
    const id = setInterval(() => load(true), 5000)
    return () => clearInterval(id)
  }, [state.status, state.data?.refreshing, load])

  return { ...state, reload: load, forceRefresh }
}
