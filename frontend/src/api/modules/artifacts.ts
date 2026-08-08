import request from '@/api/request'
import type { Artifact, ArtifactQuery } from '@/types/artifact'

export function getArtifacts(params?: ArtifactQuery): Promise<Artifact[]> {
  return request.get('/artifacts', { params })
}

export function getArtifactById(id: number): Promise<Artifact> {
  return request.get(`/artifacts/${id}`)
}

export function deleteArtifact(id: number): Promise<void> {
  return request.delete(`/artifacts/${id}`)
}

export function markAsTrash(ids: number[]): Promise<void> {
  return request.put('/artifacts/mark-trash', { ids })
}

export function unmarkTrash(ids: number[]): Promise<void> {
  return request.put('/artifacts/unmark-trash', { ids })
}
