import QtQuick
import QtQuick.Controls

ProgressBar {
    id: control
    implicitWidth: Theme.contentWidth
    implicitHeight: 8
    property color accentColor: Theme.accent

    background: Rectangle {
        implicitWidth: control.implicitWidth
        implicitHeight: control.implicitHeight
        color: Theme.separator
        radius: 4
    }

    contentItem: Item {
        implicitWidth: control.implicitWidth
        implicitHeight: control.implicitHeight

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: 4
            color: control.accentColor
        }
    }
}