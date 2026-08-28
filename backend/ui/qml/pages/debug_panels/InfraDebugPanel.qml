import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// InfraDebug / StatusBarPresenter 是 Python 通过 setContextProperty 注入的上下文属性

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

            // ---- 状态栏 ----
            GCard {
                title: "状态栏"
                Layout.fillWidth: true

                Flow {
                    Layout.fillWidth: true
                    spacing: 10

                    Repeater {
                        model: [
                            { level: "INFO", label: "信息 (灰)", btnColor: "#6B6E8A" },
                            { level: "SUCCESS", label: "成功 (绿)", btnColor: "#4CAF50" },
                            { level: "WARNING", label: "警告 (橙)", btnColor: "#FF9800" },
                            { level: "ERROR", label: "错误 (红)", btnColor: "#EF5350" },
                            { level: "CRITICAL", label: "严重", btnColor: "#C62828" }
                        ]

                        GButton {
                            text: modelData.label
                            btnColor: modelData.btnColor
                            implicitWidth: 100
                            implicitHeight: 32
                            onClicked: InfraDebug.testStatusBar(modelData.level)
                        }
                    }
                }
            }

            // ---- GMessageBox（QML 直接渲染） ----
            GCard {
                title: "GMessageBox（QML 渲染）"
                Layout.fillWidth: true

                Flow {
                    Layout.fillWidth: true
                    spacing: 10

                    GButton {
                        text: "信息 (蓝)"
                        colorType: "info"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: {
                            infoBox.msgType = "info"
                            infoBox.msgText = "[基础设施调试] QML渲染 — 信息消息"
                            infoBox.open()
                        }
                    }

                    GButton {
                        text: "成功 (绿)"
                        colorType: "success"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: {
                            successBox.msgType = "success"
                            successBox.msgText = "[基础设施调试] QML渲染 — 成功消息"
                            successBox.open()
                        }
                    }

                    GButton {
                        text: "警告 (橙)"
                        colorType: "warning"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: {
                            warningBox.msgType = "warning"
                            warningBox.msgText = "[基础设施调试] QML渲染 — 警告消息"
                            warningBox.open()
                        }
                    }

                    GButton {
                        text: "错误 (红)"
                        colorType: "danger"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: {
                            errorBox.msgType = "error"
                            errorBox.msgText = "[基础设施调试] QML渲染 — 错误消息"
                            errorBox.open()
                        }
                    }
                }
            }

            // ---- GMessageBox（Python 桥接） ----
            GCard {
                title: "GMessageBox（Python 桥接）"
                Layout.fillWidth: true

                Flow {
                    Layout.fillWidth: true
                    spacing: 10

                    GButton {
                        text: "信息 (蓝)"
                        colorType: "info"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBox("info")
                    }

                    GButton {
                        text: "成功 (绿)"
                        colorType: "success"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBox("success")
                    }

                    GButton {
                        text: "警告 (橙)"
                        colorType: "warning"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBox("warning")
                    }

                    GButton {
                        text: "错误 (红)"
                        colorType: "danger"
                        implicitWidth: 100
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBox("error")
                    }
                }
            }

            // ---- GMessageBox 聚焦测试（延迟触发，可切到其他窗口测试） ----
            GCard {
                title: "GMessageBox 聚焦测试（延迟触发）"
                subtitle: "点击后延迟3秒弹窗，可切换到其他窗口测试是否拉到前台"
                Layout.fillWidth: true

                Flow {
                    Layout.fillWidth: true
                    spacing: 10

                    GButton {
                        text: "错误 (3s后)"
                        colorType: "danger"
                        implicitWidth: 110
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBoxDelayed("error", 3)
                    }

                    GButton {
                        text: "警告 (3s后)"
                        colorType: "warning"
                        implicitWidth: 110
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBoxDelayed("warning", 3)
                    }

                    GButton {
                        text: "信息 (3s后)"
                        colorType: "info"
                        implicitWidth: 110
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBoxDelayed("info", 3)
                    }

                    GButton {
                        text: "成功 (3s后)"
                        colorType: "success"
                        implicitWidth: 110
                        implicitHeight: 32
                        onClicked: InfraDebug.testGMessageBoxDelayed("success", 3)
                    }
                }
            }

            // ---- GProgressBar（进度条调试） ----
            GCard {
                title: "GProgressBar（进度条调试）"
                subtitle: "状态由 InfraDebug Presenter 管理"
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 12

                    GProgressBar {
                        id: debugProgress
                        Layout.fillWidth: true
                        indeterminate: InfraDebug.debugIndeterminate
                        value: InfraDebug.debugProgressValue
                        progressText: InfraDebug.debugProgressText
                    }

                    RowLayout {
                        spacing: 10
                        GButton {
                            text: "模拟不确定"
                            colorType: "info"
                            implicitHeight: 30
                            onClicked: InfraDebug.simulateIndeterminateProgress()
                        }
                        GButton {
                            text: "模拟确定进度"
                            colorType: "primary"
                            implicitHeight: 30
                            onClicked: InfraDebug.simulateDeterminateProgress()
                        }
                        GButton {
                            text: "模拟完成"
                            colorType: "success"
                            implicitHeight: 30
                            onClicked: InfraDebug.simulateCompletedProgress()
                        }
                    }
                }
            }

            // ---- 数据库 & 模型清理 ----
            GCard {
                title: "数据库 & 模型清理"
                subtitle: "⚠ 危险操作，清空数据不可恢复"
                Layout.fillWidth: true

                Flow {
                    Layout.fillWidth: true
                    spacing: 10

                    GButton {
                        text: "清空套装表"
                        colorType: "danger"
                        implicitWidth: 110
                        implicitHeight: 32
                        onClicked: InfraDebug.clearArtifactSets()
                    }

                    GButton {
                        text: "清空单件表"
                        colorType: "danger"
                        implicitWidth: 110
                        implicitHeight: 32
                        onClicked: InfraDebug.clearArtifactPieces()
                    }

                    GButton {
                        text: "删除 OCR 模型"
                        colorType: "warning"
                        implicitWidth: 120
                        implicitHeight: 32
                        onClicked: InfraDebug.deleteOcrModel()
                    }
                }
            }

            // ---- GMessageBox 实例（QML 渲染用，每个类型独立避免并发冲突） ----
            GMessageBox { id: infoBox }
            GMessageBox { id: successBox }
            GMessageBox { id: warningBox }
            GMessageBox { id: errorBox }
        }
    }
}