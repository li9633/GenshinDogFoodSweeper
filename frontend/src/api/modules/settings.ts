import request from '@/api/request'
import type { AppSettings } from '@/types/settings'

export function getSettings(): Promise<AppSettings> {
  return request.get('/settings')
}

export function updateSettings(data: Partial<AppSettings>): Promise<AppSettings> {
  return request.put('/settings', data)
}
