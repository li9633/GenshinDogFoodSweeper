export interface Artifact {
  id: number
  artifactKey: string
  artifactName: string
  pieceType: 'flower' | 'plume' | 'sands' | 'goblet' | 'circlet'
  level: number
  rarity: 4 | 5
  mainStat: string
  mainStatValue: number
  subStat1?: string
  subStat1Value?: number
  subStat2?: string
  subStat2Value?: number
  subStat3?: string
  subStat3Value?: number
  subStat4?: string
  subStat4Value?: number
  isLocked: boolean
  isMarkedTrash: boolean
  score: number
  scannedAt: string
  iconPath?: string
}

export interface ArtifactQuery {
  page?: number
  pageSize?: number
  pieceType?: string
  rarity?: number
  setKey?: string
  minScore?: number
  isMarkedTrash?: boolean
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  keyword?: string
}

export interface ArtifactSet {
  key: string
  name: string
  iconPath: string
  description: string
  bonus2pc: string
  bonus4pc: string
}
