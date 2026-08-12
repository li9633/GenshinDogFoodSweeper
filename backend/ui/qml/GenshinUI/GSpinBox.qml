import QtQuick
import QtQuick.Controls

SpinBox {
    id: control

    implicitHeight: 30
    implicitWidth: 70

    contentItem: TextInput {
        text: control.displayText
        font.family: Theme.fontFamily
        font.pixelSize: 14
        color: Theme.textPrimary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: Qt.ImhFormattedNumbersOnly
    }

    up.indicator: Rectangle {
        x: control.width - width
        y: 0
        implicitWidth: 20
        implicitHeight: control.height / 2
        color: control.up.pressed ? Theme.border : Theme.bgTrack
        border.color: Theme.border

        Text {
            anchors.centerIn: parent
            text: "▲"
            font.pixelSize: 8
            color: Theme.textSecondary
        }
    }

    down.indicator: Rectangle {
        x: control.width - width
        y: control.height / 2
        implicitWidth: 20
        implicitHeight: control.height / 2
        color: control.down.pressed ? Theme.border : Theme.bgTrack
        border.color: Theme.border

        Text {
            anchors.centerIn: parent
            text: "▼"
            font.pixelSize: 8
            color: Theme.textSecondary
        }
    }

    background: Rectangle {
        implicitWidth: 80
        implicitHeight: 28
        radius: Theme.radius
        color: Theme.bgTrack
        border.color: control.activeFocus ? Theme.accent : Theme.border
    }
}