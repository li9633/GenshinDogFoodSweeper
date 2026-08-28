import QtQuick
import QtQuick.Layouts
import GenshinUI

pragma ComponentBehavior: Bound

// 垂直 Tab 菜单：图标 + 文字，选中高亮，hover 效果
Rectangle {
    id: root

    // ============================================================
    // 公开属性
    // ============================================================
    property int currentIndex: 0
    property var model: []
    property int itemHeight: 36
    property int iconSize: 14

    signal tabSelected(int index)

    color: Theme.bgSidebar
    implicitWidth: 120

    // ============================================================
    // Tab 列表
    // ============================================================
    Column {
        anchors.fill: parent
        anchors.topMargin: 8
        spacing: 2

        Repeater {
            model: root.model

            delegate: Rectangle {
                id: delegateItem
                required property int index
                required property var modelData

                width: parent.width - 8
                height: root.itemHeight
                radius: 6
                anchors.horizontalCenter: parent.horizontalCenter
                color: root.currentIndex === index ? Theme.bgPrimary : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    spacing: 10

                    Text {
                        text: delegateItem.modelData.icon || ""
                        font.family: Icon.fontSolid
                        font.pixelSize: root.iconSize
                        color: root.currentIndex === delegateItem.index ? Theme.accent : Theme.textSecondary
                        Layout.preferredWidth: 18
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Text {
                        text: delegateItem.modelData.label || ""
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: root.currentIndex === delegateItem.index ? Theme.textPrimary : Theme.textSecondary
                        font.bold: root.currentIndex === delegateItem.index
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: {
                        root.currentIndex = delegateItem.index
                        root.tabSelected(delegateItem.index)
                    }

                    Rectangle {
                        anchors.fill: parent
                        color: Theme.accentOverlay6
                        radius: 6
                        visible: parent.containsMouse
                                 && root.currentIndex !== delegateItem.index
                    }
                }
            }
        }
    }
}