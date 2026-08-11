import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

Rectangle {
    id: root
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    property bool roiExpanded: false
    property bool roiEditable: false

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 12
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 8

            // ---- ROI 折叠区 ----
            Button {
                id: roiHeader
                Layout.fillWidth: true
                checkable: true
                checked: roiExpanded
                text: (checked ? "▾" : "▸") + " ROI 区域定义（相对于游戏窗口）"
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textPrimary
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 8
                }
                background: Rectangle {
                    color: parent.checked ? Theme.accentOverlay10 : "transparent"
                    border.color: Theme.border
                    radius: Theme.radius
                }
                onClicked: roiExpanded = !roiExpanded
            }

            ColumnLayout {
                visible: roiExpanded
                spacing: 4

                CheckBox {
                    id: chkEditRoi
                    text: "编辑 ROI"
                    checked: roiEditable
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                        verticalAlignment: Text.AlignVCenter
                    }
                    onCheckedChanged: roiEditable = checked
                }

                Repeater {
                    model: [
                        { name: "圣遗物等级", dx: 1338, dy: 452, dw: 71,  dh: 44 },
                        { name: "圣遗物星级", dx: 1742, dy: 159, dw: 39,  dh: 40 },
                        { name: "圣遗物名称", dx: 1329, dy: 144, dw: 262, dh: 62 },
                        { name: "部位+主词条", dx: 1339, dy: 214, dw: 160, dh: 174 },
                        { name: "副词条区",   dx: 1347, dy: 498, dw: 276, dh: 166 }
                    ]

                    RowLayout {
                        spacing: 2
                        Text {
                            text: modelData.name + ":"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textSecondary
                            Layout.preferredWidth: 80
                        }
                        Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                        SpinBox {
                            Layout.preferredWidth: 55
                            from: 0; to: 9999
                            value: modelData.dx
                            enabled: roiEditable
                        }
                        Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                        SpinBox {
                            Layout.preferredWidth: 55
                            from: 0; to: 9999
                            value: modelData.dy
                            enabled: roiEditable
                        }
                        Text { text: "W:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                        SpinBox {
                            Layout.preferredWidth: 55
                            from: 0; to: 9999
                            value: modelData.dw
                            enabled: roiEditable
                        }
                        Text { text: "H:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                        SpinBox {
                            Layout.preferredWidth: 55
                            from: 0; to: 9999
                            value: modelData.dh
                            enabled: roiEditable
                        }
                        Item { Layout.fillWidth: true }
                    }
                }
            }

            // ---- 识别结果（左右并排）----
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 180
                spacing: 8

                // 识别结果 OCR 原始输出
                GroupBox {
                    title: "识别结果"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    background: Rectangle {
                        color: Theme.bgSecondary
                        radius: Theme.radius
                        border.color: Theme.border
                    }
                    label: Text {
                        text: "识别结果（OCR 原始输出）"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: true
                        color: Theme.textPrimary
                        x: parent.leftPadding
                    }

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 4
                        clip: true

                        TextArea {
                            id: ocrResultText
                            readOnly: true
                            placeholderText: "点击「识别」查看 OCR 原始结果…"
                            font.family: "Consolas"
                            font.pixelSize: 12
                            color: Theme.textPrimary
                            background: null
                            wrapMode: TextEdit.Wrap
                        }
                    }
                }

                // 格式化解析结果
                GroupBox {
                    title: "格式化解析结果"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    background: Rectangle {
                        color: Theme.bgSecondary
                        radius: Theme.radius
                        border.color: Theme.border
                    }
                    label: Text {
                        text: "格式化解析结果"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.bold: true
                        color: Theme.textPrimary
                        x: parent.leftPadding
                    }

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 4
                        clip: true

                        TextArea {
                            id: structuredResultText
                            readOnly: true
                            placeholderText: "结构化解析结果将显示在此…"
                            font.family: "Consolas"
                            font.pixelSize: 12
                            color: Theme.textPrimary
                            background: null
                            wrapMode: TextEdit.Wrap
                        }
                    }
                }
            }

            // ---- 操作按钮 ----
            RowLayout {
                spacing: 8

                Button {
                    id: btnCapture
                    text: "截图并识别"
                    implicitHeight: 34
                    Layout.fillWidth: true
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        color: Theme.bgPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.accent; radius: Theme.radius }
                }

                Button {
                    text: "清除"
                    implicitHeight: 34
                    implicitWidth: 80
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.bgTrack; radius: Theme.radius }
                }
            }
        }
    }
}