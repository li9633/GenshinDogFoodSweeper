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
                        onClicked: ArtifactScan.navigateToSlot(navPage.value, navRow.value, navCol.value)
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
                            model: ArtifactScan.availableConfigNames
                            currentIndex: ArtifactScan.activeConfigIndex
                            onActivated: (index) => ArtifactScan.setActiveConfigByIndex(index)
                        }
                        Text {
                            text: ArtifactScan.activeConfigHasCount ? "" : "(无数量显示)"
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
                            onClicked: ArtifactScan.scrollPageByDetection(scrollFlagX.value, scrollFlagY.value, scrollDelay.value)
                        }

                        GButton {
                            text: "自动翻到底"
                            colorType: "primary"
                            onClicked: ArtifactScan.scrollPageToBottom(scrollFlagX.value, scrollFlagY.value, scrollDelay.value)
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
                        text: "当前配置: " + ArtifactScan.activeConfigName
                              + " | " + ArtifactScan.activeConfigCols + "×" + ArtifactScan.activeConfigRows
                              + " | 格子: " + ArtifactScan.activeConfigSlotW + "×" + ArtifactScan.activeConfigSlotH
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.accent
                    }

                    Text {
                        text: "ROI: (" + ArtifactScan.activeConfigRoiX + ", " + ArtifactScan.activeConfigRoiY
                              + ", " + ArtifactScan.activeConfigRoiW + ", " + ArtifactScan.activeConfigRoiH + ")"
                              + " | 间距: " + ArtifactScan.gridGap + "px | 点击间隔: " + ArtifactScan.batchClickInterval + "ms"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    // 按钮 + 进度
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: ArtifactScan.batchRunning ? "点击中…" : "连续点击"
                            colorType: "primary"
                            enabled: !ArtifactScan.batchRunning
                            onClicked: ArtifactScan.startBatchClick()
                        }

                        GButton {
                            text: "停止"
                            colorType: "default"
                            visible: ArtifactScan.batchRunning
                            onClicked: ArtifactScan.stopBatchClick()
                        }

                        Text {
                            text: ArtifactScan.batchProgress
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                            color: Theme.accent
                            visible: ArtifactScan.batchProgress !== ""
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
                            enabled: !ArtifactScan.anchorScrollRunning
                            onClicked: ArtifactScan.recognizeFirstAnchor()
                        }

                        Text {
                            text: ArtifactScan.anchorFirstX > 0
                                ? "已定位: (" + ArtifactScan.anchorFirstX + ", " + ArtifactScan.anchorFirstY + ")"
                                : "未定位"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: ArtifactScan.anchorFirstX > 0 ? Theme.accent : Theme.textSecondary
                        }

                        Text {
                            visible: ArtifactScan.anchorFirstRecognized
                            text: "首锚点识别结果:\n" + ArtifactScan.anchorFirstDisplayText
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
                            enabled: ArtifactScan.anchorFirstX > 0 && !ArtifactScan.anchorScrollRunning
                            onClicked: ArtifactScan.scrollToBottom()
                        }

                        GButton {
                            text: "颜色检测是否到底"
                            colorType: "primary"
                            enabled: ArtifactScan.anchorFirstX > 0 && !ArtifactScan.anchorScrollRunning
                            onClicked: ArtifactScan.checkScrollBottomByColor()
                        }
                    }

                    // 灰度截图
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "灰度截图"
                            colorType: "default"
                            onClicked: ArtifactScan.captureGrayscalePreview()
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
                            text: "当前配置: " + ArtifactScan.activeConfigName
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.accent
                        }

                        Text {
                            text: "ROI: (" + ArtifactScan.activeConfigRoiX + ", " + ArtifactScan.activeConfigRoiY
                                  + ", " + ArtifactScan.activeConfigRoiW + ", " + ArtifactScan.activeConfigRoiH + ")"
                                  + " | " + ArtifactScan.activeConfigCols + "×" + ArtifactScan.activeConfigRows
                                  + " | 格子: " + ArtifactScan.activeConfigSlotW + "×" + ArtifactScan.activeConfigSlotH
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textSecondary
                        }

                        Text {
                            text: "左offset: " + ArtifactScan.activeConfigLeftOffset + "px"
                                  + " | 右offset: " + ArtifactScan.activeConfigRightOffset + "px"
                                  + " | 上offset: " + ArtifactScan.activeConfigTopOffset + "px"
                                  + " | 白色阈值: " + ArtifactScan.activeConfigWhiteThreshold
                                  + " | 容差: " + ArtifactScan.activeConfigTolerance
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textSecondary
                        }

                        RowLayout {
                            spacing: 6
                            GButton {
                                text: "检测格子"
                                colorType: "primary"
                                onClicked: ArtifactScan.detectSlots()
                            }
                            Text {
                                text: "使用当前选中配置检测格子，结果绘制到预览窗口"
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
                            enabled: !ArtifactScan.anchorScrollRunning && ArtifactScan.anchorFirstX > 0
                            onClicked: ArtifactScan.recognizeLastAnchor()
                        }

                        Text {
                            text: ArtifactScan.anchorLastX > 0
                                ? "已定位: (" + ArtifactScan.anchorLastX + ", " + ArtifactScan.anchorLastY + ")"
                                : "未定位"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: ArtifactScan.anchorLastX > 0 ? Theme.accent : Theme.textSecondary
                        }
                    }

                    Text {
                        visible: ArtifactScan.anchorTailRecognized
                        text: "尾锚点识别结果:\n" + ArtifactScan.anchorTailDisplayText
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.accent
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 计算结果
                    Text {
                        text: "计算结果: " + ArtifactScan.anchorTotalRows + " 行, "
                              + ArtifactScan.anchorTotalPages + " 页"
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        font.bold: true
                        color: ArtifactScan.anchorTotalPages > 0 ? Theme.accent : Theme.textSecondary
                    }


                }
            }

            // ---- 圣遗物扫描（全量） ----
            GCard {
                title: "圣遗物扫描"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "一键全量扫描：识别数量 → 锚点定位 → 逐格识别 → 自动翻页 → 数量验证"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 网格参数（来自当前检测配置）
                    Text {
                        text: "当前配置: " + ArtifactScan.activeConfigName
                              + " | " + ArtifactScan.activeConfigCols + "×" + ArtifactScan.activeConfigRows
                              + " | 格子: " + ArtifactScan.activeConfigSlotW + "×" + ArtifactScan.activeConfigSlotH
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.accent
                    }

                    Text {
                        text: "ROI: (" + ArtifactScan.activeConfigRoiX + ", " + ArtifactScan.activeConfigRoiY
                              + ", " + ArtifactScan.activeConfigRoiW + ", " + ArtifactScan.activeConfigRoiH + ")"
                              + " | 间距: " + ArtifactScan.gridGap + "px | 点击间隔: " + ArtifactScan.fullScanClickInterval + "ms"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    Text {
                        text: "翻页参数: 锚点(" + ArtifactScan.scrollFlagX + ", " + ArtifactScan.scrollFlagY
                              + ") | 滚动延迟: " + ArtifactScan.scrollTickDelay + "ms | 页面等待: " + ArtifactScan.scrollPageSettle + "ms"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    // 控制按钮
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: ArtifactScan.fullScanRunning ? "扫描中…" : "开始圣遗物扫描"
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

                    // 进度显示
                    Text {
                        text: "步骤: " + ArtifactScan.fullScanStep
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        color: Theme.accent
                        visible: ArtifactScan.fullScanStep !== ""
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "进度: " + ArtifactScan.fullScanProgress
                              + (ArtifactScan.fullScanCurrentPage > 0 ? " | 第 " + ArtifactScan.fullScanCurrentPage + "/" + ArtifactScan.fullScanTotalPages + " 页" : "")
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.accent
                        visible: ArtifactScan.fullScanProgress !== ""
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            // 底部留白
            Item { Layout.fillHeight: true }
        }
    }
}