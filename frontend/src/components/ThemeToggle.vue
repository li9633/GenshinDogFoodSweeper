<template>
  <el-switch
    v-model="isDark"
    @change="toggleTheme"
    active-text="深色"
    inactive-text="浅色"
    inline-prompt
  />
</template>

<script setup lang="ts">
  import { ref, onMounted } from 'vue'

  // Element Plus dark mode 切换
  const isDark = ref(false)

  function toggleTheme() {
    isDark.value = !isDark.value
    document.documentElement.classList.toggle('dark', isDark.value)
  }

  onMounted(() => {
    isDark.value = document.documentElement.classList.contains('dark')
  })
</script>
