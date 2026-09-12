import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import GenshinUI

// qmllint disable unqualified
// UpdatePresenter 是 Python 通过 setContextProperty 注入的上下文属性

Window {
    id: root

    // ============================================================
    // 窗口基础设置
    // ============================================================
    width: 480
    height: 520
    minimumWidth: 400
    minimumHeight: 420
    color: "transparent"
    flags: Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowTitleHint
    title: "发现新版本"

    // ============================================================
    // 信号：纯渲染层，仅向上抛出用户意图
    // ============================================================
    signal updateNow()
    signal remindLater()

    // ============================================================
    // 阴影容器 — 与 MainWindow 一致的 MultiEffect 阴影方案
    // ============================================================
    readonly property int shadowMargin: 4

    Rectangle {
        id: shadowLayer
        anchors.fill: parent
        anchors.margins: root.shadowMargin
        radius: Theme.windowRadius
        color: Theme.bgPrimary

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowBlur: 0.5
            shadowColor: "#40000000"
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 2
        }
    }

    // ============================================================
    // 内容容器
    // ============================================================
    Rectangle {
        id: windowContent
        anchors.fill: parent
        anchors.margins: root.shadowMargin
        radius: Theme.windowRadius
        color: Theme.bgPrimary
        clip: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── 顶部标题区 ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: Theme.accentOverlay6
                radius: Theme.windowRadius

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: parent.radius
                    color: parent.color
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    Rectangle {
                        implicitWidth: 40; implicitHeight: 40; radius: 20
                        color: Theme.accentSoft

                        Text {
                            anchors.centerIn: parent
                            text: Icon.arrowsRotate
                            font.family: Icon.fontSolid
                            font.pixelSize: 20
                            color: Theme.accent
                        }
                    }

                    ColumnLayout {
                        spacing: 2
                        Text {
                            text: "发现新版本"
                            font.family: Theme.fontFamily
                            font.pixelSize: 16
                            font.bold: true
                            color: Theme.textPrimary
                        }
                        Text {
                            text: "版本 " + UpdatePresenter.version + " 可用"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textSecondary
                        }
                    }

                    Item { Layout.fillWidth: true }

                    GButton {
                        implicitWidth: 28; implicitHeight: 28
                        colorType: "default"
                        text: Icon.close
                        fontFamily: Icon.fontSolid
                        onClicked: root.remindLater()
                    }
                }
            }

            // ── 版本号对比区 ──
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 20
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                spacing: 20

                ColumnLayout {
                    spacing: 4
                    Text {
                        text: "当前版本"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textMuted
                    }
                    Rectangle {
                        Layout.preferredWidth: currentVerText.implicitWidth + 16
                        Layout.preferredHeight: 26
                        radius: 13
                        color: Theme.bgTrack
                        Text {
                            id: currentVerText
                            anchors.centerIn: parent
                            text: UpdatePresenter.currentVersion
                            font.family: "Consolas"
                            font.pixelSize: 12
                            color: Theme.textSecondary
                        }
                    }
                }

                Text {
                    text: "\u2192"
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    color: Theme.accent
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    spacing: 4
                    Text {
                        text: "最新版本"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textMuted
                    }
                    Rectangle {
                        implicitWidth: newVerText.implicitWidth + 16
                        Layout.preferredHeight: 26
                        Layout.minimumWidth: 40
                        radius: 13
                        color: Theme.bgTrack
                        Text {
                            id: newVerText
                            anchors.centerIn: parent
                            text: UpdatePresenter.version
                            font.family: "Consolas"
                            font.pixelSize: 12
                            font.bold: true
                            color: Theme.textPrimary
                        }
                    }
                }
            }

            // ── 更新日志 ──
            Item { Layout.preferredHeight: 16 }

            Text {
                Layout.leftMargin: 24
                text: "更新日志"
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.bold: true
                color: Theme.textSecondary
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 24
                Layout.topMargin: 8
                Layout.bottomMargin: 8
                Layout.preferredHeight: 180
                color: Theme.bgTrack
                radius: Theme.radius
                clip: true

                Flickable {
                    id: changelogFlick
                    anchors.fill: parent
                    anchors.margins: 12
                    contentWidth: changelogText.implicitWidth
                    contentHeight: changelogText.implicitHeight
                    flickableDirection: Flickable.VerticalFlick
                    boundsBehavior: Flickable.StopAtBounds

                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                    }

                    Text {
                        id: changelogText
                        width: changelogFlick.width
                        text: UpdatePresenter.changelog || "暂无更新日志"
                        textFormat: Text.MarkdownText
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textPrimary
                        wrapMode: Text.WordWrap
                        lineHeight: 1.6
                    }
                }
            }

            // ── 下载进度条 ──
            Item {
                visible: UpdatePresenter.downloading
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                Layout.preferredHeight: 24

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4

                    Text {
                        text: UpdatePresenter.downloadTotal > 0
                            ? "正在下载 " + (UpdatePresenter.downloadProgress / 1048576).toFixed(1)
                              + " / " + (UpdatePresenter.downloadTotal / 1048576).toFixed(1) + " MB"
                            : "正在下载…"
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textSecondary
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 6
                        radius: 3
                        color: Theme.bgTrack

                        Rectangle {
                            width: UpdatePresenter.downloadTotal > 0
                                ? parent.width * UpdatePresenter.downloadProgress / UpdatePresenter.downloadTotal
                                : 0
                            height: parent.height
                            radius: 3
                            color: Theme.accent
                            Behavior on width { NumberAnimation { duration: 200 } }
                        }
                    }
                }
            }

            // ── 底部分隔线 ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Theme.border
            }

            // ── 操作按钮 ──
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 16
                spacing: 12

                GButton {
                    text: "稍后再说"
                    colorType: "default"
                    enabled: !UpdatePresenter.downloading
                    onClicked: root.remindLater()
                }

                Item { Layout.fillWidth: true }

                GButton {
                    text: UpdatePresenter.downloading ? "下载中…" : "立即更新"
                    colorType: "primary"
                    enabled: !UpdatePresenter.downloading
                    onClicked: root.updateNow()
                }
            }
        }
    }
}