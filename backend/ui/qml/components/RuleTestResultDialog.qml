import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI
// qmllint disable unqualified

Dialog {
    id: root
    title: "规则测试结果"
    modal: true
    width: 480
    height: 600
    anchors.centerIn: Overlay.overlay
    standardButtons: Dialog.Close
    padding: 0

    property var resultData: ({
                                  ok: false,
                                  error: "",
                                  rule_name: "",
                                  rule_action: "keep",
                                  matched: false,
                                  detail: ({}),
                                  final_action: "keep",
                                  artifact: ({
                                                 set_name: "",
                                                 piece_icon: "",
                                                 piece_type: "",
                                                 piece_name: "",
                                                 rarity: 0,
                                                 level: 0,
                                                 main_stat: "",
                                                 sub_stats: [],
                                                 is_locked: false,
                                                 is_material: false,
                                                 material_name: ""
                                             })
                              })

    function _actionLabel(a) {
        return a === "discard" ? "丢弃" : "保留"
    }
    function _actionColor(a) {
        return a === "discard" ? Theme.danger : Theme.success
    }

    background: Rectangle {
        radius: 10
        color: Theme.bgPrimary
        border.color: Theme.border
    }

    header: Rectangle {
        implicitHeight: 44
        color: "transparent"
        Text {
            anchors.centerIn: parent
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.bold: true
            color: Theme.textPrimary
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Theme.border
        }
    }

    footer: Rectangle {
        implicitHeight: 48
        color: "transparent"
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            color: Theme.border
        }
        RowLayout {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            GButton {
                text: "关闭"
                colorType: "default"
                onClicked: root.close()
            }
        }
    }

    contentItem: ScrollView {
        contentWidth: availableWidth
        clip: true
        implicitWidth: 480
        implicitHeight: Math.min(520, contentLayout.implicitHeight + 32)

        ColumnLayout {
            id: contentLayout
            width: parent.width - 40
            x: 20
            y: 16
            spacing: 14

            // ===== 错误状态 =====
            Text {
                Layout.fillWidth: true
                visible: !root.resultData.ok
                text: "测试失败: " + (root.resultData.error || "未知错误")
                font.family: Theme.fontFamily
                font.pixelSize: 14
                color: Theme.danger
                wrapMode: Text.WordWrap
            }

            // ===== 识别结果 =====
            ColumnLayout {
                visible: root.resultData.ok
                spacing: 12

                // 部位图标（顶部居中）
                Image {
                    Layout.alignment: Qt.AlignHCenter
                    source: root.resultData.artifact.piece_icon || ""
                    width: 48
                    height: 48
                    sourceSize: Qt.size(48, 48)
                    asynchronous: true
                    fillMode: Image.PreserveAspectFit
                    mipmap: true
                    visible: source !== ""
                }

                SectionLabel { text: "▎识别到的圣遗物" }

                GCard {
                    Layout.fillWidth: true
                    padding: 14
                    ColumnLayout {
                        spacing: 6
                        Layout.fillWidth: true

                        RowLayout {
                            spacing: 8
                            Text {
                                text: "⭐".repeat(root.resultData.artifact.rarity || 0)
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                color: Theme.warning
                            }
                            Text {
                                text: "+" + (root.resultData.artifact.level || 0)
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                font.bold: true
                                color: Theme.textPrimary
                            }
                            Text {
                                visible: root.resultData.artifact.piece_name !== ""
                                text: root.resultData.artifact.piece_name || ""
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                color: Theme.textSecondary
                            }
                            Item { Layout.fillWidth: true }
                            Rectangle {
                                radius: 3
                                implicitWidth: lockLabel.implicitWidth + 10
                                implicitHeight: 20
                                color: "transparent"
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 3
                                    color: root.resultData.artifact.is_locked ? Theme.accent : Theme.success
                                    opacity: 0.12
                                }
                                Text {
                                    id: lockLabel
                                    anchors.centerIn: parent
                                    text: root.resultData.artifact.is_locked ? "🔒 已锁" : "🔓 未锁"
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    color: root.resultData.artifact.is_locked ? Theme.accent : Theme.success
                                }
                            }
                            Rectangle {
                                visible: root.resultData.artifact.is_material
                                radius: 3
                                implicitWidth: matBg.implicitWidth + 10
                                implicitHeight: 20
                                color: "transparent"
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 3
                                    color: Theme.warning
                                    opacity: 0.12
                                }
                                Text {
                                    id: matBg
                                    anchors.centerIn: parent
                                    text: root.resultData.artifact.material_name || "强化材料"
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    color: Theme.warning
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16
                            Text {
                                text: "套装: " + (root.resultData.artifact.set_name || "—")
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                color: Theme.textPrimary
                            }
                            Text {
                                text: "部位: " + (root.resultData.artifact.piece_type || "—")
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                color: Theme.textPrimary
                            }
                        }

                        Text {
                            text: "主词条: " + (root.resultData.artifact.main_stat || "—")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            color: Theme.textPrimary
                        }

                        Repeater {
                            model: root.resultData.artifact.sub_stats || []
                            delegate: RowLayout {
                                spacing: 6
                                Rectangle {
                                    width: 6; height: 6; radius: 3
                                    color: modelData.activated ? Theme.success : Theme.textMuted
                                }
                                Text {
                                    text: modelData.name + " +" + modelData.value
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 12
                                    color: modelData.activated ? Theme.textPrimary : Theme.textMuted
                                }
                            }
                        }
                    }
                }

                // ===== 规则匹配结果 =====
                SectionLabel { text: "▎规则匹配结果" }

                GCard {
                    Layout.fillWidth: true
                    padding: 14
                    ColumnLayout {
                        spacing: 8
                        Layout.fillWidth: true

                        RowLayout {
                            spacing: 8
                            Text {
                                text: "规则: " + (root.resultData.rule_name || "")
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                font.bold: true
                                color: Theme.textPrimary
                            }
                            Rectangle {
                                radius: 3
                                color: _actionColor(root.resultData.rule_action)
                                implicitWidth: actLabel.implicitWidth + 12
                                implicitHeight: 20
                                Text {
                                    id: actLabel
                                    anchors.centerIn: parent
                                    text: _actionLabel(root.resultData.rule_action)
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: Theme.bgPrimary
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: Theme.border
                        }

                        RowLayout {
                            spacing: 8
                            Rectangle {
                                width: 8; height: 8; radius: 4
                                color: root.resultData.matched ? Theme.success : Theme.danger
                            }
                            Text {
                                text: root.resultData.matched ? "✓ 规则匹配成功" : "✗ 规则不匹配"
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                font.bold: true
                                color: root.resultData.matched ? Theme.success : Theme.danger
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: Theme.border
                        }

                        RowLayout {
                            spacing: 8
                            Text {
                                text: "最终判定:"
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                color: Theme.textPrimary
                            }
                            Rectangle {
                                radius: 3
                                color: _actionColor(root.resultData.final_action)
                                implicitWidth: finalLabel.implicitWidth + 12
                                implicitHeight: 22
                                Text {
                                    id: finalLabel
                                    anchors.centerIn: parent
                                    text: _actionLabel(root.resultData.final_action)
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: Theme.bgPrimary
                                }
                            }
                            Text {
                                text: root.resultData.final_action === "discard"
                                      ? "（命中规则，建议丢弃）" : "（未命中任何规则，保留）"
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: Theme.textMuted
                            }
                        }
                    }
                }
            }
        }
    }

    // ========== 内联组件 ==========
    component SectionLabel: Text {
        font.family: Theme.fontFamily
        font.pixelSize: 12
        font.bold: true
        color: Theme.accent
    }
}