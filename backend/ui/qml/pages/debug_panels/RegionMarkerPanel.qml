import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// RegionMarker 是 Python 通过 setContextProperty 注入的上下文属性，qmllint 无法识别

Rectangle {
    id: root
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 8
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 6

            // ---- 坐标输入 ----
            RowLayout {
                spacing: 4

                Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                GSpinBox { id: spinX; Layout.preferredWidth: 70; from: 0; to: 9999; value: RegionMarker.regionX; onValueChanged: RegionMarker.setCoords(value, spinY.value, spinW.value, spinH.value) }

                Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                GSpinBox { id: spinY; Layout.preferredWidth: 70; from: 0; to: 9999; value: RegionMarker.regionY; onValueChanged: RegionMarker.setCoords(spinX.value, value, spinW.value, spinH.value) }

                Text { text: "宽:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                GSpinBox { id: spinW; Layout.preferredWidth: 70; from: 1; to: 9999; value: RegionMarker.regionW; onValueChanged: RegionMarker.setCoords(spinX.value, spinY.value, value, spinH.value) }

                Text { text: "高:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                GSpinBox { id: spinH; Layout.preferredWidth: 70; from: 1; to: 9999; value: RegionMarker.regionH; onValueChanged: RegionMarker.setCoords(spinX.value, spinY.value, spinW.value, value) }
            }

            // ---- 保存模板 ----
            RowLayout {
                spacing: 4

                Text { text: "文件名:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                TextField {
                    id: filenameInput
                    Layout.fillWidth: true
                    placeholderText: "输入模板名称，如 圣遗物文本"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textPrimary
                    background: Rectangle {
                        color: Theme.bgTrack
                        radius: 4
                        border.color: Theme.border
                    }
                }
                GButton {
                    text: "保存为模板"
                    colorType: "primary"
                    onClicked: RegionMarker.saveTemplate(filenameInput.text)
                }
            }

            // ---- 操作按钮 ----
            RowLayout {
                spacing: 6

                GButton {
                    id: btnMark
                    text: RegionMarker.marking ? "截图中…" : "截图并标记"
                    colorType: "primary"
                    enabled: !RegionMarker.marking
                    onClicked: RegionMarker.mark()
                }

                GButton {
                    id: btnSelect
                    checkable: true
                    checked: RegionMarker.selectionMode
                    text: checked ? "选区中…" : "选区模式"
                    colorType: checked ? "primary" : "default"
                    onToggled: {
                        RegionMarker.selectionMode = checked
                    }
                }

                GButton {
                    text: "复制坐标"
                    colorType: "default"
                    onClicked: {
                        RegionMarker.copyCoords()
                    }
                }

                Item { Layout.fillWidth: true }
            }

            // ---- 颜色提取 ----
            RowLayout {
                spacing: 6

                GButton {
                    id: btnColor
                    text: RegionMarker.extracting ? "提取中…" : "提取颜色"
                    colorType: "primary"
                    enabled: !RegionMarker.extracting
                    onClicked: RegionMarker.extractColor()
                }

                Rectangle {
                    id: colorSwatch
                    width: 24; height: 24
                    color: "#333333"
                    border.color: Theme.border
                    radius: 2
                }

                Text {
                    id: colorInfo
                    text: "点击按钮提取区域颜色"
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textSecondary
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    // ============================================================
    // Presenter 信号连接
    // ============================================================
    Connections {
        target: RegionMarker

        function onColorExtracted(r, g, b, h, s, v) {
            colorSwatch.color = Qt.rgba(r / 255, g / 255, b / 255, 1)
        }

        function onColorExtractedString(text) {
            colorInfo.text = text
        }

        function onTemplateSaved(filename) {
            filenameInput.text = ""
        }

        function onCopyToClipboard(text) {
            Clipboard.setText(text)
        }
    }

    // 初始化坐标
    Component.onCompleted: {
        spinX.value = RegionMarker.regionX
        spinY.value = RegionMarker.regionY
        spinW.value = RegionMarker.regionW
        spinH.value = RegionMarker.regionH
    }
}