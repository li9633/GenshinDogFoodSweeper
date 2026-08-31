import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

Popup {
    id: root

    padding: 0
    margins: 0
    modal: true
    closePolicy: Popup.CloseOnEscape
    parent: Overlay.overlay
    width: parent ? parent.width : 1920
    height: parent ? parent.height : 1080

    // -- 公开属性 --
    property url source: ""
    property real zoomFactor: 1.0
    property bool fitToView: true

    function zoomIn() {
        root.fitToView = false
        root.zoomFactor = Math.min(root.zoomFactor + 0.5, 10.0)
    }
    function zoomOut() {
        root.fitToView = false
        root.zoomFactor = Math.max(root.zoomFactor - 0.5, 0.25)
    }
    function zoomFit() {
        root.fitToView = true
        root.zoomFactor = 1.0
    }
    function zoomOne() {
        root.fitToView = false
        root.zoomFactor = 1.0
    }

    background: Rectangle {
        color: "#CC000000"
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // -- 顶部工具栏 --
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 12
            spacing: 8

            GButton {
                text: Icon.close
                fontFamily: Icon.fontSolid
                implicitWidth: 36
                implicitHeight: 36
                colorType: "danger"
                onClicked: root.close()
            }

            Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 24; color: "#44FFFFFF" }

            GButton {
                text: "适应"
                colorType: "info"
                onClicked: root.zoomFit()
            }

            GButton {
                text: "1:1"
                colorType: "default"
                onClicked: root.zoomOne()
            }

            GButton {
                text: "−"
                implicitWidth: 30
                implicitHeight: 30
                colorType: "default"
                onClicked: root.zoomOut()
            }

            Text {
                text: root.fitToView ? "适应" : Math.round(root.zoomFactor * 100) + "%"
                font.family: Theme.fontFamily
                font.pixelSize: 14
                color: "#FFFFFF"
                Layout.preferredWidth: 50
                horizontalAlignment: Text.AlignHCenter
            }

            GButton {
                text: "+"
                implicitWidth: 30
                implicitHeight: 30
                colorType: "default"
                onClicked: root.zoomIn()
            }

            Item { Layout.fillWidth: true }
        }

        // -- 图片显示区 --
        Flickable {
            id: flickable
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: imageContainer.width
            contentHeight: imageContainer.height

            // 滚轮缩放
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                onWheel: function (wheel) {
                    if (wheel.angleDelta.y > 0)
                        root.zoomIn()
                    else
                        root.zoomOut()
                }
            }

            Item {
                id: imageContainer
                width: root.fitToView ? flickable.width : Math.max(flickable.width, fullImage.width)
                height: root.fitToView ? flickable.height : Math.max(flickable.height, fullImage.height)

                Image {
                    id: fullImage
                    anchors.centerIn: parent
                    source: root.source
                    fillMode: Image.PreserveAspectFit
                    width: root.fitToView ? flickable.width : implicitWidth * root.zoomFactor
                    height: root.fitToView ? flickable.height : implicitHeight * root.zoomFactor
                }
            }
        }
    }
}