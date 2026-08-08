<script setup lang="ts">
  import { ref } from 'vue'
  import { useRoute } from 'vue-router'
  import { library } from '@fortawesome/fontawesome-svg-core'
  import {
    faBars,
    faBarsStaggered,
    faGem,
    faGaugeHigh,
    faGear
  } from '@fortawesome/free-solid-svg-icons'

  library.add(faBars, faBarsStaggered, faGem, faGaugeHigh, faGear)

  const route = useRoute()
  const isCollapsed = ref(false)
  const activeMenu = ref(route.path)

  const menuItems = [
    { path: '/dashboard', title: '仪表盘', icon: 'fa-gauge-high' },
    { path: '/artifacts', title: '圣遗物列表', icon: 'fa-gem' },
    { path: '/settings', title: '设置', icon: 'fa-gear' }
  ]

  function toggleCollapse() {
    isCollapsed.value = !isCollapsed.value
  }
</script>

<template>
  <el-container
    class="main-layout"
    v-loading="false"
  >
    <!-- 侧边栏 -->
    <el-aside
      :width="isCollapsed ? '64px' : '220px'"
      class="sidebar"
    >
      <div class="logo">
        <font-awesome-icon
          icon="fa-solid fa-gem"
          class="logo-icon"
        />
        <span
          v-show="!isCollapsed"
          class="logo-text"
        >
          原神狗粮清扫器
        </span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :collapse-transition="false"
        router
        class="nav-menu"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <font-awesome-icon :icon="`fa-solid ${item.icon}`" />
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部导航 -->
      <el-header class="header">
        <div class="header-left">
          <font-awesome-icon
            :icon="isCollapsed ? 'fa-solid fa-bars' : 'fa-solid fa-bars-staggered'"
            class="collapse-btn"
            @click="toggleCollapse"
          />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag
            type="success"
            effect="dark"
            size="small"
          >
            在线
          </el-tag>
          <span class="version">v0.1.0</span>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<style lang="scss" scoped>
  .main-layout {
    height: 100vh;
  }

  .sidebar {
    background-color: var(--el-menu-bg-color);
    border-right: 1px solid var(--el-border-color-lighter);
    transition: width 0.3s ease;
    overflow: hidden;

    .logo {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 60px;
      border-bottom: 1px solid var(--el-border-color-lighter);
      overflow: hidden;
      padding: 0 16px;
      gap: 10px;

      .logo-icon {
        font-size: 24px;
        color: var(--el-color-primary);
        flex-shrink: 0;
      }

      .logo-text {
        font-size: 14px;
        font-weight: 600;
        white-space: nowrap;
      }
    }

    .nav-menu {
      border-right: none;
    }
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: var(--el-bg-color);
    border-bottom: 1px solid var(--el-border-color-lighter);
    padding: 0 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 20px;

      .collapse-btn {
        font-size: 18px;
        cursor: pointer;
        padding: 6px;
        border-radius: 4px;

        &:hover {
          background-color: var(--el-fill-color-light);
        }
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;

      .version {
        font-size: 12px;
        color: var(--el-text-color-secondary);
      }
    }
  }

  .main-content {
    padding: 20px;
    background-color: var(--el-bg-color-page);
    overflow-y: auto;
  }
</style>
