<template>
  <el-config-provider :locale="en">
    <router-view />
  </el-config-provider>
</template>

<script setup>
import { ElConfigProvider } from 'element-plus'
// 🚨 架构师修正：全面切换至英文环境，匹配欧洲业务生态
import en from 'element-plus/dist/locale/en.mjs'
</script>

<style>
/* 基础重置样式，确保页面铺满全屏 */
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  width: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>