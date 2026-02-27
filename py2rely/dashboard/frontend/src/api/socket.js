export function createSocket(onMessage, onStatusChange) {
  let ws = null
  let retryDelay = 1000
  let stopped = false

  function connect() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${window.location.host}/ws`)

    ws.onopen = () => {
      retryDelay = 1000
      onStatusChange('connected')
    }

    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)) } catch (_) {}
    }

    ws.onclose = () => {
      onStatusChange('disconnected')
      if (!stopped) {
        setTimeout(connect, retryDelay)
        retryDelay = Math.min(retryDelay * 2, 30000)
      }
    }

    ws.onerror = () => onStatusChange('error')
  }

  connect()
  return { close() { stopped = true; ws?.close() } }
}
