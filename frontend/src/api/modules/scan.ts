import request from '@/api/request'

export function startScan(): Promise<void> {
  return request.post('/scan/start')
}

export function stopScan(): Promise<void> {
  return request.post('/scan/stop')
}

export function getScanStatus(): Promise<{ status: string; progress: number }> {
  return request.get('/scan/status')
}
