<template>
  <div class="artifact-list">
    <!-- 筛选区 -->
    <el-card class="filter-card">
      <el-form
        :inline="true"
        :model="{ keyword: searchKeyword }"
      >
        <el-form-item label="关键词">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索套装名称"
            clearable
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="星级">
          <el-select
            v-model="filterRarity"
            placeholder="全部"
            clearable
            style="width: 120px"
          >
            <el-option
              :value="5"
              label="5 星"
            />
            <el-option
              :value="4"
              label="4 星"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="部位">
          <el-select
            v-model="filterPiece"
            placeholder="全部"
            clearable
            style="width: 140px"
          >
            <el-option
              v-for="p in pieceTypes"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            @click="handleSearch"
          >
            <font-awesome-icon
              icon="fa-solid fa-magnifying-glass"
              class="mr-6"
            />
            搜索
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card class="table-card">
      <template #header>
        <div class="table-header">
          <span>圣遗物列表 ({{ artifactStore.total }})</span>
          <div
            class="table-actions"
            v-if="selectedIds.length > 0"
          >
            <el-tag>已选 {{ selectedIds.length }} 件</el-tag>
            <el-button
              type="warning"
              size="small"
            >
              标记分解
            </el-button>
            <el-button
              type="primary"
              size="small"
            >
              批量保留
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="artifactStore.artifacts"
        v-loading="artifactStore.loading"
        @selection-change="handleSelectionChange"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column
          type="selection"
          width="50"
        />
        <el-table-column
          prop="artifactName"
          label="名称"
          min-width="160"
        >
          <template #default="{ row }">
            <div class="artifact-name">
              <font-awesome-icon
                :icon="pieceTypes.find((p) => p.value === row.pieceType)?.icon || 'fa-solid fa-gem'"
              />
              <span>{{ row.artifactName }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          prop="pieceType"
          label="部位"
          width="90"
        >
          <template #default="{ row }">
            <span>{{ pieceTypes.find((p) => p.value === row.pieceType)?.label || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="rarity"
          label="星级"
          width="80"
        >
          <template #default="{ row }">
            <el-tag :type="row.rarity === 5 ? 'warning' : undefined">{{ row.rarity }} 星</el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="level"
          label="等级"
          width="70"
        >
          <template #default="{ row }">+{{ row.level }}</template>
        </el-table-column>
        <el-table-column
          prop="mainStat"
          label="主属性"
          min-width="130"
        >
          <template #default="{ row }">
            <span>{{ row.mainStat }} +{{ row.mainStatValue }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="score"
          label="评分"
          width="90"
          sortable
        >
          <template #default="{ row }">
            <span
              :class="{
                'high-score': row.score >= 18,
                'mid-score': row.score >= 12 && row.score < 18
              }"
            >
              {{ row.score.toFixed(1) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="150"
          fixed="right"
        >
          <template>
            <el-button
              size="small"
              type="primary"
              link
            >
              查看
            </el-button>
            <el-button
              size="small"
              type="warning"
              link
            >
              分解
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue'
  import type { Artifact } from '@/types/artifact'
  import { useArtifactStore } from '@/stores/artifact'
  import { library } from '@fortawesome/fontawesome-svg-core'
  import {
    faClock,
    faCrown,
    faFeather,
    faGem,
    faMagnifyingGlass,
    faSeedling,
    faWineGlass
  } from '@fortawesome/free-solid-svg-icons'

  library.add(faClock, faCrown, faFeather, faGem, faMagnifyingGlass, faSeedling, faWineGlass)

  const artifactStore = useArtifactStore()
  const searchKeyword = ref('')
  const filterRarity = ref<number | null>(null)
  const filterPiece = ref<string>('')
  const selectedIds = ref<number[]>([])

  const pieceTypes = [
    { value: 'flower', label: '生之花', icon: 'fa-solid fa-seedling' },
    { value: 'plume', label: '死之羽', icon: 'fa-solid fa-feather' },
    { value: 'sands', label: '时之沙', icon: 'fa-solid fa-clock' },
    { value: 'goblet', label: '空之杯', icon: 'fa-solid fa-wine-glass' },
    { value: 'circlet', label: '理之冠', icon: 'fa-solid fa-crown' }
  ]

  async function handleSearch() {
    await artifactStore.fetchList({
      keyword: searchKeyword.value,
      rarity: filterRarity.value || undefined,
      pieceType: filterPiece.value || undefined
    } as never)
  }

  function handleSelectionChange(rows: Artifact[]) {
    selectedIds.value = rows.map((r) => r.id)
  }

  onMounted(() => {
    artifactStore.fetchList()
  })
</script>

<style lang="scss" scoped>
  .artifact-list {
    .filter-card {
      margin-bottom: 16px;
    }

    .table-card {
      .table-header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        .table-actions {
          display: flex;
          gap: 12px;
          align-items: center;
        }
      }
    }

    .artifact-name {
      display: flex;
      align-items: center;
      gap: 8px;

      svg {
        color: var(--el-color-primary);
      }
    }

    .high-score {
      color: var(--el-color-success);
      font-weight: 600;
    }

    .mid-score {
      color: var(--el-color-warning);
      font-weight: 500;
    }

    .mr-6 {
      margin-right: 6px;
    }
  }
</style>
