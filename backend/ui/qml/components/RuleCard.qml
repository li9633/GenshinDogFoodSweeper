import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

Rectangle {
    id: card

    // ============================================================
    // 公开属性
    // ============================================================
    property var ruleData: ({
        name: "",
        part: "*",
        part_exclude: "",
        main_stat: "*",
        set_name: "*",
        sub_stats: [],
        sub_count: 0,
        action: "keep",
        priority: 0,
        enabled: true
    })

    signal editRequested(var rule)
    signal deleteRequested(var rule)
    signal duplicateRequested(var rule)
    signal clicked(var rule)

    property bool highlighted: false
    property bool rightClickEnabled: true

    implicitHeight: contentLayout.implicitHeight + 24
    color: highlighted ? Theme.accentOverlay10 : (cardMouse.containsMouse ? Theme.bgTrack : Theme.bgCard)
    radius: Theme.radius
    border.color: highlighted ? Theme.accent : (cardMouse.containsMouse ? Theme.borderHover : Theme.border)
    opacity: (ruleData.enabled !== false) ? 1.0 : 0.55

    // 左侧强调色条
    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: 4
        anchors.bottomMargin: 4
        width: 4
        radius: 2
        color: ruleData.action === "discard" ? Theme.danger : Theme.success
    }

    // 选中标记（✓ 圆形图标）
    Rectangle {
        visible: card.highlighted
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        width: 24
        height: 24
        radius: 12
        color: Theme.accent

        Behavior on opacity { NumberAnimation { duration: 150 } }

        Text {
            anchors.centerIn: parent
            text: Icon.check
            font.family: Icon.fontSolid
            font.pixelSize: 14
            font.bold: true
            color: Theme.bgPrimary
        }
    }

    // ============================================================
    // 鼠标交互
    MouseArea {
        id: cardMouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor

        onClicked: function(mouse) {
            if (mouse.button === Qt.RightButton) {
                if (card.rightClickEnabled) {
                    ctxMenu.x = mouse.x
                    ctxMenu.y = mouse.y
                    ctxMenu.open()
                }
            } else if (mouse.button === Qt.LeftButton) {
                card.clicked(card.ruleData)
            }
        }
    }

    // ============================================================
    // 辅助格式化函数
    // ============================================================
    // 内容区
    // ============================================================
    ColumnLayout {
        id: contentLayout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 20
        anchors.rightMargin: card.highlighted ? 42 : 12
        spacing: 4

        // -- 第一行：名称 + 操作标签 + 优先级 --
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: ruleData.name || "(未命名)"
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.bold: true
                color: Theme.textPrimary
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            // 操作标签
            Rectangle {
                radius: 3
                color: Theme[RulePresenter.actionColor(ruleData.action)]
                implicitWidth: actionLabel.implicitWidth + 12
                implicitHeight: 20
                Text {
                    id: actionLabel
                    anchors.centerIn: parent
                    text: RulePresenter.actionLabel(ruleData.action)
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.bold: true
                    color: Theme.bgPrimary
                }
            }

            // 优先级
            Rectangle {
                radius: 3
                color: Theme.accentOverlay6
                implicitWidth: priorityLabel.implicitWidth + 10
                implicitHeight: 20
                Text {
                    id: priorityLabel
                    anchors.centerIn: parent
                    text: ruleData.display.priority
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.accent
                }
            }
        }

        // -- 第二行：部位 + 排除 + 主词条 + 套装 --
        Text {
            Layout.fillWidth: true
            text: ruleData.display.meta
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.textSecondary
            elide: Text.ElideRight
            visible: text !== ""
        }

        // -- 第三行：副词条 + 配置标签 --
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: ruleData.display.sub_stats !== ""

            Text {
                Layout.fillWidth: true
                text: ruleData.display.sub_stats
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
                elide: Text.ElideRight
            }

            // 包含待激活
            Rectangle {
                radius: 3
                color: Theme.accentOverlay6
                implicitWidth: tagUnactivated.implicitWidth + 8
                implicitHeight: 18
                visible: ruleData.include_unactivated !== false
                Text {
                    id: tagUnactivated
                    anchors.centerIn: parent
                    text: "含待激活"
                    font.family: Theme.fontFamily
                    font.pixelSize: 10
                    color: Theme.accent
                }
            }

            // 主词条计入
            Rectangle {
                radius: 3
                color: Theme.accentOverlay6
                implicitWidth: tagMainStat.implicitWidth + 8
                implicitHeight: 18
                visible: ruleData.include_main_stat === true
                Text {
                    id: tagMainStat
                    anchors.centerIn: parent
                    text: "主词条计入"
                    font.family: Theme.fontFamily
                    font.pixelSize: 10
                    color: Theme.accent
                }
            }
        }
    }

    // ============================================================
    // ============================================================
    // 主题化右键菜单
    // ============================================================
    Popup {
        id: ctxMenu
        padding: 4
        implicitWidth: 120
        closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape

        background: Rectangle {
            color: Theme.bgSecondary
            radius: Theme.radius
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 2

            // 编辑
            Rectangle {
                Layout.fillWidth: true
                Layout.minimumWidth: 100
                implicitHeight: 32
                radius: 4
                color: editHover.containsMouse ? Theme.accentOverlay6 : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "编辑"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textPrimary
                }

                MouseArea {
                    id: editHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        ctxMenu.close()
                        card.editRequested(ruleData)
                    }
                }
            }

            // 复制
            Rectangle {
                Layout.fillWidth: true
                Layout.minimumWidth: 100
                implicitHeight: 32
                radius: 4
                color: dupHover.containsMouse ? Theme.accentOverlay6 : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "复制"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textPrimary
                }

                MouseArea {
                    id: dupHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        ctxMenu.close()
                        card.duplicateRequested(ruleData)
                    }
                }
            }

            // 分隔线
            Rectangle {
                Layout.fillWidth: true
                Layout.leftMargin: 6
                Layout.rightMargin: 6
                implicitHeight: 1
                color: Theme.border
            }

            // 删除
            Rectangle {
                Layout.fillWidth: true
                Layout.minimumWidth: 100
                implicitHeight: 32
                radius: 4
                color: delHover.containsMouse ? Theme.accentOverlay6 : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "删除"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.danger
                }

                MouseArea {
                    id: delHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        ctxMenu.close()
                        card.deleteRequested(ruleData)
                    }
                }
            }
        }
    }
}