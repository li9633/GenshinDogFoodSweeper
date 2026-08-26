import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// ArtifactScan / GameDetector 是 Python 通过 setContextProperty 注入的上下文属性

Rectangle {
    id: root
    property string pageTitle: "圣遗物扫描器"
    color: Theme.bgPrimary

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 16
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 16

            // ==== 游戏状态 ====
            GCard {
                title: "游戏状态"
                Layout.fillWidth: true

                RowLayout {
                    spacing: 8

                    Rectangle {
                        width: 10
                        height: 10
                        radius: 5
                        color: GameDetector.isRunning ? "#4CAF50" : "#EF5350"
                    }

                    Text {
                        text: GameDetector.isRunning ? "原神运行中" : "未检测到原神"
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        font.bold: true
                        color: GameDetector.isRunning ? "#4CAF50" : Theme.textSecondary
                    }

                    Text {
                        visible: GameDetector.isRunning
                        text: "窗口: " + GameDetector.winWidth + "×" + GameDetector.winHeight
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }
                }

                GButton {
                    text: "聚焦窗口"
                    colorType: "default"
                    onClicked: ArtifactScan.focusGame()
                }
            }

            // ==== 检测配置 ====
            GCard {
                title: "检测配置"
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 8

                    RowLayout {
                        spacing: 6
                        Text {
                            text: "配置:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            color: Theme.textSecondary
                        }
                        GComboBox {
                            id: configCombo
                            implicitWidth: 150
                            model: ArtifactScan.availableConfigNames
                            currentIndex: ArtifactScan.activeConfigIndex
                            onActivated: (index) => ArtifactScan.setActiveConfigByIndex(index)
                        }
                    }

                    Text {
                        text: ArtifactScan.activeConfigCols + "×" + ArtifactScan.activeConfigRows
                              + " | 格子 " + ArtifactScan.activeConfigSlotW + "×" + ArtifactScan.activeConfigSlotH
                              + " | ROI(" + ArtifactScan.activeConfigRoiX + "," + ArtifactScan.activeConfigRoiY
                              + "," + ArtifactScan.activeConfigRoiW + "," + ArtifactScan.activeConfigRoiH + ")"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }
                }
            }

            // ==== 扫描选项 ====
            GCard {
                title: "扫描选项"
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 8

                    // 去重开关（仅五星模式可用）
                    GCheckBox {
                        id: dedupCheck
                        text: "启用圣遗物去重检测"
                        enabled: ArtifactScan.scanStopMode === "five_star_only"
                        Component.onCompleted: checked = ArtifactScan.scanEnableDedup
                        onToggled: ArtifactScan.setScanEnableDedup(checked)
                    }

                    Text {
                        visible: ArtifactScan.scanStopMode !== "five_star_only"
                        text: "去重仅在「仅扫描五星」模式下可用"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    // 停止条件
                    RowLayout {
                        spacing: 8
                        Text {
                            text: "停止条件:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            color: Theme.textPrimary
                        }
                        GComboBox {
                            id: stopModeCombo
                            anchors.verticalCenter: undefined
                            Layout.preferredWidth: 140
                            model: ["首尾锚点定位", "仅扫描五星", "固定扫描数量"]
                            currentIndex: ArtifactScan.scanStopModeIndex
                            onActivated: function(index) {
                                ArtifactScan.setScanStopModeByIndex(index);
                            }
                        }
                    }

                    // 固定数量（仅固定数量模式可见）
                    RowLayout {
                        spacing: 8
                        visible: ArtifactScan.scanStopMode === "fixed_count"
                        Text {
                            text: "扫描数量:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            color: Theme.textPrimary
                        }
                        GSpinBox {
                            id: fixedCountSpin
                            anchors.verticalCenter: undefined
                            Layout.preferredWidth: 80
                            from: 1
                            to: 9999
                            Component.onCompleted: value = ArtifactScan.scanFixedCount > 0 ? ArtifactScan.scanFixedCount : 100
                            onValueChanged: ArtifactScan.setScanFixedCount(value)
                        }
                    }

                    // 模式提示
                    Text {
                        visible: ArtifactScan.scanStopMode === "anchor"
                        text: "💡 首锚点为圣遗物, 尾锚点为强化材料(3★/4★)。"
                              + "扫描到尾锚点时自动停止。需背包底部有强化材料方可使用。"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: ArtifactScan.scanStopMode === "five_star_only"
                        text: "💡 仅扫描五星圣遗物, 非五星直接跳过。"
                              + "去重仅对五星生效, 四星不参与去重。"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: ArtifactScan.scanStopMode === "fixed_count"
                        text: "💡 扫描指定数量后自动停止, 进度使用输入数量计算剩余时间。"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            // ==== 全量扫描 ====
            GCard {
                title: "全量扫描"
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 10

                    // 步骤提示
                    Text {
                        text: ArtifactScan.fullScanStep
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        color: Theme.accent
                        visible: ArtifactScan.fullScanStep !== ""
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 进度
                    Text {
                        text: ArtifactScan.fullScanProgress
                              + (ArtifactScan.fullScanCurrentPage > 0
                                 ? " | 第 " + ArtifactScan.fullScanCurrentPage
                                   + "/" + ArtifactScan.fullScanTotalPages + " 页"
                                 : "")
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.accent
                        visible: ArtifactScan.fullScanProgress !== ""
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 按钮
                    RowLayout {
                        spacing: 10

                        GButton {
                            text: ArtifactScan.fullScanRunning ? "扫描中…" : "开始扫描"
                            colorType: "primary"
                            enabled: !ArtifactScan.fullScanRunning
                            onClicked: ArtifactScan.startFullScan()
                        }

                        GButton {
                            text: "停止扫描"
                            colorType: "default"
                            visible: ArtifactScan.fullScanRunning
                            onClicked: ArtifactScan.stopFullScan()
                        }
                    }
                }
            }

            // ==== 扫描结果 ====
            GCard {
                title: "扫描结果"
                Layout.fillWidth: true
                visible: ArtifactScan.fullScanSavedPath !== ""

                ColumnLayout {
                    spacing: 6

                    Text {
                        text: "上次扫描已完成，结果已保存至:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }
                    Text {
                        text: ArtifactScan.fullScanSavedPath
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.accent
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                    }
                }
            }

            // 底部留白
            Item { Layout.fillHeight: true }
        }
    }
}