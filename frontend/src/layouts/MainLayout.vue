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
  import ThemeToggle from '@/components/ThemeToggle.vue'

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
          <ThemeToggle />
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
    background-color: var(--color-bg-secondary, #252640);
    border-right: 1px solid var(--color-border-subtle, #3A3D5C);
    transition: width var(--duration-slow, 300ms) var(--ease-out);
    overflow: hidden;

    .logo {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 60px;
      border-bottom: 1px solid var(--color-border-subtle, #3A3D5C);
      overflow: hidden;
      padding: 0 16px;
      gap: 10px;

      .logo-icon {
        font-size: 24px;
        color: var(--color-accent, #C9A96E);
        flex-shrink: 0;
      }

      .logo-text {
        font-family: var(--font-serif);
        font-size: var(--font-size-body);
        font-weight: 600;
        color: var(--color-accent, #C9A96E);
        white-space: nowrap;
      }
    }

    .nav-menu {
      border-right: none;

      :deep(.el-menu-item) {
        font-family: var(--font-sans);
        font-size: var(--font-size-body);
        font-weight: 500;
        color: var(--color-text-secondary, #B8B5C0);
        transition: all var(--duration-fast, 150ms) var(--ease-out);

        &:hover {
          color: var(--color-accent-light, #E8D5A3);
          background-color: rgba(201, 169, 110, 0.08);
        }

        &.is-active {
          color: var(--color-accent, #C9A96E);
          border-left: 3px solid var(--color-accent, #C9A96E);
          background-color: rgba(201, 169, 110, 0.08);
        }
      }
    }
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: var(--color-bg-secondary, #252640);
    border-bottom: 1px solid var(--color-border-subtle, #3A3D5C);
    padding: 0 var(--space-5, 24px);

    .header-left {
      display: flex;
      align-items: center;
      gap: 20px;

      .collapse-btn {
        font-size: 18px;
        cursor: pointer;
        padding: 6px;
        border-radius: var(--radius-sm, 6px);
        color: var(--color-text-secondary, #B8B5C0);
        transition: all var(--duration-fast, 150ms) var(--ease-out);

        &:hover {
          color: var(--color-accent, #C9A96E);
          background-color: rgba(201, 169, 110, 0.1);
        }
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;

      .version {
        font-family: var(--font-mono);
        font-size: var(--font-size-caption);
        color: var(--color-text-disabled, #6B6E8A);
      }
    }
  }

  .main-content {
    padding: var(--space-5, 24px);
    background-color: var(--color-bg-primary, #1A1B2E);
    overflow-y: auto;
  }
</style>