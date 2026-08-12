import QtQuick
import QtQuick.Controls

Button {
    id: control

    // "primary" | "danger" | "default"
    property string colorType: "default"
    // 自定义颜色（优先级高于 colorType），自动推导 hover/pressed 变体
    property string btnColor: ""

    implicitHeight: 28
    implicitWidth: Math.max(56, contentItem.implicitWidth + 20)

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    contentItem: Text {
        text: control.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        color: {
            if (!control.enabled) return Theme.textMuted
            if (control.btnColor !== "") return Theme.bgPrimary
            if (control.colorType === "primary" || control.colorType === "danger") return Theme.bgPrimary
            return Theme.textPrimary
        }
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: Theme.radius
        color: {
            if (!control.enabled) return Theme.bgTrack
            // 自定义颜色模式：自动推导 hover/pressed
            if (control.btnColor !== "") {
                if (control.pressed) return Qt.darker(control.btnColor, 1.15)
                if (control.hovered) return Qt.lighter(control.btnColor, 1.15)
                return control.btnColor
            }
            if (control.pressed) {
                if (control.colorType === "danger") return Theme.dangerPressed
                if (control.colorType === "primary") return Qt.darker(Theme.accent, 1.15)
                return Qt.darker(Theme.bgTrack, 1.1)
            }
            if (control.hovered) {
                if (control.colorType === "danger") return Theme.dangerHover
                if (control.colorType === "primary") return Theme.accentHover
                return Theme.borderHover
            }
            if (control.colorType === "danger") return Theme.danger
            if (control.colorType === "primary") return Theme.accent
            return Theme.bgTrack
        }
    }
}