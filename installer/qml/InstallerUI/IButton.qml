import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string btnType: "default" // primary | default | flat | danger

    readonly property color dangerColor: "#D32F2F"
    readonly property color dangerHoverColor: "#E53935"

    font.family: Theme.fontFamily
    font.pixelSize: Theme.fontSizeNormal

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    contentItem: Text {
        text: control.text
        font: control.font
        color: {
            if (control.btnType === "primary" || control.btnType === "danger")
                return Theme.bgWhite
            return Theme.primaryText
        }
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 4
        color: {
            if (!control.enabled) return Theme.separator
            if (control.pressed) {
                if (control.btnType === "danger") return Qt.darker(control.dangerColor, 1.2)
                if (control.btnType === "primary") return Qt.darker(Theme.accent, 1.15)
                return Qt.darker(Theme.separator, 1.15)
            }
            if (control.hovered) {
                if (control.btnType === "danger") return control.dangerHoverColor
                if (control.btnType === "primary") return Theme.accentHover
                if (control.btnType === "flat") return Qt.rgba(0, 0, 0, 0.05)
                return Theme.separator
            }
            if (control.btnType === "danger") return control.dangerColor
            if (control.btnType === "primary") return Theme.accent
            if (control.btnType === "flat") return "transparent"
            return Theme.separator
        }
    }
}