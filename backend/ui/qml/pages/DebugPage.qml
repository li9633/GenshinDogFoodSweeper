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

            Repeater {
                model: ["区域标记", "元素定位", "圣遗物识别", "圣遗物扫描", "状态栏"]

                TabButton {
                    required property int index
                    required property string modelData

                    text: modelData
                    font.family: Theme.fontFamily
                    font.pixelSize: 14

                    HoverHandler {
                        id: tabHover
                        cursorShape: Qt.PointingHandCursor
                    }

                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: parent.checked ? Theme.accent : Theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        color: {
                            if (parent.checked) return Theme.accentOverlay10
                            if (tabHover.hovered) return Theme.accentOverlay6
                            return "transparent"
                        }
                    }
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
            ArtifactScanPanel {}
            StatusBarTestPanel {}
        }

        // -- 分割线 --
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
        }

        // -- 预览区（状态栏/输入测试 Tab 不显示）--
        CapturePreview {
            id: preview
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: tabBar.currentIndex !== 4
            selectionMode: RegionMarker.selectionMode

            onRegionSelected: (x, y, w, h) => {
                RegionMarker.setCoords(x, y, w, h)
                RegionMarker.selectionMode = false
            }

            onClearRequested: {
                switch (tabBar.currentIndex) {
                    case 0: RegionMarker.clear(); break
                    case 2: ArtifactRecognition.clear(); break
                }
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

    Connections {
        target: ArtifactScan

        function onDebugPreviewReady(key) {
            preview.source = ""
            preview.source = "image://preview/" + key
            preview.infoText = "灰度检测调试预览"
        }
    }
}