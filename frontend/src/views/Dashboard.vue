<template>
  <div class="dashboard">
    <!-- 顶部统计卡片 -->
    <el-row
      :gutter="16"
      class="stats-row"
    >
      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card
          shadow="hover"
          class="stat-card"
        >
          <div class="stat-item">
            <font-awesome-icon
              icon="fa-solid fa-gem"
              class="stat-icon total"
            />
            <div class="stat-info">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">圣遗物总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card
          shadow="hover"
          class="stat-card"
        >
          <div class="stat-item">
            <font-awesome-icon
              icon="fa-solid fa-star"
              class="stat-icon five-star"
            />
            <div class="stat-info">
              <div class="stat-value">{{ stats.fiveStar }}</div>
              <div class="stat-label">5 星数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card
          shadow="hover"
          class="stat-card"
        >
          <div class="stat-item">
            <font-awesome-icon
              icon="fa-solid fa-star-half-stroke"
              class="stat-icon four-star"
            />
            <div class="stat-info">
              <div class="stat-value">{{ stats.fourStar }}</div>
              <div class="stat-label">4 星数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card
          shadow="hover"
          class="stat-card"
        >
          <div class="stat-item">
            <font-awesome-icon
              icon="fa-solid fa-chart-line"
              class="stat-icon score"
            />
            <div class="stat-info">
              <div class="stat-value">{{ stats.avgScore }}</div>
              <div class="stat-label">平均评分</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 扫描状态 -->
    <el-card
      class="scan-status-card"
      v-if="appStore.scanning || scanStatus !== 'idle'"
    >
      <template #header>
        <div class="card-header">
          <span>扫描状态</span>
          <el-tag :type="scanStatus === 'running' ? 'warning' : 'info'">
            {{ scanStatus === 'running' ? '扫描中' : '已停止' }}
          </el-tag>
        </div>
      </template>
      <el-progress
        :percentage="progress"
        :status="scanStatus === 'running' ? undefined : 'success'"
      />
    </el-card>

    <!-- 快速操作 -->
    <el-card class="quick-actions">
      <template #header>
        <span>快速操作</span>
      </template>
      <el-row :gutter="16">
        <el-col :span="8">
          <el-button
            type="primary"
            size="large"
            class="action-btn"
          >
            <font-awesome-icon
              icon="fa-solid fa-play"
              class="mr-8"
            />
            开始扫描
          </el-button>
        </el-col>
        <el-col :span="8">
          <el-button
            type="danger"
            size="large"
            class="action-btn"
          >
            <font-awesome-icon
              icon="fa-solid fa-trash"
              class="mr-8"
            />
            批量分解
          </el-button>
        </el-col>
        <el-col :span="8">
          <el-button
            size="large"
            class="action-btn"
          >
            <font-awesome-icon
              icon="fa-solid fa-filter"
              class="mr-8"
            />
            筛选优质
          </el-button>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import type { Artifact } from '@/types/artifact'
  import { getScanStatus } from '@/api/modules/scan'
  import { useArtifactStore } from '@/stores/artifact'
  import { useAppStore } from '@/stores/app'
  import { library } from '@fortawesome/fontawesome-svg-core'
  import {
    faChartLine,
    faFilter,
    faGem,
    faPlay,
    faStar,
    faStarHalfStroke,
    faTrash
  } from '@fortawesome/free-solid-svg-icons'

  library.add(faChartLine, faFilter, faGem, faPlay, faStar, faStarHalfStroke, faTrash)

  defineOptions({ name: 'DashboardPage' })

  const artifactStore = useArtifactStore()
  const appStore = useAppStore()

  const scanStatus = ref('idle')
  const progress = ref(0)

  const stats = computed(() => {
    const artifacts = artifactStore.artifacts as Artifact[]
    const total = artifacts.length
    const fiveStar = artifacts.filter((a) => a.rarity === 5).length
    const fourStar = artifacts.filter((a) => a.rarity === 4).length
    const avgScore =
      total > 0 ? (artifacts.reduce((sum, a) => sum + a.score, 0) / total).toFixed(1) : '0.0'
    return { total, fiveStar, fourStar, avgScore }
  })

  onMounted(async () => {
    try {
      await artifactStore.fetchList()
      const status = await getScanStatus()
      scanStatus.value = status.status
      progress.value = status.progress
      appStore.setScanning(status.status === 'running')
    } catch {
      // 后端未启动时忽略错误
    }
  })
</script>

<style lang="scss" scoped>
  .dashboard {
    .stats-row {
      margin-bottom: var(--space-5, 24px);
    }

    .stat-card {
      :deep(.el-card__body) {
        padding: var(--space-4, 16px) var(--space-5, 24px);
      }

      .stat-item {
        display: flex;
        align-items: center;
        gap: var(--space-4, 16px);
      }

      .stat-icon {
        font-size: 36px;
        width: 56px;
        height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: var(--radius-md, 8px);
      }

      .total {
        color: var(--color-accent, #C9A96E);
        background-color: rgba(201, 169, 110, 0.12);
      }

      .five-star {
        color: var(--color-rarity-5, #F59E0B);
        background-color: var(--color-rarity-5-bg, rgba(245, 158, 11, 0.15));
      }

      .four-star {
        color: var(--color-rarity-4, #A855F7);
        background-color: var(--color-rarity-4-bg, rgba(168, 85, 247, 0.15));
      }

      .score {
        color: var(--color-success, #66BB6A);
        background-color: rgba(102, 187, 106, 0.12);
      }

      .stat-info {
        .stat-value {
          font-family: var(--font-display);
          font-size: var(--font-size-display);
          font-weight: 700;
          color: var(--color-text-primary, #F0EDE5);
          line-height: 1.2;
        }

        .stat-label {
          font-family: var(--font-sans);
          font-size: var(--font-size-caption);
          color: var(--color-text-secondary, #B8B5C0);
          margin-top: var(--space-1, 4px);
        }
      }
    }

    .scan-status-card {
      margin-bottom: var(--space-5, 24px);

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
    }

    .quick-actions {
      .action-btn {
        width: 100%;
        font-family: var(--font-sans);
        font-weight: 500;

        .mr-8 {
          margin-right: var(--space-2, 8px);
        }
      }
    }
  }
</style>