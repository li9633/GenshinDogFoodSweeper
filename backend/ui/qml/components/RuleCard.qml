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
    color: highlighted ? Theme.accentOverlay10 : (cardMouse.containsMouse ? Theme.bgTrack : Theme.bgSecondary)
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
            text: "\u2713"
            font.family: Theme.fontFamily
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
    function _fmtPart(p) {
        return (!p || p === "*") ? "任意部位" : p
    }

    function _fmtMainStat(ms) {
        return (!ms || ms === "*") ? "任意主词条" : ms
    }

    function _fmtSetName(sn) {
        return (!sn || sn === "*") ? "" : sn
    }

    function _fmtSubStats(subs) {
        if (!subs || subs.length === 0) return ""
        const parts = subs.map(function(s) {
            if (s.op && s.value)
                return s.name + s.op + s.value + "%"
            return s.name
        })
        return parts.join(", ")
    }

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
                    text: "P" + (ruleData.priority || 0)
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.accent
                }
            }
        }

        // -- 第二行：部位 + 主词条 + 套装 --
        Text {
            Layout.fillWidth: true
            text: {
                const parts = [_fmtPart(ruleData.part)]
                const ms = _fmtMainStat(ruleData.main_stat)
                if (ms !== "任意主词条") parts.push(ms)
                const sn = _fmtSetName(ruleData.set_name)
                if (sn) parts.push(sn)
                return parts.join(" · ")
            }
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.textSecondary
            elide: Text.ElideRight
            visible: text !== ""
        }

        // -- 第三行：副词条 --
        Text {
            Layout.fillWidth: true
            text: {
                const subs = _fmtSubStats(ruleData.sub_stats)
                if (!subs) return ""
                let line = "副词条: " + subs
                if (ruleData.sub_count > 0)
                    line += "  (≥" + ruleData.sub_count + "条匹配)"
                return line
            }
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.textSecondary
            elide: Text.ElideRight
            visible: text !== ""
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