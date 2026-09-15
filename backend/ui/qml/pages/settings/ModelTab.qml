import QtQuick
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: 16
    Layout.margins: 24

    property bool downloading: false
    property string modelProgressText: ""

    onVisibleChanged: {
        if (visible) {
            modelProgressText = ""
        }
    }

    Text {
        text: "模型"
        font.family: Theme.fontFamily
        font.pixelSize: 18
        font.bold: true
        color: Theme.textPrimary
    }

    GCard {
        Layout.fillWidth: true
        title: "OCR 模型管理"
        subtitle: "下载和管理 OCR 识别模型"

        ColumnLayout {
            spacing: 12

            RowLayout {
                spacing: 12
                GButton {
                    text: root.downloading ? "下载中…" : "下载模型"
                    enabled: !root.downloading
                    onClicked: {
                        root.downloading = true
                        root.modelProgressText = ""
                        SettingsPresenter.downloadModels()
                    }
                }
                Text {
                    text: SettingsPresenter.modelStatus
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: SettingsPresenter.modelReady ? Theme.success : Theme.warning
                }
            }

            ColumnLayout {
                visible: root.downloading
                spacing: 4
                Layout.fillWidth: true

                GProgressBar {
                    id: modelBar
                    Layout.fillWidth: true
                    indeterminate: root.downloading && root.modelProgressText === ""
                    progressText: root.modelProgressText
                }
            }

            Text {
                text: SettingsPresenter.modelVersion
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
            }
        }
    }

    Connections {
        target: SettingsPresenter
        function onModelDownloadProgress(current, total, text) {
            modelBar.indeterminate = false
            modelBar.value = total > 0 ? current / total : 0
            root.modelProgressText = text
        }
        function onModelDownloadFinished(success, message) {
            modelBar.indeterminate = false
            root.downloading = false
            root.modelProgressText = ""
            modelBar.indeterminate = false
        }
    }
}