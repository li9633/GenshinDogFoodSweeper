export interface AppSettings {
  scanRegion: { x: number; y: number; width: number; height: number }
  matchThreshold: number
  scanInterval: number
  autoDecompose: boolean
  autoDecomposeThreshold: number
  defaultPieces: Record<string, unknown>
}
