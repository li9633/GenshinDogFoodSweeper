import QtQuick
import QtQuick.Controls

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

    // ---- 下拉列表 ----
    popup: Popup {
        y: control.height + 2
        width: control.width
        implicitHeight: Math.min(contentItem.contentHeight, 200)
        padding: 2

        contentItem: ListView {
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