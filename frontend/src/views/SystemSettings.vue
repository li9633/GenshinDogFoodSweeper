<template>
  <div class="settings">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>通用设置</span>
          <el-button
            type="primary"
            :loading="saving"
            @click="saveSettings"
          >
            <font-awesome-icon
              icon="fa-solid fa-floppy-disk"
              class="mr-6"
            />
            保存设置
          </el-button>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        label-width="160px"
        class="settings-form"
      >
        <el-divider content-position="left">扫描设置</el-divider>

        <el-form-item label="扫描区域">
          <el-row :gutter="12">
            <el-col :span="6">
              <el-input-number
                v-model="form.scanRegion.x"
                placeholder="X"
                :min="0"
              />
            </el-col>
            <el-col :span="6">
              <el-input-number
                v-model="form.scanRegion.y"
                placeholder="Y"
                :min="0"
              />
            </el-col>
            <el-col :span="6">
              <el-input-number
                v-model="form.scanRegion.width"
                placeholder="宽度"
                :min="100"
              />
            </el-col>
            <el-col :span="6">
              <el-input-number
                v-model="form.scanRegion.height"
                placeholder="高度"
                :min="100"
              />
            </el-col>
          </el-row>
        </el-form-item>

        <el-form-item label="匹配阈值">
          <el-slider
            v-model="form.matchThreshold"
            :min="0.5"
            :max="1"
            :step="0.01"
            show-input
          />
          <div class="form-tip">模板匹配相似度阈值，越高越严格（推荐 0.85+）</div>
        </el-form-item>

        <el-form-item label="扫描间隔 (秒)">
          <el-input-number
            v-model="form.scanInterval"
            :min="0.5"
            :max="10"
            :step="0.5"
          />
        </el-form-item>

        <el-divider content-position="left">自动分解设置</el-divider>

        <el-form-item label="启用自动分解">
          <el-switch v-model="form.autoDecompose" />
        </el-form-item>

        <el-form-item label="分解阈值评分">
          <el-input-number
            v-model="form.autoDecomposeThreshold"
            :min="0"
            :max="20"
          />
          <div class="form-tip">评分低于此值的圣遗物将被自动分解</div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
  import { ref, onMounted, reactive } from 'vue'
  import { getSettings, updateSettings } from '@/api/modules/settings'
  import { ElMessage } from 'element-plus'
  import { library } from '@fortawesome/fontawesome-svg-core'
  import { faFloppyDisk } from '@fortawesome/free-solid-svg-icons'

  library.add(faFloppyDisk)

  const formRef = ref()
  const saving = ref(false)

  const form = reactive({
    scanRegion: { x: 0, y: 0, width: 1920, height: 1080 },
    matchThreshold: 0.85,
    scanInterval: 1.5,
    autoDecompose: false,
    autoDecomposeThreshold: 8
  })

  async function loadSettings() {
    try {
      const data = await getSettings()
      Object.assign(form, data)
    } catch {
      // 后端未启动时使用默认值
    }
  }

  async function saveSettings() {
    saving.value = true
    try {
      await updateSettings(form)
      ElMessage.success('设置保存成功')
    } catch {
      ElMessage.error('保存失败')
    } finally {
      saving.value = false
    }
  }

  onMounted(loadSettings)
</script>

<style lang="scss" scoped>
  .settings {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .settings-form {
      max-width: 800px;
    }

    .form-tip {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-top: 4px;
    }

    .mr-6 {
      margin-right: 6px;
    }
  }
</style>
