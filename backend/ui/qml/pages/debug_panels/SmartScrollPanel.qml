import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// ArtifactScan 是 Python 通过 setContextProperty 注入的上下文属性

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

            // ---- 游戏状态 ----
            GCard {
                title: "游戏状态"
                Layout.fillWidth: true

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spacing

                    GButton {
                        text: "聚焦游戏"
                        onClicked: ArtifactScan.focusGame()
                    }

                    GButton {
                        text: "滚动到顶"
                        onClicked: ArtifactScan.smartScrollToTop()
                    }
                }
            }

            // ---- 校准 ----
            GCard {
                title: "校准"
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 8

                    RowLayout {
                        spacing: Theme.spacing
                        GButton {
                            text: "测量行高"
                            onClicked: ArtifactScan.smartMeasureRowHeight()
                        }
                        GButton {
                            text: "校准"
                            onClicked: ArtifactScan.smartCalibrate()
                        }
                    }
                    Text {
                        text: "px/tick: " + ArtifactScan.smartPixelsPerScroll.toFixed(2)
                        font.family: Theme.fontFamily
                        color: Theme.textPrimary
                    }
                    Text {
                        text: ArtifactScan.smartCalibrated ? "✅ 已校准" : "❌ 未校准 (请先测量行高 → 校准)"
                        font.family: Theme.fontFamily
                        color: ArtifactScan.smartCalibrated ? Theme.accent : Theme.textSecondary
                    }
                }
            }

            // ---- 翻行 ----
            GCard {
                title: "翻行"
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 8

                    RowLayout {
                        spacing: Theme.spacing
                        Text {
                            text: "行数:"
                            font.family: Theme.fontFamily
                            color: Theme.textPrimary
                        }
                        GSpinBox {
                            id: scrollRowsInput
                            value: 8
                            from: 1; to: 1000
                        }
                        GButton {
                            text: "翻行"
                            onClicked: ArtifactScan.smartScrollRows(scrollRowsInput.value)
                        }
                    }

                    Text {
                        text: "当前行: " + ArtifactScan.smartCurrentRow
                        font.family: Theme.fontFamily
                        color: Theme.textPrimary
                    }
                }
            }

            // ---- 重置 ----
            GCard {
                title: "状态"
                Layout.fillWidth: true

                RowLayout {
                    spacing: Theme.spacing
                    GButton {
                        text: "重置"
                        onClicked: ArtifactScan.smartReset()
                    }
                }
            }
        }
    }
}