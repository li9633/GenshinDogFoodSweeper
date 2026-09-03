import QtQuick
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

Rectangle {
    id: root
    property string pageTitle: "圣遗物扫描器"
    color: Theme.bgPrimary

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
                    text: ArtifactScan.fullScanProgress
                          + (ArtifactScan.fullScanCurrentPage > 0
                             ? " | 第 " + ArtifactScan.fullScanCurrentPage
                               + "/" + ArtifactScan.fullScanTotalPages + " 页"
                             : "")
                    font.family: Theme.fontFamily
                    font.pixelSize: 24
                    color: Theme.accent
                    visible: ArtifactScan.fullScanProgress !== ""
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }

                // 空闲状态提示
                Text {
                    text: "选择扫描选项后点击「开始扫描」"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textMuted
                    visible: ArtifactScan.fullScanStep === "" && ArtifactScan.fullScanProgress === ""
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
                model: ["首尾锚点定位", "仅扫描五星", "固定扫描数量"]
                currentIndex: ArtifactScan.scanStopModeIndex
                enabled: !ArtifactScan.fullScanRunning
                onActivated: (index) => ArtifactScan.setScanStopModeByIndex(index)
            }

            // 去重（仅五星模式）
            GCheckBox {
                visible: ArtifactScan.scanStopMode === "five_star_only"
                text: "去重"
                checked: ArtifactScan.scanEnableDedup
                enabled: !ArtifactScan.fullScanRunning
                onToggled: ArtifactScan.setScanEnableDedup(checked)
            }

            // 固定数量
            Text {
                visible: ArtifactScan.scanStopMode === "fixed_count"
                text: "数量:"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }

            GSpinBox {
                id: fixedCountSpin
                visible: ArtifactScan.scanStopMode === "fixed_count"
                from: 1
                to: 9999
                editable: true
                implicitWidth: 70
                implicitHeight: 32
                enabled: !ArtifactScan.fullScanRunning
                onValueChanged: ArtifactScan.setScanFixedCount(value)
                Component.onCompleted: value = ArtifactScan.scanFixedCount > 0 ? ArtifactScan.scanFixedCount : 100
            }

            Item { Layout.fillWidth: true }

            // 统计信息
            Text {
                text: ArtifactScan.fullScanProgress || ""
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
                visible: text !== ""
                Layout.rightMargin: 8
            }

            GButton {
                text: ArtifactScan.fullScanRunning ? "扫描中…" : "开始扫描"
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