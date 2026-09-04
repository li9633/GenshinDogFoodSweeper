pragma Singleton
import QtQuick

QtObject {
    // -- 字体家族（对应 main.py 中加载的 FontAwesome 字体） --
    readonly property string fontSolid: "Font Awesome 7 Free Solid"
    readonly property string fontRegular: "Font Awesome 7 Free"

    // -- 通用图标 --
    readonly property string close:          "\uf00d"   // fa-xmark
    readonly property string check:          "\uf00c"   // fa-check
    readonly property string search:         "\uf002"   // fa-magnifying-glass
    readonly property string star:           "\uf005"   // fa-star
    readonly property string exclamation:    "\uf071"   // fa-triangle-exclamation
    readonly property string info:           "\uf05a"   // fa-circle-info

    // -- 导航 --
    readonly property string rocket:         "\uf135"   // fa-rocket
    readonly property string list:           "\uf0ca"   // fa-list
    readonly property string gear:           "\uf013"   // fa-gear
    readonly property string sliders:        "\uf1de"   // fa-sliders
    readonly property string wrench:         "\uf0ad"   // fa-wrench

    // -- 状态 --
    readonly property string lock:           "\uf023"   // fa-lock
    readonly property string lockOpen:       "\uf3c1"   // fa-lock-open
    readonly property string lightbulb:      "\uf0eb"   // fa-lightbulb
    readonly property string circleCheck:    "\uf058"   // fa-circle-check
    readonly property string circleXmark:    "\uf057"   // fa-circle-xmark
    readonly property string chevronDown:    "\uf078"   // fa-chevron-down
    readonly property string chevronRight:   "\uf054"   // fa-chevron-right

    // -- 窗口控制 --
    readonly property string circleHalfStroke: "\uf042"   // fa-circle-half-stroke（主题切换）
    readonly property string minus:          "\uf068"   // fa-minus（最小化）
    readonly property string anglesDown:     "\uf103"   // fa-angles-down（托盘）
    readonly property string windowMinimize: "\uf2d1"   // fa-window-minimize
    readonly property string windowMaximize: "\uf2d0"   // fa-window-maximize
    readonly property string windowRestore:  "\uf2d2"   // fa-window-restore

    // -- 设置页 --
    readonly property string palette:        "\uf53f"   // fa-palette
    readonly property string arrowsRotate:   "\uf021"   // fa-arrows-rotate
    readonly property string flask:          "\uf0c3"   // fa-flask
    readonly property string clock:          "\uf017"   // fa-clock
    readonly property string keyboard:       "\uf11c"   // fa-keyboard
}