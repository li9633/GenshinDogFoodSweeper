pragma Singleton
import QtQuick

QtObject {
    // ============================================================
    // GenshinDogFoodSweeper — 主题系统
    // 一个 isDark 开关，所有组件自动响应式切换
    // ============================================================

    property bool isDark: true

    // -- 背景 --
    readonly property color bgPrimary:   isDark ? "#1A1B2E" : "#F7F5F0"
    readonly property color bgSecondary: isDark ? "#252640" : "#FFFFFF"
    readonly property color bgSidebar:   isDark ? "#111224" : "#E8E5DD"
    readonly property color bgTrack:     isDark ? "#2E3055" : "#EFEDE8"

    // -- 文字 --
    readonly property color textPrimary:   isDark ? "#F0EDE5" : "#1A1B2E"
    readonly property color textSecondary: isDark ? "#B8B5C0" : "#4A4D6A"
    readonly property color textMuted:     isDark ? "#6B6E8A" : "#9E9E9E"

    // -- 强调色 --
    readonly property color accent:         isDark ? "#C9A96E" : "#A87B3F"
    readonly property color accentHover:    isDark ? "#E8D5A3" : "#B88A4F"
    readonly property color accentSoft:     isDark ? "#E8D5A3" : "#C9A96E"
    readonly property color accentOverlay6: isDark ? "#1AC9A96E" : "#0DA87B3F"
    readonly property color accentOverlay10: isDark ? "#1AC9A96E" : "#1AA87B3F"

    // -- 边框 --
    readonly property color border:      isDark ? "#3A3D5C" : "#E0DDD5"
    readonly property color borderHover: isDark ? "#5A5E8A" : "#B8B5A8"

    // -- 危险色 --
    readonly property color danger:         isDark ? "#EF5350" : "#C62828"
    readonly property color dangerHover:    isDark ? "#F44336" : "#D32F2F"
    readonly property color dangerPressed:  isDark ? "#D32F2F" : "#B71C1C"

    // -- 图标 --
    readonly property string fontFamily: "Microsoft YaHei"
    readonly property int fontSize: 14
    readonly property int radius: 6
}