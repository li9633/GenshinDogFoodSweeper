import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AppSettings } from '@/types/settings'

export const useAppStore = defineStore('app', () => {
  const settings = ref<AppSettings | null>(null)
  const scanning = ref(false)

  function setSettings(newSettings: AppSettings) {
    settings.value = newSettings
  }

  function setScanning(status: boolean) {
    scanning.value = status
  }

  return {
    settings,
    scanning,
    setSettings,
    setScanning
  }
})
