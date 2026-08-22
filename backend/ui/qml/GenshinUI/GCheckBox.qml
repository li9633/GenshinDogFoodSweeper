import QtQuick
import QtQuick.Controls

CheckBox {
    id: control

    topPadding: 0
    bottomPadding: 0
    leftPadding: indicator.width + 6

    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        x: 0
        y: (control.availableHeight - height) / 2
        radius: 3
        color: control.checked ? Theme.accent : Theme.bgTrack
        border.color: control.checked ? Theme.accent : Theme.border

        Text {
            anchors.centerIn: parent
            text: "✓"
            font.pixelSize: 12
            color: Theme.bgPrimary
            visible: control.checked
        }
    }

    contentItem: Item {
        implicitWidth: textItem.implicitWidth
        implicitHeight: textItem.implicitHeight

        Text {
            id: textItem
            anchors.verticalCenter: parent.verticalCenter
            text: control.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            color: Theme.textPrimary
        }
    }
}