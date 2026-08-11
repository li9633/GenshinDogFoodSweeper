import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

Rectangle {
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 12
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 10

            // ---- 坐标输入 ----
            RowLayout {
                spacing: 6

                Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinX; Layout.preferredWidth: 70; from: 0; to: 9999; value: 0 }

                Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinY; Layout.preferredWidth: 70; from: 0; to: 9999; value: 0 }

                Text { text: "宽:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinW; Layout.preferredWidth: 70; from: 1; to: 9999; value: 100 }

                Text { text: "高:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinH; Layout.preferredWidth: 70; from: 1; to: 9999; value: 100 }
            }

            // ---- 保存模板 ----
            RowLayout {
                spacing: 6

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
                Button {
                    text: "保存为模板"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.bgPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.accent; radius: Theme.radius }
                }
            }

            // ---- 操作按钮 ----
            RowLayout {
                spacing: 6

                Button {
                    text: "截图并标记"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.bgPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.accent; radius: Theme.radius }
                }

                Button {
                    id: btnSelect
                    checkable: true
                    text: checked ? "选区模式(开)" : "选区模式"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: parent.checked ? Theme.bgPrimary : Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: parent.checked ? Theme.accent : Theme.bgTrack
                        radius: Theme.radius
                    }
                }

                Button {
                    text: "复制坐标"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.bgTrack; radius: Theme.radius }
                }

                Button {
                    text: "清除"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.bgTrack; radius: Theme.radius }
                }

                Item { Layout.fillWidth: true }
            }

            // ---- 颜色提取 ----
            RowLayout {
                spacing: 8

                Button {
                    text: "提取颜色"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.bgPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.accent; radius: Theme.radius }
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
}