import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { Snapshot } from './types'

/** Live snapshot over WebSocket, with polling as a fallback when the socket is down. */
export function useSnapshot() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [connected, setConnected] = useState(false)
  const socket = useRef<WebSocket | null>(null)

  const refresh = useCallback(async () => {
    try {
      setSnapshot(await api.snapshot())
    } catch {
      /* backend not up yet */
    }
  }, [])

  useEffect(() => {
    let closed = false
    let retry: ReturnType<typeof setTimeout>
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws`)
      socket.current = ws
      ws.onopen = () => setConnected(true)
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'snapshot') setSnapshot(msg.data)
      }
      ws.onclose = () => {
        setConnected(false)
        if (!closed) retry = setTimeout(connect, 1500)
      }
    }
    connect()
    const poll = setInterval(() => {
      if (socket.current?.readyState !== WebSocket.OPEN) refresh()
    }, 3000)
    refresh()
    return () => {
      closed = true
      clearTimeout(retry)
      clearInterval(poll)
      socket.current?.close()
    }
  }, [refresh])

  return { snapshot, connected, refresh }
}
