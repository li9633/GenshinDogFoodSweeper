import QtQuick
import QtQuick.Controls

CheckBox {
    id: control

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
            font.pixelSize: 11
            color: Theme.bgPrimary
            visible: control.checked
        }
    }

    contentItem: Text {
        text: control.text
        font.family: Theme.fontFamily
        font.pixelSize: 13
        color: Theme.textPrimary
        verticalAlignment: Text.AlignVCenter
        leftPadding: 0
    }
}