import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// StatusBarPresenter 是 Python 通过 setContextProperty 注入的上下文属性

Rectangle {
    id: root

    // ============================================================
    // 颜色映射（QML 侧，原生 color 类型，避免 Python str→QColor 转换）
    // ============================================================
    readonly property var levelColors: ({
        "DEBUG":    { text: "#3498DB", bg: "#1B2A3A" },
        "INFO":     { text: "#B8B5C0", bg: "#1E1F2E" },
        "SUCCESS":  { text: "#27AE60", bg: "#1B2E20" },
        "WARNING":  { text: "#F39C12", bg: "#2E2A1B" },
        "ERROR":    { text: "#E74C3C", bg: "#311B1B" },
        "CRITICAL": { text: "#C0392B", bg: "#3C1A1A" }
    })

    readonly property var currentColors: {
        let c = levelColors[StatusBarPresenter.level]
        return c || levelColors["INFO"]
    }

    readonly property color barTextColor: currentColors.text
    readonly property color barBgColor: currentColors.bg

    // ============================================================
    // 布局（始终可见）
    // ============================================================
    implicitHeight: 32
    color: barBgColor
    clip: true

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 8
        spacing: 8

        // 级别标签
        Rectangle {
            Layout.preferredWidth: levelBadgeText.implicitWidth + 12
            Layout.preferredHeight: 20
            radius: 3
            color: Qt.rgba(root.barTextColor.r, root.barTextColor.g, root.barTextColor.b, 0.15)

            Text {
                id: levelBadgeText
                anchors.centerIn: parent
                text: StatusBarPresenter.level
                font.family: Theme.fontFamily
                font.pixelSize: 10
                font.bold: true
                color: root.barTextColor
            }
        }

        // 消息文本
        Text {
            Layout.fillWidth: true
            text: StatusBarPresenter.message
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: root.barTextColor
            elide: Text.ElideRight
            maximumLineCount: 1
            verticalAlignment: Text.AlignVCenter
        }

        // 关闭按钮（仅 ERROR / CRITICAL）
        Button {
            id: dismissBtn
            visible: StatusBarPresenter.dismissable
            Layout.preferredWidth: 20
            Layout.preferredHeight: 20
            flat: true

            HoverHandler {
                cursorShape: Qt.PointingHandCursor
            }

            contentItem: Text {
                text: "\u2715"
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: root.barTextColor
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                color: dismissBtn.hovered ? Qt.rgba(1, 1, 1, 0.1) : "transparent"
                radius: 3
            }

            onClicked: StatusBarPresenter.dismiss()
        }
    }
}