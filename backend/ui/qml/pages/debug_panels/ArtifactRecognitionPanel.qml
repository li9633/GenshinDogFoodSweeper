import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// ArtifactRecognition 是 Python 通过 setContextProperty 注入的上下文属性，qmllint 无法识别

Rectangle {
    id: root
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    property bool roiEditable: false
    property bool roiExpanded: false

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 8
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: Theme.spacing

            // ---- ROI 区域定义（可折叠，默认折叠）----
            GCard {
                title: ""
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    // 可点击标题行
                    Item {
                        Layout.fillWidth: true
                        implicitHeight: titleText.implicitHeight

                        RowLayout {
                            anchors.fill: parent
                            spacing: 6
                            Text {
                                text: roiExpanded ? "▼" : "▶"
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: Theme.textSecondary
                                width: 14
                            }
                            Text {
                                id: titleText
                                text: "ROI 区域定义（相对于游戏窗口）"
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                font.bold: true
                                color: Theme.textPrimary
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: roiExpanded = !roiExpanded
                        }
                    }

                    // 可折叠内容
                    ColumnLayout {
                        visible: roiExpanded
                        Layout.fillWidth: true
                        spacing: 4

                        GCheckBox {
                            id: chkEditRoi
                            text: "编辑 ROI"
                            checked: roiEditable
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
                                    font.pixelSize: 13
                                    color: Theme.textSecondary
                                    Layout.preferredWidth: 80
                                }
                                Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                                GSpinBox {
                                    from: 0; to: 9999
                                    value: modelData.dx
                                    enabled: roiEditable
                                }
                                Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                                GSpinBox {
                                    from: 0; to: 9999
                                    value: modelData.dy
                                    enabled: roiEditable
                                }
                                Text { text: "W:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                                GSpinBox {
                                    from: 0; to: 9999
                                    value: modelData.dw
                                    enabled: roiEditable
                                }
                                Text { text: "H:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                                GSpinBox {
                                    from: 0; to: 9999
                                    value: modelData.dh
                                    enabled: roiEditable
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }
                    }
                }
            }

            // ---- 识别结果（左右并排）----
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 180
                spacing: 6

                // 识别结果 OCR 原始输出
                GCard {
                    title: "识别结果（OCR 原始输出）"
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true

                        Text {
                            id: ocrResultText
                            text: ""
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textPrimary
                            wrapMode: Text.Wrap
                            width: parent.width
                        }
                    }
                }

                // 格式化解析结果
                GCard {
                    title: "格式化解析结果"
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true

                        Text {
                            id: structuredResultText
                            text: ""
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textPrimary
                            wrapMode: Text.Wrap
                            width: parent.width
                        }
                    }
                }
            }

            // ---- 操作 ----
            GCard {
                title: "操作"
                Layout.fillWidth: true

                GButton {
                    id: btnCapture
                    text: ArtifactRecognition.recognizing ? "识别中…" : "截图并识别"
                    colorType: "primary"
                    enabled: !ArtifactRecognition.recognizing
                    Layout.fillWidth: true
                    onClicked: ArtifactRecognition.recognize()
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

        function onClearPreview() {
            ocrResultText.text = ""
            structuredResultText.text = ""
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