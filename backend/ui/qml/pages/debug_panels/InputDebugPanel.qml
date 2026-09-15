import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// InputDebug 是 Python 通过 setContextProperty 注入的上下文属性

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

            // ---- 窗口信息（WindowHelper） ----
            GCard {
                title: "窗口信息（WindowHelper）"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: "窗口原点(屏幕): (" + InputDebug.winOriginX + ", " + InputDebug.winOriginY + ")"
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        color: InputDebug.isWindowFound ? Theme.accent : Theme.textSecondary
                    }

                    Text {
                        text: "窗口句柄(HWND): " + InputDebug.winHwnd
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    Text {
                        text: "屏幕分辨率: " + InputDebug.screenWidth + "x" + InputDebug.screenHeight
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    Text {
                        text: "管理员权限: " + (InputDebug.isAdmin ? "是" : "否")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: InputDebug.isAdmin ? Theme.success : Theme.warning
                    }

                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "聚焦窗口"
                            colorType: "primary"
                            implicitWidth: 100
                            onClicked: InputDebug.focusWindow()
                        }

                        GButton {
                            text: "刷新信息"
                            colorType: "default"
                            implicitWidth: 100
                            onClicked: InputDebug.refreshWindowInfo()
                        }
                    }
                }
            }

            // ---- 鼠标移动与点击（MouseController） ----
            GCard {
                title: "鼠标移动与点击（窗口相对坐标）"
                subtitle: "坐标相对于原神窗口左上角，MouseController 自动转换为屏幕绝对坐标"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

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

                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "移动"
                            colorType: "default"
                            onClicked: InputDebug.moveTo(spinX.value, spinY.value)
                        }

                        GButton {
                            text: "点击（当前位置）"
                            colorType: "default"
                            onClicked: InputDebug.click()
                        }

                        GButton {
                            text: "移动并点击"
                            colorType: "primary"
                            onClicked: InputDebug.moveAndClick(spinX.value, spinY.value)
                        }
                    }
                }
            }

            // ---- 滚轮测试 ----
            GCard {
                title: "滚轮测试"
                subtitle: "鼠标需悬停在原神窗口内，滚轮事件才能被游戏接收"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    RowLayout {
                        spacing: 6

                        GButton {
                            text: "上滚 1 格"
                            colorType: "default"
                            onClicked: InputDebug.scroll(1)
                        }

                        GButton {
                            text: "下滚 1 格"
                            colorType: "default"
                            onClicked: InputDebug.scroll(-1)
                        }

                        GButton {
                            text: "下滚 5 格"
                            colorType: "primary"
                            onClicked: InputDebug.scroll(-5)
                        }
                    }
                }
            }

            // ---- 拖拽测试 ----
            GCard {
                title: "拖拽测试"
                subtitle: "从起点拖拽到终点，模拟滑轨拖拽"
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    RowLayout {
                        spacing: 4
                        Text {
                            text: "起点:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textSecondary
                        }
                        GSpinBox {
                            id: dragFromX
                            from: 0
                            to: 9999
                            value: 200
                            Layout.preferredWidth: 80
                        }
                        GSpinBox {
                            id: dragFromY
                            from: 0
                            to: 9999
                            value: 500
                            Layout.preferredWidth: 80
                        }
                        Text {
                            text: "终点:"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textSecondary
                        }
                        GSpinBox {
                            id: dragToX
                            from: 0
                            to: 9999
                            value: 200
                            Layout.preferredWidth: 80
                        }
                        GSpinBox {
                            id: dragToY
                            from: 0
                            to: 9999
                            value: 200
                            Layout.preferredWidth: 80
                        }
                    }

                    GButton {
                        text: "执行拖拽"
                        colorType: "primary"
                        implicitWidth: 100
                        onClicked: InputDebug.drag(
                                       dragFromX.value, dragFromY.value,
                                       dragToX.value, dragToY.value
                                       )
                    }
                }
            }

            // 底部留白
            Item { Layout.fillHeight: true }
        }
    }
}