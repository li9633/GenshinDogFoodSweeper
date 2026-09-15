import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// qmllint disable unqualified
// DebugPanelPresenter 是 Python 通过 setContextProperty 注入的上下文属性

Window {
    id: panel
    width: 340
    height: 480
    minimumWidth: 300
    minimumHeight: 360
    title: "调试面板 — GDFS_INSTALLER_DEBUG"
    flags: Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowTitleHint

    // ── 颜色常量 ──
    readonly property color bgColor: "#2b2b2b"
    readonly property color sectionColor: "#e0e0e0"
    readonly property color labelColor: "#b0b0b0"
    readonly property color valueColor: "#ffffff"
    readonly property color activeColor: "#81c784"
    readonly property color disabledColor: "#555555"

    color: bgColor

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // ── 页面切换 ──
        Text {
            Layout.fillWidth: true
            text: "页面切换"
            color: sectionColor
            font.bold: true
            font.pixelSize: 13
        }

        RowLayout {
            spacing: 4

            Repeater {
                model: DebugPanelPresenter.pages

                Button {
                    id: pageBtn
                    text: modelData.label
                    flat: true
                    font.pixelSize: 11
                    font.bold: DebugPanelPresenter.currentPage === modelData.key
                    implicitWidth: 36
                    implicitHeight: 28
                    enabled: modelData.enabled

                    contentItem: Text {
                        text: pageBtn.text
                        color: {
                            if (!pageBtn.enabled) return disabledColor;
                            return DebugPanelPresenter.currentPage === modelData.key
                                   ? activeColor : labelColor;
                        }
                        font: pageBtn.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        color: pageBtn.hovered && pageBtn.enabled ? "#3a3a3a" : "transparent"
                        radius: 4
                        border.color: {
                            if (!pageBtn.enabled) return "#3a3a3a";
                            return DebugPanelPresenter.currentPage === modelData.key
                                   ? activeColor : "#555555";
                        }
                        border.width: 1
                    }

                    onClicked: DebugPanelPresenter.navigateTo(modelData.key)
                }
            }
        }

        // ── 模式切换 ──
        Text {
            Layout.fillWidth: true
            text: "模式切换"
            color: sectionColor
            font.bold: true
            font.pixelSize: 13
        }

        RowLayout {
            spacing: 4

            Repeater {
                model: DebugPanelPresenter.modes

                Button {
                    id: modeBtn
                    text: modelData.label
                    flat: true
                    font.pixelSize: 11
                    font.bold: DebugPanelPresenter.currentMode === modelData.key
                    implicitWidth: 56
                    implicitHeight: 28

                    contentItem: Text {
                        text: modeBtn.text
                        color: DebugPanelPresenter.currentMode === modelData.key
                               ? activeColor
                               : labelColor
                        font: modeBtn.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        color: modeBtn.hovered ? "#3a3a3a" : "transparent"
                        radius: 4
                        border.color: DebugPanelPresenter.currentMode === modelData.key
                                      ? modelData.color
                                      : "#555555"
                        border.width: 1
                    }

                    onClicked: DebugPanelPresenter.setMode(modelData.key)
                }
            }
        }

        // ── 快速更新 ──
        RowLayout {
            CheckBox {
                id: quickUpdateCheck
                checked: DebugPanelPresenter.quickUpdate
                onToggled: DebugPanelPresenter.setQuickUpdate(checked)
            }
            Text {
                text: "快速更新模式"
                color: labelColor
                font.pixelSize: 12
            }
        }

        // ── 分隔线 ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: "#444444"
        }

        // ── 状态信息 ──
        Text {
            Layout.fillWidth: true
            text: "运行状态（可选中复制）"
            color: sectionColor
            font.bold: true
            font.pixelSize: 13
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true

            TextArea {
                id: infoArea
                readOnly: true
                text: DebugPanelPresenter.debugInfo
                selectByMouse: true
                color: valueColor
                font.family: "Consolas"
                font.pixelSize: 12
                wrapMode: TextEdit.NoWrap

                background: Rectangle {
                    color: "#1e1e1e"
                    radius: 4
                    border.color: "#444444"
                    border.width: 1
                }
            }
        }
    }
}