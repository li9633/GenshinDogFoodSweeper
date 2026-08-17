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

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 8
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: Theme.spacing

            // ---- 检测配置选择 ----
            GCard {
                title: "检测配置"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    RowLayout {
                        spacing: 4
                        Text {
                            text: "当前方案:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            color: Theme.textSecondary
                        }
                        GComboBox {
                            id: configCombo
                            implicitWidth: 160
                            model: ArtifactRecognition.availableConfigNames
                            currentIndex: ArtifactRecognition.activeConfigIndex
                            onActivated: (index) => ArtifactRecognition.setActiveConfigByIndex(index)
                        }
                    }

                    Text {
                        text: ArtifactRecognition.activeConfigDetail
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "提示：切换配置后，识别时自动使用对应页面的详情弹窗 ROI 坐标"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
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