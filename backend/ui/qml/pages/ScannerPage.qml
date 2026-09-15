import QtQuick
import QtQuick.Dialogs
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

Rectangle {
    id: root
    property string pageTitle: "圣遗物扫描器"
    color: Theme.bgPrimary

    // 保存位置选择（权限与写法对齐 RulesPage 的导出目录选择）
    FolderDialog {
        id: saveDirDialog
        title: "选择扫描结果保存位置"
        onAccepted: ArtifactScan.setSaveDirectory(selectedFolder)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ==== 扫描进度 ====
        Text {
            text: "全量扫描"
            font.family: Theme.fontFamily
            font.pixelSize: 14
            color: Theme.textPrimary
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.centerIn: parent
                width: parent.width
                spacing: 12

                // 步骤提示
                Text {
                    text: ArtifactScan.fullScanStep
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    font.bold: true
                    color: Theme.accent
                    visible: ArtifactScan.fullScanStep !== ""
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                }

                // 进度
                Text {
                    text: ArtifactScan.fullScanProgressText
                    font.family: Theme.fontFamily
                    font.pixelSize: 24
                    color: Theme.accent
                    visible: ArtifactScan.fullScanProgressText !== ""
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }

                // 空闲状态提示
                Text {
                    text: "选择扫描选项后点击「开始扫描」"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textMuted
                    visible: ArtifactScan.fullScanIdle
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }

                // 扫描结果
                ColumnLayout {
                    visible: ArtifactScan.fullScanSavedPath !== ""
                    spacing: 4
                    Layout.fillWidth: true

                    Text {
                        text: "上次扫描已完成，结果已保存至:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                    Text {
                        text: ArtifactScan.fullScanSavedPath
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.accent
                        wrapMode: Text.WrapAnywhere
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                    }
                }

                // 保存失败提示
                Text {
                    visible: ArtifactScan.fullScanSaveError !== ""
                    text: ArtifactScan.fullScanSaveError
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: "#D32F2F"
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
            }
        }

        // ==== 保存设置 ====
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "保存位置:"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }

                Text {
                    Layout.fillWidth: true
                    Layout.maximumWidth: 420
                    text: ArtifactScan.saveDirectory
                    elide: Text.ElideMiddle
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textMuted
                }

                GButton {
                    text: "选择目录"
                    colorType: "default"
                    enabled: !ArtifactScan.fullScanRunning
                    onClicked: saveDirDialog.open()
                }

                Text {
                    text: "保存格式:"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                    Layout.leftMargin: 8
                }

                GComboBox {
                    implicitWidth: 180
                    model: ArtifactScan.saveFormatNames
                    currentIndex: ArtifactScan.saveFormatIndex
                    enabled: !ArtifactScan.fullScanRunning
                    onActivated: (index) => ArtifactScan.setSaveFormatByIndex(index)
                }
            }

            // 当前格式说明
            Text {
                Layout.leftMargin: 68
                text: ArtifactScan.saveFormatDescription
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        // ==== 底部操作栏 ====
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // 停止条件
            Text {
                text: "停止条件:"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }

            GComboBox {
                implicitWidth: 150
                model: ArtifactScan.scanStopModeNames
                currentIndex: ArtifactScan.scanStopModeIndex
                enabled: !ArtifactScan.fullScanRunning
                onActivated: (index) => ArtifactScan.setScanStopModeByIndex(index)
            }

            // 去重（仅五星模式）
            GCheckBox {
                visible: ArtifactScan.scanShowsDedup
                text: "去重"
                checked: ArtifactScan.scanEnableDedup
                enabled: !ArtifactScan.fullScanRunning
                onToggled: ArtifactScan.setScanEnableDedup(checked)
            }

            // 固定数量
            Text {
                visible: ArtifactScan.scanShowsFixedCount
                text: "数量:"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }

            GSpinBox {
                id: fixedCountSpin
                visible: ArtifactScan.scanShowsFixedCount
                from: 1
                to: 9999
                editable: true
                implicitWidth: 70
                implicitHeight: 32
                enabled: !ArtifactScan.fullScanRunning
                onValueChanged: ArtifactScan.setScanFixedCount(value)
                Component.onCompleted: value = ArtifactScan.scanFixedCountInitial
            }

            Item { Layout.fillWidth: true }

            // 统计信息
            Text {
                text: ArtifactScan.fullScanProgress
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
                visible: text !== ""
                Layout.rightMargin: 8
            }

            GButton {
                text: ArtifactScan.fullScanButtonText
                colorType: "primary"
                enabled: !ArtifactScan.fullScanRunning
                onClicked: ArtifactScan.startFullScan()
            }

            GButton {
                visible: ArtifactScan.fullScanRunning
                text: "停止"
                colorType: "danger"
                onClicked: ArtifactScan.stopFullScan()
            }
        }
    }
}