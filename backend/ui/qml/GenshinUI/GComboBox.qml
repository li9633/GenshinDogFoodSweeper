import QtQuick
import QtQuick.Controls

pragma ComponentBehavior: Bound

ComboBox {
    id: control

    implicitHeight: 30
    implicitWidth: 120

    HoverHandler {
        cursorShape: Qt.PointingHandCursor
    }

    // ---- 下拉箭头 ----
    indicator: Text {
        x: control.width - width - 10
        y: (control.height - height) / 2
        text: "▼"
        font.pixelSize: 10
        color: control.hovered ? Theme.accent : Theme.textMuted
    }

    // ---- 显示文字 ----
    contentItem: Text {
        text: control.displayText
        font.family: Theme.fontFamily
        font.pixelSize: 14
        color: Theme.textPrimary
        verticalAlignment: Text.AlignVCenter
        leftPadding: 10
        rightPadding: 28
        elide: Text.ElideRight
    }

    // ---- 背景（含 hover / focus 状态） ----
    background: Rectangle {
        radius: Theme.radius
        color: Theme.bgTrack
        border.color: {
            if (control.activeFocus) return Theme.accent
            if (control.hovered) return Theme.borderHover
            return Theme.border
        }
    }

    // ---- 下拉项委托（使用 Theme 颜色，避免深色模式下黑字看不清） ----
    delegate: ItemDelegate {
        id: itemDelegate
        width: control.width - 4
        height: 30

        required property int index

        HoverHandler {
            cursorShape: Qt.PointingHandCursor
        }

        contentItem: Text {
            text: control.textAt(itemDelegate.index)
            font.family: Theme.fontFamily
            font.pixelSize: 14
            color: Theme.textPrimary
            verticalAlignment: Text.AlignVCenter
            leftPadding: 10
            elide: Text.ElideRight
        }

        background: Rectangle {
            radius: Theme.radius
            color: {
                if (itemDelegate.index === control.highlightedIndex) return Theme.accentOverlay6
                if (itemDelegate.hovered) return Theme.bgTrack
                return "transparent"
            }
        }
    }

    // ---- 下拉列表 ----
    popup: Popup {
        y: control.height + 2
        width: control.width
        implicitHeight: Math.min(popupList.contentHeight, 200) + padding * 2
        padding: 2

        contentItem: ListView {
            id: popupList
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }

        background: Rectangle {
            color: Theme.bgSecondary
            radius: Theme.radius
            border.color: Theme.border
        }
    }
}