import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI
import "debug_panels"
import "../components"

// qmllint disable unqualified
// RegionMarker / ElementDetection / ArtifactRecognition 是 Python 上下文属性
// qmllint disable missing-property
// TabButton 的 contentItem/background 代理中 parent.text/font/checked 是标准 Qt 用法，qmllint 误报

Rectangle {
    id: root
    color: Theme.bgPrimary

    // ============================================================
    // 布局：TabBar 上方 + 预览区下方
    // ============================================================
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // -- Tab 栏 --
        TabBar {
            id: tabBar
            Layout.fillWidth: true
            background: Rectangle {
                color: Theme.bgSidebar
            }

            TabButton {
                text: "区域标记"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                contentItem: Text {
                    text: parent.text
                    font: parent.font
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: parent.checked ? Theme.accentOverlay10 : "transparent"
                }
            }
            TabButton {
                text: "元素定位"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                contentItem: Text {
                    text: parent.text
                    font: parent.font
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: parent.checked ? Theme.accentOverlay10 : "transparent"
                }
            }
            TabButton {
                text: "圣遗物识别"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                contentItem: Text {
                    text: parent.text
                    font: parent.font
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: parent.checked ? Theme.accentOverlay10 : "transparent"
                }
            }
            TabButton {
                text: "状态栏"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                contentItem: Text {
                    text: parent.text
                    font: parent.font
                    color: parent.checked ? Theme.accent : Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: parent.checked ? Theme.accentOverlay10 : "transparent"
                }
            }
        }

        // -- 面板区 --
        StackLayout {
            id: panelStack
            Layout.fillWidth: true
            Layout.preferredHeight: 280
            currentIndex: tabBar.currentIndex

            RegionMarkerPanel {}
            ElementDetectionPanel {}
            ArtifactRecognitionPanel {}
            StatusBarTestPanel {}
        }

        // -- 分割线 --
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
        }

        // -- 预览区（状态栏 Tab 不显示）--
        CapturePreview {
            id: preview
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: tabBar.currentIndex !== 3
            selectionMode: RegionMarker.selectionMode

            onRegionSelected: function(x, y, w, h) {
                RegionMarker.setCoords(x, y, w, h)
            }
        }
    }

    // ============================================================
    // 各面板 Presenter 信号 → CapturePreview
    // ============================================================
    Connections {
        target: RegionMarker

        function onCaptureFinished(key, x, y, w, h) {
            preview.source = "image://preview/" + key
            preview.infoText = "标记区域 (" + x + "," + y + "," + w + "x" + h + ")"
            tabBar.currentIndex = 0
        }
         function onClearPreview() {
            preview.source = ""
            preview.infoText = "等待截图…"
        }
    }

    Connections {
        target: ElementDetection

        function onDetectionFinished(allPassed, detailText, key) {
            preview.source = "image://preview/" + key
            preview.infoText = allPassed ? "✓ 全部通过" : "✗ 未通过"
            tabBar.currentIndex = 1
        }
    }

    Connections {
        target: ArtifactRecognition

        function onRecognitionFinished(ocrText, structuredText, key) {
            preview.source = "image://preview/" + key
            preview.infoText = "识别完成"
            tabBar.currentIndex = 2
        }

        function onClearPreview() {
            preview.source = ""
            preview.infoText = "等待截图…"
        }
    }
}