import QtQuick

Text {
    id: control

    property string url: ""
    property string colorType: "primary"

    font.family: Theme.fontFamily
    font.pixelSize: 13
    color: {
        if (control.colorType === "primary") return Theme.accent
        return Theme.textSecondary
    }

    HoverHandler {
        cursorShape: control.url !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
        onHoveredChanged: control.font.underline = hovered
    }

    TapHandler {
        onTapped: {
            if (control.url !== "") {
                Qt.openUrlExternally(control.url)
            }
        }
    }
}