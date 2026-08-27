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

    // ============================================================
    // 语义色：渐进式调色板 (Light → Medium → Default → Deep)
    // ============================================================

    // -- Danger (红) --
    readonly property color dangerLight:  isDark ? "#3A1F1F" : "#FDECEC"
    readonly property color dangerMedium: isDark ? "#C06060" : "#E57373"
    readonly property color danger:       isDark ? "#D47373" : "#C62828"
    readonly property color dangerDeep:   isDark ? "#A84848" : "#B71C1C"

    // -- Success (绿) --
    readonly property color successLight:  isDark ? "#1B2E22" : "#E8F5E9"
    readonly property color successMedium: isDark ? "#5AA868" : "#66BB6A"
    readonly property color success:       isDark ? "#6EBA7A" : "#2E7D32"
    readonly property color successDeep:   isDark ? "#4A9258" : "#1B5E20"

    // -- Warning (橙) --
    readonly property color warningLight:  isDark ? "#3D2A1A" : "#FFF3E0"
    readonly property color warningMedium: isDark ? "#C89840" : "#FFA726"
    readonly property color warning:       isDark ? "#D8AA52" : "#EF6C00"
    readonly property color warningDeep:   isDark ? "#B08032" : "#E65100"

    // -- Info (科技蓝) --
    readonly property color infoLight:  isDark ? "#13283A" : "#EBF5FF"
    readonly property color infoMedium: isDark ? "#3388CC" : "#66B1FF"
    readonly property color info:       isDark ? "#409EFF" : "#409EFF"
    readonly property color infoDeep:   isDark ? "#3070C0" : "#1A6ECC"

    // -- 向后兼容别名 (Hover → Default, Pressed → Deep) --
    readonly property color dangerHover:    danger
    readonly property color dangerPressed:  dangerDeep
    readonly property color successHover:   success
    readonly property color successPressed: successDeep
    readonly property color warningHover:   warning
    readonly property color warningPressed: warningDeep
    readonly property color infoHover:      info
    readonly property color infoPressed:    infoDeep

    // -- 图标 --
    readonly property string fontFamily: "Microsoft YaHei"
    readonly property int fontSize: 15
    readonly property int radius: 6
    readonly property int spacing: 8
}