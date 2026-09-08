import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string btnType: "default" // primary | default | flat

    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontSizeNormal

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.btnType === "primary" ? Theme.bgWhite : Theme.primaryText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 4
        color: {
            if (!control.enabled) return Theme.separator
            if (control.pressed) return Qt.darker(
                                     control.btnType === "primary" ? Theme.accent : Theme.separator, 1.15)
            if (control.hovered) {
                if (control.btnType === "primary") return Theme.accentHover
                if (control.btnType === "flat") return Qt.rgba(0, 0, 0, 0.05)
                return Theme.separator
            }
            if (control.btnType === "primary") return Theme.accent
            if (control.btnType === "flat") return "transparent"
            return Theme.separator
        }
    }
}