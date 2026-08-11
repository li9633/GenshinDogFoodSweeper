import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI
import "debug_panels"
import "../components"

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
            Layout.preferredHeight: 250
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
        }
    }
}