import QtQuick
import QtQuick.Controls
import InstallerUI

Label {
    id: control
    property string labelType: "normal" // title | heading | body | normal | small

    font.family: Theme.fontFamily
    font.pixelSize: {
        switch (labelType) {
        case "title": return Theme.fontSizeTitle
        case "heading": return Theme.fontSizeHeading
        case "body": return Theme.fontSizeBody
        case "small": return Theme.fontSizeSmall
        default: return Theme.fontSizeNormal
        }
    }
    font.bold: labelType === "title" || labelType === "heading"
    color: {
        switch (labelType) {
        case "title":
        case "heading": return Theme.primaryText
        case "body": return Theme.secondaryText
        case "small": return Theme.hintText
        default: return Theme.subtleText
        }
    }
    wrapMode: labelType === "body" ? Text.WordWrap : Text.NoWrap
    horizontalAlignment: labelType === "body" ? Text.AlignHCenter : Text.AlignLeft
}