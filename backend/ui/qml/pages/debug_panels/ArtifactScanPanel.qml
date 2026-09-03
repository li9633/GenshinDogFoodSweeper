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

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    RowLayout {
                        spacing: 8

                        Text {
                            text: "原神运行状态:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            color: Theme.textSecondary
                        }

                        Rectangle {
                            width: 12
                            height: 12
                            radius: 6
                            color: GameDetector.statusColor
                        }

                        Text {
                            text: GameDetector.statusText
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                            color: GameDetector.isRunning ? GameDetector.statusColor : Theme.textSecondary
                        }
                    }

                    Text {
                        visible: GameDetector.isRunning
                        text: "窗口位置: (" + GameDetector.winLeft + ", " + GameDetector.winTop
                              + ") 大小: " + GameDetector.winWidth + "x" + GameDetector.winHeight
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }
                }
            }

            // === 格子定位 ===
            GCard {
                title: "格子定位 (P页R行C列)"
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 6

                    RowLayout {
                        spacing: 4
                        Text { text: "页"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                        GSpinBox { id: navPage; from: 0; to: 99; value: 0; editable: true; Layout.preferredWidth: 80 }
                        Text { text: "行"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                        GSpinBox { id: navRow; from: 0; to: 7; value: 0; editable: true; Layout.preferredWidth: 80 }
                        Text { text: "列"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                        GSpinBox { id: navCol; from: 0; to: 7; value: 0; editable: true; Layout.preferredWidth: 80 }
                    }

                    GButton {
                        text: "定位并点击"
                        colorType: "primary"
                        onClicked: ArtifactScanDebug.navigateToSlot(navPage.value, navRow.value, navCol.value)
                    }
                }
            }

            // 底部留白
            Item { Layout.fillHeight: true }

            // ---- 格子翻页（基于格子检测，动态计算滚动距离） ----
            GCard {
                title: "格子翻页"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    // 配置选择
                    RowLayout {
                        spacing: 4
                        Text {
                            text: "检测配置:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            color: Theme.textSecondary
                        }
                        GComboBox {
                            id: configCombo
                            implicitWidth: 160
                            model: ArtifactScanDebug.availableConfigNames
                            currentIndex: ArtifactScanDebug.activeConfigIndex
                            onActivated: (index) => ArtifactScanDebug.setActiveConfigByIndex(index)
                        }
                        Text {
                            text: ArtifactScanDebug.activeConfigHasCount ? "" : "(无数量显示)"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.warning
                        }
                    }

                    Text {
                        text: "截图 → 检测格子 → 计算最后一行底部Y坐标 → 自动滚动"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 锚点坐标（滚动时鼠标所在位置，确保滚轮事件发给原神）
                    RowLayout {
                        spacing: 4
                        Text { text: "锚点X:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: scrollFlagX; from: 0; to: 9999; value: 230 }
                        Text { text: "锚点Y:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: scrollFlagY; from: 0; to: 9999; value: 335 }
                        Text { text: "延迟(ms):"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: scrollDelay; from: 10; to: 500; value: 80 }
                    }

                    // 按钮
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "格子翻页"
                            colorType: "success"
                            onClicked: ArtifactScanDebug.scrollPageByDetection(scrollFlagX.value, scrollFlagY.value, scrollDelay.value)
                        }

                        GButton {
                            text: "自动翻到底"
                            colorType: "primary"
                            onClicked: ArtifactScanDebug.scrollPageToBottom(scrollFlagX.value, scrollFlagY.value, scrollDelay.value)
                        }
                    }

                    Text {
                        text: "提示：「格子翻页」翻一页，「自动翻到底」循环翻页直到检测到底部"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            // ---- 网格批量点击 ----
            GCard {
                title: "网格批量点击"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "当前配置: " + ArtifactScanDebug.activeConfigName
                              + " | " + ArtifactScanDebug.activeConfigCols + "×" + ArtifactScanDebug.activeConfigRows
                              + " | 格子: " + ArtifactScanDebug.activeConfigSlotW + "×" + ArtifactScanDebug.activeConfigSlotH
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.accent
                    }

                    Text {
                        text: "ROI: (" + ArtifactScanDebug.activeConfigRoiX + ", " + ArtifactScanDebug.activeConfigRoiY
                              + ", " + ArtifactScanDebug.activeConfigRoiW + ", " + ArtifactScanDebug.activeConfigRoiH + ")"
                              + " | 间距: " + ArtifactScanDebug.gridGap + "px | 点击间隔: " + ArtifactScanDebug.batchClickInterval + "ms"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    // 按钮 + 进度
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: ArtifactScanDebug.batchRunning ? "点击中…" : "连续点击"
                            colorType: "primary"
                            enabled: !ArtifactScanDebug.batchRunning
                            onClicked: ArtifactScanDebug.startBatchClick()
                        }

                        GButton {
                            text: "停止"
                            colorType: "default"
                            visible: ArtifactScanDebug.batchRunning
                            onClicked: ArtifactScanDebug.stopBatchClick()
                        }

                        Text {
                            text: ArtifactScanDebug.batchProgress
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                            color: Theme.accent
                            visible: ArtifactScanDebug.batchProgress !== ""
                        }
                    }
                }
            }

            // ---- 首尾锚点定位 ----
            GCard {
                title: "首尾锚点定位"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "手动滚到顶部识别首锚点 → 智能拖拽到底 → 识别尾锚点 → 计算页数"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 首锚点（滚动到顶部后点击定位）
                    Text {
                        text: "请先滚动到顶部，再点击下方按钮自动定位首个圣遗物"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "定位首锚点"
                            colorType: "primary"
                            enabled: !ArtifactScanDebug.anchorScrollRunning
                            onClicked: ArtifactScanDebug.recognizeFirstAnchor()
                        }

                        Text {
                            text: ArtifactScanDebug.anchorFirstX > 0
                                ? "已定位: (" + ArtifactScanDebug.anchorFirstX + ", " + ArtifactScanDebug.anchorFirstY + ")"
                                : "未定位"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: ArtifactScanDebug.anchorFirstX > 0 ? Theme.accent : Theme.textSecondary
                        }

                        Text {
                            visible: ArtifactScanDebug.anchorFirstRecognized
                            text: "首锚点识别结果:\n" + ArtifactScanDebug.anchorFirstDisplayText
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.accent
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    // 智能拖拽到底（检测顶部 → 拖拽 → 检测底部 → 完成）
                    Text {
                        text: "滑轨区域由当前格子检测配置自动计算"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "智能拖拽到底"
                            colorType: "primary"
                            enabled: ArtifactScanDebug.anchorFirstX > 0 && !ArtifactScanDebug.anchorScrollRunning
                            onClicked: ArtifactScanDebug.scrollToBottom()
                        }

                        GButton {
                            text: "颜色检测是否到底"
                            colorType: "primary"
                            enabled: ArtifactScanDebug.anchorFirstX > 0 && !ArtifactScanDebug.anchorScrollRunning
                            onClicked: ArtifactScanDebug.checkScrollBottomByColor()
                        }
                    }

                    // 灰度截图
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "灰度截图"
                            colorType: "default"
                            onClicked: ArtifactScanDebug.captureGrayscalePreview()
                        }

                        Text {
                            text: "独立灰度截图，用于测量颜色值"
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textSecondary
                        }
                    }

                    // 格子检测
                    ColumnLayout {
                        spacing: 4

                        Text {
                            text: "格子检测"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                            color: Theme.textPrimary
                        }

                        Text {
                            text: "当前配置: " + ArtifactScanDebug.activeConfigName
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.accent
                        }

                        Text {
                            text: "ROI: (" + ArtifactScanDebug.activeConfigRoiX + ", " + ArtifactScanDebug.activeConfigRoiY
                                  + ", " + ArtifactScanDebug.activeConfigRoiW + ", " + ArtifactScanDebug.activeConfigRoiH + ")"
                                  + " | " + ArtifactScanDebug.activeConfigCols + "×" + ArtifactScanDebug.activeConfigRows
                                  + " | 格子: " + ArtifactScanDebug.activeConfigSlotW + "×" + ArtifactScanDebug.activeConfigSlotH
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textSecondary
                        }

                        Text {
                            text: "左offset: " + ArtifactScanDebug.activeConfigLeftOffset + "px"
                                  + " | 右offset: " + ArtifactScanDebug.activeConfigRightOffset + "px"
                                  + " | 上offset: " + ArtifactScanDebug.activeConfigTopOffset + "px"
                                  + " | 白色阈值: " + ArtifactScanDebug.activeConfigWhiteThreshold
                                  + " | 容差: " + ArtifactScanDebug.activeConfigTolerance
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textSecondary
                        }

                        RowLayout {
                            spacing: 6
                            GButton {
                                text: "检测格子"
                                colorType: "primary"
                                onClicked: ArtifactScanDebug.detectSlots()
                            }
                            Text {
                                text: "使用当前选中配置检测格子，结果绘制到预览窗口"
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: Theme.textSecondary
                            }
                        }

                        RowLayout {
                            spacing: 6
                            GButton {
                                text: "连续检测"
                                colorType: "warning"
                                onClicked: ArtifactScanDebug.detectSlotsRepeatedly(repeatCount.value)
                            }
                            GSpinBox {
                                id: repeatCount
                                from: 2
                                to: 100
                                value: 10
                                editable: true
                                Layout.preferredWidth: 80
                            }
                            Text {
                                text: "次，比对格子数量是否一致"
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: Theme.textSecondary
                            }
                        }
                    }

                    // 尾锚点（滚动到底部后点击定位）
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "定位尾锚点"
                            colorType: "primary"
                            enabled: !ArtifactScanDebug.anchorScrollRunning && ArtifactScanDebug.anchorFirstX > 0
                            onClicked: ArtifactScanDebug.recognizeLastAnchor()
                        }

                        Text {
                            text: ArtifactScanDebug.anchorLastX > 0
                                ? "已定位: (" + ArtifactScanDebug.anchorLastX + ", " + ArtifactScanDebug.anchorLastY + ")"
                                : "未定位"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: ArtifactScanDebug.anchorLastX > 0 ? Theme.accent : Theme.textSecondary
                        }
                    }

                    Text {
                        visible: ArtifactScanDebug.anchorTailRecognized
                        text: "尾锚点识别结果:\n" + ArtifactScanDebug.anchorTailDisplayText
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.accent
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 计算结果
                    Text {
                        text: "计算结果: " + ArtifactScanDebug.anchorTotalRows + " 行, "
                              + ArtifactScanDebug.anchorTotalPages + " 页"
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        font.bold: true
                        color: ArtifactScanDebug.anchorTotalPages > 0 ? Theme.accent : Theme.textSecondary
                    }


                }
            }

            // 底部留白
            Item { Layout.fillHeight: true }
        }
    }
}