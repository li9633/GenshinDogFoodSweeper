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

            // ---- GMessageBox 实例（QML 渲染用，每个类型独立避免并发冲突） ----
            GMessageBox { id: infoBox }
            GMessageBox { id: successBox }
            GMessageBox { id: warningBox }
            GMessageBox { id: errorBox }
        }
    }
}