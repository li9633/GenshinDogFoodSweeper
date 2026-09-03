import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// StatusBarPresenter 是 Python 通过 setContextProperty 注入的上下文属性

Rectangle {
    id: root

    // ============================================================
    // 颜色映射（使用 Theme 语义颜色，跟随 isDark 自动切换）
    // ============================================================
    readonly property var levelColors: ({
        "DEBUG":    { text: Theme.info, bg: Theme.bgTrack },
        "INFO":     { text: Theme.textSecondary, bg: Theme.bgTrack },
        "SUCCESS":  { text: Theme.success, bg: Theme.bgTrack },
        "WARNING":  { text: Theme.warning, bg: Theme.bgTrack },
        "ERROR":    { text: Theme.danger, bg: Theme.bgTrack },
        "CRITICAL": { text: "#FFFFFF", bg: Theme.danger }
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
    radius: 20
    color: barBgColor
    clip: true

    // 覆盖顶部圆角，保持顶部直边与上方内容无缝衔接
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 20
        color: barBgColor
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 8
        spacing: 8

        // 级别标签（默认"就绪"状态不显示）
        Rectangle {
            visible: StatusBarPresenter.showLevel
            Layout.preferredWidth: levelBadgeText.implicitWidth + 12
            Layout.preferredHeight: 20
            radius: 3
            color: Qt.rgba(root.barTextColor.r, root.barTextColor.g, root.barTextColor.b, 0.12)

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
                color: dismissBtn.hovered ? (Theme.isDark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0, 0, 0, 0.08)) : "transparent"
                radius: 3
            }

            onClicked: StatusBarPresenter.dismiss()
        }
    }
}