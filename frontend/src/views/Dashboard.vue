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
      margin-bottom: 20px;
    }

    .stat-card {
      :deep(.el-card__body) {
        padding: 16px 20px;
      }

      .stat-item {
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .stat-icon {
        font-size: 36px;
        width: 56px;
        height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
      }

      .total {
        color: var(--el-color-primary);
        background-color: rgba(64, 158, 255, 0.1);
      }

      .five-star {
        color: #ffb700;
        background-color: rgba(255, 183, 0, 0.1);
      }

      .four-star {
        color: #9c27b0;
        background-color: rgba(156, 39, 176, 0.1);
      }

      .score {
        color: var(--el-color-success);
        background-color: rgba(103, 194, 58, 0.1);
      }

      .stat-info {
        .stat-value {
          font-size: 28px;
          font-weight: 700;
          color: var(--el-text-color-primary);
          line-height: 1.2;
        }

        .stat-label {
          font-size: 13px;
          color: var(--el-text-color-secondary);
          margin-top: 4px;
        }
      }
    }

    .scan-status-card {
      margin-bottom: 20px;

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
    }

    .quick-actions {
      .action-btn {
        width: 100%;

        .mr-8 {
          margin-right: 8px;
        }
      }
    }
  }
</style>
