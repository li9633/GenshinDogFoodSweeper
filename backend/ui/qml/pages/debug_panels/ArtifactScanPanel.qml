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
                            color: GameDetector.isRunning ? "#4CAF50" : "#EF5350"
                        }

                        Text {
                            text: GameDetector.isRunning ? "运行中" : "未检测到"
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                            color: GameDetector.isRunning ? "#4CAF50" : Theme.textSecondary
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

            // ---- 鼠标操作 ----
            GCard {
                title: "鼠标操作（窗口内相对坐标）"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "坐标相对于原神窗口左上角，自动转换为屏幕绝对坐标"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    // 坐标输入
                    RowLayout {
                        spacing: 4

                        Text {
                            text: "X:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            color: Theme.textSecondary
                        }
                        GSpinBox {
                            id: spinX
                            from: 0
                            to: 9999
                            value: 180
                        }
                        Text {
                            text: "Y:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            color: Theme.textSecondary
                        }
                        GSpinBox {
                            id: spinY
                            from: 0
                            to: 9999
                            value: 266
                        }
                    }

                    // 操作按钮
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "聚焦窗口"
                            colorType: "default"
                            onClicked: ArtifactScan.focusGame()
                        }

                        GButton {
                            text: "移动到坐标"
                            colorType: "default"
                            onClicked: ArtifactScan.moveTo(spinX.value, spinY.value)
                        }

                        GButton {
                            text: "点击坐标"
                            colorType: "primary"
                            onClicked: ArtifactScan.clickAt(spinX.value, spinY.value)
                        }
                    }

                    Text {
                        text: "提示：聚焦窗口只需点一次，点击坐标耗时 ~10ms，批量扫描前先聚焦"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 结果文字
                    Text {
                        text: ArtifactScan.clickResult
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                        visible: ArtifactScan.clickResult !== ""
                    }
                }
            }

            // ---- 滚轮操作 ----
            GCard {
                title: "滚轮操作"
                Layout.fillWidth: true

                RowLayout {
                    spacing: 6

                    GButton {
                        text: "滚轮上 (-1)"
                        colorType: "default"
                        onClicked: ArtifactScan.scrollWheel(-1)
                    }

                    GButton {
                        text: "滚轮下 (+1)"
                        colorType: "default"
                        onClicked: ArtifactScan.scrollWheel(1)
                    }
                }
            }

            // 底部留白
            Item { Layout.fillHeight: true }

            // ---- 精准翻页（yas 视觉锚点状态机） ----
            GCard {
                title: "精准翻页"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "固定滚 10 格 = 1 行（4 行为一页时需滚 40 格）"
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

                    // 进度
                    Text {
                        text: "已滚 " + ArtifactScan.scrollTicks + " / 10 格"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                        visible: ArtifactScan.scrollTicks > 0
                    }

                    // 按钮
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "精准滚一行"
                            colorType: "primary"
                            enabled: !ArtifactScan.scrollRunning
                            onClicked: ArtifactScan.scrollOneRow(scrollFlagX.value, scrollFlagY.value, scrollDelay.value)
                        }

                        GButton {
                            text: "重置"
                            colorType: "default"
                            onClicked: ArtifactScan.resetScrollState()
                        }
                    }

                    Text {
                        text: "提示：先聚焦原神窗口，再点击\"精准滚一行\"自动滚动 10 格"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            // ---- 自动翻页（OCR 识别数量 + 逐页滚动） ----
            GCard {
                title: "自动翻页"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "每页: 4 行 × 8 列 = 32 个圣遗物"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    // ROI 区域（背包右上角圣遗物数量显示区域）
                    Text {
                        text: "ROI 区域（背包右上角数量显示，屏幕绝对坐标）:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        spacing: 4

                        Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: roiX; from: 0; to: 9999; value: 1606 }
                        Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: roiY; from: 0; to: 9999; value: 52 }
                        Text { text: "W:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: roiW; from: 10; to: 9999; value: 206 }
                        Text { text: "H:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: roiH; from: 10; to: 9999; value: 49 }
                    }

                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "OCR 识别数量"
                            colorType: "primary"
                            onClicked: ArtifactScan.ocrCount(roiX.value, roiY.value, roiW.value, roiH.value)
                        }

                        Text {
                            text: "识别结果: " + ArtifactScan.detectedCount + " 个，共 "
                                  + ArtifactScan.detectedTotalPages + " 页"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                            color: Theme.accent
                            visible: ArtifactScan.detectedCount > 0
                        }
                    }

                    // 滚动参数
                    Text {
                        text: "滚动参数:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        spacing: 4

                        Text { text: "锚点X:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: autoScrollFlagX; from: 0; to: 9999; value: 230 }
                        Text { text: "锚点Y:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: autoScrollFlagY; from: 0; to: 9999; value: 335 }
                        Text { text: "每行次数:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: ticksPerRow; from: 5; to: 20; value: 10 }
                        Text { text: "滚动延迟(ms):"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: autoTickDelay; from: 10; to: 500; value: 30 }
                        Text { text: "页面等待(ms):"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: pageSettleMs; from: 100; to: 5000; value: 200 }
                    }

                    // 控制按钮 + 进度
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "开始自动翻页"
                            colorType: "primary"
                            enabled: !ArtifactScan.autoScanRunning && ArtifactScan.detectedCount > 0
                            onClicked: ArtifactScan.startAutoScroll(
                                    autoScrollFlagX.value, autoScrollFlagY.value,
                                    ticksPerRow.value, autoTickDelay.value, pageSettleMs.value
                                )
                        }

                        GButton {
                            text: "停止"
                            colorType: "default"
                            visible: ArtifactScan.autoScanRunning
                            onClicked: ArtifactScan.stopAutoScroll()
                        }

                        Text {
                            text: "进度: " + ArtifactScan.autoScanProgress
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                            color: Theme.accent
                            visible: ArtifactScan.autoScanProgress !== ""
                        }
                    }

                    Text {
                        text: "提示：先点击「OCR 识别数量」获取总页数，再点击「开始自动翻页」逐页滚动到底"
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
                        text: "公式: X = marginX + (gap + 宽) × col + 宽/2, Y = marginY + (gap + 高) × row + 高/2"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 边距
                    RowLayout {
                        spacing: 4
                        Text { text: "边距X:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridMarginX; from: 0; to: 9999; value: 118 }
                        Text { text: "边距Y:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridMarginY; from: 0; to: 9999; value: 189 }
                    }

                    // 物品尺寸 + 间距
                    RowLayout {
                        spacing: 4
                        Text { text: "宽:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridItemW; from: 1; to: 999; value: 124 }
                        Text { text: "高:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridItemH; from: 1; to: 999; value: 155 }
                        Text { text: "间距:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridGap; from: 0; to: 999; value: 24 }
                    }

                    // 行列 + 间隔
                    RowLayout {
                        spacing: 4
                        Text { text: "行:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridRows; from: 1; to: 10; value: 4 }
                        Text { text: "列:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridCols; from: 1; to: 10; value: 8 }
                        Text { text: "间隔(ms):"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: gridInterval; from: 0; to: 5000; value: 100 }
                    }

                    // 按钮 + 进度
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: ArtifactScan.batchRunning ? "点击中…" : "连续点击"
                            colorType: "primary"
                            enabled: !ArtifactScan.batchRunning
                            onClicked: ArtifactScan.startBatchClick(
                                            gridMarginX.value, gridMarginY.value,
                                            gridItemW.value, gridItemH.value, gridGap.value,
                                            gridRows.value, gridCols.value, gridInterval.value
                                            )
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
                        text: "手动滚到顶部标记首锚点 → 自动滚到底部 → 查找尾锚点 → 计算页数"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    // 首锚点参数
                    Text {
                        text: "首锚点（假设已滚到顶部，固定位置 118,189）:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        spacing: 4
                        Text { text: "W:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorFirstW; from: 10; to: 999; value: 124 }
                        Text { text: "H:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorFirstH; from: 10; to: 999; value: 155 }

                        GButton {
                            text: "标记首锚点"
                            colorType: "primary"
                            onClicked: ArtifactScan.markFirstAnchor(118, 189, anchorFirstW.value, anchorFirstH.value)
                        }

                        Text {
                            text: "已标记: (118, 189) " + ArtifactScan.anchorFirstW + "x" + ArtifactScan.anchorFirstH
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: ArtifactScan.anchorFirstX > 0 ? Theme.accent : Theme.textSecondary
                        }
                    }

                    // 滚动条拖拽（使用模板「背包滚动条滑块」的 region 自动定位）
                    Text {
                        text: "滚动条轨道高度（滑块从顶到底的像素距离）:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        spacing: 6

                        Text { text: "轨道高度(px):"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: scrollbarTrackHeight; from: 100; to: 2000; value: 760 }

                        GButton {
                            text: "智能滚轮到底"
                            colorType: "primary"
                            enabled: ArtifactScan.anchorFirstX > 0 && !ArtifactScan.anchorScrollRunning
                            onClicked: {
                                ArtifactScan.scrollbarTrackHeight = scrollbarTrackHeight.value
                                ArtifactScan.scrollToBottom()
                            }
                        }

                        Text {
                            text: "滚动: " + ArtifactScan.anchorScrollProgress
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                            color: Theme.accent
                            visible: ArtifactScan.anchorScrollProgress !== ""
                        }
                    }

                    Connections {
                        target: ArtifactScan
                        function onScrollbarDragFinished() {
                            ArtifactScan.findLastAnchor()
                        }
                    }

                    // 滚到底部参数
                    Text {
                        text: "或使用滚轮方式（锚点坐标 + 滚动次数 + 延迟）:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    RowLayout {
                        spacing: 4
                        Text { text: "锚点X:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorScrollFlagX; from: 0; to: 9999; value: 230 }
                        Text { text: "锚点Y:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorScrollFlagY; from: 0; to: 9999; value: 335 }
                        Text { text: "总次数:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorTotalTicks; from: 10; to: 2000; value: 400 }
                        Text { text: "延迟(ms):"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorTickDelay; from: 10; to: 500; value: 20 }
                    }

                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "滚到底部"
                            colorType: "primary"
                            enabled: !ArtifactScan.anchorScrollRunning && ArtifactScan.anchorFirstX > 0
                            onClicked: ArtifactScan.startScrollToBottom(
                                anchorScrollFlagX.value, anchorScrollFlagY.value,
                                anchorTotalTicks.value, anchorTickDelay.value
                            )
                        }

                        GButton {
                            text: "停止"
                            colorType: "default"
                            visible: ArtifactScan.anchorScrollRunning
                            onClicked: ArtifactScan.stopScrollToBottom()
                        }

                        Text {
                            text: "滚动: " + ArtifactScan.anchorScrollProgress
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.bold: true
                            color: Theme.accent
                            visible: ArtifactScan.anchorScrollProgress !== ""
                        }
                    }

                    // 尾锚点 + 计算结果
                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "查找尾锚点"
                            colorType: "primary"
                            enabled: !ArtifactScan.anchorScrollRunning && ArtifactScan.anchorFirstX > 0
                            onClicked: ArtifactScan.findLastAnchor()
                        }

                        Text {
                            text: "尾锚点: (" + ArtifactScan.anchorLastX + ", " + ArtifactScan.anchorLastY + ")"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: ArtifactScan.anchorLastY > 0 ? Theme.accent : Theme.textSecondary
                        }
                    }

                    // 手动尾锚点
                    RowLayout {
                        spacing: 4
                        Text { text: "手动尾X:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorLastX; from: 0; to: 9999; value: 0 }
                        Text { text: "手动尾Y:"; font.family: Theme.fontFamily; font.pixelSize: 14; color: Theme.textSecondary }
                        GSpinBox { id: anchorLastY; from: 0; to: 9999; value: 0 }

                        GButton {
                            text: "手动标记尾锚点"
                            colorType: "default"
                            onClicked: ArtifactScan.markLastAnchor(anchorLastX.value, anchorLastY.value)
                        }
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

                    Text {
                        text: ArtifactScan.clickResult
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                        visible: ArtifactScan.clickResult !== ""
                    }
                }
            }
        }
    }
}