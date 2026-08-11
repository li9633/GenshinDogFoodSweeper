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
                    id: roiRepeater
                    model: ArtifactRecognition.roiDefinitions

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
                    text: ArtifactRecognition.recognizing ? "识别中…" : "截图并识别"
                    enabled: !ArtifactRecognition.recognizing
                    implicitHeight: 34
                    Layout.fillWidth: true
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        color: parent.enabled ? Theme.bgPrimary : Theme.textMuted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: parent.enabled ? Theme.accent : Theme.bgTrack; radius: Theme.radius }
                    onClicked: ArtifactRecognition.recognize()
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
                    onClicked: {
                        ArtifactRecognition.clear()
                        ocrResultText.text = ""
                        structuredResultText.text = ""
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    // ============================================================
    // Presenter 信号连接
    // ============================================================
    Connections {
        target: ArtifactRecognition

        function onRecognitionFinished(ocrText, structuredText, imagePath, dbEmpty) {
            ocrResultText.text = ocrText
            structuredResultText.text = structuredText
            if (dbEmpty) {
                dbEmptyDialog.open()
            }
        }

        function onErrorOccurred(msg) {
            ocrResultText.text = "错误: " + msg
        }
    }

    // ---- 数据库为空警告对话框 ----
    Dialog {
        id: dbEmptyDialog
        title: "本地圣遗物模板为空"
        modal: true
        standardButtons: Dialog.Ok
        anchors.centerIn: parent

        Text {
            text: "数据库中暂无圣遗物套装数据，将仅显示 OCR 识别结果，不进行匹配。\n\n" +
                  "请前往[设置]页面，点击「圣遗物同步」拉取最新圣遗物数据。"
            font.family: Theme.fontFamily
            font.pixelSize: 13
            color: Theme.textPrimary
            wrapMode: Text.WordWrap
            width: 320
        }
    }
}