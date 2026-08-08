<template>
  <div class="theme-toggle" @click="toggle" :title="isDark ? '切换到浅色主题' : '切换到暗色主题'">
    <span class="toggle-icon">{{ isDark ? '🌙' : '☀️' }}</span>
    <span class="toggle-label">{{ isDark ? '暗色' : '浅色' }}</span>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const THEME_KEY = 'genshin-theme'
const isDark = ref(true)

function toggle() {
  isDark.value = !isDark.value
  const theme = isDark.value ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(THEME_KEY, theme)
}

onMounted(() => {
  const saved = localStorage.getItem(THEME_KEY) || 'dark'
  isDark.value = saved === 'dark'
  document.documentElement.setAttribute('data-theme', saved)
})
</script>

<style lang="scss" scoped>
.theme-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-full, 20px);
  cursor: pointer;
  user-select: none;
  background-color: var(--color-bg-tertiary);
  border: 1px solid var(--color-border-subtle);
  transition: all var(--duration-base, 200ms) var(--ease-out);

  &:hover {
    border-color: var(--color-accent);
    background-color: var(--color-accent-glow);
  }

  .toggle-icon {
    font-size: 14px;
    line-height: 1;
  }

  .toggle-label {
    font-family: var(--font-sans);
    font-size: var(--font-size-caption, 12px);
    color: var(--color-text-secondary);
    font-weight: 500;
  }
}
</style>