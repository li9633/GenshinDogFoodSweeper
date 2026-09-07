pragma Singleton
import QtQuick

QtObject {
    // ── 调色板 ──
    readonly property color primaryText: "#333333"
    readonly property color secondaryText: "#555555"
    readonly property color subtleText: "#888888"
    readonly property color hintText: "#aaaaaa"
    readonly property color bgWindow: "#f5f5f5"
    readonly property color bgWhite: "#ffffff"
    readonly property color separator: "#e0e0e0"
    readonly property color success: "#4caf50"
    readonly property color error: "#d32f2f"
    readonly property color accent: "#1976D2"
    readonly property color accentHover: "#1565C0"

    // ── 字体 ──
    readonly property string fontFamily: "Microsoft YaHei"

    // ── 字号 ──
    readonly property int fontSizeTitle: 22
    readonly property int fontSizeHeading: 18
    readonly property int fontSizeBody: 14
    readonly property int fontSizeNormal: 13
    readonly property int fontSizeSmall: 12
    readonly property int fontSizeIcon: 48

    // ── 间距 ──
    readonly property int spacingLg: 16
    readonly property int spacingMd: 10
    readonly property int spacingSm: 6
    readonly property int pageMargin: 20

    // ── 布局 ──
    readonly property int contentWidth: 440

    // ── 窗口 ──
    readonly property int windowWidth: 520
    readonly property int windowHeight: 420
    readonly property string windowTitle: "原神狗粮扫荡器 安装向导"
}