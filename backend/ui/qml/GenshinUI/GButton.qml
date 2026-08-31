import QtQuick
import QtQuick.Controls

Button {
    id: control

    // 预设主题：primary | success | warning | danger | info | secondary | default
    property string colorType: "default"
    // 自定义颜色（优先级高于 colorType），自动推导 hover/pressed 变体
    property string btnColor: ""
    // 自定义字体（默认使用 Theme 字体，设为 Icon.fontSolid 可显示图标）
    property string fontFamily: Theme.fontFamily

    implicitHeight: 34
    implicitWidth: Math.max(64, contentItem.implicitWidth + 24)

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    // ---- 颜色映射函数 ----
    function _baseColor() {
        if (btnColor !== "") return btnColor
        switch (colorType) {
            case "primary": return Theme.accent
            case "success": return Theme.successMedium
            case "warning": return Theme.warningMedium
            case "danger":  return Theme.dangerMedium
            case "info":    return Theme.infoMedium
            case "secondary": return Theme.bgTrack
            default:        return Theme.bgTrack
        }
    }

    function _hoverColor() {
        if (btnColor !== "") return Qt.lighter(btnColor, 1.15)
        switch (colorType) {
            case "primary": return Theme.accentHover
            case "success": return Theme.success
            case "warning": return Theme.warning
            case "danger":  return Theme.danger
            case "info":    return Theme.info
            case "secondary": return Theme.borderHover
            default:        return Theme.borderHover
        }
    }

    function _pressedColor() {
        if (btnColor !== "") return Qt.darker(btnColor, 1.15)
        switch (colorType) {
            case "primary": return Qt.darker(Theme.accent, 1.15)
            case "success": return Theme.successDeep
            case "warning": return Theme.warningDeep
            case "danger":  return Theme.dangerDeep
            case "info":    return Theme.infoDeep
            case "secondary": return Qt.darker(Theme.bgTrack, 1.1)
            default:        return Qt.darker(Theme.bgTrack, 1.1)
        }
    }

    function _isColored() {
        return btnColor !== "" || (colorType !== "default" && colorType !== "secondary")
    }

    contentItem: Text {
        text: control.text
        font.family: control.fontFamily
        font.pixelSize: 14
        color: {
            if (!control.enabled) return Theme.textMuted
            if (control._isColored()) return Theme.bgPrimary
            return Theme.textPrimary
        }
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: Theme.radius
        color: {
            if (!control.enabled) return Theme.bgTrack
            if (control.pressed) return control._pressedColor()
            if (control.hovered) return control._hoverColor()
            return control._baseColor()
        }
    }
}