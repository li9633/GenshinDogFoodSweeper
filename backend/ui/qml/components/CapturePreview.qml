import QtQuick
import QtQuick.Layouts
import GenshinUI

Rectangle {
    id: root

    color: Theme.bgTrack
    border.color: Theme.border
    radius: Theme.radius
    implicitHeight: 150
    implicitWidth: 200

    // ---- 公开属性 ----
    property url source: ""          // 图片源
    property string infoText: "等待截图…" // 底部信息
    property bool selectionMode: false   // 选区模式
    property real zoomFactor: 1.0
    property bool fitToView: true

    // ---- 信号 ----
    signal regionSelected(int x, int y, int w, int h)
    signal clearRequested()

    // ---- 缩放函数 ----
    function zoomIn() {
        root.fitToView = false;
        root.zoomFactor = Math.min(root.zoomFactor + 0.25, 5.0);
    }
    function zoomOut() {
        root.fitToView = false;
        root.zoomFactor = Math.max(root.zoomFactor - 0.25, 0.25);
    }
    function zoomFit() {
        root.fitToView = true;
        root.zoomFactor = 1.0;
    }
    function clear() {
        root.source = "";
        root.infoText = "等待截图…";
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- 工具栏 ----
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 6
            spacing: 4

            Item {
                Layout.fillWidth: true
            }

            GButton {
                text: "-"
                implicitWidth: 28
                implicitHeight: 24
                onClicked: root.zoomOut()
            }

            Text {
                text: root.fitToView ? "适应" : Math.round(root.zoomFactor * 100) + "%"
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
                Layout.preferredWidth: 40
                horizontalAlignment: Text.AlignHCenter
            }

            GButton {
                text: "+"
                implicitWidth: 28
                implicitHeight: 24
                onClicked: root.zoomIn()
            }

            GButton {
                text: "适应"
                implicitWidth: 44
                implicitHeight: 24
                onClicked: root.zoomFit()
            }

            GButton {
                text: "清除"
                visible: root.source !== null && root.source.toString() !== ""
                implicitWidth: 44
                implicitHeight: 24
                colorType: "default"
                onClicked: {
                    root.clear()
                    root.clearRequested()
                }
            }

            Text {
                text: root.infoText
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textMuted
                elide: Text.ElideRight
                Layout.maximumWidth: 200
            }
        }

        // ---- 图片预览区 ----
        Flickable {
            id: flickable
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: imageContainer.width
            contentHeight: imageContainer.height

            Rectangle {
                anchors.fill: parent
                color: Theme.bgPrimary
            }

            // Ctrl+滚轮缩放
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                onWheel: function (wheel) {
                    if (wheel.modifiers & Qt.ControlModifier) {
                        if (wheel.angleDelta.y > 0)
                            root.zoomIn();
                        else
                            root.zoomOut();
                    }
                }
            }

            Item {
                id: imageContainer
                width: root.fitToView ? flickable.width : Math.max(flickable.width, imageItem.width)
                height: root.fitToView ? flickable.height : Math.max(flickable.height, imageItem.height)

                Image {
                    id: imageItem
                    anchors.centerIn: parent
                    source: root.source
                    visible: root.source !== null && root.source.toString() !== ""
                    fillMode: root.fitToView ? Image.PreserveAspectFit : Image.Pad
                    width: root.fitToView ? flickable.width : implicitWidth * root.zoomFactor
                    height: root.fitToView ? flickable.height : implicitHeight * root.zoomFactor

                    // 选区拖拽
                    MouseArea {
                        anchors.fill: parent
                        enabled: root.selectionMode
                        cursorShape: enabled ? Qt.CrossCursor : Qt.ArrowCursor
                        preventStealing: true

                        property point startPoint
                        property bool dragging: false

                        onPressed: function (mouse) {
                            startPoint = Qt.point(mouse.x, mouse.y);
                            dragging = true;
                            rubberBand.x = mouse.x;
                            rubberBand.y = mouse.y;
                            rubberBand.width = 0;
                            rubberBand.height = 0;
                            rubberBand.visible = true;
                        }
                        onPositionChanged: function (mouse) {
                            if (!dragging)
                                return;
                            let x = Math.min(startPoint.x, mouse.x);
                            let y = Math.min(startPoint.y, mouse.y);
                            let w = Math.abs(mouse.x - startPoint.x);
                            let h = Math.abs(mouse.y - startPoint.y);
                            rubberBand.x = x;
                            rubberBand.y = y;
                            rubberBand.width = w;
                            rubberBand.height = h;
                        }
                        onReleased: function (mouse) {
                            dragging = false;
                            rubberBand.visible = false;
                            let x = Math.min(startPoint.x, mouse.x);
                            let y = Math.min(startPoint.y, mouse.y);
                            let w = Math.abs(mouse.x - startPoint.x);
                            let h = Math.abs(mouse.y - startPoint.y);
                            if (w > 5 && h > 5) {
                                // 映射回原始图像坐标
                                let scaleX = imageItem.implicitWidth / imageItem.width;
                                let scaleY = imageItem.implicitHeight / imageItem.height;
                                root.regionSelected(Math.round(x * scaleX), Math.round(y * scaleY), Math.round(w * scaleX), Math.round(h * scaleY));
                            }
                        }
                    }

                    // 选区框
                    Rectangle {
                        id: rubberBand
                        visible: false
                        color: "#0F00FF00"
                        border.color: "#00FF00"
                        border.width: 2
                    }
                }

                // 无图片时的占位文字
                Text {
                    anchors.centerIn: parent
                    visible: !imageItem.visible
                    text: "未开始预览\n点击「开始预览」查看游戏画面"
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    color: Theme.textMuted
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}