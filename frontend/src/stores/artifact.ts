import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Artifact } from '@/types/artifact'
import { getArtifacts } from '@/api/modules/artifacts'

export const useArtifactStore = defineStore('artifact', () => {
  const artifacts = ref<Artifact[]>([])
  const loading = ref(false)
  const total = ref(0)

  async function fetchList(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const data = await getArtifacts(params as never)
      artifacts.value = data || []
      total.value = artifacts.value.length
    } finally {
      loading.value = false
    }
  }

  return {
    artifacts,
    loading,
    total,
    fetchList
  }
})
